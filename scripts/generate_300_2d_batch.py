from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, PngImagePlugin

from house_plan_generator.plan_data import _transform_plan, make_plan
from house_plan_generator.renderer_2d import render_2d

ROOT = Path(__file__).resolve().parent
MAIN_OUT = ROOT / "generated" / "plan_types"
MAIN_OUT.mkdir(parents=True, exist_ok=True)


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")


def _add_png_metadata(path: Path, stamp: str) -> None:
    with Image.open(path) as img:
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("GeneratedAt", stamp)
        metadata.add_text("Project", "House Plan Generator")
        metadata.add_text("Kind", "2D Floor Plan")
        img.save(path, pnginfo=metadata)


def _make_bucket_variant(width: int, depth: int, facing: str, bedrooms: int, index: int):
    base = make_plan(index, width, depth, facing, bedrooms)
    variant = base
    if index % 2 == 0:
        variant = _transform_plan(base, index, f"{width}x{depth} batch variant {index}", mirror_x=True)
    if index % 3 == 0:
        variant = _transform_plan(variant, index, f"{width}x{depth} batch variant {index}", mirror_y=True)
    if index % 5 == 0:
        variant["plot"]["facing"] = "east" if variant["plot"]["facing"] == "north" else "north"
    return variant


def generate_300() -> list[Path]:
    bucket_specs = [
        (30, 40, "north", 3, 100),
        (30, 50, "north", 3, 100),
        (20, 50, "east", 3, 100),
    ]
    created: list[Path] = []
    serial = 1
    for width, depth, facing, bedrooms, target_count in bucket_specs:
        out_dir = MAIN_OUT / f"{width}x{depth}"
        out_dir.mkdir(parents=True, exist_ok=True)
        for idx in range(1, target_count + 1):
            plan = _make_bucket_variant(width, depth, facing, bedrooms, idx)
            stamp = _stamp()
            design_id = f"design_{serial:03d}_{width}x{depth}_{plan['plot']['facing']}_{bedrooms}bhk_{idx}"
            filename = f"{design_id}_{stamp}_2d.png"
            output_path = out_dir / filename
            render_2d(plan, output_path)
            _add_png_metadata(output_path, datetime.now(timezone.utc).isoformat())
            created.append(output_path)
            serial += 1
            print(f"{serial - 1}/300 -> {output_path.relative_to(ROOT)}")
    summary = {"generated": len(created), "folder": str(MAIN_OUT), "sizes": ["30x40", "30x50", "20x50"]}
    (MAIN_OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return created


if __name__ == "__main__":
    generate_300()
