"""Strategy-driven template generation CLI.

Runs each master template in the library through the existing fail-closed gates
(exact tiling -> assemble_layout -> validate_catalog_plan -> DiversityIndex),
generating at most N candidates per template, rendering only accepted candidates,
and reporting the exact per-template yield. It never runs an unrestricted solver
search and never weakens a gate or the duplicate detection.

Usage (PowerShell, repo root):
    $env:PYTHONPATH = 'src'
    python scripts/generate_from_templates.py
    python scripts/generate_from_templates.py --render --max 10
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from house_plan_generator import template_library
from house_plan_generator.catalog_diversity import DiversityIndex
from house_plan_generator.catalog_validation import validate_catalog_plan
from house_plan_generator.template_generator import generate_from_template

OUT_DIR = ROOT / "plans" / "template_pilot"
PREVIEW_DIR = OUT_DIR / "preview"


def _seed_index():
    """Seed the diversity index with everything already accepted so new template
    candidates are compared against the whole known bank."""
    index = DiversityIndex()
    for directory in (ROOT / "generated" / "catalog_v2" / "plans",
                      ROOT / "plans" / "step_e_pilot"):
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            if path.name.endswith("report.json"):
                continue
            plan = json.loads(path.read_text())
            if validate_catalog_plan(plan)["overall"] == "PASS":
                try:
                    index.add(plan)
                except ValueError:
                    pass
    return index


def main(max_candidates=10, render=False):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index = _seed_index()
    reports = []
    total_accepted = 0
    for template in template_library.TEMPLATES:
        accepted, report = generate_from_template(template, index, max_candidates)
        for plan in accepted:
            name = f"{plan['design_id']}_{template.width}x{template.depth}_{template.bedrooms}bhk"
            (OUT_DIR / f"{name}.json").write_text(json.dumps(plan, indent=2) + "\n")
            if render:
                from house_plan_generator.renderer_2d import render_2d
                PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
                render_2d(plan, PREVIEW_DIR / f"{name}.png")
        report["rendered"] = len(accepted) if render else 0
        reports.append(report)
        total_accepted += len(accepted)

    summary = {
        "generator": "strategy_template",
        "templates": len(template_library.TEMPLATES),
        "max_candidates_per_template": max_candidates,
        "total_accepted": total_accepted,
        "per_template": reports,
        "catalog_status": "INCOMPLETE",
        "production_ready": False,
        "visual_review": "pending; numerical PASS is not catalogue approval",
    }
    (OUT_DIR / "template_pilot_report.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0 if total_accepted > 0 else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=10, help="max candidates per template")
    parser.add_argument("--render", action="store_true", help="render only accepted candidates")
    args = parser.parse_args()
    raise SystemExit(main(max_candidates=args.max, render=args.render))
