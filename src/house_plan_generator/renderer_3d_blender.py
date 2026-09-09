"""Blender-based procedural 3D architectural visualization renderer.

Replaces the Pillow cutaway as the primary 3D presentation pipeline.
The canonical plan JSON remains the single source of truth for geometry;
this module only decides how the house is presented.

Run inside Blender's Python (e.g. via run_blender_render.py):
    render_3d_blender(plan_or_path, output_path, samples=..., resolution=...)
"""

import json
import math
import sys
from pathlib import Path

import bpy

from . import blender_geom
from .blender_materials import build_materials
from . import blender_walls as BW
from . import blender_rooms
from . import blender_lighting as BL


def _clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _choose_cam_side(plan):
    """Look from the plot corner opposite the entrance, favoring the street
    side so parking/driveway read correctly."""
    facing = str(plan["plot"].get("facing", "south")).lower()
    order = {
        "north": ("north", "east"),
        "south": ("south", "east"),
        "east": ("east", "south"),
        "west": ("west", "south"),
        "northeast": ("north", "east"),
        "northwest": ("north", "west"),
        "southeast": ("south", "east"),
        "southwest": ("south", "west"),
    }
    return order.get(facing, ("south", "east"))


def _mark_cut_sides(cam_side):
    """Camera-facing plot sides get the low cutaway; far sides stay tall."""
    sides = {"west": False, "east": False, "north": False, "south": False}
    for s in cam_side:
        sides[s] = True
    BW.CUT_SIDES.update(sides)


def build_scene(plan, cam_side=None, samples=192, resolution=(2400, 1800)):
    """Build the full Blender scene from a canonical plan dict."""
    _clear_scene()
    M = build_materials()

    if cam_side is None:
        cam_side = _choose_cam_side(plan)
    _mark_cut_sides(cam_side)

    # geometry
    BW.build_floors(plan, M)
    BW.build_walls(plan, M)
    BW.build_opening_trims(plan, M)
    for room in plan["rooms"]:
        blender_rooms.furnish_room(plan, M, room)
    BW.build_site(plan, M)

    # presentation
    BL.setup_world()
    BL.setup_sun(plan, cam_side)
    BL.setup_fill(plan, cam_side)
    BL.setup_camera(plan, cam_side)
    BL.render_settings(samples=samples, resolution=resolution)
    return M


# ------------------------------------------------------------- manifest ----

def build_manifest(plan):
    """Geometry manifest (same contract as the Pillow renderer)."""
    return {"plot": dict(plan["plot"]),
            "rooms": [{k: r[k] for k in ("id", "x_ft", "y_ft",
                                         "width_ft", "depth_ft")}
                      for r in plan["rooms"]]}


def render_3d_blender(plan, output_path, geometry_path=None, samples=192,
                      resolution=(2400, 1800), sheet=True):
    """Render a canonical plan to a presentation-quality 3D PNG.

    Args:
        plan: canonical plan dict or path to plan JSON.
        output_path: output PNG path.
        geometry_path: optional path to write the geometry manifest JSON.
        samples: Cycles samples (quality vs speed).
        resolution: output pixel size.
        sheet: draw the title/summary/north presentation overlay.

    Returns:
        The geometry manifest dict (same contract as the Pillow renderer).
    """
    if isinstance(plan, (str, Path)):
        plan = json.loads(Path(plan).read_text(encoding="utf-8"))
    # Blender resolves render paths against its own working directory, not the
    # process cwd - always give it an absolute path.
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    M = build_scene(plan, samples=samples, resolution=resolution)

    cam = bpy.context.scene.camera
    BL.render(output_path)

    if sheet:
        _draw_sheet(plan, output_path)

    manifest = build_manifest(plan)
    if geometry_path:
        Path(geometry_path).write_text(json.dumps(manifest, indent=2) + "\n",
                                       encoding="utf-8")
    return manifest


# --------------------------------------------------------------- sheet ----

def _draw_sheet(plan, image_path):
    """Title strip + summary overlay. Only runs when Pillow is available
    (project-side runner applies it after Blender exits; inside Blender's
    bare Python it no-ops)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return False

    p = Path(image_path)
    img = Image.open(p).convert("RGB")
    W, H = img.size
    strip_h = int(H * 0.085)
    sheet = Image.new("RGB", (W, H + strip_h), "#faf6ec")
    sheet.paste(img, (0, strip_h))
    dr = ImageDraw.Draw(sheet)
    ink, mid = "#3f3426", "#7a6c54"

    def font(sz, bold=False):
        for name in (["arialbd.ttf"] if bold else []) + ["arial.ttf",
                                                          "DejaVuSans.ttf"]:
            try:
                return ImageFont.truetype(name, sz)
            except Exception:
                continue
        return ImageFont.load_default()

    w = plan["plot"]["width_ft"]
    d = plan["plot"]["depth_ft"]
    facing = str(plan["plot"].get("facing", "")).upper()
    head = f"{plan['design_id'].replace('_', ' ').upper()}   |   {w} x {d} FT   |   {facing} FACING"
    prog = []
    if plan.get("bedrooms"):
        prog.append(f"{plan['bedrooms']} BEDROOM{'S' if plan['bedrooms'] > 1 else ''}")
    if plan.get("bathrooms"):
        prog.append(f"{plan['bathrooms']} BATHROOM{'S' if plan['bathrooms'] > 1 else ''}")
    if any(r.get("kind") == "parking" for r in plan["rooms"]):
        prog.append("COVERED PARKING")
    dr.rectangle((0, 0, W, strip_h), fill="#faf6ec")
    dr.text((28, strip_h * 0.18), head, font=font(38, True), fill=ink)
    dr.text((28, strip_h * 0.62), "  ·  ".join(prog),
            font=font(24), fill=mid)
    disc = plan.get("disclaimer", "")
    if disc:
        import textwrap
        dr.text((28, H + strip_h - 26), textwrap.fill(disc, 200)[:160],
                font=font(15), fill=mid)
    sheet.save(p)
    return True


# ------------------------------------------------------------------ CLI ----

def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--geometry", default=None,
                    help="optional path for the geometry manifest JSON")
    ap.add_argument("--samples", type=int, default=128)
    ap.add_argument("--width", type=int, default=2400)
    ap.add_argument("--height", type=int, default=1800)
    ap.add_argument("--no-sheet", action="store_true")
    args = ap.parse_args(argv)
    render_3d_blender(args.plan, args.out, geometry_path=args.geometry,
                      samples=args.samples,
                      resolution=(args.width, args.height),
                      sheet=not args.no_sheet)


if __name__ == "__main__":
    main()
