from __future__ import annotations

import json
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def _font(size, bold=False):
    names = ["arialbd.ttf", "arial.ttf"] if bold else ["arial.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


INK = "#1f1d1a"          # walls / primary lines
MID = "#4d4842"          # door arcs / secondary lines
FAINT = "#8d867c"        # furniture strokes
FURN = "#d9d3c5"         # furniture fill
WOOD = "#c8b798"         # wood elements
GLASS = "#eef3f3"        # window glazing
PAPER = "#fbfaf5"        # sheet background
VOID = "#e8e4da"         # exterior void
HATCH = "#cdc7ba"        # void hatch lines
DIYA = "#c07b36"
TINT = {
    "habitable": "#f6f1e6",
    "kitchen": "#efe3c8",
    "bathroom": "#dce8ec",
    "parking": "#e3e7ea",
    "staircase": "#eae6dc",
    "puja": "#f2e0cd",
    "circulation": "#f3efe6",
}
EXT, INT = 7, 4          # wall thickness in px


def _room_point(room, side, offset):
    if side in {"north", "south"}:
        return room["x_ft"] + offset, room["y_ft"] if side == "north" else room["y_ft"] + room["depth_ft"]
    return room["x_ft"] if side == "west" else room["x_ft"] + room["width_ft"], room["y_ft"] + offset


def _fmt_ft(v):
    feet = int(v)
    inches = int(round((v - feet) * 12))
    if inches == 12:
        feet, inches = feet + 1, 0
    return f"{feet}'-{inches}\""


def _runs(length, openings):
    """Wall segments [start, end] along an edge, excluding opening intervals."""
    ops = sorted((max(0.0, a), min(length, b)) for a, b in openings if b > 0.01 and a < length - 0.01)
    segs, cur = [], 0.0
    for a, b in ops:
        if a > cur + 0.01:
            segs.append((cur, a))
        cur = max(cur, b)
    if cur < length - 0.01:
        segs.append((cur, length))
    return segs


def _halo(draw, xy, text, font, fill=INK, halo=PAPER, anchor="mm", spacing=4, width=3):
    try:
        draw.multiline_text(xy, text, fill=fill, font=font, anchor=anchor, align="center",
                            spacing=spacing, stroke_width=width, stroke_fill=halo)
    except TypeError:
        draw.multiline_text(xy, text, fill=fill, font=font, anchor=anchor, align="center", spacing=spacing)


def _halo1(draw, xy, text, font, fill=INK, halo=PAPER, anchor="mm", width=3):
    try:
        draw.text(xy, text, fill=fill, font=font, anchor=anchor, stroke_width=width, stroke_fill=halo)
    except TypeError:
        draw.text(xy, text, fill=fill, font=font, anchor=anchor)


def _vtext(image, xy, text, font, fill=INK, halo=PAPER):
    bb = font.getbbox(text)
    tmp = Image.new("RGBA", (bb[2] - bb[0] + 14, bb[3] - bb[1] + 14), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    try:
        d.text((7, 7), text, font=font, fill=fill, stroke_width=3, stroke_fill=halo)
    except TypeError:
        d.text((7, 7), text, font=font, fill=fill)
    tmp = tmp.rotate(90, expand=True)
    image.paste(tmp, xy, tmp)



def render_2d(plan, output_path, geometry_path=None):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    width, depth = plan["plot"]["width_ft"], plan["plot"]["depth_ft"]
    scale = max(22, min(28, 1400 // max(width, depth)))
    left, top, right, bottom = 175, 150, 235, 215
    W, H = width * scale + left + right, depth * scale + top + bottom
    image = Image.new("RGB", (W, H), PAPER)
    draw = ImageDraw.Draw(image)

    f_title, f_sub = _font(32, True), _font(18)
    f_room, f_dim = _font(19, True), _font(15, True)
    f_small, f_tag = _font(13), _font(12, True)
    ox, oy = left, top

    # ---------- header ----------
    beds = sum(1 for r in plan["rooms"] if r["kind"] == "habitable" and "bed" in r["name"].lower())
    baths = sum(1 for r in plan["rooms"] if r["kind"] == "bathroom")
    draw.text((28, 24), "CONCEPTUAL RESIDENTIAL FLOOR PLAN", fill=INK, font=f_title)
    sub = (f"{width} x {depth} ft PLOT   |   {plan['plot']['facing'].upper()} FACING   |   "
           f"{plan.get('bedrooms', beds)} BHK   |   {plan.get('bathrooms', baths)} BATHS   |   SINGLE FLOOR")
    draw.text((28, 62), sub, fill=MID, font=f_sub)
    draw.line((28, 88, W - 28, 88), fill=INK, width=2)

    # ---------- north arrow ----------
    nx, ny, nr = W - 66, 56, 16
    draw.ellipse((nx - nr, ny - nr, nx + nr, ny + nr), outline=INK, width=2)
    draw.polygon([(nx, ny - 10), (nx - 6, ny + 7), (nx, ny + 3), (nx + 6, ny + 7)], fill=INK)
    _halo1(draw, (nx, ny + nr + 9), "N", f_dim)

    px1, py1 = ox, oy
    px2, py2 = ox + width * scale, oy + depth * scale

    # ---------- plot underlay with void hatch ----------
    draw.rectangle((px1, py1, px2, py2), fill=VOID)
    step = 9
    span = int(depth * scale)
    for i in range(-span, width * scale + step, step):
        draw.line((px1 + i, py2, px1 + i + span, py1), fill=HATCH, width=1)

    # ---------- room fills ----------
    by_id = {r["id"]: r for r in plan["rooms"]}
    for room in plan["rooms"]:
        x1, y1 = ox + room["x_ft"] * scale, oy + room["y_ft"] * scale
        x2, y2 = ox + (room["x_ft"] + room["width_ft"]) * scale, oy + (room["y_ft"] + room["depth_ft"]) * scale
        draw.rectangle((x1, y1, x2, y2), fill=TINT.get(room.get("kind"), TINT["habitable"]))

    manifest = {"plot": dict(plan["plot"]), "rooms": [
        {k: r[k] for k in ("id", "x_ft", "y_ft", "width_ft", "depth_ft")} for r in plan["rooms"]]}

    # ---------- geometry helpers ----------
    def _side_geom(room, side):
        x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
        if side == "north":
            return (x, y), (x + w, y), w
        if side == "south":
            return (x, y + d), (x + w, y + d), w
        if side == "west":
            return (x, y), (x, y + d), d
        return (x + w, y), (x + w, y + d), d

    def _is_ext(room, side):
        return ((side == "north" and room["y_ft"] == 0)
                or (side == "south" and room["y_ft"] + room["depth_ft"] == depth)
                or (side == "west" and room["x_ft"] == 0)
                or (side == "east" and room["x_ft"] + room["width_ft"] == width))

    wins_by = {}
    for wn in plan["windows"]:
        wins_by.setdefault((wn["room_id"], wn["side"]), []).append(wn)

    def _proj(p, ax, ay, bx, by, length):
        vx, vy = bx - ax, by - ay
        L2 = vx * vx + vy * vy
        if L2 == 0:
            return None
        t = ((p[0] - ax) * vx + (p[1] - ay) * vy) / L2
        qx, qy = ax + vx * t, ay + vy * t
        if (qx - p[0]) ** 2 + (qy - p[1]) ** 2 > 0.0036:
            return None
        s = t * length
        return s if 0.02 <= s <= length - 0.02 else None

    # door openings in absolute ft so they punch BOTH rooms sharing the wall
    abs_openings = []
    for dr in plan["doors"]:
        droom = by_id[dr["room_id"]]
        dlen = _side_geom(droom, dr["side"])[2]
        dw = min(3.5 if dr["id"] == "entrance" else 3.0, dlen * 0.6)
        c = min(max(dr["offset_ft"], dw / 2 + 0.1), dlen - dw / 2 - 0.1)
        abs_openings.append((_room_point(droom, dr["side"], c - dw / 2),
                             _room_point(droom, dr["side"], c + dw / 2)))


    def _pxs(room, side, s):
        (ax, ay), (bx, by), length = _side_geom(room, side)
        return (ox + (ax + (bx - ax) * s / length) * scale, oy + (ay + (by - ay) * s / length) * scale)

    # ---------- walls with punched openings ----------
    for room in plan["rooms"]:
        for side in ("north", "south", "west", "east"):
            (ax, ay), (bx, by), length = _side_geom(room, side)
            t = EXT if _is_ext(room, side) else INT
            ops = []
            for p0, p1 in abs_openings:
                s = _proj(p0, ax, ay, bx, by, length)
                e = _proj(p1, ax, ay, bx, by, length)
                if s is not None and e is not None:
                    ops.append((min(s, e), max(s, e)))
            for wn in wins_by.get((room["id"], side), []):
                ops.append((wn["offset_ft"], wn["offset_ft"] + wn["width_ft"]))
            for s0, s1 in _runs(length, ops):
                x1, y1 = _pxs(room, side, s0)
                x2, y2 = _pxs(room, side, s1)
                pad = t / 2 + 1
                if ay == by:
                    draw.line((x1 - pad, y1, x2 + pad, y2), fill=INK, width=t)
                else:
                    draw.line((x1, y1 - pad, x2, y2 + pad), fill=INK, width=t)
    draw.rectangle((px1, py1, px2, py2), outline=INK, width=EXT)


    # ---------- windows: triple-line glazing ----------
    for wn in plan["windows"]:
        room = by_id[wn["room_id"]]
        t = EXT if _is_ext(room, wn["side"]) else INT
        wlen = _side_geom(room, wn["side"])[2]
        s0 = min(max(wn["offset_ft"], 0.15), max(0.15, wlen - wn["width_ft"] - 0.15))
        s1 = s0 + wn["width_ft"]
        x1, y1 = _pxs(room, wn["side"], s0)
        x2, y2 = _pxs(room, wn["side"], s1)
        hw = t / 2
        if y1 == y2:
            draw.rectangle((x1, y1 - hw, x2, y1 + hw), fill=GLASS)
            draw.line((x1, y1 - hw, x2, y1 - hw), fill=INK, width=2)
            draw.line((x1, y1 + hw, x2, y1 + hw), fill=INK, width=2)
            draw.line((x1, y1, x2, y1), fill=MID, width=2)
        else:
            draw.rectangle((x1 - hw, y1, x1 + hw, y2), fill=GLASS)
            draw.line((x1 - hw, y1, x1 - hw, y2), fill=INK, width=2)
            draw.line((x1 + hw, y1, x1 + hw, y2), fill=INK, width=2)
            draw.line((x1, y1, x1, y2), fill=MID, width=2)

    # ---------- doors: opening, leaf, hinge, swing arc ----------
    zones = {r["id"]: [] for r in plan["rooms"]}
    inward = {"north": (0, 1), "south": (0, -1), "west": (1, 0), "east": (-1, 0)}
    outward = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0)}
    for dr in plan["doors"]:
        room = by_id[dr["room_id"]]
        side = dr["side"]
        t = EXT if _is_ext(room, side) else INT
        dlen = _side_geom(room, side)[2]
        dw = min(3.5 if dr["id"] == "entrance" else 3.0, dlen * 0.6)
        c = min(max(dr["offset_ft"], dw / 2 + 0.1), dlen - dw / 2 - 0.1)
        s0, s1 = c - dw / 2, c + dw / 2
        hx, hy = _pxs(room, side, s0)
        tx, ty = _pxs(room, side, s1)
        ix, iy = inward[side]
        r = dw * scale
        lx, ly = hx + ix * r, hy + iy * r
        if iy == 0:
            draw.rectangle((hx, hy - t / 2 - 1, tx, hy + t / 2 + 1), fill=PAPER)
            draw.line((hx, hy - t / 2, hx, hy + t / 2), fill=INK, width=1)
            draw.line((tx, hy - t / 2, tx, hy + t / 2), fill=INK, width=1)
        else:
            draw.rectangle((hx - t / 2 - 1, hy, hx + t / 2 + 1, ty), fill=PAPER)
            draw.line((hx - t / 2, hy, hx + t / 2, hy), fill=INK, width=1)
            draw.line((hx - t / 2, ty, hx + t / 2, ty), fill=INK, width=1)
        if side in ("north", "west"):
            draw.arc((hx - r, hy - r, hx + r, hy + r), 0, 90, fill=MID, width=2)
        elif side == "south":
            draw.arc((hx - r, hy - r, hx + r, hy + r), 270, 360, fill=MID, width=2)
        else:
            draw.arc((hx - r, hy - r, hx + r, hy + r), 90, 180, fill=MID, width=2)
        draw.line((hx, hy, lx, ly), fill=INK, width=4 if dr["id"] == "entrance" else 3)
        draw.ellipse((hx - 2.5, hy - 2.5, hx + 2.5, hy + 2.5), fill=INK)
        qx = -1 if side == "east" else 1
        qy = -1 if side == "south" else 1
        zone = (hx, hy, r, qx, qy)
        for rid in {dr["room_id"], dr.get("connects_to")}:
            if rid in zones:
                zones[rid].append(zone)
        if dr["id"] == "entrance":
            gx, gy = outward[side]
            _halo1(draw, ((hx + tx) / 2 + gx * 15, (hy + ty) / 2 + gy * 15), "ENTRY", f_tag)


    # ---------- furniture primitives ----------
    def _ft_rect(room, fx, fy, fw, fd):
        return (ox + fx * scale, oy + fy * scale,
                ox + (fx + fw) * scale, oy + (fy + fd) * scale)

    def _free(zl, rect, pad=2):
        for z in zl:
            zx, zy, zr, qx, qy = z
            cxp = min(max(zx, rect[0]), rect[2])
            cyp = min(max(zy, rect[1]), rect[3])
            if qx * (cxp - zx) < -0.5 or qy * (cyp - zy) < -0.5:
                continue
            if (cxp - zx) ** 2 + (cyp - zy) ** 2 < (zr + pad) ** 2:
                return False
        return True

    def _overlap(a, b):
        return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])

    def _pillows(r, head, single):
        out = []
        if head in ("south", "north"):
            yy = r[3] - 14 if head == "south" else r[1] + 5
            if single:
                out.append((r[0] + 5, yy, r[2] - 5, yy + 9))
            else:
                mid = (r[0] + r[2]) / 2
                out.append((r[0] + 5, yy, mid - 2, yy + 9))
                out.append((mid + 2, yy, r[2] - 5, yy + 9))
        else:
            xx = r[0] + 5 if head == "west" else r[2] - 14
            if single:
                out.append((xx, r[1] + 5, xx + 9, r[3] - 5))
            else:
                mid = (r[1] + r[3]) / 2
                out.append((xx, r[1] + 5, xx + 9, mid - 2))
                out.append((xx, mid + 2, xx + 9, r[3] - 5))
        return out

    def _furn_bedroom(room, zl, plan_ref):
        x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
        single = min(w, d) < 9
        bw, bl = (3.5, 6.3) if single else (5.0, 6.6)
        bed = head = None
        for side in ("south", "west", "east", "north"):
            if side in ("south", "north"):
                if bw > w - 1.4 or bl > d - 1.4:
                    continue
                cand = (x + (w - bw) / 2,
                        y + d - 0.6 - bl if side == "south" else y + 0.6, bw, bl)
            else:
                if bl > w - 1.4 or bw > d - 1.4:
                    continue
                cand = (x + 0.6 if side == "west" else x + w - 0.6 - bl,
                        y + (d - bw) / 2, bl, bw)
            prect = _ft_rect(room, *cand)
            if _free(zl, prect):
                bed, head = cand, side
                break
        bedrect = None
        if bed:
            bedrect = _ft_rect(room, *bed)
            draw.rectangle(bedrect, fill=FURN, outline=FAINT, width=2)
            if head == "south":
                hb = (bedrect[0], bedrect[3] - 6, bedrect[2], bedrect[3])
            elif head == "north":
                hb = (bedrect[0], bedrect[1], bedrect[2], bedrect[1] + 6)
            elif head == "west":
                hb = (bedrect[0], bedrect[1], bedrect[0] + 6, bedrect[3])
            else:
                hb = (bedrect[2] - 6, bedrect[1], bedrect[2], bedrect[3])
            draw.rectangle(hb, fill=WOOD, outline=FAINT, width=1)
            for pr in _pillows(bedrect, head, single):
                draw.rectangle(pr, fill="#f4f0e5", outline=FAINT, width=1)
            if head in ("south", "north"):
                fy_ = bedrect[1] + (bedrect[3] - bedrect[1]) * (0.24 if head == "south" else 0.76)
                draw.line((bedrect[0] + 3, fy_, bedrect[2] - 3, fy_), fill=FAINT, width=1)
            else:
                fx_ = bedrect[0] + (bedrect[2] - bedrect[0]) * (0.24 if head == "west" else 0.76)
                draw.line((fx_, bedrect[1] + 3, fx_, bedrect[3] - 3), fill=FAINT, width=1)
            if not single:
                ns = 1.3
                if head in ("south", "north"):
                    ny = y + d - 0.6 - ns if head == "south" else y + 0.6
                    for sx in (x + (w - bw) / 2 - ns - 0.3, x + (w + bw) / 2 + 0.3):
                        if sx >= x + 0.2 and sx + ns <= x + w - 0.2:
                            nrect = _ft_rect(room, sx, ny, ns, ns)
                            if _free(zl, nrect) and not _overlap(nrect, bedrect):
                                draw.rectangle(nrect, fill=FURN, outline=FAINT, width=1)
                                mx, my = (nrect[0] + nrect[2]) / 2, (nrect[1] + nrect[3]) / 2
                                draw.ellipse((mx - 2, my - 2, mx + 2, my + 2), fill=FAINT)
        _wardrobe(room, zl, head, bedrect)

    def _wardrobe(room, zl, head, bedrect):
        x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
        for wside in ("north", "west", "east", "south"):
            if wside == head:
                continue
            wdep = 2.0
            if wside in ("north", "south"):
                if w < 4.2 or d < 3.0:
                    continue
                wl = min(4.5, w - 1.0)
                cand = (x + (w - wl) / 2,
                        y + 0.5 if wside == "north" else y + d - 0.5 - wdep, wl, wdep)
            else:
                if d < 4.2 or w < 3.0:
                    continue
                wl = min(4.5, d - 1.0)
                cand = (x + 0.5 if wside == "west" else x + w - 0.5 - wdep,
                        y + (d - wl) / 2, wdep, wl)
            wrect = _ft_rect(room, *cand)
            if _free(zl, wrect) and not (bedrect and _overlap(wrect, bedrect)):
                draw.rectangle(wrect, fill=WOOD, outline=FAINT, width=1)
                if wside in ("north", "south"):
                    mx = (wrect[0] + wrect[2]) / 2
                    draw.line((mx, wrect[1] + 2, mx, wrect[3] - 2), fill=FAINT, width=1)
                else:
                    my = (wrect[1] + wrect[3]) / 2
                    draw.line((wrect[0] + 2, my, wrect[2] - 2, my), fill=FAINT, width=1)
                return


    def _furn_living(room, zl, plan_ref):
        x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
        sofa = back = None
        for side in ("west", "east", "south", "north"):
            if side in ("west", "east"):
                if 6.5 > d - 1.4 or 2.9 > w - 1.4:
                    continue
                cand = (x + 0.6 if side == "west" else x + w - 0.6 - 2.9,
                        y + (d - 6.5) / 2, 2.9, 6.5)
            else:
                if 6.5 > w - 1.4 or 2.9 > d - 1.4:
                    continue
                cand = (x + (w - 6.5) / 2,
                        y + 0.6 if side == "north" else y + d - 0.6 - 2.9, 6.5, 2.9)
            srect = _ft_rect(room, *cand)
            if _free(zl, srect):
                sofa, back = cand, side
                break
        if not sofa:
            return
        srect = _ft_rect(room, *sofa)
        draw.rectangle(srect, fill=FURN, outline=FAINT, width=2)
        band = 6
        if back in ("north", "south"):
            bb = (srect[0], srect[1], srect[2], srect[1] + band) if back == "north" else \
                 (srect[0], srect[3] - band, srect[2], srect[3])
            draw.rectangle(bb, fill=WOOD, outline=FAINT, width=1)
            for ex in (srect[0], srect[2] - 7):
                draw.rectangle((ex, srect[1], ex + 7, srect[3]), outline=FAINT, width=1)
            mx = (srect[0] + srect[2]) / 2
            draw.line((mx, srect[1] + band, mx, srect[3] - 2), fill=FAINT, width=1)
            if back == "north" and sofa[1] + sofa[3] + 2.9 <= y + d - 0.4:
                cy_ = sofa[1] + sofa[3] + 1.2
            elif back == "south" and sofa[1] - 2.9 >= y + 0.4:
                cy_ = sofa[1] - 1.2 - 1.7
            else:
                cy_ = None
            if cy_ is not None:
                trect = _ft_rect(room, sofa[0] + (sofa[2] - 3.4) / 2, cy_, 3.4, 1.7)
                if _free(zl, trect):
                    draw.rectangle(trect, fill=FURN, outline=FAINT, width=1)
                    draw.ellipse((trect[0] + 4, trect[1] + 3, trect[2] - 4, trect[3] - 3), outline=FAINT, width=1)
        else:
            bb = (srect[0], srect[1], srect[0] + band, srect[3]) if back == "west" else \
                 (srect[2] - band, srect[1], srect[2], srect[3])
            draw.rectangle(bb, fill=WOOD, outline=FAINT, width=1)
            for ey in (srect[1], srect[3] - 7):
                draw.rectangle((srect[0], ey, srect[2], ey + 7), outline=FAINT, width=1)
            my = (srect[1] + srect[3]) / 2
            draw.line((srect[0] + band, my, srect[2] - 2, my), fill=FAINT, width=1)
        tvside = {"north": "south", "south": "north", "west": "east", "east": "west"}[back]
        tlen, tdep = 5.0, 1.4
        if tvside in ("north", "south"):
            if tlen <= w - 0.8 and tdep <= d - 0.8:
                tvy = y + 0.4 if tvside == "north" else y + d - 0.4 - tdep
                trect = _ft_rect(room, x + (w - tlen) / 2, tvy, tlen, tdep)
                if _free(zl, trect) and not _overlap(trect, srect):
                    draw.rectangle(trect, fill=FURN, outline=FAINT, width=1)
                    bx0 = (trect[0] + trect[2]) / 2 - 16
                    tvr = (bx0, trect[1] + 2, bx0 + 32, trect[1] + 6) if tvside == "north" else \
                          (bx0, trect[3] - 6, bx0 + 32, trect[3] - 2)
                    draw.rectangle(tvr, fill="#3d3b38", outline=FAINT, width=1)
        else:
            if tlen <= d - 0.8 and tdep <= w - 0.8:
                tvx = x + 0.4 if tvside == "west" else x + w - 0.4 - tdep
                trect = _ft_rect(room, tvx, y + (d - tlen) / 2, tdep, tlen)
                if _free(zl, trect) and not _overlap(trect, srect):
                    draw.rectangle(trect, fill=FURN, outline=FAINT, width=1)
                    by0 = (trect[1] + trect[3]) / 2 - 16
                    tvr = (trect[0] + 2, by0, trect[0] + 6, by0 + 32) if tvside == "west" else \
                          (trect[2] - 6, by0, trect[2] - 2, by0 + 32)
                    draw.rectangle(tvr, fill="#3d3b38", outline=FAINT, width=1)


    def _furn_dining(room, zl, plan_ref):
        x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
        horiz = w >= d
        tl, tw = (5.5, 3.0) if (w >= 9 and d >= 7.5) else (4.2, 2.8)
        if not horiz:
            tl, tw = tw, tl
        if tl > w - 1.2 or tw > d - 1.2:
            return
        tx, ty = x + (w - tl) / 2, y + (d - tw) / 2
        crect = _ft_rect(room, tx, ty, tl, tw)
        if not _free(zl, crect):
            return
        cs = 1.25
        chairs = []
        if horiz:
            for k in (0.3, 0.7):
                cxx = tx + tl * k - cs / 2
                chairs.append((cxx, ty - cs - 0.15))
                chairs.append((cxx, ty + tw + 0.15))
        else:
            for k in (0.3, 0.7):
                cyy = ty + tl * k - cs / 2
                chairs.append((tx - cs - 0.15, cyy))
                chairs.append((tx + tw + 0.15, cyy))
        for chx, chy in chairs:
            if chx < x + 0.1 or chy < y + 0.1 or chx + cs > x + w - 0.1 or chy + cs > y + d - 0.1:
                continue
            prect = _ft_rect(room, chx, chy, cs, cs)
            if _free(zl, prect):
                draw.rectangle(prect, fill=FURN, outline=FAINT, width=1)
                draw.rectangle((prect[0] + 2, prect[1] + 2, prect[2] - 2, prect[3] - 2), outline=FAINT, width=1)
        draw.rectangle(crect, fill=WOOD, outline=FAINT, width=2)
        draw.rectangle((crect[0] + 4, crect[1] + 4, crect[2] - 4, crect[3] - 4), outline=FAINT, width=1)

    def _furn_study(room, zl, plan_ref):
        x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
        for side in ("north", "west", "east", "south"):
            if side in ("north", "south"):
                if 4.5 > w - 1.2 or 2.0 > d - 1.2:
                    continue
                desk = (x + (w - 4.5) / 2,
                        y + 0.5 if side == "north" else y + d - 0.5 - 2.0, 4.5, 2.0)
            else:
                if 4.5 > d - 1.2 or 2.0 > w - 1.2:
                    continue
                desk = (x + 0.5 if side == "west" else x + w - 0.5 - 2.0,
                        y + (d - 4.5) / 2, 2.0, 4.5)
            drect = _ft_rect(room, *desk)
            if not _free(zl, drect):
                continue
            draw.rectangle(drect, fill=WOOD, outline=FAINT, width=2)
            draw.line((drect[0] + 4, drect[1] + 4, drect[2] - 4, drect[3] - 4), fill=FAINT, width=1)
            if side in ("north", "south"):
                cy_ = desk[1] + desk[3] + 0.2 if side == "north" else desk[1] - 0.2 - 1.25
                crect = _ft_rect(room, x + (w - 1.25) / 2, cy_, 1.25, 1.25)
            else:
                cx_ = desk[0] + desk[2] + 0.2 if side == "west" else desk[0] - 0.2 - 1.25
                crect = _ft_rect(room, cx_, y + (d - 1.25) / 2, 1.25, 1.25)
            if _free(zl, crect):
                draw.rectangle(crect, fill=FURN, outline=FAINT, width=1)
            break


    def _furn_kitchen(room, zl, plan_ref):
        x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
        cdep = 2.0
        if w < 4.0 or d < 4.0:
            return

        def wall_busy(side):
            (ax, ay), (bx, by), length = _side_geom(room, side)
            for p0, p1 in abs_openings:
                s = _proj(p0, ax, ay, bx, by, length)
                e = _proj(p1, ax, ay, bx, by, length)
                if s is not None and e is not None:
                    return True
            return False

        def crect(side, skip=None):
            if side == "north":
                return (x + 0.15, y + 0.15, w - 0.3, cdep)
            if side == "south":
                return (x + 0.15, y + d - 0.15 - cdep, w - 0.3, cdep)
            y0 = y + 0.15 + (cdep if skip == "north" else 0.0)
            y1 = y + d - 0.15 - (cdep if skip == "south" else 0.0)
            if side == "west":
                return (x + 0.15, y0, cdep, max(0.5, y1 - y0))
            return (x + w - 0.15 - cdep, y0, cdep, max(0.5, y1 - y0))

        counters = []
        for a, b in (("north", "west"), ("north", "east"), ("south", "west"), ("south", "east")):
            if wall_busy(a) or wall_busy(b):
                continue
            ra, rb = crect(a), crect(b, skip=a)
            if not _free(zl, _ft_rect(room, *ra)):
                continue
            counters.append((a, ra))
            if _free(zl, _ft_rect(room, *rb)) and not _overlap(_ft_rect(room, *ra), _ft_rect(room, *rb)):
                counters.append((b, rb))
            break
        if not counters:
            for s in ("north", "south", "west", "east"):
                if wall_busy(s):
                    continue
                rs = crect(s)
                if _free(zl, _ft_rect(room, *rs)):
                    counters.append((s, rs))
                    break
        if not counters:
            return
        for side, rr in counters:
            rrect = _ft_rect(room, *rr)
            draw.rectangle(rrect, fill="#efe9db", outline=FAINT, width=2)
            horiz_c = side in ("north", "south")
            run_len = rr[2] if horiz_c else rr[3]
            for i in range(1, int(run_len // 2) + 1):
                if horiz_c:
                    xx = rrect[0] + i * 2 * scale
                    if xx < rrect[2] - 2:
                        draw.line((xx, rrect[1] + 2, xx, rrect[3] - 2), fill=FAINT, width=1)
                else:
                    yy = rrect[1] + i * 2 * scale
                    if yy < rrect[3] - 2:
                        draw.line((rrect[0] + 2, yy, rrect[2] - 2, yy), fill=FAINT, width=1)


        side0, r0 = counters[0]
        rect0 = _ft_rect(room, *r0)
        if side0 in ("north", "south"):
            sw, sd = 2.1, 1.4
            sx = rect0[0] + (rect0[2] - rect0[0] - sw * scale) / 2
            sy = rect0[1] + 3 if side0 == "north" else rect0[3] - 3 - sd * scale
        else:
            sw, sd = 1.4, 2.1
            sy = rect0[1] + (rect0[3] - rect0[1] - sd * scale) / 2
            sx = rect0[0] + 3 if side0 == "west" else rect0[2] - 3 - sw * scale
        sink = (sx, sy, sx + sw * scale, sy + sd * scale)
        draw.rectangle(sink, outline=FAINT, width=1)
        draw.ellipse((sink[0] + 3, sink[1] + 3, sink[2] - 3, sink[3] - 3), outline=FAINT, width=1)
        if side0 == "north":
            draw.line(((sink[0] + sink[2]) / 2, sink[1], (sink[0] + sink[2]) / 2, sink[1] - 4), fill=FAINT, width=2)
        elif side0 == "south":
            draw.line(((sink[0] + sink[2]) / 2, sink[3], (sink[0] + sink[2]) / 2, sink[3] + 4), fill=FAINT, width=2)
        side1, r1 = counters[1] if len(counters) > 1 else counters[0]
        rect1 = _ft_rect(room, *r1)
        horiz1 = side1 in ("north", "south")
        cw_, cd_ = (2.0, 1.8) if horiz1 else (1.8, 2.0)
        if (rect1[2] - rect1[0]) >= cw_ * scale + 6 and (rect1[3] - rect1[1]) >= cd_ * scale + 6:
            if horiz1:
                cx_ = rect1[2] - 6 - cw_ * scale if len(counters) > 1 else rect1[0] + 6
                cy_ = rect1[1] + 3 if side1 == "north" else rect1[3] - 3 - cd_ * scale
            else:
                cy_ = rect1[3] - 6 - cd_ * scale if len(counters) > 1 else rect1[1] + 6
                cx_ = rect1[0] + 3 if side1 == "west" else rect1[2] - 3 - cw_ * scale
            cook = (cx_, cy_, cx_ + cw_ * scale, cy_ + cd_ * scale)
            if not _overlap(cook, sink):
                draw.rectangle(cook, outline=FAINT, width=1)
                for fx in (0.3, 0.7):
                    for fy in (0.35, 0.75):
                        bx_ = cook[0] + (cook[2] - cook[0]) * fx
                        by_ = cook[1] + (cook[3] - cook[1]) * fy
                        draw.ellipse((bx_ - 3.5, by_ - 3.5, bx_ + 3.5, by_ + 3.5), outline=FAINT, width=1)
        fs = 2.5
        for sx, sy in ((x + w - 0.25 - fs, y + d - 0.25 - fs), (x + 0.25, y + d - 0.25 - fs),
                       (x + w - 0.25 - fs, y + 0.25), (x + 0.25, y + 0.25)):
            frect = _ft_rect(room, sx, sy, fs, fs)
            if _free(zl, frect) and not any(_overlap(frect, _ft_rect(room, *rr)) for _, rr in counters):
                draw.rectangle(frect, fill="#f4f2ec", outline=FAINT, width=2)
                if sx > x + w / 2:
                    draw.line((frect[2] - 4, frect[1] + 5, frect[2] - 4, frect[1] + fs * scale - 5), fill=FAINT, width=1)
                else:
                    draw.line((frect[0] + 4, frect[1] + 5, frect[0] + 4, frect[1] + fs * scale - 5), fill=FAINT, width=1)
                break


    def _furn_bath(room, zl, plan_ref):
        x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
        s = 2.8 if min(w, d) >= 5.0 else 2.4
        zcs = [((z[0] + z[2]) / 2, (z[1] + z[3]) / 2) for z in zl]
        best = bestd = None
        for i, (sx, sy) in enumerate(((x + 0.2, y + 0.2), (x + w - 0.2 - s, y + 0.2),
                                      (x + 0.2, y + d - 0.2 - s), (x + w - 0.2 - s, y + d - 0.2 - s))):
            if sx + s > x + w - 0.05 or sy + s > y + d - 0.05:
                continue
            rect = _ft_rect(room, sx, sy, s, s)
            if not _free(zl, rect):
                continue
            dist = min((abs(ox + (sx + s / 2) * scale - zx) + abs(oy + (sy + s / 2) * scale - zy)
                        for zx, zy in zcs), default=-i)
            if bestd is None or dist > bestd:
                best, bestd = rect, dist
        if best:
            draw.rectangle(best, fill="#d3e2e8", outline=FAINT, width=2)
            draw.line((best[0] + 2, best[1] + 2, best[2] - 2, best[3] - 2), fill=FAINT, width=1)
            draw.line((best[2] - 2, best[1] + 2, best[0] + 2, best[3] - 2), fill=FAINT, width=1)
            mx, my = (best[0] + best[2]) / 2, (best[1] + best[3]) / 2
            draw.ellipse((mx - 2, my - 2, mx + 2, my + 2), fill=FAINT)
        if w >= 3.2 and d >= 3.4:
            for wside in ("south", "north"):
                wx = x + w - 0.25 - 1.5
                wy = y + 0.2 if wside == "north" else y + d - 0.2 - 2.2
                wrect = _ft_rect(room, wx, wy, 1.5, 2.2)
                if _free(zl, wrect) and not (best and _overlap(wrect, best)):
                    if wside == "north":
                        draw.rectangle((wrect[0] + 2, wrect[1], wrect[2] - 2, wrect[1] + 8), fill=FURN, outline=FAINT, width=1)
                        draw.ellipse((wrect[0] + 3, wrect[1] + 9, wrect[2] - 3, wrect[3] - 3), fill="#f4f0e5", outline=FAINT, width=1)
                    else:
                        draw.rectangle((wrect[0] + 2, wrect[3] - 8, wrect[2] - 2, wrect[3]), fill=FURN, outline=FAINT, width=1)
                        draw.ellipse((wrect[0] + 3, wrect[1] + 3, wrect[2] - 3, wrect[3] - 9), fill="#f4f0e5", outline=FAINT, width=1)
                    break
        if d >= 3.0 and w >= 3.4:
            for bside in ("west", "east"):
                bx_ = x + 0.2 if bside == "west" else x + w - 0.2 - 1.5
                brect = _ft_rect(room, bx_, y + d - 0.2 - 1.6, 1.5, 1.6)
                if _free(zl, brect) and not (best and _overlap(brect, best)):
                    draw.rectangle(brect, fill=FURN, outline=FAINT, width=1)
                    draw.ellipse((brect[0] + 3, brect[1] + 3, brect[2] - 3, brect[3] - 5), fill="#f4f0e5", outline=FAINT, width=1)
                    break


    def _furn_puja(room, zl, plan_ref):
        x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]

        def wall_mid(side):
            (ax, ay), (bx, by), length = _side_geom(room, side)
            return ox + (ax + bx) / 2 * scale, oy + (ay + by) / 2 * scale

        zcs = [((z[0] + z[2]) / 2, (z[1] + z[3]) / 2) for z in zl]
        if zcs:
            side = max(("north", "south", "west", "east"),
                       key=lambda sd: min(abs(wall_mid(sd)[0] - zx) + abs(wall_mid(sd)[1] - zy) for zx, zy in zcs))
        else:
            side = "north"
        pdep = 1.3
        if side in ("north", "south"):
            run = min(w - 1.0, 3.2)
            if run < 1.6 or d < 2.6:
                return
            px_ = x + (w - run) / 2
            py_ = y + 0.25 if side == "north" else y + d - 0.25 - pdep
            prect = _ft_rect(room, px_, py_, run, pdep)
        else:
            run = min(d - 1.0, 3.2)
            if run < 1.6 or w < 2.6:
                return
            py_ = y + (d - run) / 2
            px_ = x + 0.25 if side == "west" else x + w - 0.25 - pdep
            prect = _ft_rect(room, px_, py_, pdep, run)
        if not _free(zl, prect):
            return
        draw.rectangle(prect, fill=WOOD, outline=FAINT, width=2)
        if side in ("north", "south"):
            iy_ = prect[1] + 3 if side == "north" else prect[3] - 12
            ir = ((prect[0] + prect[2]) / 2 - 8, iy_, (prect[0] + prect[2]) / 2 + 8, iy_ + 9)
            dys = [(prect[0] + (prect[2] - prect[0]) * 0.2, (prect[1] + prect[3]) / 2),
                   (prect[0] + (prect[2] - prect[0]) * 0.8, (prect[1] + prect[3]) / 2)]
        else:
            ix_ = prect[0] + 3 if side == "west" else prect[2] - 12
            ir = (ix_, (prect[1] + prect[3]) / 2 - 8, ix_ + 9, (prect[1] + prect[3]) / 2 + 8)
            dys = [((prect[0] + prect[2]) / 2, prect[1] + (prect[3] - prect[1]) * 0.2),
                   ((prect[0] + prect[2]) / 2, prect[1] + (prect[3] - prect[1]) * 0.8)]
        draw.rectangle(ir, fill="#b59a72", outline=FAINT, width=1)
        for dx_, dy_ in dys:
            draw.ellipse((dx_ - 2.5, dy_ - 2.5, dx_ + 2.5, dy_ + 2.5), fill=DIYA)

    def _furn_stair(room, zl, plan_ref):
        x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
        st = next((s for s in plan_ref.get("stairs", []) if s.get("room_id") == room["id"]), None)
        n = max(3, int(st.get("riser_count", 14)) - 1) if st else 12
        if d >= w:
            y0, y1 = y + 0.35, y + d - 0.35
            for i in range(1, n):
                yy = oy + (y0 + (y1 - y0) * i / n) * scale
                draw.line((ox + (x + 0.25) * scale, yy, ox + (x + w - 0.25) * scale, yy), fill=FAINT, width=1)
            draw.line((ox + (x + 0.25) * scale, oy + y0 * scale, ox + (x + 0.25) * scale, oy + y1 * scale), fill=MID, width=2)
            draw.line((ox + (x + w - 0.25) * scale, oy + y0 * scale, ox + (x + w - 0.25) * scale, oy + y1 * scale), fill=MID, width=2)
            cx = ox + (x + w / 2) * scale
            door_off = next((dr["offset_ft"] for dr in plan_ref["doors"]
                             if dr["room_id"] == room["id"] and dr["side"] in ("east", "west")), None)
            if door_off is not None and door_off > d / 2:
                ay_, by_ = oy + (y1 - 0.25) * scale, oy + y0 * scale + 14
            else:
                ay_, by_ = oy + (y0 + 0.25) * scale, oy + y1 * scale - 14
            sgn = 1 if by_ > ay_ else -1
            draw.line((cx, ay_, cx, by_), fill=INK, width=2)
            draw.polygon([(cx, by_), (cx - 5, by_ - sgn * 9), (cx + 5, by_ - sgn * 9)], fill=INK)
            _halo1(draw, (cx + 14, (ay_ + by_) / 2), "UP", f_tag)
        else:
            x0, x1 = x + 0.35, x + w - 0.35
            for i in range(1, n):
                xx = ox + (x0 + (x1 - x0) * i / n) * scale
                draw.line((xx, oy + (y + 0.25) * scale, xx, oy + (y + d - 0.25) * scale), fill=FAINT, width=1)
            draw.line((ox + x0 * scale, oy + (y + 0.25) * scale, ox + x0 * scale, oy + (y + d - 0.25) * scale), fill=MID, width=2)
            draw.line((ox + x1 * scale, oy + (y + 0.25) * scale, ox + x1 * scale, oy + (y + d - 0.25) * scale), fill=MID, width=2)
            cy = oy + (y + d / 2) * scale
            door_off = next((dr["offset_ft"] for dr in plan_ref["doors"]
                             if dr["room_id"] == room["id"] and dr["side"] in ("north", "south")), None)
            if door_off is not None and door_off > w / 2:
                ax_, bx_ = ox + (x1 - 0.25) * scale, ox + x0 * scale + 14
            else:
                ax_, bx_ = ox + (x0 + 0.25) * scale, ox + x1 * scale - 14
            sgn = 1 if bx_ > ax_ else -1
            draw.line((ax_, cy, bx_, cy), fill=INK, width=2)
            draw.polygon([(bx_, cy), (bx_ - sgn * 9, cy - 5), (bx_ - sgn * 9, cy + 5)], fill=INK)
            _halo1(draw, ((ax_ + bx_) / 2, cy - 12), "UP", f_tag)


    def _furn_parking(room, zl, plan_ref):
        x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
        if room["y_ft"] == 0:
            nose = "north"
        elif room["y_ft"] + room["depth_ft"] == depth:
            nose = "south"
        elif room["x_ft"] == 0:
            nose = "west"
        else:
            nose = "east"
        cl, cw = 11.0, 5.5
        if nose in ("north", "south"):
            cl = min(cl, d - 1.4)
            cw = min(cw, w - 1.4)
            body = _ft_rect(room, x + (w - cw) / 2, y + (d - cl) / 2, cw, cl)
        else:
            cl = min(cl, w - 1.4)
            cw = min(cw, d - 1.4)
            body = _ft_rect(room, x + (w - cl) / 2, y + (d - cw) / 2, cl, cw)
        try:
            draw.rounded_rectangle(body, radius=9, fill="#f0efe9", outline=FAINT, width=2)
        except (AttributeError, TypeError):
            draw.rectangle(body, fill="#f0efe9", outline=FAINT, width=2)
        if nose in ("north", "south"):
            ch = (body[3] - body[1]) * 0.40
            if nose == "north":
                cab = (body[0] + 4, body[1] + 5, body[2] - 4, body[1] + 5 + ch)
            else:
                cab = (body[0] + 4, body[3] - 5 - ch, body[2] - 4, body[3] - 5)
            draw.rectangle(cab, fill="#d6dde2", outline=FAINT, width=1)
            for wy in (body[1] + (body[3] - body[1]) * 0.16, body[1] + (body[3] - body[1]) * 0.84):
                draw.rectangle((body[0] + 1, wy - 6, body[0] + 7, wy + 6), fill="#6a6660")
                draw.rectangle((body[2] - 7, wy - 6, body[2] - 1, wy + 6), fill="#6a6660")
            ny = body[1] + 2 if nose == "north" else body[3] - 2
            for hx in (body[0] + (body[2] - body[0]) * 0.3, body[0] + (body[2] - body[0]) * 0.7):
                draw.line((hx, ny, hx, ny + (3 if nose == "north" else -3)), fill=FAINT, width=2)
        else:
            cw2 = (body[2] - body[0]) * 0.40
            if nose == "west":
                cab = (body[0] + 5, body[1] + 4, body[0] + 5 + cw2, body[3] - 4)
            else:
                cab = (body[2] - 5 - cw2, body[1] + 4, body[2] - 5, body[3] - 4)
            draw.rectangle(cab, fill="#d6dde2", outline=FAINT, width=1)
            for wx in (body[0] + (body[2] - body[0]) * 0.16, body[0] + (body[2] - body[0]) * 0.84):
                draw.rectangle((wx - 6, body[1] + 1, wx + 6, body[1] + 7), fill="#6a6660")
                draw.rectangle((wx - 6, body[3] - 7, wx + 6, body[3] - 1), fill="#6a6660")
            nx = body[0] + 2 if nose == "west" else body[2] - 2
            for hy in (body[1] + (body[3] - body[1]) * 0.3, body[1] + (body[3] - body[1]) * 0.7):
                draw.line((nx, hy, nx + (3 if nose == "west" else -3), hy), fill=FAINT, width=2)

    def _role(room):
        k, n, i = room.get("kind", ""), room["name"].lower(), room["id"].lower()
        if k == "habitable":
            if "bed" in n or "bed" in i:
                return "bedroom"
            if "din" in n or "din" in i:
                return "dining"
            if "study" in n or "study" in i:
                return "study"
            return "living"
        return k

    dispatch = {"bedroom": _furn_bedroom, "living": _furn_living, "dining": _furn_dining,
                "study": _furn_study, "kitchen": _furn_kitchen, "bathroom": _furn_bath,
                "puja": _furn_puja, "staircase": _furn_stair, "parking": _furn_parking}
    for room in plan["rooms"]:
        fn = dispatch.get(_role(room))
        if fn:
            fn(room, zones.get(room["id"], []), plan)

    # ---------- room labels ----------
    for room in plan["rooms"]:
        x1, y1 = ox + room["x_ft"] * scale, oy + room["y_ft"] * scale
        x2, y2 = ox + (room["x_ft"] + room["width_ft"]) * scale, oy + (room["y_ft"] + room["depth_ft"]) * scale
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        if y2 - y1 < 42 or x2 - x1 < 56:
            _halo1(draw, (cx, cy), room["name"].upper(), f_tag)
            continue
        _halo1(draw, (cx, cy - 9), room["name"].upper(), f_room)
        _halo1(draw, (cx, cy + 11), f"{_fmt_ft(room['width_ft'])} \u00d7 {_fmt_ft(room['depth_ft'])}", f_small, fill=MID)


    # ---------- overall dimensions ----------
    dy = oy - 36
    draw.line((px1, dy, px2, dy), fill=INK, width=1)
    for xx in (px1, px2):
        draw.line((xx, oy - 8, xx, dy - 9), fill=INK, width=1)
        draw.line((xx - 5, dy + 5, xx + 5, dy - 5), fill=INK, width=2)
    _halo1(draw, ((px1 + px2) / 2, dy - 14), _fmt_ft(width), f_dim)

    dx = ox - 36
    draw.line((dx, py1, dx, py2), fill=INK, width=1)
    for yy in (py1, py2):
        draw.line((ox - 8, yy, dx - 9, yy), fill=INK, width=1)
        draw.line((dx - 5, yy + 5, dx + 5, yy - 5), fill=INK, width=2)
    bb = f_dim.getbbox(_fmt_ft(depth))
    _vtext(image, (int(dx - (bb[3] - bb[1]) - 22), int((py1 + py2) / 2 - (bb[2] - bb[0]) / 2 - 7)),
           _fmt_ft(depth), f_dim)

    # ---------- footer ----------
    fsep = py2 + 22
    draw.line((28, fsep, W - 28, fsep), fill=HATCH, width=1)
    fy = fsep + 14
    draw.arc((30, fy - 2, 62, fy + 26), 270, 360, fill=MID, width=2)
    draw.line((46, fy + 10, 46, fy + 26), fill=INK, width=3)
    draw.text((70, fy + 2), "DOOR SWING", fill=MID, font=f_tag)
    draw.line((185, fy + 5, 235, fy + 5), fill=INK, width=3)
    draw.line((185, fy + 11, 235, fy + 11), fill=MID, width=2)
    draw.line((185, fy + 17, 235, fy + 17), fill=INK, width=3)
    draw.text((245, fy + 2), "WINDOW", fill=MID, font=f_tag)
    draw.rectangle((330, fy + 4, 372, fy + 18), fill=FURN, outline=FAINT, width=1)
    draw.text((382, fy + 2), "FURNITURE", fill=MID, font=f_tag)
    ty = fy + 34
    strat = plan.get("layout_strategy")
    if strat:
        for line in textwrap.fill("STRATEGY: " + strat.upper(), 118).splitlines():
            draw.text((30, ty), line, fill=INK, font=f_tag)
            ty += 15
    for line in textwrap.fill(plan.get("disclaimer", ""), 128).splitlines():
        draw.text((30, ty), line, fill="#6b655c", font=f_small)
        ty += 14

    image.save(output_path, dpi=(150, 150))
    if geometry_path:
        Path(geometry_path).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
