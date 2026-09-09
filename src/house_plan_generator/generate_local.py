from __future__ import annotations

import json
from pathlib import Path

from .match_validator import compare_geometry
from .plan_data import get_plans
from .renderer_2d import render_2d
from .renderer_3d import render_3d
from .validator import validate_plan

ROOT = Path(__file__).parents[1]
PLANS_DIR = ROOT / "plans"
VALIDATION_DIR = ROOT / "validation"
RENDER_DIR = ROOT / "generated" / "local"


def main():
    PLANS_DIR.mkdir(exist_ok=True)
    VALIDATION_DIR.mkdir(exist_ok=True)
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    summary = []
    for plan in get_plans():
        design = plan["design_id"]
        (PLANS_DIR / f"{design}.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        result = validate_plan(plan)
        result["design_id"] = design
        (VALIDATION_DIR / f"{design}_validation.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        geometry_2d = render_2d(plan, RENDER_DIR / f"{design}_2d.png", VALIDATION_DIR / f"{design}_2d_geometry.json")
        geometry_3d = render_3d(plan, RENDER_DIR / f"{design}_3d.png", VALIDATION_DIR / f"{design}_3d_geometry.json")
        match = compare_geometry(plan, geometry_2d, geometry_3d)
        result["match"] = match
        (VALIDATION_DIR / f"{design}_validation.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        summary.append(result)
    output = {"designs_tested": len(summary), "passed": sum(item["overall"] == "PASS" for item in summary), "failed": sum(item["overall"] != "PASS" for item in summary), "results": summary}
    (VALIDATION_DIR / "summary.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"designs_tested": output["designs_tested"], "passed": output["passed"], "failed": output["failed"]}, indent=2))


if __name__ == "__main__":
    main()
