"""Runner: executes the Blender renderer for one or more canonical plans.

Usage (from project root, with the portable Blender in tools/blender):
    python run_blender_render.py --plans design_001 design_005 \
        --outdir generated/blender_3d --samples 128
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent
BLENDER = ROOT / "tools" / "blender" / "blender.exe"
SCRIPT = ROOT / "blender_entry.py"


def _apply_sheet(plan_path: Path, image_path: Path):
    """Title strip + summary overlay applied project-side (Pillow lives here,
    not in Blender's bundled Python)."""
    from PIL import Image, ImageDraw, ImageFont

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    img = Image.open(image_path).convert("RGB")
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
    head = (f"{plan['design_id'].replace('_', ' ').upper()}   |   "
            f"{w} x {d} FT   |   {facing} FACING")
    prog = []
    if plan.get("bedrooms"):
        prog.append(f"{plan['bedrooms']} BEDROOM{'S' if plan['bedrooms'] > 1 else ''}")
    if plan.get("bathrooms"):
        prog.append(f"{plan['bathrooms']} BATHROOM{'S' if plan['bathrooms'] > 1 else ''}")
    if any(r.get("kind") == "parking" for r in plan["rooms"]):
        prog.append("COVERED PARKING")
    dr.rectangle((0, 0, W, strip_h), fill="#faf6ec")
    dr.text((28, strip_h * 0.16), head, font=font(40, True), fill=ink)
    dr.text((28, strip_h * 0.62), "  -  ".join(prog), font=font(24), fill=mid)
    import textwrap
    disc = plan.get("disclaimer", "")
    if disc:
        dr.text((28, H + strip_h - 30), textwrap.fill(disc, 210).splitlines()[0][:170],
                font=font(16), fill=mid)
    sheet.save(image_path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plans", nargs="+", required=True,
                    help="design ids, e.g. design_001, or 'all'")
    ap.add_argument("--outdir", default="generated/blender_3d")
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--width", type=int, default=2400)
    ap.add_argument("--height", type=int, default=1800)
    ap.add_argument("--no-sheet", action="store_true")
    args = ap.parse_args()

    if not BLENDER.exists():
        print(f"Blender not found at {BLENDER}", file=sys.stderr)
        return 2
    outdir = ROOT / args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    if args.plans == ["all"]:
        plan_paths = sorted((ROOT / "plans").glob("design_*.json"))
    else:
        plan_paths = [ROOT / "plans" / f"{p}.json" for p in args.plans]

    failures = 0
    for pp in plan_paths:
        if not pp.exists():
            print(f"MISSING plan: {pp}", file=sys.stderr)
            failures += 1
            continue
        out = outdir / f"{pp.stem}_3d_blender.png"
        manifest_out = outdir / f"{pp.stem}_geometry.json"
        cmd = [
            str(BLENDER), "-b", "--factory-startup",
            "-P", str(SCRIPT), "--",
            "--plan", str(pp), "--out", str(out),
            "--geometry", str(manifest_out),
            "--samples", str(args.samples),
            "--width", str(args.width), "--height", str(args.height),
            "--no-sheet",  # sheet applied project-side below
        ]
        t0 = time.time()
        print(f"[{pp.stem}] rendering -> {out.name} ...", flush=True)
        proc = subprocess.run(cmd, capture_output=True, text=True)
        dt = time.time() - t0
        if proc.returncode != 0 or not out.exists():
            failures += 1
            print(f"[{pp.stem}] FAILED in {dt:.1f}s", flush=True)
            tail = (proc.stderr or "").strip().splitlines()[-12:]
            print("\n".join(tail), file=sys.stderr, flush=True)
            continue
        if not manifest_out.exists():
            failures += 1
            print(f"[{pp.stem}] FAILED: no geometry manifest written",
                  file=sys.stderr, flush=True)
            continue
        if not args.no_sheet:
            try:
                _apply_sheet(pp, out)
            except Exception as exc:  # sheet is cosmetic; never fail the render
                print(f"[{pp.stem}] sheet skipped: {exc}", flush=True)
        print(f"[{pp.stem}] OK in {dt:.1f}s", flush=True)
    print(f"done: {len(plan_paths) - failures}/{len(plan_paths)} rendered")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
