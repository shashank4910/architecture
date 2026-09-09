from __future__ import annotations

import json
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

SKY_TOP = "#edf2f6"
SKY_BOT = "#f8f3e8"
GROUND = "#cfc9b8"
INK = "#3a332b"
MID = "#6b6558"
OUTLINE = "#4a4238"
PLINTH_TOP = "#efe9db"
PLINTH_SIDE = "#a89f8c"
WALL_TOP = "#f3ecdd"
WALL_LIT = "#e3d8c3"
WALL_SHADE = "#c8bca6"
WOOD = "#a5794c"
WOOD_D = "#7d5732"
SOFA = "#b3a68f"
MATTRESS = "#f5f2ea"
PILLOW = "#fcfbf7"
COUNTER = "#c9b493"
COUNTER_D = "#9c8767"
FRIDGE = "#eceae4"
CAR = "#c2564a"
CAR_GLASS = "#aebfc9"
SHADOW = "#b7af9d"
GLASS = "#b9d0de"
PLANT = "#7d9b6a"
PLANT_D = "#69875a"
FLOOR_FILL = {
    "habitable": "#d9bd92",
    "kitchen": "#e7decb",
    "bathroom": "#dde4e6",
    "puja": "#e9d2c6",
    "parking": "#cdd0d2",
    "staircase": "#d9bd92",
    "circulation": "#d9bd92",
}
WALL_H = 3.0
PAL_WALL = (WALL_TOP, WALL_LIT, WALL_SHADE)
PAL_WOOD = ("#c29a6b", WOOD, WOOD_D)
PAL_SOFT = ("#e9e2d2", "#cdc3ae", "#b3a88f")


def _font(size: int, bold: bool = False):
    for name in (["arialbd.ttf", "arial.ttf"] if bold else ["arial.ttf"]):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _quad(draw, pts, fill, outline=OUTLINE, width=1):
    draw.polygon(pts, fill=fill, outline=outline, width=width)


def _box(draw, iso, x, y, z, w, d, h, pal, outline=OUTLINE):
    top, right, left = pal
    _quad(draw, [iso(x + w, y, z), iso(x + w, y + d, z), iso(x + w, y + d, z + h), iso(x + w, y, z + h)], right)
    _quad(draw, [iso(x, y + d, z), iso(x + w, y + d, z), iso(x + w, y + d, z + h), iso(x, y + d, z + h)], left)
    _quad(draw, [iso(x, y, z + h), iso(x + w, y, z + h), iso(x + w, y + d, z + h), iso(x, y + d, z + h)], top)


def _shadow(draw, iso, x, y, w, d):
    draw.polygon(
        [iso(x + 0.45, y + 0.45, 0), iso(x + w + 0.45, y + 0.45, 0), iso(x + w + 0.45, y + d + 0.45, 0), iso(x + 0.45, y + d + 0.45, 0)],
        fill=SHADOW,
    )


def _leaf_ft(room, door):
    if door["side"] in {"north", "south"}:
        return round(min(2.5, room["width_ft"] - door["offset_ft"]), 2)
    return round(min(2.5, room["depth_ft"] - door["offset_ft"]), 2)


def _side_len(room, side):
    return room["width_ft"] if side in {"north", "south"} else room["depth_ft"]


def _side_openings(plan, room, side):
    spans = []
    for door in plan["doors"]:
        if door["room_id"] == room["id"] and door["side"] == side:
            spans.append(("door", door["offset_ft"], _leaf_ft(room, door)))
    for win in plan["windows"]:
        if win["room_id"] == room["id"] and win["side"] == side:
            width = min(win["width_ft"], _side_len(room, side) - win["offset_ft"])
            spans.append(("window", win["offset_ft"], width))
    return spans


def _wall_side(draw, iso, room, side, openings, exterior):
    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
    length = _side_len(room, side)
    t = 0.6 if exterior else 0.45
    pal = PAL_WALL
    cuts = sorted((o, o + ln) for _, o, ln in openings)
    segs = []
    cur = 0.0
    for a, b in cuts:
        if a - cur > 0.2:
            segs.append((cur, a))
        cur = max(cur, b)
    if length - cur > 0.2:
        segs.append((cur, length))

    def seg(a, b, z0=0.0, h=WALL_H):
        if b - a <= 0.05:
            return
        if side == "north":
            _box(draw, iso, x + a, y - t, z0, b - a, t, h, pal)
        elif side == "south":
            _box(draw, iso, x + a, y + d, z0, b - a, t, h, pal)
        elif side == "west":
            _box(draw, iso, x - t, y + a, z0, t, b - a, h, pal)
        else:
            _box(draw, iso, x + w, y + a, z0, t, b - a, h, pal)

    def plane(a, b, z0, z1, fill):
        if side == "north":
            pts = [iso(x + a, y, z0), iso(x + b, y, z0), iso(x + b, y, z1), iso(x + a, y, z1)]
        elif side == "south":
            pts = [iso(x + a, y + d, z0), iso(x + b, y + d, z0), iso(x + b, y + d, z1), iso(x + a, y + d, z1)]
        elif side == "west":
            pts = [iso(x, y + a, z0), iso(x, y + b, z0), iso(x, y + b, z1), iso(x, y + a, z1)]
        else:
            pts = [iso(x + w, y + a, z0), iso(x + w, y + b, z0), iso(x + w, y + b, z1), iso(x + w, y + a, z1)]
        _quad(draw, pts, fill)

    for a, b in segs:
        seg(a, b)
    for kind, o, ln in openings:
        a, b = o, o + ln
        if kind == "door":
            seg(a, b, z0=2.3, h=WALL_H - 2.3)
            plane(a, b, 0.0, 2.2, WOOD)
        else:
            seg(a, b, z0=0.0, h=1.0)
            seg(a, b, z0=2.4, h=WALL_H - 2.4)
            plane(a, b, 1.0, 2.4, GLASS)


def _bed3d(draw, iso, r, head):
    x, y, w, d = r
    _shadow(draw, iso, x, y, w, d)
    _box(draw, iso, x, y, 0, w, d, 0.8, (MATTRESS, "#e5e1d6", "#cfcabf"))
    if head in {"n", "s"}:
        hb_y = y - 0.18 if head == "n" else y + d - 0.18
        _box(draw, iso, x, hb_y, 0, w, 0.32, 1.8, PAL_WOOD)
        pw = (w - 1.0) / 2
        pz = y + 0.4 if head == "n" else y + d - 1.3
        _box(draw, iso, x + 0.3, pz, 0.8, pw, 0.9, 0.28, (PILLOW, "#eeeadf", "#d9d4c6"))
        _box(draw, iso, x + 0.7 + pw, pz, 0.8, pw, 0.9, 0.28, (PILLOW, "#eeeadf", "#d9d4c6"))
    else:
        hb_x = x - 0.18 if head == "w" else x + w - 0.18
        _box(draw, iso, hb_x, y, 0, 0.32, d, 1.8, PAL_WOOD)
        ph = (d - 1.0) / 2
        px_ = x + 0.4 if head == "w" else x + w - 1.3
        _box(draw, iso, px_, y + 0.3, 0.8, 0.9, ph, 0.28, (PILLOW, "#eeeadf", "#d9d4c6"))
        _box(draw, iso, px_, y + 0.7 + ph, 0.8, 0.9, ph, 0.28, (PILLOW, "#eeeadf", "#d9d4c6"))


def _sofa3d(draw, iso, r, back):
    x, y, w, d = r
    _shadow(draw, iso, x, y, w, d)
    _box(draw, iso, x, y, 0, w, d, 0.75, (SOFA, "#a3967d", "#8b8069"))
    if back in {"n", "s"}:
        by = y + 0.08 if back == "n" else y + d - 0.53
        _box(draw, iso, x + 0.1, by, 0.75, w - 0.2, 0.45, 0.95, (SOFA, "#a3967d", "#8b8069"))
    else:
        bx = x + 0.08 if back == "w" else x + w - 0.53
        _box(draw, iso, bx, y + 0.1, 0.75, 0.45, d - 0.2, 0.95, (SOFA, "#a3967d", "#8b8069"))


def _table3d(draw, iso, r, h=1.1):
    x, y, w, d = r
    _shadow(draw, iso, x, y, w, d)
    _box(draw, iso, x, y, 0, w, d, h, PAL_WOOD)


def _chair3d(draw, iso, cx, cy):
    _box(draw, iso, cx, cy, 0, 1.2, 1.2, 0.95, (SOFA, "#a3967d", "#8b8069"))


def _tv3d(draw, iso, r):
    x, y, w, d = r
    _box(draw, iso, x, y, 0, w, d, 0.7, PAL_SOFT)
    _box(draw, iso, x + 0.3, y + d / 2 - 0.12, 0.7, w - 0.6, 0.24, 0.75, ("#2f3438", "#22262a", "#181b1e"))


def _stair3d(draw, iso, room):
    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
    steps = 11
    pal = ("#e8e0cd", "#d5c9b0", "#bfb299")
    if d >= w:
        run = (d - 0.6) / steps
        for i in range(steps):
            _box(draw, iso, x + 0.3, y + 0.3 + i * run, 0, w - 0.6, run - 0.03, 0.22 + i * 0.24, pal)
    else:
        run = (w - 0.6) / steps
        for i in range(steps):
            _box(draw, iso, x + 0.3 + i * run, y + 0.3, 0, run - 0.03, d - 0.6, 0.22 + i * 0.24, pal)


def _car3d(draw, iso, room):
    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
    if d >= w:
        cw, ch = min(5.6, w - 2.2), min(12.5, d - 2.4)
        bx, by = x + (w - cw) / 2, y + (d - ch) / 2
    else:
        cw, ch = min(12.5, w - 2.4), min(5.6, d - 2.2)
        bx, by = x + (w - cw) / 2, y + (d - ch) / 2
    _shadow(draw, iso, bx, by, cw, ch)
    _box(draw, iso, bx, by, 0.25, cw, ch, 0.85, (CAR, "#a5453b", "#8c3a32"))
    if d >= w:
        _box(draw, iso, bx + 0.5, by + ch * 0.32, 1.1, cw - 1.0, ch * 0.4, 0.7, (CAR_GLASS, "#93a6b1", "#7f929d"))
    else:
        _box(draw, iso, bx + cw * 0.32, by + 0.5, 1.1, cw * 0.4, ch - 1.0, 0.7, (CAR_GLASS, "#93a6b1", "#7f929d"))
    r = max(3, int(min(cw, ch) / 5))
    for wx, wy in ((bx + 0.4, by + 0.8), (bx + cw - 1.3, by + 0.8), (bx + 0.4, by + ch - 1.9), (bx + cw - 1.3, by + ch - 1.9)):
        c = iso(wx + 0.45, wy + 0.45, 0.02)
        draw.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), fill="#2c2c2e")


def _puja3d(draw, iso, room):
    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
    _box(draw, iso, x + 0.35, y + 0.25, 0, w - 0.7, min(1.7, d - 0.6), 0.55, ("#efe3da", "#dcc9b8", "#c4ac97"))
    _box(draw, iso, x + w / 2 - 0.5, y + 0.55, 0.55, 1.0, 0.85, 0.9, ("#e0c9b8", "#c8a892", "#ab8a72"))


def _kitchen3d(draw, iso, room, plan):
    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]

    def spans(length, side):
        ops = sorted((o, o + ln) for k, o, ln in _side_openings(plan, room, side) if k == "door")
        res, cur = [], 0.0
        for a, b in ops:
            if a - cur > 2.0:
                res.append((cur, a))
            cur = max(cur, b)
        if length - cur > 2.0:
            res.append((cur, length))
        return res

    cd = 2.0
    pal = (COUNTER, "#b49e7c", COUNTER_D)
    for a, b in spans(w, "north"):
        _box(draw, iso, x + a, y, 0, b - a, cd, 1.05, pal)
    for a, b in spans(w, "south"):
        _box(draw, iso, x + a, y + d - cd, 0, b - a, cd, 1.05, pal)
    for a, b in spans(d, "west"):
        if b - a > 4.5:
            _box(draw, iso, x, y + a, 0, cd, b - a - 2.7, 1.05, pal)
            _box(draw, iso, x + 0.1, y + b - 2.6, 0, 2.3, 2.3, 2.3, (FRIDGE, "#dcdad4", "#c2c0ba"))
        else:
            _box(draw, iso, x, y + a, 0, cd, b - a, 1.05, pal)
    for a, b in spans(d, "east"):
        _box(draw, iso, x + w - cd, y + a, 0, cd, b - a, 1.05, pal)
    ns = spans(w, "north")
    if ns:
        a, b = max(ns, key=lambda t: t[1] - t[0])
        cx0 = x + (a + b) / 2 - 1.0
        _box(draw, iso, cx0, y + 0.45, 1.05, 2.0, 1.1, 0.06, ("#3c3630", "#2e2a25", "#211e1a"))
        for dx in (0.5, 1.5):
            for dy in (0.35, 0.85):
                c = iso(cx0 + dx, y + 0.45 + dy, 1.13)
                draw.ellipse((c[0] - 3, c[1] - 3, c[0] + 3, c[1] + 3), fill="#6b655c")
        if len(ns) > 1:
            a2, b2 = ns[1]
            _box(draw, iso, x + (a2 + b2) / 2 - 0.9, y + 0.4, 1.05, 1.8, 1.2, 0.12, ("#c6cdd1", "#a9b2b7", "#8f989d"))


def _bath3d(draw, iso, room):
    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
    if w >= 5.0 and d >= 4.5:
        _box(draw, iso, x + 0.2, y + 0.2, 0, 2.6, 2.6, 0.12, ("#dfe6e8", "#c9d2d4", "#b4bec1"))
        _box(draw, iso, x + 0.25, y + 2.75, 0, 2.5, 0.12, 2.0, (GLASS, "#9db6c4", "#8aa3b1"))
    _box(draw, iso, x + w / 2 - 0.8, y + d - 0.75, 0, 1.6, 0.55, 1.0, ("#f6f6f4", "#e2e2df", "#cfcfcb"))
    c = iso(x + w / 2, y + d - 1.7, 0.03)
    rr = max(5, int(min(w, d) * 1.6))
    draw.ellipse((c[0] - rr, c[1] - int(rr * 1.3), c[0] + rr, c[1] + int(rr * 1.3)), outline="#b9bcc0", width=2)
    _box(draw, iso, x + w - 1.75, y + d / 2 - 0.8, 0, 1.5, 1.6, 0.95, ("#f6f6f4", "#e2e2df", "#cfcfcb"))
    c2 = iso(x + w - 1.0, y + d / 2, 0.97)
    draw.ellipse((c2[0] - 8, c2[1] - 8, c2[0] + 8, c2[1] + 8), outline="#9aa4a9", width=2)


def _door_zone3d(room, door):
    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
    side, off, leaf = door["side"], door["offset_ft"], _leaf_ft(room, door)
    if side == "north":
        return (x + off, y, leaf, leaf)
    if side == "south":
        return (x + off, y + d - leaf, leaf, leaf)
    if side == "west":
        return (x, y + off, leaf, leaf)
    return (x + w - leaf, y + off, leaf, leaf)


def _hits(r, zones):
    return any(not (r[0] + r[2] <= z[0] or z[0] + z[2] <= r[0] or r[1] + r[3] <= z[1] or z[1] + z[3] <= r[1]) for z in zones)


def _furnish3d(draw, iso, room, plan):
    kind = room.get("kind")
    rid = room["id"]
    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
    if kind == "habitable":
        zones = [_door_zone3d(room, dr) for dr in plan["doors"] if dr["room_id"] == rid]
        if rid == "living":
            sc = []
            if w >= 8.5:
                sc += [(x + (w - 6.5) / 2, y + d - 3.0, 6.5, 2.6), (x + (w - 6.5) / 2, y + 0.4, 6.5, 2.6)]
            if d >= 8.5:
                sc += [(x + 0.4, y + (d - 6.5) / 2, 2.6, 6.5), (x + w - 3.0, y + (d - 6.5) / 2, 2.6, 6.5)]
            sofa = next((r for r in sc if not _hits(r, zones)), None)
            if sofa:
                back = "s" if abs(sofa[1] + sofa[3] - (y + d)) < 0.7 else "n" if abs(sofa[1] - y) < 0.7 else "w" if abs(sofa[0] - x) < 0.7 else "e"
                _sofa3d(draw, iso, sofa, back)
                horiz = back in {"n", "s"}
                if horiz:
                    _table3d(draw, iso, (x + (w - 3.2) / 2, y + (d - 1.6) / 2, 3.2, 1.6), 0.8)
                    tv = (x + (w - 4.2) / 2, y + 0.3, 4.2, 1.1) if back == "s" else (x + (w - 4.2) / 2, y + d - 1.4, 4.2, 1.1)
                    if not _hits(tv, zones):
                        _tv3d(draw, iso, tv)
                else:
                    _table3d(draw, iso, (x + (w - 1.6) / 2, y + (d - 3.2) / 2, 1.6, 3.2), 0.8)
            else:
                _table3d(draw, iso, (x + w / 2 - 1.5, y + d / 2 - 1.0, 3.0, 2.0), 0.8)
        elif "dining" in rid:
            horiz = w >= d
            tw, td = (min(5.0, w - 3.4), min(2.8, d - 2.6)) if horiz else (min(2.8, w - 2.6), min(5.0, d - 3.4))
            if tw >= 2.4 and td >= 2.2:
                table = (x + (w - tw) / 2, y + (d - td) / 2, tw, td)
                _table3d(draw, iso, table, 1.05)
                if horiz:
                    for fx in (0.28, 0.72):
                        _chair3d(draw, iso, x + (w - tw) * fx + tw * fx - 0.6, table[1] - 1.45)
                        _chair3d(draw, iso, x + (w - tw) * fx + tw * fx - 0.6, table[1] + table[3] + 0.25)
                else:
                    for fy in (0.28, 0.72):
                        _chair3d(draw, iso, table[0] - 1.45, y + (d - td) * fy + td * fy - 0.6)
                        _chair3d(draw, iso, table[0] + table[2] + 0.25, y + (d - td) * fy + td * fy - 0.6)
        else:
            small = min(w, d) < 7.5
            bw, bl = (3.4, 6.4) if small else (5.0, 6.8)
            cands = []
            if w >= bw + 1.4:
                cands += [(x + (w - bw) / 2, y + 0.5, bw, bl), (x + (w - bw) / 2, y + d - bl - 0.5, bw, bl)]
            if d >= bw + 1.4:
                cands += [(x + 0.5, y + (d - bw) / 2, bl, bw), (x + w - bl - 0.5, y + (d - bw) / 2, bl, bw)]
            bed = next((r for r in cands if not _hits(r, zones)), None)
            if bed:
                head = "n" if abs(bed[1] - y) < 0.7 else "s" if abs(bed[1] + bed[3] - (y + d)) < 0.7 else "w" if abs(bed[0] - x) < 0.7 else "e"
                _bed3d(draw, iso, bed, head)
                if not small:
                    if head in {"n", "s"}:
                        hy = bed[1] + 0.2 if head == "n" else bed[1] + bed[3] - 1.5
                        spots = [(bed[0] - 1.6, hy, 1.3, 1.3), (bed[0] + bed[2] + 0.3, hy, 1.3, 1.3)]
                        ok = lambda s: x <= s[0] and s[0] + s[2] <= x + w and not _hits(s, zones)
                    else:
                        hx = bed[0] + 0.2 if head == "w" else bed[0] + bed[2] - 1.5
                        spots = [(hx, bed[1] - 1.6, 1.3, 1.3), (hx, bed[1] + bed[3] + 0.3, 1.3, 1.3)]
                        ok = lambda s: y <= s[1] and s[1] + s[3] <= y + d and not _hits(s, zones)
                    for s in spots:
                        if ok(s):
                            _box(draw, iso, s[0], s[1], 0, 1.3, 1.3, 1.3, PAL_WOOD)
    elif kind == "kitchen":
        _kitchen3d(draw, iso, room, plan)
    elif kind == "bathroom":
        _bath3d(draw, iso, room)
    elif kind == "staircase":
        _stair3d(draw, iso, room)
    elif kind == "parking":
        _car3d(draw, iso, room)
    elif kind == "puja":
        _puja3d(draw, iso, room)


def _blend(c1, c2, t):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _tree(draw, iso, tx, ty):
    base = iso(tx, ty, 0)
    draw.ellipse((base[0] - 16, base[1] - 8, base[0] + 16, base[1] + 8), fill=SHADOW)
    top = iso(tx, ty, 2.6)
    draw.line((base[0], base[1], top[0], top[1]), fill="#7a5b3a", width=4)
    draw.ellipse((top[0] - 22, top[1] - 26, top[0] + 22, top[1] + 18), fill=PLANT)
    draw.ellipse((top[0] - 30, top[1] - 10, top[0] + 6, top[1] + 26), fill=PLANT_D)
    draw.ellipse((top[0] - 6, top[1] - 32, top[0] + 30, top[1] + 6), fill=PLANT)


def render_3d_legacy(plan, output_path, geometry_path=None):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    width, depth = plan["plot"]["width_ft"], plan["plot"]["depth_ft"]
    scale = max(10, min(20, 800 // max(width, depth)))
    sx, sy, sz = scale, scale // 2, 16
    image = Image.new("RGB", (1500, 950), SKY_TOP)
    draw = ImageDraw.Draw(image)
    for row in range(0, 470):
        draw.line((0, row, 1500, row), fill=_blend(SKY_TOP, SKY_BOT, row / 470))
    draw.rectangle((0, 470, 1500, 950), fill=GROUND)

    def raw_iso(x, y, z=0):
        return ((x - y) * sx, (x + y) * sy - z * sz)

    bounds = [raw_iso(x, y, z) for x, y in ((0, 0), (width, 0), (width, depth), (0, depth)) for z in (0, WALL_H)]
    min_x, min_y = min(p[0] for p in bounds), min(p[1] for p in bounds)
    max_x = max(p[0] for p in bounds)
    origin = (750 - (min_x + max_x) / 2, 540 - min_y)

    def iso(x, y, z=0):
        rx, ry = raw_iso(x, y, z)
        return (origin[0] + rx, origin[1] + ry)

    _box(draw, iso, -0.35, -0.35, -1.1, width + 0.7, depth + 0.7, 1.1, (PLINTH_TOP, PLINTH_SIDE, PLINTH_SIDE))
    for room in plan["rooms"]:
        x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
        pts = [iso(x, y, 0.02), iso(x + w, y, 0.02), iso(x + w, y + d, 0.02), iso(x, y + d, 0.02)]
        draw.polygon(pts, fill=FLOOR_FILL.get(room.get("kind"), "#d9bd92"), outline="#8f8672")
    manifest = {"plot": dict(plan["plot"]), "rooms": [{k: r[k] for k in ("id", "x_ft", "y_ft", "width_ft", "depth_ft")} for r in plan["rooms"]]}
    for room in sorted(plan["rooms"], key=lambda r: r["x_ft"] + r["y_ft"]):
        x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
        ext = {"north": y == 0, "south": y + d == depth, "west": x == 0, "east": x + w == width}
        for side in ("north", "west"):
            _wall_side(draw, iso, room, side, _side_openings(plan, room, side), ext[side])
        _furnish3d(draw, iso, room, plan)
        for side in ("south", "east"):
            _wall_side(draw, iso, room, side, _side_openings(plan, room, side), ext[side])
        c = iso(x + w / 2, y + d / 2, 0.15)
        draw.text(c, room["name"], anchor="mm", fill=INK, font=_font(12, True))
    if (width + depth) * sx < 1260:
        _tree(draw, iso, -2.6, -2.4)
        _tree(draw, iso, width + 2.4, -2.8)
    draw.text((28, 22), f"{plan['design_id']}  |  ISOMETRIC VIEW", fill=INK, font=_font(22, True))
    draw.text((28, 52), "deterministic cutaway generated from the canonical JSON", fill=MID, font=_font(12))
    draw.line((28, 78, 1472, 78), fill="#b9b19f", width=1)
    draw.multiline_text((28, 888), textwrap.fill(plan.get("disclaimer", ""), 150), fill=MID, font=_font(11), spacing=2)
    image.save(output_path)
    if geometry_path:
        Path(geometry_path).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest




