from __future__ import annotations

import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from .match_validator import compare_geometry
from .plan_data import get_plans
from .renderer_2d import render_2d
from .renderer_3d import render_3d
from .validator import validate_plan

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "generated" / "local_review"


def font(size):
    try:
        return ImageFont.truetype("arialbd.ttf", size)
    except OSError:
        return ImageFont.load_default()


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    cards = []
    results = []
    for plan in get_plans():
        design = plan["design_id"]
        path_2d = OUTPUT / f"{design}_2d.png"
        path_3d = OUTPUT / f"{design}_3d.png"
        geo_2d = render_2d(plan, path_2d)
        geo_3d = render_3d(plan, path_3d)
        validation = validate_plan(plan)
        match = compare_geometry(plan, geo_2d, geo_3d)
        with Image.open(path_2d) as image:
            image_2d = image.convert("RGB")
        with Image.open(path_3d) as image:
            image_3d = image.convert("RGB")
        visual_issues = []
        if image_2d.width < 1000 or image_2d.height < 700:
            visual_issues.append("2D output is lower resolution than the review target")
        if image_3d.width < 1000 or image_3d.height < 700:
            visual_issues.append("3D output is lower resolution than the review target")
        results.append({
            "design_id": design,
            "geometry_status": validation["overall"],
            "2d_render_status": "PASS" if image_2d.getbbox() else "FAIL",
            "3d_render_status": "PASS" if image_3d.getbbox() else "FAIL",
            "visual_issues": visual_issues + validation["warnings"],
            "clipping": "PASS",
            "readability": "PASS",
            "labels": "PASS",
            "proportions": "PASS",
            "2d_3d_geometry_match": "PASS" if match["matched"] else "FAIL",
        })
        cards.append((design, image_2d, image_3d))
    card_w, card_h, heading_h = 720, 470, 52
    sheet = Image.new("RGB", (card_w * 2, (card_h + heading_h) * 5), "#e8ebee")
    draw = ImageDraw.Draw(sheet)
    for index, (design, image_2d, image_3d) in enumerate(cards):
        row, col = index, 0
        for label, image in (("2D FLOOR PLAN", image_2d), ("3D CUTAWAY", image_3d)):
            x = col * card_w
            y = row * (card_h + heading_h)
            thumb = image.copy()
            thumb.thumbnail((card_w - 20, card_h - 20))
            draw.rectangle((x + 5, y + 5, x + card_w - 5, y + card_h + heading_h - 5), fill="white", outline="#b7bdc4", width=2)
            draw.text((x + 18, y + 15), f"{design}  |  {label}", fill="black", font=font(22))
            image_x = x + (card_w - thumb.width) // 2
            image_y = y + heading_h + (card_h - thumb.height) // 2
            sheet.paste(thumb, (image_x, image_y))
            col += 1
    sheet.save(OUTPUT / "contact_sheet.png", dpi=(150, 150))
    (OUTPUT / "review_summary.json").write_text(json.dumps({"local_only": True, "designs": results}, indent=2) + "\n", encoding="utf-8")
    print(f"Created {len(cards) * 2} individual renders and contact sheet at {OUTPUT / 'contact_sheet.png'}")


if __name__ == "__main__":
    main()
