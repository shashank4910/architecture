"""Rebuild the C01/C02 review sheet from their canonical JSON files."""
import json
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from house_plan_generator.concept_review import review_concept
from house_plan_generator.renderer_2d import render_2d


def main():
    images = []
    reports = []
    for code in ('C01', 'C02'):
        plan = json.loads((ROOT / f'plans/curated/{code}_north_20x50_2bhk.json').read_text())
        folder = ROOT / 'generated/curated' / code
        folder.mkdir(parents=True, exist_ok=True)
        report = review_concept(plan)
        if report['errors']:
            raise SystemExit(f"{code}: {report['errors']}")
        (folder / 'review.json').write_text(json.dumps(report, indent=2) + '\n')
        render_2d(plan, folder / 'floor_plan.png', folder / 'geometry.json')
        with Image.open(folder / 'floor_plan.png') as image:
            images.append(image.copy())
        reports.append(report)

    gap, margin, header, footer = 28, 24, 106, 142
    width = sum(im.width for im in images) + gap + 2 * margin
    height = max(im.height for im in images) + header + footer
    sheet = Image.new('RGB', (width, height), '#fbfaf5')
    draw = ImageDraw.Draw(sheet)
    def font(size, bold=False):
        try:
            return ImageFont.truetype('arialbd.ttf' if bold else 'arial.ttf', size)
        except OSError:
            return ImageFont.load_default()
    headings = [('C01 | FRONT LIVING + MIDDLE STAIR', 'One double bedroom + one single-bed room'),
                ('C02 | FRONT STAIR + CENTRAL LIVING', 'Two double bedrooms; smaller kitchen')]
    x = margin
    for im, (title, subtitle) in zip(images, headings):
        draw.text((x+28, 18), title, fill='#1f1d1a', font=font(27, True))
        draw.text((x+28, 58), subtitle, fill='#4d4842', font=font(22))
        sheet.paste(im, (x, header))
        x += im.width + gap

    before, after = (r['circulation_cell_area_sqft'] for r in reports)
    y = header + max(im.height for im in images)
    draw.line((margin, y, width-margin, y), fill='#cdc7ba', width=2)
    reduction = (before-after)/before*100
    draw.text((margin+28, y+16), f'DEDICATED CIRCULATION: {before:g} to {after:g} sq ft ({reduction:.1f}% less, including C02 entry).', font=font(25, True), fill='#1f1d1a')
    draw.text((margin+28, y+56), 'Both retain one common bathroom. Room labels are planning-cell dimensions; clear sizes are in the review notes.', font=font(21), fill='#4d4842')
    draw.text((margin+28, y+93), 'CONCEPT COMPARISON ONLY | Setbacks, legal ventilation openings and stair headroom remain unresolved.', font=font(21), fill='#4d4842')
    output = ROOT / 'generated/curated/C02/comparison_C01_C02.png'
    sheet.save(output, dpi=(150, 150))
    print(output)


if __name__ == '__main__':
    main()
