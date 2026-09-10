"""Validate and optionally render the bounded Step E structural-seed pilot.

This is intentionally limited to the three E01-E03 seeds marked in
``data/structural_seeds.json``. It does not run the 300-plan generator or a
solver search.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from house_plan_generator.bulk_assembly import assemble_layout
from house_plan_generator.catalog_diversity import DiversityIndex
from house_plan_generator.catalog_validation import validate_catalog_plan


def _tile_error(raw, width, depth):
    scale = 2
    expected = {(x, y) for x in range(round(width * scale)) for y in range(round(depth * scale))}
    occupied = set()
    for room_id, rect in raw["rooms"].items():
        x, y, w, d = (round(float(value) * scale) for value in rect)
        if w <= 0 or d <= 0:
            return f"{room_id}: non-positive rectangle"
        cells = {(ix, iy) for ix in range(x, x + w) for iy in range(y, y + d)}
        if occupied.intersection(cells):
            return f"{room_id}: overlapping rectangle"
        occupied.update(cells)
    if occupied != expected:
        return f"plot tiling mismatch: covered {len(occupied)} of {len(expected)} half-foot cells"
    return None


def _content_hash(plan):
    payload = {key: value for key, value in plan.items() if key not in {
        "design_id", "pilot_seed_id", "layout_strategy", "provenance", "generation_source",
    }}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _load_index():
    index = DiversityIndex()
    existing_dir = ROOT / "generated" / "catalog_v2" / "plans"
    for path in sorted(existing_dir.glob("*.json")):
        plan = json.loads(path.read_text())
        if validate_catalog_plan(plan)["overall"] == "PASS":
            index.add(plan)
    return index


def main(render=False):
    seeds = json.loads((ROOT / "data" / "structural_seeds.json").read_text())
    seeds = [seed for seed in seeds if seed.get("seed_id") in {"E01", "E02", "E03"}]
    if len(seeds) != 3:
        raise RuntimeError(f"Expected exactly E01-E03, found {len(seeds)} pilot seeds")

    output_dir = ROOT / "plans" / "step_e_pilot"
    preview_dir = output_dir / "preview"
    output_dir.mkdir(parents=True, exist_ok=True)
    if render:
        preview_dir.mkdir(parents=True, exist_ok=True)

    index = _load_index()
    results = []
    for seed in seeds:
        seed_id = seed["seed_id"]
        raw = seed["raw"]
        result = {"seed_id": seed_id, "group": {
            "width": seed["width"], "depth": seed["depth"],
            "bedrooms": seed["bedrooms"], "store": seed["store"],
        }}
        tile_error = _tile_error(raw, seed["width"], seed["depth"])
        if tile_error:
            result.update(status="REJECTED", stage="tiling", reason=tile_error)
            results.append(result)
            continue

        plan, assembly_error = assemble_layout(
            raw, seed["width"], seed["depth"], seed["bedrooms"], seed["store"],
            seed["assembly_seed"],
        )
        if assembly_error:
            result.update(status="REJECTED", stage="assembly", reason=assembly_error)
            results.append(result)
            continue

        plan.update(
            design_id=f"step_e_{seed_id.lower()}",
            pilot_seed_id=seed_id,
            layout_strategy=seed["strategy"],
            provenance=seed["provenance"],
            generation_source="step_e_structural_seed_pilot",
        )
        validation = validate_catalog_plan(plan)
        if validation["overall"] != "PASS":
            result.update(status="REJECTED", stage="catalog_validation", reason=validation["errors"])
            results.append(result)
            continue
        reason, score = index.check(plan)
        if reason:
            result.update(status="REJECTED", stage="diversity", reason=reason, similarity=score)
            results.append(result)
            continue

        index.add(plan)
        canonical_path = output_dir / f"{seed_id.lower()}_{seed['width']}x{seed['depth']}_{seed['bedrooms']}bhk_{'store' if seed['store'] else 'no_store'}.json"
        canonical_path.write_text(json.dumps(plan, indent=2) + "\n")
        result.update(status="ACCEPTED", canonical=str(canonical_path.relative_to(ROOT)), similarity=score or 0)

        if render:
            image_path = preview_dir / f"{seed_id.lower()}_{seed['width']}x{seed['depth']}_{seed['bedrooms']}bhk_{'store' if seed['store'] else 'no_store'}.png"
            if image_path.exists():
                result["image"] = str(image_path.relative_to(ROOT))
                result["image_status"] = "cached"
            else:
                from house_plan_generator.renderer_2d import render_2d
                render_2d(plan, image_path)
                result["image"] = str(image_path.relative_to(ROOT))
                result["image_status"] = "rendered"
        results.append(result)

    report = {
        "pilot": "Step E",
        "seed_count": len(seeds),
        "accepted": sum(item["status"] == "ACCEPTED" for item in results),
        "rejected": sum(item["status"] == "REJECTED" for item in results),
        "results": results,
        "catalog_status": "INCOMPLETE",
        "catalog_accepted_after_pilot": 1 + sum(item["status"] == "ACCEPTED" for item in results),
        "catalog_shortfall_after_pilot": 300 - 1 - sum(item["status"] == "ACCEPTED" for item in results),
        "production_ready": False,
        "visual_review": "pending" if not render else "assistant inspection required",
    }
    (output_dir / "pilot_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["rejected"] == 0 else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--render", action="store_true", help="Render only accepted pilot plans")
    args = parser.parse_args()
    raise SystemExit(main(render=args.render))
