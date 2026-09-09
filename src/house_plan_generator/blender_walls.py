"""Architectural shell: walls with real thickness, boolean openings, floors,
cutaway strategy, and the exterior site.

Wall construction uses the union approach: every room contributes four wall
segments centered on its edges; overlapping segments merge visually because
they share materials and exact alignment. Openings (doors/windows) are cut
with boolean modifiers so jambs and recesses are real geometry.

Cutaway strategy: exterior walls on camera-facing plot sides are lowered to
CUT_H with a flat cap; all other walls stay full height and OPAQUE.
"""

import math

import bpy

from .blender_geom import box, cyl, sph, absorb

WALL_H = 9.0        # full exterior wall height (ft)
PART_H = 8.0        # interior partition height (ft)
CUT_H = 3.4         # camera-facing exterior wall cut height (ft)
DOOR_H = 6.8        # door opening height (ft)
SILL_H = 3.0        # window sill (ft)
HEAD_H = 6.6        # window head (ft)
WALL_T = 0.5        # exterior wall thickness (ft)
PART_T = 0.35       # interior wall thickness (ft)
SLAB_T = 0.30       # floor slab thickness (ft)

# camera-facing plot sides, set by the renderer before wall building
CUT_SIDES = {"west": False, "east": False, "north": False, "south": False}


def _bool_cut(obj, cutter):
    """Subtract cutter mesh from obj (destructive, removes cutter)."""
    mod = obj.modifiers.new("cut", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.object = cutter
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def _neighbors(plan):
    """Map room id -> set of sides shared with another room (interior edges)."""
    nbr = {r["id"]: set() for r in plan["rooms"]}
    rooms = plan["rooms"]
    for r in rooms:
        x, y, w, d = r["x_ft"], r["y_ft"], r["width_ft"], r["depth_ft"]
        for o in rooms:
            if o["id"] == r["id"]:
                continue
            ox, oy, ow, od = o["x_ft"], o["y_ft"], o["width_ft"], o["depth_ft"]
            # shared vertical edge (r west vs o east etc.)
            if abs(x - (ox + ow)) < 0.02 and not (y + d <= oy + 0.02 or oy + od <= y + 0.02):
                nbr[r["id"]].add("west")
            if abs((x + w) - ox) < 0.02 and not (y + d <= oy + 0.02 or oy + od <= y + 0.02):
                nbr[r["id"]].add("east")
            if abs(y - (oy + od)) < 0.02 and not (x + w <= ox + 0.02 or ox + ow <= x + 0.02):
                nbr[r["id"]].add("north")
            if abs((y + d) - oy) < 0.02 and not (x + w <= ox + 0.02 or ox + ow <= x + 0.02):
                nbr[r["id"]].add("south")
    return nbr


def _openings_for(plan, r, side):
    """Door/window openings along room edge `side`, as (t0, t1, kind, rec)."""
    span = r["width_ft"] if side in ("north", "south") else r["depth_ft"]
    out = []
    for dr in plan.get("doors", []):
        if dr.get("room_id") != r["id"] or dr.get("side") != side:
            continue
        off = float(dr.get("offset_ft", 0))
        leaf = min(2.8, max(1.6, span - off))
        out.append((off, off + leaf, "door", dr))
    for wn in plan.get("windows", []):
        if wn.get("room_id") != r["id"] or wn.get("side") != side:
            continue
        off = float(wn.get("offset_ft", 0))
        leaf = max(1.6, min(float(wn.get("width_ft", 4.0)), span - off - 0.3))
        out.append((off, off + leaf, "window", wn))
    return out


def _side_edge(r, side):
    x, y, w, d = r["x_ft"], r["y_ft"], r["width_ft"], r["depth_ft"]
    if side == "north":
        return (x, y, x + w, y)
    if side == "south":
        return (x, y + d, x + w, y + d)
    if side == "west":
        return (x, y, x, y + d)
    return (x + w, y, x + w, y + d)


def _on_plot_boundary(plan, r, side):
    w, d = plan["plot"]["width_ft"], plan["plot"]["depth_ft"]
    x, y, rw, rd = r["x_ft"], r["y_ft"], r["width_ft"], r["depth_ft"]
    if side == "west":
        return abs(x) < 0.02
    if side == "east":
        return abs(x + rw - w) < 0.02
    if side == "north":
        return abs(y) < 0.02
    return abs(y + rd - d) < 0.02


def build_floors(plan, M):
    """Per-room floor slabs + house base slab."""
    made = []
    base_w = plan["plot"]["width_ft"] + 1.0
    base_d = plan["plot"]["depth_ft"] + 1.0
    box("BaseSlab", base_w / 2 - 0.5, base_d / 2 - 0.5, -SLAB_T / 2 - 0.02,
        base_w, base_d, SLAB_T, M["floor_park"])
    for r in plan["rooms"]:
        mat = M["floor_wood"]
        kind = r.get("kind", "habitable")
        if kind in ("kitchen",):
            mat = M["floor_kitchen"]
        elif kind in ("bathroom",):
            mat = M["floor_bath"]
        elif kind in ("parking",):
            mat = M["floor_park"]
        elif kind in ("staircase", "circulation", "puja"):
            mat = M["floor_tile"]
        x, y, w, d = r["x_ft"], r["y_ft"], r["width_ft"], r["depth_ft"]
        box(f"Floor_{r['id']}", x + w / 2, y + d / 2, -0.07, w, d, 0.14, mat)
        made.append(r)
    return made


def build_walls(plan, M):
    """Build all walls with thickness; cut openings; apply cutaway."""
    nbr = _neighbors(plan)
    w, d = plan["plot"]["width_ft"], plan["plot"]["depth_ft"]

    # decide exterior sides of the plot that face the camera -> cut
    cut_sides = {k for k, v in CUT_SIDES.items() if v}

    for r in plan["rooms"]:
        for side in ("north", "south", "west", "east"):
            ax0, ay0, ax1, ay1 = _side_edge(r, side)
            seglen = math.hypot(ax1 - ax0, ay1 - ay0)
            if seglen < 0.3:
                continue
            exterior = _on_plot_boundary(plan, r, side) or side not in nbr[r["id"]]
            interior = side in nbr[r["id"]]
            is_cut = exterior and side in cut_sides
            th = PART_T if interior else WALL_T
            h = CUT_H if is_cut else (PART_H if interior else WALL_H)
            cx, cy = (ax0 + ax1) / 2, (ay0 + ay1) / 2
            horiz = side in ("north", "south")
            sx = seglen if horiz else th
            sy = seglen if not horiz else th
            wall = box(f"Wall_{r['id']}_{side}", cx, cy, h / 2, sx, sy, h,
                       M["wall_ext"] if (exterior or is_cut) else M["wall_paint"])

            # openings
            ops = _openings_for(plan, r, side)
            for t0, t1, kind, rec in ops:
                if is_cut:
                    continue  # low cut wall stays solid; slab trimmed separately
                leaf = t1 - t0
                mid = (t0 + t1) / 2
                along_x = horiz
                th_cut = th + 0.3
                if kind == "door":
                    zc, zh = (DOOR_H + h) / 2 + 0.01, h - DOOR_H + 0.2
                else:
                    zc, zh = (SILL_H + HEAD_H) / 2, HEAD_H - SILL_H + 0.2
                if along_x:
                    cutter = box("cut", ax0 + mid, cy, zc, leaf + 0.12, th_cut, zh, None)
                else:
                    cutter = box("cut", cx, ay0 + mid, zc, th_cut, leaf + 0.12, zh, None)
                _bool_cut(wall, cutter)

            # flat cap on cut walls
            if is_cut:
                cap = box(f"Cap_{r['id']}_{side}", cx, cy, CUT_H + 0.09,
                          sx + 0.12, sy + 0.12, 0.18, M["cut_cap"])
    return


def build_opening_trims(plan, M):
    """Door slabs/frames and window frames/glass at canonical positions."""
    for dr in plan.get("doors", []):
        r = next((rr for rr in plan["rooms"] if rr["id"] == dr["room_id"]), None)
        if r is None:
            continue
        side = dr["side"]
        span = r["width_ft"] if side in ("north", "south") else r["depth_ft"]
        off = float(dr.get("offset_ft", 0))
        leaf = min(2.8, max(1.6, span - off))
        ax0, ay0, ax1, ay1 = _side_edge(r, side)
        horiz = side in ("north", "south")
        exterior = dr.get("connects_to") == "exterior"
        th = WALL_T if (exterior or _on_plot_boundary(plan, r, side)) else PART_T
        is_cut_side = exterior and side in {"k": k for k, v in CUT_SIDES.items() if v}
        wall_h = CUT_H if is_cut_side else (WALL_H if not horiz or True else PART_H)
        # door height limited by cut walls
        dh = min(DOOR_H, (CUT_H - 0.2) if is_cut_side else DOOR_H)
        cx, cy = (ax0 + ax1) / 2, (ay0 + ay1) / 2
        if horiz:
            px = ax0 + off + leaf / 2
            # frame
            box(f"DoorFrame_{dr['id']}", px, cy, dh / 2, leaf + 0.24, th + 0.16,
                0.28, M["door_frame"])
            # slab (slightly open look: inset)
            box(f"DoorSlab_{dr['id']}", px, cy, dh / 2 - 0.1, leaf - 0.08,
                th * 0.5, dh - 0.15, M["door_wood"])
            if exterior:
                # porch slab outside
                out_y = cy + (2.2 if side == "south" else -2.2)
                box(f"Porch_{dr['id']}", px, out_y, 0.04, leaf + 2.4, 4.4, 0.16,
                    M["paving"])
        else:
            py = ay0 + off + leaf / 2
            box(f"DoorFrame_{dr['id']}", cx, py, dh / 2, th + 0.16, leaf + 0.24,
                0.28, M["door_frame"])
            box(f"DoorSlab_{dr['id']}", cx, py, dh / 2 - 0.1, th * 0.5,
                leaf - 0.08, dh - 0.15, M["door_wood"])
            if exterior:
                out_x = cx + (2.2 if side == "east" else -2.2)
                box(f"Porch_{dr['id']}", out_x, py, 0.04, 4.4, leaf + 2.4, 0.16,
                    M["paving"])

    for wn in plan.get("windows", []):
        r = next((rr for rr in plan["rooms"] if rr["id"] == wn["room_id"]), None)
        if r is None:
            continue
        side = wn["side"]
        span = r["width_ft"] if side in ("north", "south") else r["depth_ft"]
        off = float(wn.get("offset_ft", 0))
        leaf = max(1.6, min(float(wn.get("width_ft", 4.0)), span - off - 0.3))
        exterior = _on_plot_boundary(plan, r, side)
        if not exterior:
            continue
        if side in {k for k, v in CUT_SIDES.items() if v}:
            continue  # cut side: no window trims
        ax0, ay0, ax1, ay1 = _side_edge(r, side)
        horiz = side in ("north", "south")
        cx, cy = (ax0 + ax1) / 2, (ay0 + ay1) / 2
        zc = (SILL_H + HEAD_H) / 2
        wh = HEAD_H - SILL_H
        if horiz:
            px = ax0 + off + leaf / 2
            box(f"WinSill_{wn['id']}", px, cy, SILL_H - 0.06, leaf + 0.3,
                WALL_T + 0.3, 0.12, M["win_frame"])
            box(f"WinFrame_{wn['id']}", px, cy, zc, leaf, WALL_T * 0.6, wh,
                M["win_frame"])
            box(f"WinGlass_{wn['id']}", px, cy, zc, leaf - 0.14, 0.06, wh - 0.14,
                M["glass"])
            box(f"WinTop_{wn['id']}", px, cy, HEAD_H + 0.06, leaf + 0.3,
                WALL_T + 0.3, 0.12, M["win_frame"])
        else:
            py = ay0 + off + leaf / 2
            box(f"WinSill_{wn['id']}", cx, py, SILL_H - 0.06, WALL_T + 0.3,
                leaf + 0.3, 0.12, M["win_frame"])
            box(f"WinFrame_{wn['id']}", cx, py, zc, WALL_T * 0.6, leaf, wh,
                M["win_frame"])
            box(f"WinGlass_{wn['id']}", cx, py, zc, 0.06, leaf - 0.14, wh - 0.14,
                M["glass"])
            box(f"WinTop_{wn['id']}", cx, py, HEAD_H + 0.06, WALL_T + 0.3,
                leaf + 0.3, 0.12, M["win_frame"])


def build_site(plan, M):
    """Ground, plot slab, boundary wall on far sides, driveway, walkway, trees."""
    w, d = plan["plot"]["width_ft"], plan["plot"]["depth_ft"]
    # ground plane
    bpy.ops.mesh.primitive_plane_add(size=1, location=(w / 2, d / 2, -0.42))
    g = bpy.context.active_object
    g.name = "Ground"
    g.scale = (220, 220, 1)
    g.data.materials.append(M["ground"])
    absorb(g)

    # boundary wall on the two far sides (opposite the camera)
    far_x = "east" if CUT_SIDES.get("west") else "west"
    far_y = "south" if CUT_SIDES.get("north") else "north"
    th, bh = 0.5, 4.5
    off = 0.75
    if far_x == "east":
        box("BndX", w + off, d / 2, bh / 2 - 0.3, th, d + 2 * off, bh, M["boundary"])
    else:
        box("BndX", -off, d / 2, bh / 2 - 0.3, th, d + 2 * off, bh, M["boundary"])
    if far_y == "south":
        box("BndY", w / 2, d + off, bh / 2 - 0.3, w + 2 * off, th, bh, M["boundary"])
    else:
        box("BndY", w / 2, -off, bh / 2 - 0.3, w + 2 * off, th, bh, M["boundary"])

    # driveway in front of parking (outside the plot)
    parking = next((r for r in plan["rooms"] if r.get("kind") == "parking"), None)
    if parking is not None:
        px, py, pw, pd = (parking["x_ft"], parking["y_ft"],
                          parking["width_ft"], parking["depth_ft"])
        if abs(px) < 0.02:
            box("Driveway", px - 4.5, py + pd / 2, -0.30, 9.0, pd + 2, 0.2,
                M["paving"])
        elif abs(px + pw - w) < 0.02:
            box("Driveway", px + pw + 4.5, py + pd / 2, -0.30, 9.0, pd + 2, 0.2,
                M["paving"])
        elif abs(py) < 0.02:
            box("Driveway", px + pw / 2, py - 4.5, -0.30, pw + 2, 9.0, 0.2,
                M["paving"])
        else:
            box("Driveway", px + pw / 2, py + pd + 4.5, -0.30, pw + 2, 9.0, 0.2,
                M["paving"])

    # trees outside the far corners
    seed = 0
    for tx, ty in ((-3.0, -3.0), (w + 3.0, d + 3.0), (-3.0, d * 0.6)):
        seed += 1
        s = 0.9 + 0.25 * ((seed * 37) % 3)
        cyl(f"Trunk{seed}", tx, ty, 2.2, 0.28 * s, 5.2, M["trunk"], verts=12)
        sph(f"Leaf{seed}a", tx, ty, 5.6 * s, 2.0 * s, M["leaf"])
        sph(f"Leaf{seed}b", tx + 1.1 * s, ty - 0.7 * s, 4.6 * s, 1.5 * s, M["leaf"])
        sph(f"Leaf{seed}c", tx - 0.9 * s, ty + 0.8 * s, 4.8 * s, 1.4 * s, M["leaf"])
