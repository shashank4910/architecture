from __future__ import annotations

import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from house_plan_generator.layout_diversity import analyze
from house_plan_generator.plan_data import get_plans
from house_plan_generator.renderer_2d import render_2d
from house_plan_generator.validator import validate_plan

ROOT = Path(__file__).parent
OUTPUT = ROOT / "generated" / "diversity_10"


def font(size):
    try:
        return ImageFont.truetype("arialbd.ttf", size)
    except OSError:
        return ImageFont.load_default()


def main():
    plans = get_plans()
    if len(plans) != 10:
        raise RuntimeError("Expected exactly ten canonical plans.")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    plan_results = []
    cards = []
    for plan in plans:
        validation = validate_plan(plan)
        path = OUTPUT / f"{plan['design_id']}_2d.png"
        render_2d(plan, path)
        plan_results.append({"design_id": plan["design_id"], "plot": plan["plot"], "strategy": plan.get("layout_strategy"), "validation": validation})
        cards.append((plan, Image.open(path).convert("RGB")))
    diversity = analyze(plans)
    sheet = Image.new("RGB", (1600, 5 * 430), "#e9ecef")
    draw = ImageDraw.Draw(sheet)
    for index, (plan, image) in enumerate(cards):
        thumb = image.copy()
        thumb.thumbnail((740, 370))
        x = 20 if index % 2 == 0 else 820
        y = (index // 2) * 430
        draw.rectangle((x, y, x + 760, y + 410), fill="white", outline="#999999", width=2)
        draw.text((x + 15, y + 12), f"{plan['design_id']} | {plan['plot']['width_ft']}x{plan['plot']['depth_ft']} {plan['plot']['facing']} | {plan.get('layout_strategy')}", fill="black", font=font(15))
        sheet.paste(thumb, (x + (760 - thumb.width) // 2, y + 35))
    sheet.save(OUTPUT / "contact_sheet_2d_v2.png", dpi=(150, 150))
    output = {"plans_generated": len(plans), "plans_passing_validation": sum(item["validation"]["overall"] == "PASS" for item in plan_results), "plans_rejected": sum(item["validation"]["overall"] != "PASS" for item in plan_results), "plans": plan_results, "diversity": diversity}
    (OUTPUT / "summary.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"plans_generated": output["plans_generated"], "plans_passing_validation": output["plans_passing_validation"], "plans_rejected": output["plans_rejected"], "highest_similarity": diversity["highest_similarity"], "average_similarity": diversity["average_similarity"], "pairs_at_or_above_70_percent": len(diversity["rejected_pairs"])}, indent=2))


if __name__ == "__main__":
    main()
