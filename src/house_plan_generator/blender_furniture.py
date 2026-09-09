"""Procedural furniture assets. Every asset is real 3D geometry with
sub-part detail (cushions, arms, legs, backs) — no flat rectangles.

CONVENTION: the whole Blender scene is built in FEET (1 unit = 1 ft).
Lighting is scale-independent (sun + world), so no unit conversion anywhere.

All positions are world feet from the canonical plan. `ang` rotates the asset
around its anchor (radians; axis-aligned multiples of pi/2 only).
"""

import math

from .blender_geom import box, cyl, sph, rot_pt


def _bbox(name, mat, x, y, z, ang, ox, oy, sx, sy, sz):
    """Axis-aligned box anchored at (x,y,z), offset (ox,oy) rotated by ang.
    Sizes swap for quarter-turn rotations."""
    dx, dy = rot_pt(ox, oy, ang)
    if abs(math.sin(ang)) > 0.5:
        sx, sy = sy, sx
    return box(name, x + dx, y + dy, z, sx, sy, sz, mat)


def _cylA(name, mat, x, y, z, ang, ox, oy, r, depth, verts=16, axis="z"):
    dx, dy = rot_pt(ox, oy, ang)
    rx = math.pi / 2 if axis == "y" else 0.0
    ry = math.pi / 2 if axis == "x" else 0.0
    return cyl(name, x + dx, y + dy, z, r, depth, mat, verts=verts,
               rot_x=rx, rot_y=ry)


# ---------------------------------------------------------------- sofa ----

def sofa(M, x, y, w, d, ang=0.0):
    """Sofa: base, back, two arms, seat + back cushions, pillow, feet."""
    _bbox("SofaBase", M["fabric_sofa"], x, y, 0.30, ang, 0, 0, w, d, 0.55)
    # back on local -y side
    _bbox("SofaBack", M["fabric_sofa"], x, y, 0.78, ang, 0, -d / 2 + 0.25,
          w, 0.5, 1.5)
    for sgn in (-1, 1):
        _bbox(f"SofaArm{sgn}", M["fabric_sofa"], x, y, 0.75, ang,
              sgn * (w / 2 - 0.21), 0, 0.42, d, 1.0)
    cw = (w - 1.0) / 2
    for sgn, off in ((-1, -(cw / 2 + 0.05)), (1, cw / 2 + 0.05)):
        _bbox(f"SofaSeat{sgn}", M["fabric_cush"], x, y, 0.62, ang, off, 0.15,
              cw - 0.06, d - 1.35, 0.36)
        _bbox(f"SofaBCush{sgn}", M["fabric_cush"], x, y, 1.42, ang, off,
              -d / 2 + 0.72, cw - 0.14, 0.45, 1.1)
    _bbox("SofaPillow", M["fabric_bed"], x, y, 1.34, ang,
          -(w / 2 - 0.95), -d / 2 + 0.85, 0.85, 0.34, 0.85)
    for sx in (-1, 1):
        for sy in (-1, 1):
            _cylA("SofaFoot", M["table_wood"], x, y, 0.09, ang,
                  sx * (w / 2 - 0.3), sy * (d / 2 - 0.3), 0.10, 0.18, verts=10)


def armchair(M, x, y, s=2.6, ang=0.0):
    _bbox("ArmBase", M["fabric_sofa"], x, y, 0.32, ang, 0, 0, s, s, 0.6)
    _bbox("ArmBack", M["fabric_sofa"], x, y, 0.82, ang, 0, -s / 2 + 0.24,
          s, 0.48, 1.2)
    for sgn in (-1, 1):
        _bbox(f"ArmSide{sgn}", M["fabric_sofa"], x, y, 0.74, ang,
              sgn * (s / 2 - 0.21), 0, 0.42, s, 1.0)
    _bbox("ArmCush", M["fabric_cush"], x, y, 0.68, ang, 0, 0.12,
          s - 1.0, s - 1.25, 0.32)


def coffee_table(M, x, y, w, d):
    box("CofTop", x, y, 1.32, w, d, 0.14, M["table_wood"])
    box("CofShelf", x, y, 0.58, w * 0.85, d * 0.85, 0.08, M["table_wood"])
    for sx in (-1, 1):
        for sy in (-1, 1):
            cyl("CofLeg", x + sx * (w / 2 - 0.2), y + sy * (d / 2 - 0.2), 0.63,
                0.07, 1.2, M["metal_dark"], verts=10)


def tv_console(M, x, y, w, d, ang=0.0):
    _bbox("TVBody", M["table_wood"], x, y, 1.05, ang, 0, 0, w, d, 1.7)
    _bbox("TVStand", M["metal_dark"], x, y, 2.05, ang, 0, -d / 2 + 0.15,
          1.3, 0.3, 0.3)
    _bbox("TVScreen", M["screen"], x, y, 3.4, ang, 0, -d / 2 + 0.05,
          w * 0.92, 0.14, 2.5)


def side_table(M, x, y):
    cyl("SideTop", x, y, 1.95, 0.7, 0.12, M["table_wood"], verts=20)
    cyl("SideLeg", x, y, 1.0, 0.09, 1.8, M["metal_dark"], verts=10)
    cyl("SideBase", x, y, 0.06, 0.42, 0.1, M["metal_dark"], verts=16)


def floor_lamp(M, x, y):
    cyl("LampBase", x, y, 0.05, 0.55, 0.1, M["metal_dark"], verts=16)
    cyl("LampPole", x, y, 2.6, 0.05, 5.0, M["metal_dark"], verts=8)
    cyl("LampShade", x, y, 5.5, 0.68, 1.0, M["fabric_cush"], verts=20)


def rug(M, x, y, w, d):
    box("Rug", x, y, 0.07, w, d, 0.05, M["rug"])


def plant(M, x, y, s=1.0):
    cyl("Pot", x, y, 0.85 * s, 0.75 * s, 1.7 * s, M["terracotta"], verts=18)
    cyl("Soil", x, y, 1.72 * s, 0.68 * s, 0.08, M["trunk"], verts=14)
    for i in range(7):
        a = i * math.pi * 2 / 7
        rr = 1.0 * s
        sph(f"LeafB{i}", x + math.cos(a) * rr, y + math.sin(a) * rr,
            (2.7 + (i % 3) * 0.55) * s, 0.65 * s, M["leaf"])
    sph("LeafTop", x, y, 3.5 * s, 0.85 * s, M["leaf"])


# ----------------------------------------------------------------- bed ----

def bed(M, x, y, w, d, ang=0.0):
    """Bed: frame, mattress, duvet, pillows, headboard (head at local -y)."""
    _bbox("BedFrame", M["table_wood"], x, y, 0.5, ang, 0, 0, w, d, 0.9)
    _bbox("BedMatt", M["mattress"], x, y, 1.2, ang, 0, 0.35, w - 0.35,
          d - 0.9, 0.8)
    _bbox("BedDuvet", M["fabric_bed"], x, y, 1.42, ang, 0, 1.05, w - 0.25,
          d * 0.55, 0.42)
    _bbox("BedHead", M["table_wood"], x, y, 2.5, ang, 0, -d / 2 + 0.14,
          w + 0.25, 0.3, 3.6)
    pw = (w - 1.3) / 2
    for sgn, off in ((-1, -(pw / 2 + 0.07)), (1, pw / 2 + 0.07)):
        _bbox(f"BedPil{sgn}", M["fabric_cush"], x, y, 1.78, ang, off,
              -d / 2 + 1.2, pw, 1.2, 0.4)
    if w >= 4.6:
        _bbox("BedBench", M["fabric_sofa"], x, y, 1.05, ang, 0, d / 2 - 0.6,
              w * 0.7, 1.0, 0.8)


def wardrobe(M, x, y, w, d, ang=0.0, h=7.0):
    _bbox("WardBody", M["cabinet"], x, y, h / 2, ang, 0, 0, w, d, h)
    n = max(2, int(w / 2.2))
    fw = w
    for i in range(1, n):
        t = -fw / 2 + i * (fw / n)
        _bbox(f"WardSeam{i}", M["metal_dark"], x, y, h / 2, ang, t, d / 2,
              0.04, 0.03, h - 0.3)
    for i in range(n):
        hx = -fw / 2 + (i + 0.5) * (fw / n)
        _bbox(f"WardHandle{i}", M["steel"], x, y, h * 0.52, ang, hx + 0.15,
              d / 2 + 0.04, 0.07, 0.08, 0.9)


def dresser(M, x, y, w, d, ang=0.0):
    _bbox("DressBody", M["cabinet"], x, y, 1.6, ang, 0, 0, w, d, 3.2)
    _bbox("DressTop", M["counter"], x, y, 3.26, ang, 0, 0, w + 0.12, d + 0.12,
          0.12)


# -------------------------------------------------------------- dining ----

def chair(M, x, y, ang=0.0, idx=0):
    """Dining chair: seat, 4 legs, backrest on local -y side."""
    box(f"ChSeat{idx}", x, y, 1.52, 1.55, 1.55, 0.16, M["table_wood"])
    for sx in (-1, 1):
        for sy in (-1, 1):
            box(f"ChLeg{idx}", x + sx * 0.6, y + sy * 0.6, 0.74, 0.12, 0.12,
                1.46, M["table_wood"])
    dx, dy = rot_pt(0, -0.68, ang)
    bx, by = x + dx, y + dy
    if abs(math.cos(ang)) > 0.5:
        box(f"ChBack{idx}", bx, by, 2.4, 1.5, 0.14, 1.7, M["table_wood"])
    else:
        box(f"ChBack{idx}", bx, by, 2.4, 0.14, 1.5, 1.7, M["table_wood"])


def dining_set(M, x, y, w, d):
    """Table with 4-6 chairs around it."""
    tw, td = min(w - 2.2, 5.4), min(d - 2.0, 3.0)
    if w < d:
        tw, td = td, tw
    box("DinTop", x, y, 2.52, tw, td, 0.16, M["table_wood"])
    box("DinApron", x, y, 2.26, tw - 0.5, td - 0.4, 0.2, M["table_wood"])
    for sx in (-1, 1):
        for sy in (-1, 1):
            box("DinLeg", x + sx * (tw / 2 - 0.25), y + sy * (td / 2 - 0.25),
                1.2, 0.2, 0.2, 2.4, M["table_wood"])
    if tw >= td:
        seats = [(-tw / 4, -td / 2 - 1.25, 0.0), (tw / 4, -td / 2 - 1.25, 0.0),
                 (-tw / 4, td / 2 + 1.25, math.pi), (tw / 4, td / 2 + 1.25, math.pi)]
        if w > tw + 3.2:
            seats += [(-tw / 2 - 1.25, 0.0, math.pi / 2),
                      (tw / 2 + 1.25, 0.0, -math.pi / 2)]
    else:
        seats = [(-td / 4, -tw / 2 - 1.25, 0.0), (td / 4, -tw / 2 - 1.25, 0.0),
                 (-td / 4, tw / 2 + 1.25, math.pi), (td / 4, tw / 2 + 1.25, math.pi)]
    for i, (ox, oy, a) in enumerate(seats):
        chair(M, x + ox, y + oy, a, i)


# ------------------------------------------------------------- kitchen ----

def kitchen_counters(M, room, zones):
    """Counter runs: toe-kick, cabinet, countertop, handles, backsplash."""
    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
    cd = 2.1
    for zi, (side, a, b) in enumerate(zones):
        L = b - a
        if L < 1.6:
            continue
        horiz = side in ("north", "south")
        if horiz:
            cx = x + (a + b) / 2
            cy = y + cd / 2 if side == "north" else y + d - cd / 2
        else:
            cy = y + (a + b) / 2
            cx = x + cd / 2 if side == "west" else x + w - cd / 2
        sx = L if horiz else cd
        sy = cd if horiz else L
        box(f"KitKick{zi}", cx, cy, 0.28, sx - 0.12, sy - 0.26, 0.56,
            M["metal_dark"])
        box(f"KitCab{zi}", cx, cy, 2.05, sx, sy, 3.0, M["cabinet"])
        box(f"KitTop{zi}", cx, cy, 3.62, sx + 0.08, sy + 0.08, 0.16,
            M["counter"])
        n = max(1, int(L / 2.4))
        for i in range(n):
            t = -L / 2 + (i + 0.5) * (L / n)
            if horiz:
                hy = cy + (sy / 2 + 0.04) * (1 if side == "north" else -1)
                box("KitHandle", cx + t, hy, 2.95, 0.8, 0.06, 0.09, M["steel"])
            else:
                hx = cx + (sx / 2 + 0.04) * (1 if side == "east" else -1)
                box("KitHandle", hx, cy + t, 2.95, 0.06, 0.8, 0.09, M["steel"])
        # backsplash against the wall
        if horiz:
            wy = y + (0.2 if side == "north" else d - 0.2)
            box(f"KitSplash{zi}", cx, wy, 4.9, L - 0.2, 0.16, 1.9,
                M["floor_kitchen"])
        else:
            wx = x + (0.2 if side == "west" else w - 0.2)
            box(f"KitSplash{zi}", wx, cy, 4.9, 0.16, L - 0.2, 1.9,
                M["floor_kitchen"])
    # upper cabinets over the longest run
    if zones:
        side, a, b = max(zones, key=lambda z: z[2] - z[1])
        L = b - a
        horiz = side in ("north", "south")
        if horiz:
            cx = x + (a + b) / 2
            cy = y + (cd * 0.5 if side == "north" else d - cd * 0.5)
            box("KitUpper", cx, cy, 7.6, L - 0.4, cd * 0.72, 2.6,
                M["cabinet_upper"])
        else:
            cx = x + (cd * 0.5 if side == "west" else w - cd * 0.5)
            cy = y + (a + b) / 2
            box("KitUpper", cx, cy, 7.6, cd * 0.72, L - 0.4, 2.6,
                M["cabinet_upper"])


def kitchen_sink(M, cx, cy):
    box("SinkRim", cx, cy, 3.72, 2.4, 1.6, 0.05, M["steel"])
    box("SinkBasin", cx, cy, 3.5, 2.1, 1.35, 0.4, M["steel"])
    cyl("SinkFaucet", cx, cy - 0.6, 4.35, 0.07, 1.3, M["steel"], verts=12)


def kitchen_hob(M, cx, cy):
    box("HobBase", cx, cy, 3.73, 2.6, 1.8, 0.04, M["metal_dark"])
    for dx in (-0.55, 0.55):
        for dy in (-0.32, 0.32):
            cyl("HobBurner", cx + dx, cy + dy, 3.77, 0.33, 0.03, M["metal_dark"],
                verts=16)


def fridge(M, x, y):
    """Fridge with body, freezer seam, handles; (x, y) = back-left corner."""
    bw, bd, bh = 2.8, 2.5, 6.0
    cx, cy = x + bw / 2, y + bd / 2
    box("FridgeBody", cx, cy, bh / 2 + 0.1, bw, bd, bh, M["steel"])
    box("FridgeSeam", cx, cy + bd / 2, bh * 0.62, bw - 0.1, 0.03, 0.06,
        M["metal_dark"])
    box("FridgeHandle", cx + bw / 2 - 0.3, cy + bd / 2 + 0.06, bh * 0.55,
        0.09, 0.09, 2.0, M["metal_dark"])


# ------------------------------------------------------------ bathroom ----

def bath_set(M, room):
    """WC, vanity + basin + mirror, shower tray + glass partition."""
    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
    vw = min(3.0, w - 1.6)
    vx, vy = x + w / 2, y + 0.95
    box("Vanity", vx, vy, 1.55, vw, 1.6, 3.0, M["cabinet"])
    box("VanityTop", vx, vy, 3.13, vw + 0.15, 1.7, 0.12, M["counter"])
    box("Basin", vx, vy + 0.05, 3.05, vw * 0.5, 1.15, 0.25, M["ceramic"])
    cyl("Faucet", vx, vy - 0.5, 3.75, 0.06, 1.0, M["steel"], verts=10)
    box("Mirror", vx, y + 0.12, 5.3, vw * 0.7, 0.06, 2.5, M["mirror"])
    wx, wy = x + w - 1.05, y + d - 1.05
    cyl("WCBowl", wx, wy, 1.0, 0.8, 1.2, M["porcelain"], verts=20)
    box("WCSeat", wx, wy, 1.72, 1.6, 1.5, 0.16, M["porcelain"])
    box("WCTank", wx, y + d - 0.45, 2.2, 1.5, 0.6, 2.3, M["porcelain"])
    s_w = min(2.6, w * 0.45)
    s_d = d - 1.2
    scx, scy = x + s_w / 2 + 0.1, y + d - s_d / 2 - 0.4
    box("ShowerTray", scx, scy, 0.1, s_w, s_d, 0.18, M["floor_bath"])
    box("ShowerGlass", x + s_w + 0.14, scy, 3.6, 0.08, s_d, 6.9, M["glass"])
    box("ShowerHead", scx, y + d - 0.6, 6.7, 0.6, 0.6, 0.1, M["steel"])
    box("TowelBar", x + w / 2, y + d - 0.1, 3.9, 1.6, 0.06, 0.06, M["steel"])


# ---------------------------------------------------------- staircase ----

def staircase(M, room, risers=14):
    """Steps with railing posts + sloped handrail."""
    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
    n = max(10, min(18, int(risers)))
    climb = 9.0
    rise = climb / n
    along_y = d >= w
    going = ((d - 0.8) if along_y else (w - 0.8)) / n
    sw = (w if along_y else d) - 0.5
    for i in range(n):
        z0 = i * rise
        if along_y:
            cx, cy = x + w / 2, y + 0.4 + (i + 0.5) * going
            box(f"StRiser{i}", cx, cy, z0 + rise / 2, sw, going, rise,
                M["stair_wood"])
            box(f"StTread{i}", cx, cy, z0 + rise, sw, going - 0.03, 0.06,
                M["stair_wood"])
        else:
            cx, cy = x + 0.4 + (i + 0.5) * going, y + d / 2
            box(f"StRiser{i}", cx, cy, z0 + rise / 2, going, sw, rise,
                M["stair_wood"])
            box(f"StTread{i}", cx, cy, z0 + rise, going - 0.03, sw, 0.06,
                M["stair_wood"])
    total = n * going
    if along_y:
        rx = x + w - 0.3
        for i in range(0, n + 1, 2):
            cyl("StPost", rx, y + 0.4 + i * going, i * rise + 1.5, 0.06, 3.0,
                M["metal_dark"], verts=8)
        seg = 8
        for i in range(seg):
            z0 = (i / seg) * climb
            z1 = ((i + 1) / seg) * climb
            ya = 0.4 + (i / seg) * total
            yb = 0.4 + ((i + 1) / seg) * total
            ln = math.hypot(yb - ya, z1 - z0)
            box("StRail", rx, y + (ya + yb) / 2, 3.0 + (z0 + z1) / 2, 0.16,
                ln + 0.06, 0.16, M["table_wood"])
    else:
        ry = y + d - 0.3
        for i in range(0, n + 1, 2):
            cyl("StPost", x + 0.4 + i * going, ry, i * rise + 1.5, 0.06, 3.0,
                M["metal_dark"], verts=8)
        seg = 8
        for i in range(seg):
            z0 = (i / seg) * climb
            z1 = ((i + 1) / seg) * climb
            xa = 0.4 + (i / seg) * total
            xb = 0.4 + ((i + 1) / seg) * total
            ln = math.hypot(xb - xa, z1 - z0)
            box("StRail", x + (xa + xb) / 2, ry, 3.0 + (z0 + z1) / 2,
                ln + 0.06, 0.16, 0.16, M["table_wood"])


# ----------------------------------------------------------------- car ----

def car(M, room):
    """Recognizable sedan: body, cabin, glass, wheels, lights, mirrors."""
    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
    horiz = w >= d
    bl = min(12.5, (w if horiz else d) - 1.4)   # length
    bw = min(5.6, (d if horiz else w) - 1.4)    # width
    cx, cy = x + w / 2, y + d / 2
    box("CarBody", cx, cy, 1.5, bl, bw, 1.55, M["car_paint"])
    box("CarSill", cx, cy, 0.65, bl * 0.94, bw * 0.94, 0.35, M["car_paint"])
    cab_l, cab_w = bl * 0.5, bw * 0.88
    box("CarCabin", cx, cy, 2.85, cab_l, cab_w, 1.3, M["car_paint"])
    if horiz:
        box("CarGlassF", cx + cab_l / 2 - 0.08, cy, 2.8, 0.14, cab_w * 0.84,
            1.05, M["car_glass"])
        box("CarGlassR", cx - cab_l / 2 + 0.08, cy, 2.8, 0.14, cab_w * 0.84,
            1.05, M["car_glass"])
        box("CarGlassL", cx - 0.2, cy - cab_w / 2, 2.9, cab_l * 0.78, 0.1,
            0.8, M["car_glass"])
        box("CarGlassRt", cx - 0.2, cy + cab_w / 2, 2.9, cab_l * 0.78, 0.1,
            0.8, M["car_glass"])
        for sy in (-1, 1):
            cyl("Wheel", cx + bl * 0.31, cy + sy * (bw / 2 - 0.02), 1.0, 1.0,
                0.6, M["tire"], verts=20, rot_y=math.pi / 2)
            box("Headlight", cx + bl / 2 - 0.05, cy + sy * bw * 0.28, 1.95,
                0.12, 0.8, 0.4, M["glass"])
            box("SideMirror", cx + cab_l / 4, cy + sy * (bw / 2 + 0.15), 2.9,
                0.3, 0.35, 0.15, M["car_paint"])
    else:
        box("CarGlassF", cx, cy + cab_l / 2 - 0.08, 2.8, cab_w * 0.84, 0.14,
            1.05, M["car_glass"])
        box("CarGlassR", cx, cy - cab_l / 2 + 0.08, 2.8, cab_w * 0.84, 0.14,
            1.05, M["car_glass"])
        box("CarGlassL", cx - cab_w / 2, cy - 0.2, 2.9, 0.1, cab_l * 0.78,
            0.8, M["car_glass"])
        box("CarGlassRt", cx + cab_w / 2, cy - 0.2, 2.9, 0.1, cab_l * 0.78,
            0.8, M["car_glass"])
        for sx in (-1, 1):
            cyl("Wheel", cx + sx * (bw / 2 - 0.02), cy + bl * 0.31, 1.0, 1.0,
                0.6, M["tire"], verts=20, rot_x=math.pi / 2)
            box("Headlight", cx + sx * bw * 0.28, cy + bl / 2 - 0.05, 1.95,
                0.8, 0.12, 0.4, M["glass"])
            box("SideMirror", cx + sx * (bw / 2 + 0.15), cy + cab_l / 4, 2.9,
                0.35, 0.3, 0.15, M["car_paint"])


# ---------------------------------------------------------------- puja ----

def puja_set(M, room):
    """Puja niche: platform, back panel, pedestal, idol, shelf."""
    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
    px, py = x + w / 2, y + 0.8
    pw = min(3.0, w - 0.8)
    box("PujaPlatform", px, py, 1.3, pw, 1.5, 2.6, M["puja_wood"])
    box("PujaBack", px, y + 0.14, 3.6, pw, 0.14, 4.6, M["puja_wood"])
    cyl("PujaPedestal", px, py, 2.95, 0.55, 0.7, M["ceramic"], verts=16)
    sph("PujaIdol", px, py, 3.75, 0.42, M["ceramic"])
    box("PujaShelf", px, y + 0.38, 5.2, min(2.4, w - 1.2), 0.8, 0.1,
        M["puja_wood"])
