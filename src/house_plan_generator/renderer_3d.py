from __future__ import annotations

"""Architectural 3D presentation renderer.

Deterministic Pillow-based axonometric visualization. The canonical plan JSON is
the only source of truth for geometry: every wall, room, staircase, parking area
and spatial boundary originates from the canonical rooms/doors/windows/stairs
data. This module only changes the *presentation* layer: materials, furniture
primitives, lighting, soft shadows, camera framing and exterior treatment.

Public contract is stable:

    manifest = render_3d(plan, output_path, geometry_path=None)

`manifest` contains canonical plot + room geometry so downstream geometry
matching tests keep guarding against presentation drift.
"""

import json
import math
import random
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SS = 2  # supersampling factor for anti-aliasing

# Architectural dimensions (feet).
# Cutaway strategy: camera-facing exterior walls are cut low (CUT_H) so the
# interior reads clearly; interior partitions sit at PART_H; far exterior
# walls keep full height (WALL_H) to frame the house.
WALL_H = 6.4      # full wall height for uncut (far) exterior walls
DOOR_H = 5.4      # standard door height (fits under WALL_H with lintel)
WIN_SILL = 2.9    # window sill height
WIN_HEAD = 5.0    # window head height
CUT_H = 3.2       # camera-facing exterior wall cut height
PART_H = 4.6      # interior partition height in cutaway

CAN_W, CAN_H = 2000, 1500  # output canvas dimensions


# ---------------------------------------------------------------------------
# color utilities
# ---------------------------------------------------------------------------

def _rgb(c):
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


def tint(c, k):
    """Lighten color c by factor k (0=unchanged, 1=white)."""
    r, g, b = _rgb(c)
    return "#%02x%02x%02x" % tuple(int(round(v + (255 - v) * k)) for v in (r, g, b))


def shade(c, k):
    """Darken color c by factor k (0=unchanged, 1=black)."""
    r, g, b = _rgb(c)
    return "#%02x%02x%02x" % tuple(int(round(v * (1 - k))) for v in (r, g, b))


def blend(a, b, t):
    """Linear blend between colors a and b."""
    ar, ag, ab = _rgb(a)
    br, bg, bb = _rgb(b)
    return "#%02x%02x%02x" % tuple(
        int(round(ar + (br - ar) * t)) for ar, br in ((ar, br), (ag, bg), (ab, bb))
    )


def with_alpha(c, a=255):
    r, g, b = _rgb(c)
    return (r, g, b, int(a))


# ---------------------------------------------------------------------------
# drawing layer
# ---------------------------------------------------------------------------

class Lay:
    """RGBA layer with fast gradient polygon fill and line drawing."""

    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        self.dr = ImageDraw.Draw(self.im)

    def quad(self, pts, c, alpha=255):
        if alpha <= 0:
            return
        pts = [(float(x), float(y)) for x, y in pts]
        self.dr.polygon(pts, fill=with_alpha(c, alpha))

    def grad_quad(self, pts, c_top, c_bot, alpha=255):
        """Fill a quad with a vertical gradient from c_top to c_bot."""
        if alpha <= 0:
            return
        pts = [(float(x), float(y)) for x, y in pts]
        ys = [p[1] for p in pts]
        y0, y1 = int(min(ys)), int(max(ys))
        y0 = max(0, y0)
        y1 = min(self.h - 1, y1)
        if y1 < y0:
            return
        span = max(1, y1 - y0)
        edges = [(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]
        top = _rgb(c_top)
        bot = _rgb(c_bot)
        for y in range(y0, y1 + 1):
            t = (y - y0) / span
            col = tuple(int(round(a + (b - a) * t)) for a, b in zip(top, bot))
            hits = []
            for (x1, y1_), (x2, y2_) in edges:
                if y1_ == y2_:
                    continue
                if (y1_ <= y < y2_) or (y2_ <= y < y1_):
                    tt = (y - y1_) / (y2_ - y1_)
                    hits.append(x1 + (x2 - x1) * tt)
            if len(hits) >= 2:
                hits.sort()
                fill = col if alpha == 255 else col + (alpha,)
                self.dr.line((hits[0], y, hits[-1], y), fill=fill)

    def line(self, a, b, c, width=1, alpha=255):
        self.dr.line((a[0], a[1], b[0], b[1]), fill=with_alpha(c, alpha), width=width)

    def ellipse(self, box, c, alpha=255, outline=None, width=1):
        self.dr.ellipse(box, fill=with_alpha(c, alpha),
                        outline=with_alpha(outline, alpha) if outline else None, width=width)

# ---------------------------------------------------------------------------
# material system
# ---------------------------------------------------------------------------    # Warm architectural palette - coherent across the entire house
MATERIALS = {
    # Walls
    "wall_ext":   {"top": "#f6f1e7", "lit": "#e7dfcd", "shade": "#c6b89f", "cap": "#fbf6ea", "base": "#d3c6aa"},
    "wall_int":   {"top": "#f4f0e7", "lit": "#eae4d6", "shade": "#cdc4b2", "cap": "#f8f4ea", "base": "#cfc6b0"},
    # Wood varieties
    "wood_oak":   {"top": "#dcbd8e", "lit": "#c2a273", "shade": "#8f7450", "dark": "#7d6544"},
    "wood_teak":  {"top": "#c9976b", "lit": "#a97a4e", "shade": "#7d5633", "dark": "#6d4a2b"},
    "wood_walnut": {"top": "#b98d63", "lit": "#996f47", "shade": "#6f4d2e", "dark": "#5f4126"},
    "wood_cherry": {"top": "#c98d6b", "lit": "#a9704e", "shade": "#7d4d33", "dark": "#6d3f2b"},
    # Floors
    "tile_porc":  {"top": "#eeeae1", "lit": "#ded7ca", "shade": "#b3aa9a", "grout": "#c6bfb2"},
    "tile_bath":  {"top": "#eae7e2", "lit": "#dcd7cf", "shade": "#b5aea2", "grout": "#cfc8bc"},
    "tile_marble": {"top": "#eae4da", "lit": "#dbd2c3", "shade": "#b0a48f", "grout": "#c0b5a0"},
    "stone":      {"top": "#e5ddd0", "lit": "#d5cbb9", "shade": "#a99b85"},
    "paver":      {"top": "#d2cbbd", "lit": "#c2b9a6", "shade": "#9c917c"},
    # Fabrics
    "fabric":     {"top": "#d9c9ad", "lit": "#c4b091", "shade": "#a08a6b"},
    "fabric2":    {"top": "#cdbfa4", "lit": "#b8a98c", "shade": "#97876d"},
    "fabric_blue": {"top": "#8a9ab0", "lit": "#708098", "shade": "#506078"},
    "white":      {"top": "#fbfaf6", "lit": "#f1efe6", "shade": "#dfdcd2"},
    "cream":      {"top": "#f9f5ec", "lit": "#f0e9d9", "shade": "#dcd2bd"},
    # Glass and metal
    "glass":      {"top": "#c8dde8", "lit": "#b8d0e0", "shade": "#98b8c8"},
    "metal":      {"top": "#c8c8c8", "lit": "#b0b0b0", "shade": "#888888"},
    "metal_dark": {"top": "#707070", "lit": "#585858", "shade": "#404040"},
    # Roof/cap
    "roof":       {"top": "#8b7b6b", "lit": "#7b6b5b", "shade": "#5b4b3b"},
    # Ground
    "lawn":       {"top": "#ccd6bd", "lit": "#c1ccb2", "shade": "#a9b699"},
}

# Floor material assignment by room type
FLOOR_MAT = {
    "living":    "wood_oak",
    "dining":    "wood_oak",
    "bed":       "wood_oak",
    "kitchen":   "tile_porc",
    "bathroom":  "tile_bath",
    "staircase": "stone",
    "circulation": "stone",
    "parking":   "paver",
    "puja":      "wood_teak",
}


def _mat(key):
    return MATERIALS.get(key, MATERIALS["wall_int"])

# ---------------------------------------------------------------------------
# camera / projection
# ---------------------------------------------------------------------------

class Camera:
    """Axonometric camera with auto-framing.

    Picks the most attractive ground corner for the entrance, computes a scale
    so the house fills ~75% of the canvas, and exposes iso()/P() for projecting
    the canonical (x east, y south, z up) coordinate system.
    """

    def __init__(self, plan, canvas=(CAN_W, CAN_H)):
        self.CW, self.CH = canvas
        self.w = float(plan["plot"]["width_ft"])
        self.d = float(plan["plot"]["depth_ft"])
        rooms = {r["id"]: r for r in plan["rooms"]}

        entrance = next(dr for dr in plan["doors"] if dr.get("connects_to") == "exterior")
        er = rooms[entrance["room_id"]]
        ecx = er["x_ft"] + er["width_ft"] / 2
        ecy = er["y_ft"] + er["depth_ft"] / 2
        variants = [
            (lambda x, y: (x, y)),
            (lambda x, y: (self.w - x, y)),
            (lambda x, y: (x, self.d - y)),
            (lambda x, y: (self.w - x, self.d - y)),
        ]
        self.tf = max(variants, key=lambda f: sum(f(ecx, ecy)))

        # Compute scale so house fills the canvas with margin
        sx_w = (self.CW * 0.82) / max(self.w, self.d)
        sy_k = 0.52  # vertical squash for iso angle
        vertical = (self.w + self.d) * sy_k + (WALL_H + 4.0) * 0.82
        sx_h = (self.CH * 0.80) / vertical
        self.sx = max(14.0, min(sx_w, sx_h))
        self.sy = self.sx * sy_k
        self.sz = self.sx * 0.82
        self.origin = (0.0, 0.0)
        # which world sides face the camera after the entrance transform
        self.fx = self.tf(1.0, 0.0)[0] > 1.5
        self.fy = self.tf(0.0, 1.0)[1] > 1.5

    def view(self, x, y):
        return self.tf(float(x), float(y))

    def iso(self, vx, vy, vz=0.0):
        ox, oy = self.origin
        return ((vx - vy) * self.sx + ox, (vx + vy) * self.sy - vz * self.sz + oy)

    def fit(self, plan):
        """Auto-frame: center the house and position it in the upper-middle of canvas."""
        rooms = plan["rooms"]
        pts = []
        for r in rooms:
            x, y, w, d = r["x_ft"], r["y_ft"], r["width_ft"], r["depth_ft"]
            corners = ((x - 1.6, y - 1.6), (x + w + 1.6, y - 1.6),
                       (x + w + 1.6, y + d + 1.6), (x - 1.6, y + d + 1.6))
            for cx, cy in corners:
                vx, vy = self.view(cx, cy)
                pts.append(self.iso(vx, vy, 0.0))
                pts.append(self.iso(vx, vy, WALL_H + 1.0))
        minx = min(p[0] for p in pts)
        maxx = max(p[0] for p in pts)
        miny = min(p[1] for p in pts)
        maxy = max(p[1] for p in pts)
        # Center horizontally, position vertically with house in upper 70% of canvas
        ox = self.CW / 2 - (minx + maxx) / 2
        oy = self.CH * 0.08 - miny
        if oy + maxy > self.CH * 0.96:
            oy = self.CH * 0.96 - maxy
        self.origin = (ox, oy)
        self.skyline_min = miny

    def north_dir(self):
        cx, cy = self.w / 2, self.d / 2
        vcx, vcy = self.view(cx, cy)
        vnx, vny = self.view(cx, cy - 1)
        a = self.iso(vcx, vcy, 0.0)
        b = self.iso(vnx, vny, 0.0)
        return (b[0] - a[0], b[1] - a[1])


def P(cam, x, y, z=0):
    vx, vy = cam.view(x, y)
    return cam.iso(vx, vy, z)


# ---------------------------------------------------------------------------
# core primitives
# ---------------------------------------------------------------------------

def cuboid(lay, cam, x, y, z, w, d, h, mat, alpha=255):
    """Draw an opaque box with lit top, two toned side faces, and crisp edges."""
    p1 = P(cam, x + w, y, z)
    p2 = P(cam, x + w, y + d, z)
    p3 = P(cam, x, y + d, z)
    t0 = P(cam, x, y, z + h)
    t1 = P(cam, x + w, y, z + h)
    t2 = P(cam, x + w, y + d, z + h)
    t3 = P(cam, x, y + d, z + h)
    # Lit face (faces camera-left)
    lay.grad_quad([p1, p2, t2, t1], mat["lit"], shade(mat["lit"], 0.14), alpha=alpha)
    # Shaded face (faces camera-right/back)
    lay.grad_quad([p3, p2, t2, t3], mat["shade"], shade(mat["shade"], 0.14), alpha=alpha)
    # Top face (brightest)
    lay.grad_quad([t0, t1, t2, t3], mat["top"], shade(mat["top"], 0.08), alpha=alpha)
    # Crisp architectural edge lines: hide AA seams and define every volume
    edge = shade(mat["shade"], 0.42)
    ea = int(80 * alpha / 255)
    for pts in ([p1, p2, t2, t1], [p3, p2, t2, t3], [t0, t1, t2, t3]):
        for i in range(len(pts)):
            lay.line(pts[i], pts[(i + 1) % len(pts)], edge, width=1, alpha=ea)


def soft_shadow(lay, cam, x, y, w, d, alpha=30, ex=0.25, shift=(0.25, 0.32)):
    """Soft grounded shadow: three nested offset quads for falloff."""
    for k, a in ((1.0, alpha), (0.65, int(alpha * 0.50)), (0.38, int(alpha * 0.22))):
        e = ex + (1.0 - k) * 0.50
        pts = [P(cam, x - e, y - e, 0.02), P(cam, x + w + e, y - e, 0.02),
               P(cam, x + w + e, y + d + e, 0.02), P(cam, x - e, y + d + e, 0.02)]
        pts = [(px + shift[0] * cam.sx * k, py + shift[1] * cam.sy * k) for px, py in pts]
        lay.quad(pts, "#6f6754", alpha=a)


def contact_shadow(lay, cam, x, y, w, d, alpha=24, ex=0.08):
    """Dark contact shadow directly under an object."""
    for k, a in ((1.0, alpha), (0.50, int(alpha * 0.40))):
        e = ex + (1.0 - k) * 0.24
        pts = [P(cam, x - e, y - e, 0.03), P(cam, x + w + e, y - e, 0.03),
               P(cam, x + w + e, y + d + e, 0.03), P(cam, x - e, y + d + e, 0.03)]
        lay.quad(pts, "#6f6754", alpha=a)


def _soft(lay, shadow_lay, cam, x, y, w, d):
    """Combined soft + contact shadow."""
    soft_shadow(shadow_lay, cam, x, y, w, d)
    contact_shadow(shadow_lay, cam, x, y, w, d)


# ---------------------------------------------------------------------------
# floor finishes
# ---------------------------------------------------------------------------

def _wood_planks(lay, cam, x, y, w, d, mat, seed, plank_w=1.4):
    """Draw wood plank flooring with subtle color variation per plank."""
    rng = random.Random(seed)
    base = mat["top"]
    if w >= d:
        n_planks = max(1, int(d / plank_w))
        for i in range(n_planks):
            py = y + i * plank_w
            pw = min(plank_w, d - i * plank_w)
            if pw < 0.1:
                continue
            var = rng.uniform(-0.06, 0.06)
            pc = shade(base, var)
            pts = [P(cam, x, py, 0.03), P(cam, x + w, py, 0.03),
                   P(cam, x + w, py + pw, 0.03), P(cam, x, py + pw, 0.03)]
            lay.grad_quad(pts, tint(pc, 0.04), shade(pc, 0.12))
            if i > 0:
                lay.line(P(cam, x, py, 0.035), P(cam, x + w, py, 0.035),
                         shade(mat["dark"], 0.3), width=1, alpha=80)
    else:
        n_planks = max(1, int(w / plank_w))
        for i in range(n_planks):
            px = x + i * plank_w
            ph = min(plank_w, w - i * plank_w)
            if ph < 0.1:
                continue
            var = rng.uniform(-0.06, 0.06)
            pc = shade(base, var)
            pts = [P(cam, px, y, 0.03), P(cam, px + ph, y, 0.03),
                   P(cam, px + ph, y + d, 0.03), P(cam, px, y + d, 0.03)]
            lay.grad_quad(pts, tint(pc, 0.04), shade(pc, 0.12))
            if i > 0:
                lay.line(P(cam, px, y, 0.035), P(cam, px, y + d, 0.035),
                         shade(mat["dark"], 0.3), width=1, alpha=80)


def _tile_grid(lay, cam, x, y, w, d, mat, seed, tile_sz=2.0):
    """Draw tiled floor with grout lines."""
    rng = random.Random(seed)
    grout = mat.get("grout", "#c9bcab")
    nx = max(1, int(w / tile_sz))
    ny = max(1, int(d / tile_sz))
    for iy in range(ny):
        for ix in range(nx):
            tx = x + ix * tile_sz
            ty = y + iy * tile_sz
            tw = min(tile_sz, w - ix * tile_sz)
            th = min(tile_sz, d - iy * tile_sz)
            if tw < 0.05 or th < 0.05:
                continue
            var = rng.uniform(-0.03, 0.03)
            tc = shade(mat["top"], var)
            pts = [P(cam, tx, ty, 0.03), P(cam, tx + tw, ty, 0.03),
                   P(cam, tx + tw, ty + th, 0.03), P(cam, tx, ty + th, 0.03)]
            lay.quad(pts, tc)
    for ix in range(nx + 1):
        gx = x + ix * tile_sz
        if gx > x + w:
            continue
        lay.line(P(cam, gx, y, 0.035), P(cam, gx, y + d, 0.035), grout, width=1, alpha=100)
    for iy in range(ny + 1):
        gy = y + iy * tile_sz
        if gy > y + d:
            continue
        lay.line(P(cam, x, gy, 0.035), P(cam, x + w, gy, 0.035), grout, width=1, alpha=100)


def _stone_floor(lay, cam, x, y, w, d, mat, seed):
    """Draw stone flooring with irregular pattern."""
    rng = random.Random(seed)
    pts = [P(cam, x, y, 0.03), P(cam, x + w, y, 0.03),
           P(cam, x + w, y + d, 0.03), P(cam, x, y + d, 0.03)]
    lay.grad_quad(pts, mat["top"], shade(mat["top"], 0.18))
    n_joints = max(2, int(max(w, d) / 3.0))
    for i in range(1, n_joints):
        t = i / n_joints
        if w >= d:
            jx = x + w * t + rng.uniform(-0.2, 0.2)
            lay.line(P(cam, jx, y, 0.035), P(cam, jx, y + d, 0.035),
                     mat["shade"], width=1, alpha=60)
        else:
            jy = y + d * t + rng.uniform(-0.2, 0.2)
            lay.line(P(cam, x, jy, 0.035), P(cam, x + w, jy, 0.035),
                     mat["shade"], width=1, alpha=60)


def floor_finish(lay, cam, room, seed):
    """Draw appropriate floor finish based on room type."""
    kind = room.get("kind", "habitable")
    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
    name = room.get("name", "").lower()

    if kind == "habitable":
        fkey = "bed" if "bed" in name else room["id"]
    else:
        fkey = kind
    mat_key = FLOOR_MAT.get(fkey, "wood_oak")
    mat = _mat(mat_key)

    if mat_key in ("wood_oak", "wood_teak"):
        _wood_planks(lay, cam, x, y, w, d, mat, seed)
    elif mat_key in ("tile_porc", "tile_bath", "tile_marble"):
        _tile_grid(lay, cam, x, y, w, d, mat, seed)
    elif mat_key in ("stone",):
        _stone_floor(lay, cam, x, y, w, d, mat, seed)
    elif mat_key in ("paver",):
        _stone_floor(lay, cam, x, y, w, d, mat, seed)
    else:
        _wood_planks(lay, cam, x, y, w, d, mat, seed)
    # subtle room-boundary line keeps floors crisp and separated
    edge = shade(mat["shade"], 0.30)
    for a, b in ((P(cam, x, y, 0.04), P(cam, x + w, y, 0.04)),
                 (P(cam, x + w, y, 0.04), P(cam, x + w, y + d, 0.04)),
                 (P(cam, x + w, y + d, 0.04), P(cam, x, y + d, 0.04)),
                 (P(cam, x, y + d, 0.04), P(cam, x, y, 0.04))):
        lay.line(a, b, edge, width=1, alpha=70)

# --------------------------------------------------------------------------
# furniture primitives
# --------------------------------------------------------------------------

def bed(lay, shadow_lay, cam, r, head, mat=_mat("wood_oak")):
    x, y, w, d = r
    _soft(lay, shadow_lay, cam, x, y, w, d)
    hb_h = 1.55
    cuboid(lay, cam, x, y, 0, w, d, 0.28, mat)
    cuboid(lay, cam, x + 0.12, y + 0.15, 0.28, w - 0.24, d - 0.35, 0.3, _mat("cream"))
    cuboid(lay, cam, x + 0.12, y + d * 0.34, 0.58, w - 0.24, d * 0.52, 0.22,
           {"top": "#e7dcc6", "lit": "#d9cab0", "shade": "#bda689"})
    if head in ("n", "s"):
        hy = y - 0.22 if head == "n" else y + d - 0.18
        cuboid(lay, cam, x - 0.1, hy, 0, w + 0.2, 0.35, hb_h, _mat("wood_teak"))
        cuboid(lay, cam, x - 0.08, hy, 0, 0.22, 0.34, hb_h + 0.25, _mat("wood_teak"))
        cuboid(lay, cam, x + w - 0.14, hy, 0, 0.22, 0.34, hb_h + 0.25, _mat("wood_teak"))
        pz = y + 0.55 if head == "n" else y + d - 1.35
        pw = (w - 1.2) / 2
        cuboid(lay, cam, x + 0.35, pz, 0.66, pw, 1.0, 0.26, _mat("cream"))
        cuboid(lay, cam, x + 0.75 + pw, pz, 0.66, pw, 1.0, 0.26, _mat("cream"))
    else:
        hx = x - 0.18 if head == "w" else x + w - 0.18
        cuboid(lay, cam, hx, y - 0.1, 0, 0.34, d + 0.2, hb_h, _mat("wood_teak"))
        cuboid(lay, cam, hx, y - 0.08, 0, 0.34, 0.22, hb_h + 0.25, _mat("wood_teak"))
        cuboid(lay, cam, hx, y + d - 0.14, 0, 0.34, 0.22, hb_h + 0.25, _mat("wood_teak"))
        px = x + 0.6 if head == "w" else x + w - 1.6
        phh = (d - 1.2) / 2
        cuboid(lay, cam, px, y + 0.35, 0.66, 1.0, phh, 0.26, _mat("cream"))
        cuboid(lay, cam, px, y + 0.75 + phh, 0.66, 1.0, phh, 0.26, _mat("cream"))


def side_table(lay, shadow_lay, cam, x, y):
    s = 1.35
    _soft(lay, shadow_lay, cam, x, y, s, s)
    cuboid(lay, cam, x, y, 0, s, s, 1.05, _mat("wood_walnut"))
    cuboid(lay, cam, x + 0.38, y + 0.38, 1.05, 0.58, 0.58, 0.5,
           {"top": "#f2ecd9", "lit": "#e2d8c0", "shade": "#c2b494"})


def sofa(lay, shadow_lay, cam, r, back):
    x, y, w, d = r
    _soft(lay, shadow_lay, cam, x, y, w, d)
    cuboid(lay, cam, x, y, 0, w, d, 0.45, _mat("fabric"))
    if back in ("n", "s"):
        by = y + 0.18 if back == "n" else y + d - 0.62
        cuboid(lay, cam, x + 0.1, by, 0.45, w - 0.2, 0.44, 1.0, _mat("fabric"))
        ar = y + d - 0.42 if back == "n" else y + 0.42
        cuboid(lay, cam, x + 0.02, ar, 0.45, 0.34, d - 0.84, 0.5, _mat("fabric2"))
        cuboid(lay, cam, x + w - 0.36, ar, 0.45, 0.34, d - 0.84, 0.5, _mat("fabric2"))
        sw = (w - 1.0) / 2
        cuboid(lay, cam, x + 0.25, y + 0.25, 0.5, sw - 0.2, d - 0.7, 0.22, _mat("fabric2"))
        cuboid(lay, cam, x + 0.6 + sw, y + 0.3, 0.5, sw - 0.25, d - 0.7, 0.22, _mat("fabric2"))
        py = y + d * 0.55 if back == "n" else y + d * 0.44 - 0.3
        cuboid(lay, cam, x + 0.3, py, 0.72, 1.15, 0.75, 0.3, _mat("fabric2"))
    else:
        bx = x + 0.18 if back == "w" else x + w - 0.62
        cuboid(lay, cam, bx, y + 0.1, 0.45, 0.44, d - 0.2, 1.0, _mat("fabric"))
        ar = x + w - 0.42 if back == "w" else x + 0.42
        cuboid(lay, cam, ar, y + 0.02, 0.45, w - 0.84, 0.34, 0.5, _mat("fabric2"))
        cuboid(lay, cam, ar, y + d - 0.36, 0.45, w - 0.84, 0.34, 0.5, _mat("fabric2"))
        sh = (d - 1.0) / 2
        cuboid(lay, cam, x + 0.25, y + 0.25, 0.5, w - 0.7, sh - 0.2, 0.22, _mat("fabric2"))
        cuboid(lay, cam, x + 0.3, y + 0.6 + sh, 0.5, w - 0.7, sh - 0.25, 0.22, _mat("fabric2"))
        px = x + w * 0.55 if back == "w" else x + w * 0.44 - 0.3
        cuboid(lay, cam, px, y + 0.3, 0.72, 0.75, 1.15, 0.3, _mat("fabric2"))


def armchair(lay, shadow_lay, cam, x, y, s=2.6, back="e"):
    _soft(lay, shadow_lay, cam, x, y, s, s)
    cuboid(lay, cam, x, y, 0, s, s, 0.5, _mat("fabric2"))
    if back in ("n", "s"):
        by = y + 0.1 if back == "n" else y + s - 0.5
        cuboid(lay, cam, x + 0.1, by, 0.5, s - 0.2, 0.4, 1.2, _mat("fabric2"))
    else:
        bx = x + 0.1 if back == "w" else x + s - 0.5
        cuboid(lay, cam, bx, y + 0.1, 0.5, 0.4, s - 0.2, 1.2, _mat("fabric2"))
    cuboid(lay, cam, x + 0.14, y + 0.14, 0.5, s - 0.28, s - 0.28, 0.2, _mat("fabric"))


def coffee_table(lay, shadow_lay, cam, x, y, w, d, h=0.95):
    _soft(lay, shadow_lay, cam, x, y, w, d)
    cuboid(lay, cam, x + 0.25, y + 0.25, 0, w - 0.5, d - 0.5, 0.78, _mat("wood_walnut"))
    cuboid(lay, cam, x, y, 0.78, w, d, 0.18, _mat("wood_walnut"))


def chair3(lay, shadow_lay, cam, x, y, rot=0):
    s = 1.2
    _soft(lay, shadow_lay, cam, x, y, s, s)
    cuboid(lay, cam, x + 0.15, y + 0.15, 0, s - 0.3, s - 0.3, 0.6, _mat("wood_walnut"))
    if rot == 0:
        cuboid(lay, cam, x + 0.15, y + 0.15, 0.6, s - 0.3, 0.28, 1.0, _mat("fabric2"))
    else:
        cuboid(lay, cam, x + 0.15, y + s - 0.43, 0.6, s - 0.3, 0.28, 1.0, _mat("fabric2"))

def dining_set(lay, shadow_lay, cam, x, y, w, d):
    horiz = w >= d
    tw, td = (min(5.2, w - 2.4), min(2.9, d - 2.2)) if horiz else (min(2.9, w - 2.2), min(5.2, d - 2.4))
    tx, ty = x + (w - tw) / 2, y + (d - td) / 2
    _soft(lay, shadow_lay, cam, tx, ty, tw, td)
    cuboid(lay, cam, tx, ty, 0, tw, td, 0.62, _mat("wood_oak"))
    cuboid(lay, cam, tx + 0.25, ty + 0.25, 0.62, tw - 0.5, td - 0.5, 0.5, _mat("wood_oak"))
    cuboid(lay, cam, tx, ty, 1.12, tw, td, 0.14, _mat("wood_teak"))
    for fx in (0.3, 0.7):
        chair3(lay, shadow_lay, cam, tx + tw * fx - 0.6, ty - 1.35, rot=0)
        chair3(lay, shadow_lay, cam, tx + tw * fx - 0.6, ty + td + 0.35, rot=0)
    chair3(lay, shadow_lay, cam, tx - 1.35, ty + td * 0.5 - 0.6, rot=1)
    chair3(lay, shadow_lay, cam, tx + tw + 0.35, ty + td * 0.5 - 0.6, rot=1)


def tv_unit(lay, shadow_lay, cam, x, y, w, d):
    _soft(lay, shadow_lay, cam, x, y, w, d)
    cuboid(lay, cam, x, y, 0, w, d, 0.75, _mat("wood_walnut"))
    cuboid(lay, cam, x + 0.25, y + 0.15, 0.75, w - 0.5, d - 0.3, 0.75,
           {"top": "#2d2a27", "lit": "#211f1c", "shade": "#161412"})


def wardrobe(lay, shadow_lay, cam, x, y, w, d, h=6.0):
    _soft(lay, shadow_lay, cam, x, y, w, d)
    cuboid(lay, cam, x, y, 0, w, d, h, _mat("wood_teak"))
    n = max(2, int(w / 2.2))
    for i in range(1, n):
        t = x + i * (w / n)
        lay.line(P(cam, t, y, 0.4), P(cam, t, y, h - 0.15), "#5f4528", width=1, alpha=190)
        lay.line(P(cam, t, y + d, 0.4), P(cam, t, y + d, h - 0.15), "#5f4528", width=1, alpha=190)
    for i in range(n):
        hx = x + (i + 0.5) * (w / n)
        lay.line(P(cam, hx, y + 0.15, 1.55), P(cam, hx, y + 0.15, 2.0), "#c9a02f", width=2, alpha=230)


def floor_lamp(lay, glow_lay, cam, x, y):
    cuboid(lay, cam, x, y, 0, 0.55, 0.55, 3.6,
           {"top": "#5c4a33", "lit": "#4a3a25", "shade": "#33260f"})
    cuboid(lay, cam, x - 0.2, y - 0.2, 3.6, 0.95, 0.95, 0.9,
           {"top": "#f6e8c4", "lit": "#ecd9a8", "shade": "#c9b178"})
    glow(glow_lay, cam, x + 0.28, y + 0.28, 1.4, 30)


def plant(lay, shadow_lay, cam, x, y):
    _soft(lay, shadow_lay, cam, x, y, 1.4, 1.4)
    cuboid(lay, cam, x, y, 0, 1.4, 1.4, 1.0,
           {"top": "#a56b43", "lit": "#8a5634", "shade": "#5f3820"})
    cx, cy = x + 0.7, y + 0.7
    for dx, dy, rr in ((-0.4, -0.2, 0.9), (0.55, 0.1, 0.75), (0.1, 0.62, 0.85), (-0.1, -0.55, 0.7)):
        c = P(cam, cx + dx, cy + dy, 1.6)
        r = rr * cam.sx * 1.05
        lay.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), "#7d9b6a")
        c2 = P(cam, cx + dx + 0.35, cy + dy, 1.85)
        lay.ellipse((c2[0] - r * 0.7, c2[1] - r * 0.7, c2[0] + r * 0.7, c2[1] + r * 0.7), "#69875a")


def glow(lay, cam, x, y, r, alpha):
    c = P(cam, x, y, 0.1)
    base = cam.sx
    for k, a in ((1.0, alpha), (0.72, int(alpha * 0.7)), (0.45, int(alpha * 0.4))):
        rr = r * k * base
        lay.ellipse((c[0] - rr, c[1] - rr * 0.82, c[0] + rr, c[1] + rr * 0.82),
                    "#ffe9bd", alpha=a)

def _counter_run(lay, shadow_lay, cam, x, y, w, d, seed):
    if w <= 0 or d <= 0:
        return
    _soft(lay, shadow_lay, cam, x, y, w, d)
    cuboid(lay, cam, x, y, 0, w, d, 0.78, _mat("wood_teak"))
    if d > w:
        n = max(1, int(w / 1.9))
        for i in range(1, n):
            t = x + i * (w / n)
            lay.line(P(cam, t, y, 0.2), P(cam, t, y + d, 0.2), "#5f4528", width=1, alpha=170)
            lay.line(P(cam, t, y, 0.5), P(cam, t, y + d, 0.5), "#5f4528", width=1, alpha=170)
    else:
        n = max(1, int(d / 1.9))
        for i in range(1, n):
            t = y + i * (d / n)
            lay.line(P(cam, x, t, 0.2), P(cam, x + w, t, 0.2), "#5f4528", width=1, alpha=170)
    cuboid(lay, cam, x + 0.05, y + 0.05, 0.78, w - 0.1, d - 0.1, 0.14,
           {"top": "#efe8da", "lit": "#e0d5c2", "shade": "#b9a98d"})


def upper_cabinet(lay, cam, x, y, w, d):
    cuboid(lay, cam, x, y, 1.45, w, d, 1.35,
           {"top": "#c89a63", "lit": "#a97a4e", "shade": "#7d5633"})
    seg = min(1.8, w / max(1, int(w / 1.8)))
    n = max(1, int(w / seg))
    for i in range(1, n):
        t = x + i * seg
        lay.line(P(cam, t, y, 1.55), P(cam, t, y + d, 1.55), "#5f4528", width=1, alpha=160)


def kitchen_set(lay, shadow_lay, cam, room, spans, seed):
    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
    cdepth = 2.1
    for side, a, b in spans:
        if side in ("north", "south"):
            yy = y if side == "north" else y + d - cdepth
            _counter_run(lay, shadow_lay, cam, x + a, yy, b - a, cdepth, seed)
        else:
            xx = x if side == "west" else x + w - cdepth
            _counter_run(lay, shadow_lay, cam, xx, y + a, cdepth, b - a, seed)


def fridge(lay, shadow_lay, cam, x, y):
    _soft(lay, shadow_lay, cam, x, y, 2.6, 2.5)
    cuboid(lay, cam, x, y, 0, 2.6, 2.5, 2.05,
           {"top": "#e7e4dd", "lit": "#d6d2c9", "shade": "#aeb0a9"})
    lay.line(P(cam, x, y + 0.35, 1.32), P(cam, x + 2.6, y + 0.35, 1.32), "#9b968d", width=1, alpha=200)


def _sink_overlay(lay, cam, sx, sy):
    cs = P(cam, sx, sy, 0.95)
    lay.ellipse((cs[0] - 0.75 * cam.sx, cs[1] - 0.5 * cam.sy, cs[0] + 0.75 * cam.sx, cs[1] + 0.5 * cam.sy),
                "#3a3630", alpha=235)
    lay.ellipse((cs[0] - 0.5 * cam.sx, cs[1] - 0.3 * cam.sy, cs[0] + 0.5 * cam.sx, cs[1] + 0.3 * cam.sy),
                "#6f6a5f", alpha=200)
    lay.line(P(cam, sx, sy, 0.98), P(cam, sx + 0.1, sy - 0.1, 1.4), "#b9b4ab", width=2, alpha=240)


def _hob_overlay(lay, cam, hx, hy):
    c = P(cam, hx, hy, 0.93)
    rr = 0.72 * cam.sx
    lay.ellipse((c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr), "#22201e", alpha=255)
    for dx, dy in ((0.3, 0.3), (-0.3, 0.3), (0.3, -0.3), (-0.3, -0.3)):
        c2 = P(cam, hx + dx, hy + dy, 0.945)
        lay.ellipse((c2[0] - 0.16 * cam.sx, c2[1] - 0.16 * cam.sy, c2[0] + 0.16 * cam.sx, c2[1] + 0.16 * cam.sy),
                    "#8d2f24", alpha=230)

def bath_set(lay, shadow_lay, cam, room, seed):
    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
    rng = random.Random(seed + 30)
    wx = x + rng.uniform(0.4, 0.9)
    wy = y + d - 2.7 - rng.uniform(0, 0.9)
    cuboid(lay, cam, wx, wy, 0, 1.15, 1.15, 1.55, _mat("white"))
    cuboid(lay, cam, wx + 0.28, wy + 0.2, 0.55, 0.62, 0.75, 0.55, _mat("white"))
    cuboid(lay, cam, wx + 0.05, wy + 0.05, 1.55, 1.0, 1.0, 0.9,
           {"top": "#d8d5cc", "lit": "#c2beb4", "shade": "#97938a"})
    vx = x + max(0.4, w - 3.0)
    vy = y + (d - 2.0) / 2
    cuboid(lay, cam, vx, vy, 0, 2.6, 2.0, 0.62, _mat("wood_walnut"))
    cuboid(lay, cam, vx + 0.2, vy + 0.2, 0.62, 1.7, 1.6, 0.14,
           {"top": "#f6f2ea", "lit": "#e9e2d4", "shade": "#c4b9a2"})
    bc = P(cam, vx + 1.0, vy + 1.0, 0.8)
    lay.ellipse((bc[0] - 0.55 * cam.sx, bc[1] - 0.4 * cam.sy, bc[0] + 0.55 * cam.sx, bc[1] + 0.4 * cam.sy),
                "#fbfaf6", alpha=255)
    lay.line(P(cam, vx + 1.0, vy + 1.0, 0.82), P(cam, vx + 0.2, vy + 1.0, 1.35), "#b9b4ab", width=2, alpha=240)
    if w >= 5.0 and d >= 4.8:
        sxc, syc = x + 0.3, y + 0.3
        cuboid(lay, cam, sxc, syc, 0, 2.4, 2.4, 0.1,
               {"top": "#d9d6cf", "lit": "#c2beb6", "shade": "#99948c"})
        sg = ("#cfe0e8", "#b7cdd8", "#94aebe")
        cuboid(lay, cam, sxc + 0.05, syc + 0.05, 0.1, 2.3, 0.16, 2.2,
               {"top": sg[0], "lit": sg[1], "shade": sg[2]})
        cuboid(lay, cam, sxc + 0.05, syc + 0.05, 0.1, 0.16, 2.3, 2.2,
               {"top": sg[0], "lit": sg[1], "shade": sg[2]})
        cuboid(lay, cam, sxc + 0.5, syc + 0.5, 2.05, 0.5, 1.5, 0.06,
               {"top": "#cfcbc2", "lit": "#b9b4a9", "shade": "#918c80"})
    cuboid(lay, cam, x + w - 1.3, y + 0.3, 1.8, 1.0, 0.12, 0.5,
           {"top": "#b9b4ab", "lit": "#a49e94", "shade": "#7d766b"})


def stair_set(lay, shadow_lay, cam, room):
    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
    steps = 12
    rise = 0.72
    step_pal = {"top": "#d9a96f", "lit": "#c08a4f", "shade": "#94652f"}
    rise_pal = {"top": "#e2dacb", "lit": "#cfc3ab", "shade": "#a99b85"}
    rail = {"top": "#c9a02f", "lit": "#b18a22", "shade": "#7a5c0c"}
    rail = {"top": "#9a6a3e", "lit": "#7e5330", "shade": "#5a3820"}
    if d >= w:
        run = (d - 0.9) / steps
        for i in range(steps):
            z0 = i * rise
            cuboid(lay, cam, x + 0.3, y + 0.35 + i * run, z0, w - 0.6, run - 0.04, rise, rise_pal)
            cuboid(lay, cam, x + 0.3, y + 0.35 + i * run, z0, w - 0.6, run - 0.04, 0.08, step_pal)
        bx = x + w - 0.30
        for i in range(0, steps + 1, 2):
            zz = i * rise
            cuboid(lay, cam, bx, y + 0.35 + i * run, zz, 0.14, 0.14, 2.55, rail)
        for i in range(steps):
            cuboid(lay, cam, bx - 0.05, y + 0.35 + i * run, i * rise + 2.55,
                   0.24, run + 0.04, 0.14, rail)
    else:
        run = (w - 0.9) / steps
        for i in range(steps):
            z0 = i * rise
            cuboid(lay, cam, x + 0.35 + i * run, y + 0.3, z0, run - 0.04, d - 0.6, rise, rise_pal)
            cuboid(lay, cam, x + 0.35 + i * run, y + 0.3, z0, run - 0.04, d - 0.6, 0.08, step_pal)
        by = y + d - 0.30
        for i in range(0, steps + 1, 2):
            zz = i * rise
            cuboid(lay, cam, x + 0.35 + i * run, by, zz, 0.14, 0.14, 2.55, rail)
        for i in range(steps):
            cuboid(lay, cam, x + 0.35 + i * run, by - 0.05, i * rise + 2.55,
                   run + 0.04, 0.24, 0.14, rail)

def car_set(lay, shadow_lay, glow_lay, cam, room):
    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
    if d >= w:
        cw, ch = min(5.4, w - 2.0), min(11.5, d - 2.2)
        bx, by = x + (w - cw) / 2, y + (d - ch) / 2
        horiz = False
    else:
        cw, ch = min(11.5, w - 2.2), min(5.4, d - 2.0)
        bx, by = x + (w - cw) / 2, y + (d - ch) / 2
        horiz = True
    _soft(lay, shadow_lay, cam, bx, by, cw, ch)
    body = {"top": "#ccd3d9", "lit": "#b7bfc6", "shade": "#89929a"}
    glass = {"top": "#8faebd", "lit": "#a8c3d0", "shade": "#5d7888"}
    cuboid(lay, cam, bx, by, 0.35, cw, ch, 0.62, body)
    if horiz:
        cuboid(lay, cam, bx + cw * 0.18, by + 0.25, 1.0, cw * 0.64, ch - 0.5, 0.55, glass)
        cuboid(lay, cam, bx + cw * 0.05, by + 0.1, 1.55, cw * 0.9, ch - 0.2, 0.18, body)
    else:
        cuboid(lay, cam, bx + 0.25, by + ch * 0.18, 1.0, cw - 0.5, ch * 0.64, 0.55, glass)
        cuboid(lay, cam, bx + 0.1, by + ch * 0.05, 1.55, cw - 0.2, ch * 0.9, 0.18, body)
    for wx, wy in ((bx + 0.8, by + 0.8), (bx + cw - 1.6, by + 0.8),
                   (bx + 0.8, by + ch - 1.6), (bx + cw - 1.6, by + ch - 1.6)):
        c = P(cam, wx + 0.4, wy + 0.4, 0.28)
        rr = 0.5 * cam.sx
        lay.ellipse((c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr), "#2c2c2e", alpha=255)
    for wx, wy in ((bx + 0.5, by + 0.6), (bx + cw - 1.1, by + 0.6)):
        c = P(cam, wx, wy, 1.62)
        lay.ellipse((c[0] - 0.12 * cam.sx, c[1] - 0.09 * cam.sy, c[0] + 0.12 * cam.sx, c[1] + 0.09 * cam.sy),
                    "#f5efc8", alpha=255)


def puja_set(lay, shadow_lay, glow_lay, cam, room):
    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
    _soft(lay, shadow_lay, cam, x + 0.3, y + 0.25, w - 0.6, min(1.6, d - 0.5))
    cuboid(lay, cam, x + 0.3, y + 0.2, 0, w - 0.6, min(1.7, d - 0.4), 0.65, _mat("wood_teak"))
    cuboid(lay, cam, x + w / 2 - 0.55, y + 0.42, 0.65, 1.1, 0.95, 1.15, _mat("wood_walnut"))
    c = P(cam, x + w / 2, y + 0.9, 1.85)
    rr = 0.42 * cam.sx
    lay.ellipse((c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr), "#c9a06f", alpha=255)
    glow(glow_lay, cam, x + w / 2, y + d - 1.2, 1.2, 28)
    c2 = P(cam, x + w / 2, y + d - 1.1, 0.72)
    lay.ellipse((c2[0] - 0.3 * cam.sx, c2[1] - 0.22 * cam.sy, c2[0] + 0.3 * cam.sx, c2[1] + 0.22 * cam.sy),
                "#f6c65a", alpha=255)

# --------------------------------------------------------------------------
# walls derived from the canonical room union
# --------------------------------------------------------------------------

def _side_span(r, side):
    return r["width_ft"] if side in ("north", "south") else r["depth_ft"]


def build_wall_faces(plan):
    rooms = plan["rooms"]
    w, d = plan["plot"]["width_ft"], plan["plot"]["depth_ft"]
    by_id = {r["id"]: r for r in rooms}
    xs = sorted({0.0, float(w)} | {r["x_ft"] for r in rooms} | {r["x_ft"] + r["width_ft"] for r in rooms})
    ys = sorted({0.0, float(d)} | {r["y_ft"] for r in rooms} | {r["y_ft"] + r["depth_ft"] for r in rooms})
    ncx, ncy = len(xs) - 1, len(ys) - 1

    def rooms_in(cx, cy):
        x0, x1 = xs[cx], xs[cx + 1]
        y0, y1 = ys[cy], ys[cy + 1]
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        return frozenset(r["id"] for r in rooms
                         if r["x_ft"] <= mx < r["x_ft"] + r["width_ft"]
                         and r["y_ft"] <= my < r["y_ft"] + r["depth_ft"])

    grid = [[rooms_in(cx, cy) for cy in range(ncy)] for cx in range(ncx)]
    faces = []

    def tally(orient, pos, a0, a1, s0, s1):
        if a1 - a0 > 0.15:
            faces.append({"orient": orient, "pos": pos, "a0": a0, "a1": a1,
                          "s0": s0, "s1": s1})

    for bx in range(1, len(xs)):
        cy = 0
        while cy < len(ys) - 1:
            L = grid[bx - 1][cy] if bx - 1 < ncx else frozenset()
            R = grid[bx][cy] if bx < ncx else frozenset()
            if L == R:
                cy += 1
                continue
            a0 = ys[cy]
            while cy < len(ys) - 1:
                Lr = grid[bx - 1][cy] if bx - 1 < ncx else frozenset()
                Rr = grid[bx][cy] if bx < ncx else frozenset()
                if (Lr, Rr) != (L, R):
                    break
                cy += 1
            tally("V", xs[bx], a0, ys[cy], L, R)
    for by in range(1, len(ys)):
        cx = 0
        while cx < len(xs) - 1:
            T = grid[cx][by - 1] if by - 1 < ncy else frozenset()
            B = grid[cx][by] if by < ncy else frozenset()
            if T == B:
                cx += 1
                continue
            a0 = xs[cx]
            while cx < len(xs) - 1:
                Tr = grid[cx][by - 1] if by - 1 < ncy else frozenset()
                Br = grid[cx][by] if by < ncy else frozenset()
                if (Tr, Br) != (T, B):
                    break
                cx += 1
            tally("H", ys[by], a0, xs[cx], T, B)

    for face in faces:
        face["openings"] = []
        face["exterior"] = (not face["s0"]) or (not face["s1"])
        if face["orient"] == "V":
            pos = face["pos"]
            for rid in list(face["s0"]) + list(face["s1"]):
                r = by_id[rid]
                side = "east" if abs(pos - (r["x_ft"] + r["width_ft"])) < 1e-4 else "west"
                origin = r["y_ft"]
                _collect_openings(plan, face, r, side, origin)
        else:
            pos = face["pos"]
            for rid in list(face["s0"]) + list(face["s1"]):
                r = by_id[rid]
                side = "south" if abs(pos - (r["y_ft"] + r["depth_ft"])) < 1e-4 else "north"
                origin = r["x_ft"]
                _collect_openings(plan, face, r, side, origin)
    return faces


def _collect_openings(plan, face, r, side, origin):
    span = _side_span(r, side)
    for dr in plan["doors"]:
        if dr.get("room_id") != r["id"] or dr.get("side") != side:
            continue
        off = dr["offset_ft"]
        leaf = min(2.5, max(1.5, span - off))
        t0 = max(face["a0"], origin + off)
        t1 = min(face["a1"], origin + off + leaf)
        if t1 - t0 > 0.6:
            face["openings"].append({"kind": "door", "t0": t0, "t1": t1, "rec": dr, "r": r})
    for wn in plan["windows"]:
        if wn.get("room_id") != r["id"] or wn.get("side") != side:
            continue
        off = wn["offset_ft"]
        leaf = max(1.5, min(float(wn.get("width_ft", 4.0)), span - off - 0.3))
        t0 = max(face["a0"], origin + off)
        t1 = min(face["a1"], origin + off + leaf)
        if t1 - t0 > 0.6:
            face["openings"].append({"kind": "window", "t0": t0, "t1": t1, "rec": wn, "r": r})


def _face_band(face):
    exterior = face["exterior"]
    out_h, in_h = (0.85, 0.55) if exterior else (0.30, 0.30)
    face["thick"] = out_h + in_h
    return out_h, in_h


def _wall_box(face, a0, a1, z0, h, mat):
    out_h, in_h = _face_band(face)
    if face["orient"] == "V":
        empty_west = not face["s0"]
        x0 = face["pos"] - out_h if empty_west else face["pos"] - in_h
        x1 = face["pos"] + in_h if empty_west else face["pos"] + out_h
        return (x0, a0, x1 - x0, a1 - a0)
    empty_north = not face["s0"]
    y0 = face["pos"] - out_h if empty_north else face["pos"] - in_h
    y1 = face["pos"] + in_h if empty_north else face["pos"] + out_h
    return (a0, y0, a1 - a0, y1 - y0)

def _wall_segments(face):
    ops = sorted(face["openings"], key=lambda o: o["t0"])
    segs = []
    cur = face["a0"]
    for o in ops:
        if o["t0"] - cur > 0.15:
            segs.append((cur, o["t0"]))
        cur = max(cur, o["t1"])
    if face["a1"] - cur > 0.15:
        segs.append((cur, face["a1"]))
    return segs


def draw_wall_segments(lay, shadow_lay, cam, face, wh=WALL_H):
    exterior = face["exterior"]
    mat = _mat("wall_ext") if exterior else _mat("wall_int")
    out_h, in_h = _face_band(face)
    if exterior:
        if face["orient"] == "V":
            empty_west = not face["s0"]
            sh_x = face["pos"] - out_h if empty_west else face["pos"] - in_h
            soft_shadow(shadow_lay, cam, sh_x - 0.35, face["a0"] - 0.1,
                        face["thick"] + 0.6, face["a1"] - face["a0"] + 0.2, alpha=40)
        else:
            empty_north = not face["s0"]
            sh_y = face["pos"] - out_h if empty_north else face["pos"] - in_h
            soft_shadow(shadow_lay, cam, face["a0"] - 0.1, sh_y - 0.35,
                        face["a1"] - face["a0"] + 0.2, face["thick"] + 0.6, alpha=40)
    for a0, a1 in _wall_segments(face):
        bx, by, bw, bd = _wall_box(face, a0, a1, 0.0, WALL_H, mat)
        cuboid(lay, cam, bx, by, 0, bw, bd, wh, mat)
        if exterior:
            cx0, cy0, cw0, cd0 = _wall_box(face, a0 - 0.12, a1 + 0.12, 0, 0, mat)
            cuboid(lay, cam, cx0, cy0, wh, cw0, cd0, 0.32,
                   {"top": _mat("wall_ext")["cap"], "lit": shade(_mat("wall_ext")["cap"], 0.05),
                    "shade": shade(_mat("wall_ext")["cap"], 0.14)})
            px0, py0, pw0, pd0 = _wall_box(face, a0, a1, 0, 0, mat)
            cuboid(lay, cam, px0 - 0.14, py0 - 0.14, 0, pw0 + 0.28, pd0 + 0.28, 0.55,
                   {"top": _mat("wall_ext")["base"], "lit": _mat("wall_ext")["base"],
                    "shade": shade(_mat("wall_ext")["base"], 0.12)})


def door_assembly(lay, shadow_lay, cam, face, o, wh=WALL_H):
    t0, t1 = o["t0"], o["t1"]
    exterior = o["rec"].get("connects_to") == "exterior"
    out_h, in_h = _face_band(face)
    door_mat = _mat("wood_teak")
    # keep the door (and its lintel) under the host wall's height
    dh = min(DOOR_H, wh - 0.8)
    if face["orient"] == "V":
        pos = face["pos"]
        cuboid(lay, cam, pos - in_h, t0 - 0.26, 0, face["thick"], 0.3, dh + 0.2, _mat("wall_int"))
        cuboid(lay, cam, pos - in_h, t1, 0, face["thick"], 0.3, dh + 0.2, _mat("wall_int"))
        cuboid(lay, cam, pos - in_h, t0, dh, face["thick"], t1 - t0, wh - dh, _mat("wall_int"))
        sw = face["thick"] * 0.6
        sxo = pos - (face["thick"] - sw) / 2 - sw
        cuboid(lay, cam, sxo, t0 + 0.08, 0.02, sw, t1 - t0 - 0.16, dh - 0.08, door_mat)
        lay.line(P(cam, sxo + sw * 0.5, t0 + 0.4, 0.4), P(cam, sxo + sw * 0.5, t0 + 0.4, dh - 0.6),
                 "#5f4528", width=2, alpha=150)
        lay.line(P(cam, pos + 0.06, t1 - 0.5, 1.2), P(cam, pos - 0.06, t1 - 0.5, 1.25), "#c9a02f", width=2, alpha=255)
    else:
        pos = face["pos"]
        cuboid(lay, cam, t0 - 0.26, pos - in_h, 0, 0.3, face["thick"], dh + 0.2, _mat("wall_int"))
        cuboid(lay, cam, t1, pos - in_h, 0, 0.3, face["thick"], dh + 0.2, _mat("wall_int"))
        cuboid(lay, cam, t0, pos - in_h, dh, t1 - t0, face["thick"], wh - dh, _mat("wall_int"))
        sw = face["thick"] * 0.6
        syo = pos - (face["thick"] - sw) / 2 - sw
        cuboid(lay, cam, t0 + 0.08, syo, 0.02, t1 - t0 - 0.16, sw, dh - 0.08, door_mat)
        lay.line(P(cam, t0 + 0.4, syo + sw * 0.5, 0.4), P(cam, t0 + 0.4, syo + sw * 0.5, dh - 0.6),
                 "#5f4528", width=2, alpha=150)
        lay.line(P(cam, t1 - 0.5, pos + 0.06, 1.2), P(cam, t1 - 0.5, pos - 0.06, 1.25), "#c9a02f", width=2, alpha=255)
    if exterior:
        if face["orient"] == "V":
            cuboid(lay, cam, pos - out_h - 0.6, t0 - 0.32, 0, 0.6, (t1 - t0) + 0.64, 0.38,
                   {"top": "#d6cfc2", "lit": "#c3baa8", "shade": "#9a8f78"})
        else:
            cuboid(lay, cam, t0 - 0.32, pos - out_h - 0.6, 0, (t1 - t0) + 0.64, 0.6, 0.38,
                   {"top": "#d6cfc2", "lit": "#c3baa8", "shade": "#9a8f78"})

def _curtain_or_glow(lay, glow_lay, cam, face, o, plan, t0, t1):
    r = o["r"]
    kind = r.get("kind", "habitable")
    cur = {"top": "#e6d8c0", "lit": "#d4c2a3", "shade": "#aa9472"}
    if face["orient"] == "V":
        pos = face["pos"]
        if kind not in ("bathroom", "kitchen", "staircase", "parking"):
            cuboid(lay, cam, pos - 0.3, t1 + 0.08, 0.06, 0.6, 0.36, WIN_HEAD - 0.2, cur)
            cuboid(lay, cam, pos - 0.3, t0 - 0.44, 0.06, 0.6, 0.36, WIN_HEAD - 0.2, cur)
        inside = 1 if pos < r["x_ft"] + r["width_ft"] / 2 else -1
        glow(glow_lay, cam, pos + inside * 0.6, (t0 + t1) / 2, 1.3, 20)
    else:
        pos = face["pos"]
        if kind not in ("bathroom", "kitchen", "staircase", "parking"):
            cuboid(lay, cam, t1 + 0.08, pos - 0.3, 0.06, 0.36, 0.6, WIN_HEAD - 0.2, cur)
            cuboid(lay, cam, t0 - 0.44, pos - 0.3, 0.06, 0.36, 0.6, WIN_HEAD - 0.2, cur)
        inside = 1 if pos < r["y_ft"] + r["depth_ft"] / 2 else -1
        glow(glow_lay, cam, (t0 + t1) / 2, pos + inside * 0.6, 1.3, 20)


def window_assembly(lay, shadow_lay, glow_lay, cam, face, o, wh=WALL_H, plan=None):
    t0, t1 = o["t0"], o["t1"]
    out_h, in_h = _face_band(face)
    glass_c = {"top": "#c9dce5", "lit": "#dbe8ee", "shade": "#7e96a5"}
    frame_c = {"top": "#f6f1e4", "lit": "#e8e0cb", "shade": "#c4b598"}
    sill = {"top": "#e2d8c2", "lit": "#d2c5aa", "shade": "#a8987c"}
    # keep sill/head proportions inside the host wall's height
    sill_h = min(WIN_SILL, wh * 0.44)
    head_h = min(WIN_HEAD, wh - 0.6)
    if face["orient"] == "V":
        pos = face["pos"]
        cuboid(lay, cam, pos - in_h - 0.16, t0 - 0.2, 0, face["thick"] + 0.32, (t1 - t0) + 0.4, 0.22,
               sill)
        cuboid(lay, cam, pos - in_h, t0, 0, face["thick"], t1 - t0, sill_h, _mat("wall_int"))
        cuboid(lay, cam, pos - in_h, t0 + 0.06, sill_h, face["thick"], t1 - t0 - 0.12,
               head_h - sill_h, glass_c)
        cuboid(lay, cam, pos - in_h, t0, head_h, face["thick"], t1 - t0, wh - head_h, _mat("wall_int"))
        for mt in (t0 + (t1 - t0) / 3, t0 + 2 * (t1 - t0) / 3):
            cuboid(lay, cam, pos - in_h, mt, sill_h, face["thick"], 0.13, head_h - sill_h, frame_c)
        cuboid(lay, cam, pos - in_h, t0 + 0.06, sill_h + (head_h - sill_h) / 2 - 0.07,
               face["thick"], t1 - t0 - 0.12, 0.14, frame_c)
    else:
        pos = face["pos"]
        cuboid(lay, cam, t0 - 0.2, pos - in_h - 0.16, 0, (t1 - t0) + 0.4, face["thick"] + 0.32, 0.22,
               sill)
        cuboid(lay, cam, t0, pos - in_h, 0, t1 - t0, face["thick"], sill_h, _mat("wall_int"))
        cuboid(lay, cam, t0 + 0.06, pos - in_h, sill_h, t1 - t0 - 0.12, face["thick"],
               head_h - sill_h, glass_c)
        cuboid(lay, cam, t0, pos - in_h, head_h, t1 - t0, face["thick"], wh - head_h, _mat("wall_int"))
        for mt in (t0 + (t1 - t0) / 3, t0 + 2 * (t1 - t0) / 3):
            cuboid(lay, cam, mt, pos - in_h, sill_h, 0.13, face["thick"], head_h - sill_h, frame_c)
        cuboid(lay, cam, t0 + 0.06, pos - in_h, sill_h + (head_h - sill_h) / 2 - 0.07,
               t1 - t0 - 0.12, face["thick"], 0.14, frame_c)
    _curtain_or_glow(lay, glow_lay, cam, face, o, plan, t0, t1)




def _is_cut_face(face, cam):
    """True for exterior walls whose outer side points at the camera."""
    if not face["exterior"]:
        return False
    near_side = face["s0"] if (cam.fx if face["orient"] == "V" else cam.fy) else face["s1"]
    return not near_side


def _draw_cut_wall(lay, shadow_lay, glow_lay, cam, face, plan):
    """Draw camera-facing exterior walls at cut height - flat architectural rim,
    no self-occluding sub-blocks, warm tone matching the palette."""
    out_h, in_h = _face_band(face)
    cut = {"top": "#f2e8d6", "lit": "#e4d8c2", "shade": "#c8b99f"}
    for a0, a1 in _wall_segments(face):
        bx, by, bw, bd = _wall_box(face, a0, a1, 0.0, 0.0, _mat("wall_ext"))
        cuboid(lay, cam, bx, by, 0.0, bw, bd, CUT_H, _mat("wall_ext"))
    # single continuous flat cap over the whole cut face (no per-segment blocks)
    a0 = face["a0"]
    a1 = face["a1"]
    bx, by, bw, bd = _wall_box(face, a0 - 0.02, a1 + 0.02, 0.0, 0.0, _mat("wall_ext"))
    cuboid(lay, cam, bx, by, CUT_H, bw, bd, 0.1, cut)
    west_ext = face["orient"] == "V" and not face["s0"]
    north_ext = face["orient"] == "H" and not face["s0"]
    for o in face["openings"]:
        t0, t1 = o["t0"], o["t1"]
        if face["orient"] == "V":
            cuboid(lay, cam, face["pos"] - out_h, t0, 0.0, face["thick"], t1 - t0, 0.06, _mat("stone"))
            if o["kind"] == "door":
                step_x = face["pos"] - out_h - 1.1 if west_ext else face["pos"] + out_h
                cuboid(lay, cam, step_x, t0 - 0.15, -0.8, 1.1, (t1 - t0) + 0.3, 0.8, _mat("stone"))
                if o["rec"].get("connects_to") == "exterior":
                    gx = face["pos"] + in_h + 0.6 if west_ext else face["pos"] - in_h - 0.6
                    glow(glow_lay, cam, gx, (t0 + t1) / 2, 1.6, 18)
        else:
            cuboid(lay, cam, t0, face["pos"] - out_h, 0.0, t1 - t0, face["thick"], 0.06, _mat("stone"))
            if o["kind"] == "door":
                step_y = face["pos"] - out_h - 1.1 if north_ext else face["pos"] + out_h
                cuboid(lay, cam, t0 - 0.15, step_y, -0.8, (t1 - t0) + 0.3, 1.1, 0.8, _mat("stone"))
                if o["rec"].get("connects_to") == "exterior":
                    gy = face["pos"] + in_h + 0.6 if north_ext else face["pos"] - in_h - 0.6
                    glow(glow_lay, cam, (t0 + t1) / 2, gy, 1.6, 18)


def draw_walls(lay, shadow_lay, glow_lay, cam, plan, faces):
    def depth_key(f):
        mid = (f["a0"] + f["a1"]) / 2
        if f["orient"] == "V":
            vx, vy = cam.view(f["pos"], mid)
        else:
            vx, vy = cam.view(mid, f["pos"])
        return vx + vy
    for face in sorted(faces, key=depth_key):
        if _is_cut_face(face, cam):
            _draw_cut_wall(lay, shadow_lay, glow_lay, cam, face, plan)
            continue
        wh = WALL_H if face["exterior"] else PART_H
        draw_wall_segments(lay, shadow_lay, cam, face, wh)
        for o in sorted(face["openings"], key=lambda o: o["t0"]):
            if o["kind"] == "door":
                door_assembly(lay, shadow_lay, cam, face, o, wh)
            elif face["exterior"]:
                window_assembly(lay, shadow_lay, glow_lay, cam, face, o, wh, plan)

# --------------------------------------------------------------------------
# furniture placement (presentation only; geometry stays canonical)
# --------------------------------------------------------------------------

def _door_zone(room, door):
    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
    side, off = door["side"], door["offset_ft"]
    leaf = min(2.5, _side_span(room, side) - off)
    if side == "north":
        return (x + off, y, leaf, leaf)
    if side == "south":
        return (x + off, y + d - leaf, leaf, leaf)
    if side == "west":
        return (x, y + off, leaf, leaf)
    return (x + w - leaf, y + off, leaf, leaf)


def _hits(r, zones):
    return any(not (r[0] + r[2] <= z[0] or z[0] + z[2] <= r[0]
                    or r[1] + r[3] <= z[1] or z[1] + z[3] <= r[1]) for z in zones)


def _furnish_living(lay, shadow_lay, glow_lay, cam, room, plan, ok, w, d, x, y):
    sofa_r = None
    if w >= d + 1.5:
        for sy0 in (y + 0.9, y + d - 3.4):
            cand = (x + (w - 6.6) / 2, sy0, 6.6, 2.7)
            if ok(cand):
                sofa_r = cand
                break
        if sofa_r:
            back = "n" if sofa_r[1] < y + d / 2 else "s"
            sofa(lay, shadow_lay, cam, sofa_r, back)
            ct = (sofa_r[0] + sofa_r[2] / 2 - 1.6, (sofa_r[1] + sofa_r[3] + y + d) / 2 - 0.9, 3.2, 1.8)
            if ok(ct):
                coffee_table(lay, shadow_lay, cam, ct[0], ct[1], ct[2], ct[3], 1.1)
            tv_y = y + 0.5 if back == "s" else y + d - 1.6
            tvr = (x + (w - 4.4) / 2, tv_y, 4.4, 1.1)
            if ok(tvr):
                tv_unit(lay, shadow_lay, cam, tvr[0], tvr[1], tvr[2], tvr[3])
    else:
        for sx0 in (x + 0.9, x + w - 3.4):
            cand = (sx0, y + (d - 6.6) / 2, 2.7, 6.6)
            if ok(cand):
                sofa_r = cand
                break
        if sofa_r:
            back = "w" if sofa_r[0] < x + w / 2 else "e"
            sofa(lay, shadow_lay, cam, sofa_r, back)
            ct = ((sofa_r[0] + sofa_r[2] + x + w) / 2 - 0.9, sofa_r[1] + sofa_r[3] / 2 - 1.6, 1.8, 3.2)
            if ok(ct):
                coffee_table(lay, shadow_lay, cam, ct[0], ct[1], ct[2], ct[3], 1.1)
            tv_x = x + 0.5 if back == "e" else x + w - 1.6
            tvr = (tv_x, y + (d - 4.4) / 2, 1.1, 4.4)
            if ok(tvr):
                tv_unit(lay, shadow_lay, cam, tvr[0], tvr[1], tvr[2], tvr[3])
    for ax, ay in ((x + 0.8, y + d - 4.0), (x + w - 3.6, y + 0.8)):
        if ok((ax, ay, 2.6, 2.6)):
            armchair(lay, shadow_lay, cam, ax, ay, 2.6)
            break
    for lx, ly in ((x + 2.6, y + d - 5.6), (x + w - 5.4, y + 2.4)):
        if ok((lx, ly, 1.2, 1.2), inset=1.4):
            floor_lamp(lay, glow_lay, cam, lx - 0.4, ly - 0.4)
            break
    glow(glow_lay, cam, x + w / 2, y + d / 2, 2.0, 12)


def _furnish_bedroom(lay, shadow_lay, glow_lay, cam, room, plan, ok, w, d, x, y):
    small = min(w, d) < 7.5
    bw, bl = (3.4, 6.4) if small else (5.0, 6.8)
    cands = []
    if w >= bw + 1.6:
        cands += [(x + (w - bw) / 2, y + 0.7, bw, bl), (x + (w - bw) / 2, y + d - bl - 0.7, bw, bl)]
    if d >= bw + 1.6:
        cands += [(x + 0.7, y + (d - bw) / 2, bl, bw), (x + w - bl - 0.7, y + (d - bw) / 2, bl, bw)]
    bed_r = next((c for c in cands if ok(c)), None)
    if bed_r:
        head = ("n" if abs(bed_r[1] - y) < 0.8
                else "s" if abs(bed_r[1] + bed_r[3] - y - d) < 0.8
                else "w" if abs(bed_r[0] - x) < 0.8 else "e")
        bed(lay, shadow_lay, cam, bed_r, head)
        if head in ("n", "s"):
            hy = bed_r[1] + 0.2 if head == "n" else bed_r[1] + bed_r[3] - 1.6
            spots = [(bed_r[0] - 1.7, hy, 1.4, 1.4), (bed_r[0] + bed_r[2] + 0.3, hy, 1.4, 1.4)]
            for s in spots:
                if ok(s):
                    side_table(lay, shadow_lay, cam, s[0], s[1])
                    glow(glow_lay, cam, s[0] + 0.7, s[1] + 0.5, 1.0, 26)
        else:
            hx = bed_r[0] + 0.2 if head == "w" else bed_r[0] + bed_r[2] - 1.6
            spots = [(hx, bed_r[1] - 1.7, 1.4, 1.4), (hx, bed_r[1] + bed_r[3] + 0.3, 1.4, 1.4)]
            for s in spots:
                if ok(s):
                    side_table(lay, shadow_lay, cam, s[0], s[1])
                    glow(glow_lay, cam, s[0] + 0.5, s[1] + 0.7, 1.0, 26)
        for cand in ((x + 0.6, y + 0.6, 3.0, 2.2), (x + w - 3.6, y + d - 2.8, 3.0, 2.2)):
            if ok(cand) and not _hits(cand, [bed_r]):
                wardrobe(lay, shadow_lay, cam, cand[0], cand[1], cand[2], cand[3])
                break
    if y + d >= plan["plot"]["depth_ft"] - 0.01:
        px, py = x + w - 2.4, y + d - 2.4
        if ok((px, py, 1.6, 1.6), inset=1.2):
            plant(lay, shadow_lay, cam, px, py)

def furnish_room(lay, shadow_lay, glow_lay, cam, room, plan, seed):
    kind = room.get("kind", "habitable")
    rid = room["id"]
    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
    zones = [_door_zone(room, dr) for dr in plan["doors"] if dr["room_id"] == rid]

    def ok(rr, inset=0.7):
        rx, ry, rw, rd = rr
        if rx < x + inset or ry < y + inset or rx + rw > x + w - inset or ry + rd > y + d - inset:
            return False
        return not _hits((rx, ry, rw, rd), zones)

    if kind == "habitable":
        if rid == "living":
            _furnish_living(lay, shadow_lay, glow_lay, cam, room, plan, ok, w, d, x, y)
        elif rid == "dining":
            tw, td = (min(5.2, w - 3), min(2.9, d - 2.6)) if w >= d else (min(2.9, w - 2.6), min(5.2, d - 3))
            if tw >= 2.6 and td >= 2.2:
                dining_set(lay, shadow_lay, cam, x + (w - tw) / 2, y + (d - td) / 2, tw, td)
        else:
            _furnish_bedroom(lay, shadow_lay, glow_lay, cam, room, plan, ok, w, d, x, y)
    elif kind == "kitchen":
        _furnish_kitchen(lay, shadow_lay, cam, room, plan, seed)
    elif kind == "bathroom":
        bath_set(lay, shadow_lay, cam, room, seed)
    elif kind == "staircase":
        stair_set(lay, shadow_lay, cam, room)
    elif kind == "parking":
        car_set(lay, shadow_lay, glow_lay, cam, room)
    elif kind == "puja":
        puja_set(lay, shadow_lay, glow_lay, cam, room)


def _furnish_kitchen(lay, shadow_lay, cam, room, plan, seed):
    rid = room["id"]
    x, y, w, d = room["x_ft"], room["y_ft"], room["width_ft"], room["depth_ft"]
    door_ops = {side: [] for side in ("north", "south", "west", "east")}
    for dr in plan["doors"]:
        if dr["room_id"] != rid:
            continue
        side = dr["side"]
        span = _side_span(room, side)
        door_ops[side].append((dr["offset_ft"], min(2.5, span - dr["offset_ft"])))

    def spans(length, side):
        ops = sorted((o, o + ln) for o, ln in door_ops[side])
        res, cur = [], 0.0
        for a, b in ops:
            if a - cur > 2.0:
                res.append((cur, a))
            cur = max(cur, b)
        if length - cur > 2.0:
            res.append((cur, length))
        return res

    counters = []
    for a, b in spans(w, "north"):
        counters.append(("north", a, b))
    for a, b in spans(w, "south"):
        counters.append(("south", a, b))
    for a, b in spans(d, "west"):
        counters.append(("west", a, b - 2.7) if b - a > 4.6 else ("west", a, b))
    for a, b in spans(d, "east"):
        counters.append(("east", a, b))
    if not counters:
        return
    kitchen_set(lay, shadow_lay, cam, room, counters, seed)

    runs = sorted(counters, key=lambda c: c[2] - c[1], reverse=True)
    main = runs[0]
    if main[2] - main[1] > 4.2:
        mid = (main[1] + main[2]) / 2
        if main[0] == "north":
            _sink_overlay(lay, cam, x + mid - 1.0, y + 0.9)
            _hob_overlay(lay, cam, x + mid + 0.7, y + 0.9)
        elif main[0] == "south":
            _sink_overlay(lay, cam, x + mid - 1.0, y + d - 1.3)
            _hob_overlay(lay, cam, x + mid + 0.7, y + d - 1.3)
        elif main[0] == "west":
            _sink_overlay(lay, cam, x + 0.9, y + mid - 0.9)
            _hob_overlay(lay, cam, x + 0.9, y + mid + 0.8)
        else:
            _sink_overlay(lay, cam, x + w - 1.3, y + mid - 0.9)
            _hob_overlay(lay, cam, x + w - 1.3, y + mid + 0.8)
    for side, a, b in runs:
        if side == "west" and b - a > 2.6:
            fridge(lay, shadow_lay, cam, x + 0.1, y + b - 1.5)
            break
        if side == "east" and b - a > 2.6:
            fridge(lay, shadow_lay, cam, x + w - 2.7, y + b - 1.5)
            break
        if side == "north" and b - a > 2.6:
            fridge(lay, shadow_lay, cam, x + b - 2.3, y + 0.1)
            break
        if side == "south" and b - a > 2.6:
            fridge(lay, shadow_lay, cam, x + b - 2.3, y + d - 2.6)
            break
    if main[0] == "north" and main[2] - main[1] > 2.2:
        upper_cabinet(lay, cam, x + main[1] + 0.2, y + 0.1, main[2] - main[1] - 0.4, 1.5)

# --------------------------------------------------------------------------
# scene: sky, ground, landscape
# --------------------------------------------------------------------------

def _font(size, bold=False):
    for name in (["arialbd.ttf", "arial.ttf"] if bold else ["arial.ttf"]):
        try:
            return ImageFont.truetype(name, int(size))
        except OSError:
            continue
    return ImageFont.load_default()


def _depth_of(cam, x, y):
    vx, vy = cam.view(x, y)
    return vx + vy


def _stable_seed(*parts):
    return sum(ord(ch) for ch in "|".join(str(p) for p in parts)) & 0xFFFF


def paint_sky(base, cam):
    """Paint a clean, neutral sky gradient."""
    dr = ImageDraw.Draw(base)
    top, bot = _rgb("#edf0f3"), _rgb("#f7f4ec")
    for y in range(cam.CH):
        t = min(1.0, y / max(1, int(cam.CH * 0.5)))
        col = tuple(int(a + (b - a) * t) for a, b in zip(top, bot))
        dr.line((0, y, cam.CW, y), fill=col)


LAWN = {"top": "#ccd6bd", "lit": "#c1ccb2", "shade": "#a9b699"}


def _pave_strip(lay, cam, x, y, w, d, stripe_dir, mat):
    if w <= 0 or d <= 0:
        return
    pts = [P(cam, x, y, -0.79), P(cam, x + w, y, -0.79),
           P(cam, x + w, y + d, -0.79), P(cam, x, y + d, -0.79)]
    lay.grad_quad(pts, mat["top"], mat["lit"])
    if stripe_dir == "y":
        for i in range(1, int(d / 2.4) + 1):
            yy = y + i * 2.4
            lay.line(P(cam, x, yy, -0.77), P(cam, x + w, yy, -0.77), mat["shade"], width=1, alpha=140)
    else:
        for i in range(1, int(w / 2.4) + 1):
            xx = x + i * 2.4
            lay.line(P(cam, xx, y, -0.77), P(cam, xx, y + d, -0.77), mat["shade"], width=1, alpha=140)


def _driveway(lay, cam, plan):
    w, d = cam.w, cam.d
    parking = next((r for r in plan["rooms"] if r.get("kind") == "parking"), None)
    if parking is None:
        return
    px, py, pw, pd = parking["x_ft"], parking["y_ft"], parking["width_ft"], parking["depth_ft"]
    paver = {"top": "#cdc5b4", "lit": "#bcb29c", "shade": "#948a72"}
    if (not cam.fx and abs(px + pw - w) < 0.02) or (cam.fx and abs(px) < 0.02):
        x0, x1 = (px + pw, w + 7.0) if not cam.fx else (-7.0, px)
        _pave_strip(lay, cam, x0, py - 0.35, x1 - x0, pd + 0.7, "y", paver)
    elif (not cam.fy and abs(py + pd - d) < 0.02) or (cam.fy and abs(py) < 0.02):
        y0, y1 = (py + pd, d + 7.0) if not cam.fy else (-7.0, py)
        _pave_strip(lay, cam, px - 0.35, y0, pw + 0.7, y1 - y0, "x", paver)


def _entry_walk(lay, cam, plan):
    w, d = cam.w, cam.d
    door = next((dr for dr in plan["doors"] if dr.get("connects_to") == "exterior"), None)
    if door is None:
        return
    room = next(r for r in plan["rooms"] if r["id"] == door["room_id"])
    side, off = door["side"], door["offset_ft"]
    stone = {"top": "#ded6c4", "lit": "#cfc4ac", "shade": "#a2947a"}
    if side in ("north", "south"):
        cx = room["x_ft"] + off + 1.5
        a, b = cx - 1.7, cx + 1.7
        if side == "south":
            y0 = room["y_ft"] + room["depth_ft"]
            y1 = (d + 4.0) if not cam.fy else min(d + 4.0, y0 + 9.0)
            _pave_strip(lay, cam, a, y0, b - a, y1 - y0, "x", stone)
        else:
            y1 = room["y_ft"]
            y0 = -4.0 if cam.fy else max(y1 - 9.0, -4.0)
            _pave_strip(lay, cam, a, y0, b - a, y1 - y0, "x", stone)
    else:
        cy = room["y_ft"] + off + 1.5
        a, b = cy - 1.7, cy + 1.7
        if side == "east":
            x0 = room["x_ft"] + room["width_ft"]
            x1 = (w + 4.0) if not cam.fx else min(w + 4.0, x0 + 9.0)
            _pave_strip(lay, cam, x0, a, x1 - x0, b - a, "y", stone)
        else:
            x1 = room["x_ft"]
            x0 = -4.0 if cam.fx else max(x1 - 9.0, -4.0)
            _pave_strip(lay, cam, x0, a, x1 - x0, b - a, "y", stone)

def _boundary_wall(lay, shadow_lay, cam, plan):
    w, d = cam.w, cam.d
    mat = {"top": "#e3dac6", "lit": "#d0c3a8", "shade": "#a5957a"}
    cap = {"top": "#efe7d4", "lit": "#ddd2b8", "shade": "#b3a488"}
    th = 0.4
    fx_edge = (w if cam.fx else 0.0) + (0.55 if cam.fx else -0.55)
    fy_edge = (d if cam.fy else 0.0) + (0.55 if cam.fy else -0.55)

    def run(is_x, fixed, a0, a1):
        if a1 - a0 < 0.5:
            return
        if is_x:
            soft_shadow(shadow_lay, cam, a0, fixed - th / 2, a1 - a0, th, alpha=45)
            cuboid(lay, cam, a0, fixed - th / 2, -0.8, a1 - a0, th, 2.5, mat)
            cuboid(lay, cam, a0 - 0.08, fixed - th / 2 - 0.08, 1.7, a1 - a0 + 0.16, th + 0.16, 0.14, cap)
        else:
            soft_shadow(shadow_lay, cam, fixed - th / 2, a0, th, a1 - a0, alpha=45)
            cuboid(lay, cam, fixed - th / 2, a0, -0.8, th, a1 - a0, 2.5, mat)
            cuboid(lay, cam, fixed - th / 2 - 0.08, a0 - 0.08, 1.7, th + 0.16, a1 - a0 + 0.16, 0.14, cap)

    run(True, fy_edge, -0.55, w + 0.55)
    run(False, fx_edge, -0.55, d + 0.55)
    for t in (-0.55, (w + 0.55) / 2, w + 0.55):
        cuboid(lay, cam, t - 0.35, fy_edge - 0.35, -0.8, 0.7, 0.7, 3.4, mat)
    for t in (-0.55, (d + 0.55) / 2, d + 0.55):
        cuboid(lay, cam, fx_edge - 0.35, t - 0.35, -0.8, 0.7, 0.7, 3.4, mat)


def _tree(lay, shadow_lay, cam, tx, ty, s=1.0, seed=0):
    rng = random.Random(seed)
    soft_shadow(shadow_lay, cam, tx - 0.9 * s, ty - 0.9 * s, 1.8 * s, 1.8 * s,
                alpha=64, ex=0.4, shift=(1.6, 1.8))
    cuboid(lay, cam, tx - 0.18, ty - 0.18, -0.8, 0.36, 0.36, 2.6 * s,
           {"top": "#8a6a48", "lit": "#74563a", "shade": "#57402a"})
    greens = [("#7d9b6a", "#69875a"), ("#6f8f5f", "#5c7a4e"), ("#8aa577", "#75905f")]
    blobs = ((-0.7, -0.4, 1.35), (0.75, 0.15, 1.1), (0.05, 0.8, 1.25), (-0.15, -1.0, 0.95), (0.95, -0.55, 0.8))
    for dx, dy, rr in blobs:
        c = P(cam, tx + dx * s, ty + dy * s, (2.6 + rr * 0.9) * s)
        r = rr * s * cam.sx * 0.9
        g = greens[rng.randrange(len(greens))]
        lay.ellipse((c[0] - r, c[1] - r * 0.86, c[0] + r, c[1] + r * 0.86), g[0])
        c2 = P(cam, tx + dx * s + 0.3 * s, ty + dy * s + 0.15 * s, (2.6 + rr * 0.9 + 0.5) * s)
        lay.ellipse((c2[0] - r * 0.6, c2[1] - r * 0.5, c2[0] + r * 0.6, c2[1] + r * 0.5), g[1], alpha=220)


def _far_trees(lay, shadow_lay, cam, plan):
    w, d = cam.w, cam.d
    seed = _stable_seed(plan["design_id"], "tree")
    fx_edge = w if cam.fx else 0.0
    off_x = 2.6 if fx_edge > 0 else -2.6
    _tree(lay, shadow_lay, cam, fx_edge + off_x, d * 0.22, 1.15, seed + 1)
    _tree(lay, shadow_lay, cam, fx_edge + off_x, d * 0.78, 0.95, seed + 2)
    fy_edge = d if cam.fy else 0.0
    off_y = 2.6 if fy_edge > 0 else -2.6
    _tree(lay, shadow_lay, cam, w * 0.5, fy_edge + off_y, 1.0, seed + 3)

def paint_ground(lay, shadow_lay, cam, plan):
    w, d = cam.w, cam.d
    m = 90.0
    pts = [P(cam, -m, -m, -0.8), P(cam, w + m, -m, -0.8),
           P(cam, w + m, d + m, -0.8), P(cam, -m, d + m, -0.8)]
    lay.grad_quad(pts, tint(LAWN["top"], 0.10), shade(LAWN["top"], 0.22))
    soft_shadow(shadow_lay, cam, -0.9, -0.9, w + 1.8, d + 1.8, alpha=52, ex=0.9, shift=(0.9, 1.1))
    _driveway(lay, cam, plan)
    _entry_walk(lay, cam, plan)
    # grass apron around the plot slab (keeps the plot outline readable)
    cuboid(lay, cam, -0.9, -0.9, -0.8, w + 1.8, d + 1.8, 0.8,
           {"top": LAWN["lit"], "lit": LAWN["top"], "shade": LAWN["shade"]})
    _boundary_wall(lay, shadow_lay, cam, plan)


def _bush(lay, cam, bx, by, s, seed):
    contact_shadow(lay, cam, bx - 0.6 * s, by - 0.6 * s, 1.2 * s, 1.2 * s, alpha=60)
    rng = random.Random(seed)
    for dx, dy, rr in ((-0.3, -0.2, 0.55), (0.35, 0.1, 0.45), (0.0, 0.4, 0.5)):
        c = P(cam, bx + dx * s, by + dy * s, 0.45 * s)
        r = rr * s * cam.sx
        lay.ellipse((c[0] - r, c[1] - r * 0.8, c[0] + r, c[1] + r * 0.8), "#7d9b6a")
        c2 = P(cam, bx + dx * s + 0.15 * s, by + dy * s, 0.75 * s)
        lay.ellipse((c2[0] - r * 0.55, c2[1] - r * 0.44, c2[0] + r * 0.55, c2[1] + r * 0.44),
                    "#8fae7c", alpha=230)


def _near_shrubs(lay, cam, plan):
    """Minimal exterior treatment - clean ground plane only, no floating objects."""
    pass  # Intentionally empty - clean architectural presentation

# --------------------------------------------------------------------------
# annotations + main entry
# --------------------------------------------------------------------------

def draw_labels(target, cam, plan):
    """Minimal room tags: name only, small, quiet contrast - no dimension text."""
    f = _font(10 * SS, bold=True)
    dr = ImageDraw.Draw(target)
    for room in plan["rooms"]:
        if room["width_ft"] * room["depth_ft"] < 20:
            continue
        cx = room["x_ft"] + room["width_ft"] / 2
        cy = room["y_ft"] + room["depth_ft"] / 2
        c = P(cam, cx, cy, 0.08)
        halo = with_alpha("#f6f2e8", 180)
        dr.text(c, room["name"].upper(), font=f, fill=with_alpha("#6a5a44", 210),
                anchor="mm", stroke_width=SS, stroke_fill=halo)


def draw_title(base, plan):
    dr = ImageDraw.Draw(base)
    ink, mid = "#4a3b28", "#7a6a52"
    w, d = plan["plot"]["width_ft"], plan["plot"]["depth_ft"]
    facing = str(plan["plot"].get("facing", "")).upper()
    head = "%s   |   %g FT x %g FT   |   %s FACING" % (
        plan["design_id"].replace("_", " ").upper(), w, d, facing)
    prog = []
    if plan.get("bedrooms"):
        prog.append("%d BEDROOM%s" % (plan["bedrooms"], "S" if plan["bedrooms"] > 1 else ""))
    if plan.get("bathrooms"):
        prog.append("%d BATHROOM%s" % (plan["bathrooms"], "S" if plan["bathrooms"] > 1 else ""))
    if any(r.get("kind") == "parking" for r in plan["rooms"]):
        prog.append("COVERED PARKING")
    dr.text((34 * SS, base.height - 152 * SS), head, font=_font(21 * SS, True), fill=ink)
    dr.text((34 * SS, base.height - 116 * SS), "  -  ".join(prog), font=_font(12 * SS, True), fill=mid)
    dr.text((34 * SS, base.height - 94 * SS),
            "deterministic architectural visualization generated from the canonical plan JSON",
            font=_font(11 * SS), fill=mid)
    dr.line((34 * SS, base.height - 170 * SS, base.width - 34 * SS, base.height - 170 * SS),
            fill="#b9ad93", width=SS)
    disc = plan.get("disclaimer", "")
    if disc:
        dr.multiline_text((34 * SS, base.height - 70 * SS), textwrap.fill(disc, 180),
                          font=_font(9 * SS), fill=mid, spacing=int(2 * SS))


def draw_compass(base, cam):
    dr = ImageDraw.Draw(base)
    cx, cy, r = base.width - 96 * SS, 92 * SS, 44 * SS
    dr.ellipse((cx - r, cy - r, cx + r, cy + r), fill=with_alpha("#fdf8ec", 130))
    dr.ellipse((cx - r, cy - r, cx + r, cy + r), outline=with_alpha("#7a6a52", 210), width=2 * SS)
    nd = cam.north_dir()
    n = math.hypot(nd[0], nd[1]) or 1.0
    ux, uy = nd[0] / n, nd[1] / n
    dr.line((cx - ux * r * 0.8, cy - uy * r * 0.8, cx + ux * r * 0.8, cy + uy * r * 0.8),
            fill="#7a6a52", width=2 * SS)
    ax, ay = cx + ux * r * 0.8, cy + uy * r * 0.8
    dr.polygon([(ax + ux * 8 * SS, ay + uy * 8 * SS),
                (ax - uy * 5 * SS - ux * 8 * SS, ay + ux * 5 * SS - uy * 8 * SS),
                (ax + uy * 5 * SS - ux * 8 * SS, ay - ux * 5 * SS - uy * 8 * SS)], fill="#8a5a32")
    dr.text((cx, cy - r - 12 * SS), "N", font=_font(13 * SS, True), fill="#4a3b28", anchor="mm")


def render_3d(plan, output_path, geometry_path=None):
    """Render a 3D architectural visualization of the plan.
    
    Args:
        plan: Either a plan dict or a path to a JSON plan file.
        output_path: Path for the output PNG image.
        geometry_path: Optional path to save the geometry manifest JSON.
    
    Returns:
        The geometry manifest dict.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load plan from file if a path was given
    if isinstance(plan, (str, Path)):
        plan = json.loads(Path(plan).read_text(encoding="utf-8"))

    W, H = CAN_W * SS, CAN_H * SS
    cam = Camera(plan, canvas=(W, H))
    cam.fit(plan)

    base = Image.new("RGB", (W, H))
    paint_sky(base, cam)

    lay = Lay(W, H)          # geometry layer
    shadow_lay = Lay(W, H)   # soft shadows, composited below geometry
    glow_lay = Lay(W, H)     # light glows, composited above geometry

    paint_ground(lay, shadow_lay, cam, plan)

    # unified painter's list: room contents and wall faces share one depth sort
    items = []
    for room in plan["rooms"]:
        dep = _depth_of(cam, room["x_ft"] + room["width_ft"] / 2, room["y_ft"] + room["depth_ft"] / 2)
        items.append((dep, 0, room))
    faces = build_wall_faces(plan)
    for face in faces:
        mid = (face["a0"] + face["a1"]) / 2
        if face["orient"] == "V":
            vx, vy = cam.view(face["pos"], mid)
        else:
            vx, vy = cam.view(mid, face["pos"])
        items.append((vx + vy, 1, face))
    items.sort(key=lambda t: (t[0], t[1]))

    for _, kind, obj in items:
        if kind == 0:
            seed = _stable_seed(plan["design_id"], obj["id"])
            floor_finish(lay, cam, obj, seed)
            furnish_room(lay, shadow_lay, glow_lay, cam, obj, plan, seed)
        elif _is_cut_face(obj, cam):
            _draw_cut_wall(lay, shadow_lay, glow_lay, cam, obj, plan)
        else:
            wh = WALL_H if obj["exterior"] else PART_H
            draw_wall_segments(lay, shadow_lay, cam, obj, wh)
            for o in sorted(obj["openings"], key=lambda o: o["t0"]):
                if o["kind"] == "door":
                    door_assembly(lay, shadow_lay, cam, obj, o, wh)
                elif obj["exterior"]:
                    window_assembly(lay, shadow_lay, glow_lay, cam, obj, o, wh, plan)

    lay.dr = ImageDraw.Draw(lay.im)

    _near_shrubs(lay, cam, plan)

    # composite: ground+geometry first, shadows tucked under geometry, glows on top
    base = Image.alpha_composite(base.convert("RGBA"), lay.im)
    base = Image.alpha_composite(base, shadow_lay.im)
    draw_labels(base, cam, plan)
    base = Image.alpha_composite(base, glow_lay.im)
    base = base.convert("RGB")
    draw_title(base, plan)
    draw_compass(base, cam)

    resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
    base.resize((CAN_W, CAN_H), resample).save(output_path)

    manifest = {"plot": dict(plan["plot"]),
                "rooms": [{k: r[k] for k in ("id", "x_ft", "y_ft", "width_ft", "depth_ft")}
                          for r in plan["rooms"]]}
    if geometry_path:
        Path(geometry_path).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
