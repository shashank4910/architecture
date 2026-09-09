"""Room-level furnishing driven by canonical plan data.

Placement uses door zones to avoid blocking openings, canonical room bounds,
and simple occupancy tracking per room.
"""

import math

from .blender_geom import box, cyl, sph, rot_pt
from . import blender_furniture as BF


def _door_zones(plan, room):
    """(x, y, w, d) zones in front of each door of the room."""
    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
    zones = []
    for dr in plan.get("doors", []):
        if dr.get("room_id") != room["id"]:
            continue
        side, off = dr["side"], float(dr.get("offset_ft", 0))
        span = w if side in ("north", "south") else d
        leaf = min(2.8, max(1.6, span - off))
        if side == "north":
            zones.append((x + off, y, leaf, leaf + 0.6))
        elif side == "south":
            zones.append((x + off, y + d - leaf - 0.6, leaf, leaf + 0.6))
        elif side == "west":
            zones.append((x, y + off, leaf + 0.6, leaf))
        else:
            zones.append((x + w - leaf - 0.6, y + off, leaf + 0.6, leaf))
    return zones


def _window_zones(plan, room):
    zones = []
    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
    for wn in plan.get("windows", []):
        if wn.get("room_id") != room["id"]:
            continue
        side, off = wn["side"], float(wn.get("offset_ft", 0))
        span = w if side in ("north", "south") else d
        leaf = max(1.6, min(float(wn.get("width_ft", 4.0)), span - off - 0.3))
        if side == "north":
            zones.append((x + off, y, leaf, 2.0))
        elif side == "south":
            zones.append((x + off, y + d - 2.0, leaf, 2.0))
        elif side == "west":
            zones.append((x, y + off, 2.0, leaf))
        else:
            zones.append((x + w - 2.0, y + off, 2.0, leaf))
    return zones


def _hits(a, zones):
    return any(not (a[0] + a[2] <= z[0] or z[0] + z[2] <= a[0]
                    or a[1] + a[3] <= z[1] or z[1] + z[3] <= a[1])
               for z in zones)


def _mk_ok(room, zones):
    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]

    def ok(rr, inset=0.8):
        rx, ry, rw, rd = rr
        if rx < x + inset or ry < y + inset or rx + rw > x + w - inset \
                or ry + rd > y + d - inset:
            return False
        return not _hits(rr, zones)
    return ok


def furnish_room(plan, M, room, seed=0):
    """Furnish one room according to its canonical kind."""
    kind = room.get("kind", "habitable")
    if kind == "parking":
        parking = next((p for p in plan.get("parking", [])
                        if p.get("room_id") == room["id"]), None)
        BF.car(M, room)
        return
    if kind == "staircase":
        st = next((s for s in plan.get("stairs", [])
                   if s.get("room_id") == room["id"]), None)
        BF.staircase(M, room, risers=(st or {}).get("riser_count", 14))
        return
    if kind == "bathroom":
        BF.bath_set(M, room)
        return
    if kind == "kitchen":
        _kitchen(plan, M, room)
        return
    if kind == "puja":
        BF.puja_set(M, room)
        return
    if kind != "habitable":
        return

    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
    zones = _door_zones(plan, room) + _window_zones(plan, room)
    ok = _mk_ok(room, zones)
    rid = room["id"]

    if rid == "living":
        _living(plan, M, room, ok, x, y, w, d)
    elif rid == "dining":
        BF.rug(M, x + w / 2, y + d / 2, min(w - 2.0, 7.5), min(d - 2.0, 6.0))
        BF.dining_set(M, x + w / 2, y + d / 2, w, d)
        # table centerpiece
        BF.plant(M, x + w / 2, y + d / 2, 0.28)
    else:
        _bedroom(plan, M, room, ok, x, y, w, d)


def _living(plan, M, room, ok, x, y, w, d):
    BF.rug(M, x + w / 2, y + d / 2, min(w - 3.0, 9.0), min(d - 3.0, 7.0))
    sofa_r = None
    ang = 0.0
    if w >= d + 1.0:
        for sy0, a in ((y + 0.9, math.pi), (y + d - 3.6, 0.0)):
            cand = (x + (w - 7.0) / 2, sy0, 7.0, 3.2)
            if ok(cand):
                sofa_r = (cand[0] + 3.5, cand[1] + 1.6)
                ang = a
                break
    else:
        for sx0, a in ((x + 0.9, -math.pi / 2), (x + w - 3.6, math.pi / 2)):
            cand = (sx0, y + (d - 7.0) / 2, 3.2, 7.0)
            if ok(cand):
                sofa_r = (cand[0] + 1.6, cand[1] + 3.5)
                ang = a
                break
    if sofa_r:
        sx, sy = sofa_r
        BF.sofa(M, sx, sy, 7.0, 3.2, ang)
        # coffee table in front of sofa
        fx, fy = rot_pt(0, 2.9, ang)
        if ok((sx + fx - 1.7, sy + fy - 1.0, 3.4, 2.0)):
            BF.coffee_table(M, sx + fx, sy + fy, 3.4, 2.0)
        # TV console opposite the sofa
        tx_off, ty_off = rot_pt(0, -(d / 2 - (sy - y) - 1.05), ang)
        tvx, tvy = sx + tx_off, sy + ty_off
        if y + 0.9 <= tvy <= y + d - 0.9:
            hz = w >= d
            BF.tv_console(M, tvx if hz else tvx, tvy, 5.0 if hz else 1.8,
                          1.6 if hz else 5.0, 0.0 if hz else math.pi / 2)
    # armchair near a side wall
    for ax, ay, a in ((x + 1.7, y + d - 1.9, math.pi / 2),
                      (x + w - 1.7, y + 1.9, -math.pi / 2)):
        if ok((ax - 1.4, ay - 1.4, 2.8, 2.8)):
            BF.armchair(M, ax, ay, 2.7, a)
            break
    # side table + lamp + plant
    if sofa_r:
        stx, sty = rot_pt(-(7.0 / 2 + 0.9), -1.0, ang)
        BF.side_table(M, sx + stx, sy + sty)
        lx, ly = rot_pt(7.0 / 2 + 1.0, 0.6, ang)
        if ok((sx + lx - 0.7, sy + ly - 0.7, 1.4, 1.4)):
            BF.floor_lamp(M, sx + lx, sy + ly)
    for px, py in ((x + w - 1.4, y + d - 1.4), (x + 1.4, y + 1.4)):
        if ok((px - 1.0, py - 1.0, 2.0, 2.0)):
            BF.plant(M, px, py, 1.0)
            break


def _bedroom(plan, M, room, ok, x, y, w, d):
    # large area rug anchors the room even before furniture lands
    BF.rug(M, x + w / 2, y + d / 2, min(w - 2.2, 8.0), min(d - 2.2, 8.0))
    small = min(w, d) < 7.5
    bw, bl = (3.5, 6.5) if small else (5.0, 6.8)
    cands = []
    if w >= bw + 1.4:
        cands += [(x + (w - bw) / 2, y + 0.8, bw, bl, 0.0),
                  (x + (w - bw) / 2, y + d - bl - 0.8, bw, bl, math.pi)]
    if d >= bw + 1.4:
        cands += [(x + 0.8, y + (d - bw) / 2, bl, bw, math.pi / 2),
                  (x + w - bl - 0.8, y + (d - bw) / 2, bl, bw, -math.pi / 2)]
    chosen = None
    for cx0, cy0, cw0, cd0, a in cands:
        rr = (cx0, cy0, cw0, cd0)
        if ok(rr):
            chosen = (cx0 + cw0 / 2, cy0 + cd0 / 2, cw0, cd0, a)
            break
    if chosen:
        bx, by, bw_, bd_, ang = chosen
        # head on local -y side after rotation; place with anchor at center
        BF.bed(M, bx, by, bw_, bd_, ang)
        # nightstands on head side
        for sgn in (-1, 1):
            dx, dy = rot_pt(sgn * (bw_ / 2 + 0.75), -bd_ / 2 + 0.85, ang)
            BF.side_table(M, bx + dx, by + dy)
        # wardrobe on a free wall
        for wx0, wy0, ww, wd, wa in (
                (x + 0.55, y + 0.55, 2.0, min(5.0, d - 1.4), math.pi / 2),
                (x + w - 2.55, y + 0.55, 2.0, min(5.0, d - 1.4), math.pi / 2),
                (x + 0.55, y + 0.55, min(5.0, w - 1.4), 2.0, 0.0),
                (x + 0.55, y + d - 2.55, min(5.0, w - 1.4), 2.0, 0.0)):
            rr = (wx0, wy0, ww if abs(math.sin(wa)) > 0.5 else ww,
                  wd if abs(math.sin(wa)) > 0.5 else wd)
            rr = (wx0, wy0, ww, wd)
            if ok(rr) and not _hits(rr, [(chosen[0] - bw_ / 2, chosen[1] - bd_ / 2,
                                          bw_, bd_)]):
                BF.wardrobe(M, wx0 + ww / 2, wy0 + wd / 2, ww, wd, wa)
                break
        # dresser on a free wall when space allows
        for dx0, dy0, dw, dd, da in (
                (x + w - 2.0, y + d - 2.4, 1.7, 1.9, 0.0),
                (x + 0.3, y + d - 2.4, 1.7, 1.9, 0.0)):
            rr = (dx0, dy0, dw, dd)
            if ok(rr) and not _hits(rr, [(chosen[0] - bw_ / 2,
                                          chosen[1] - bd_ / 2, bw_, bd_)]):
                BF.dresser(M, dx0 + dw / 2, dy0 + dd / 2, dw, dd)
                break
        # runner rug at the foot of the bed
        rx, ry = rot_pt(0, 1.4, ang)
        BF.rug(M, bx + rx, by + ry, min(bw_ + 1.6, w - 2.4), 3.4)
        # plant
        for px, py in ((x + w - 1.3, y + d - 1.3), (x + 1.3, y + d - 1.3)):
            if ok((px - 0.9, py - 0.9, 1.8, 1.8)):
                BF.plant(M, px, py, 0.85)
                break


def _kitchen(plan, M, room):
    """Counter runs along walls free of door zones + sink/hob/fridge."""
    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
    cd = 2.1
    dz = _door_zones(plan, room)
    counter_zones = []
    # candidate runs: full walls minus door spans
    for side in ("north", "south", "west", "east"):
        span = w if side in ("north", "south") else d
        blocks = []
        for dr in plan.get("doors", []):
            if dr.get("room_id") == room["id"] and dr["side"] == side:
                off = float(dr.get("offset_ft", 0))
                blocks.append((max(0.0, off - 0.5), min(span, off + 3.3)))
        runs = []
        cur = 0.0
        for b0, b1 in sorted(blocks):
            if b0 - cur > 2.2:
                runs.append((cur, b0))
            cur = max(cur, b1)
        if span - cur > 2.2:
            runs.append((cur, span))
        for a, b in runs:
            counter_zones.append((side, a, b))
    BF.kitchen_counters(M, room, counter_zones)
    # sink + hob on the longest run
    if counter_zones:
        side, a, b = max(counter_zones, key=lambda z: z[2] - z[1])
        mid = (a + b) / 2
        if side == "north":
            BF.kitchen_sink(M, x + mid - 1.6, y + cd / 2)
            BF.kitchen_hob(M, x + mid + 1.6, y + cd / 2)
        elif side == "south":
            BF.kitchen_sink(M, x + mid - 1.6, y + d - cd / 2)
            BF.kitchen_hob(M, x + mid + 1.6, y + d - cd / 2)
        elif side == "west":
            BF.kitchen_sink(M, x + cd / 2, y + mid - 1.6)
            BF.kitchen_hob(M, x + cd / 2, y + mid + 1.6)
        else:
            BF.kitchen_sink(M, x + w - cd / 2, y + mid - 1.6)
            BF.kitchen_hob(M, x + w - cd / 2, y + mid + 1.6)
    # fridge in the first corner clear of door swings
    fx, fy = x + 0.15, y + 0.15
    corners = [(x + 0.15, y + 0.15), (x + w - 3.0, y + 0.15),
               (x + 0.15, y + d - 2.65), (x + w - 3.0, y + d - 2.65)]
    for cxx, cyy in corners:
        if not _hits((cxx + 0.2, cyy + 0.2, 2.4, 2.1), dz):
            fx, fy = cxx, cyy
            break
    BF.fridge(M, fx, fy)
