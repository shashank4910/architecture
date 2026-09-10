"""Validate before rendering and expose every image in a cached review gallery."""
import hashlib
import html
import json
from pathlib import Path
from .catalog_diversity import DiversityIndex, geometry_key
from .catalog_validation import validate_catalog_plan


def _load_pillow():
    # Pillow is only needed once a real render is attempted; keep import lazy so
    # the bank-validation / quota / cache logic can be unit-tested without it.
    from PIL import Image, ImageDraw
    return Image, ImageDraw


def _load_renderer():
    from .renderer_2d import render_2d
    return render_2d


def verify_group_quotas(plans, config_path=None):
    """Independently re-derive per-group counts from catalog_targets.json.

    Never trusts summary['accepted']; returns the list of groups whose accepted
    count does not exactly equal the configured quota.
    """
    from .catalog import read_config, group_key, spec_key, DEFAULT_TARGETS
    cfg = read_config(config_path or DEFAULT_TARGETS)
    counts = {}
    for plan in plans:
        counts[group_key(plan)] = counts.get(group_key(plan), 0) + 1
    mismatched = []
    for g in cfg['groups']:
        key = (g['width'], g['depth'], g['bedrooms'], g['store'])
        accepted = counts.get(key, 0)
        if accepted != g['count']:
            mismatched.append(dict(group=key, accepted=accepted, quota=g['count']))
    return mismatched


def render_catalog(root, catalog, *, preview=None, config_path=None):
    root = Path(root)
    plans, summary = catalog['plans'], catalog['summary']
    if preview is not None and (not isinstance(preview, int) or isinstance(preview, bool) or preview < 1):
        raise ValueError('Preview count must be positive')
    if preview is None:
        # A full render is refused for any incomplete / wrong-quota bank BEFORE
        # the renderer is touched. Quotas are re-verified from config, not trusted.
        if len(plans) != summary['requested']:
            raise ValueError('Incomplete catalogue: request an explicit preview count')
        mismatched = verify_group_quotas(plans, config_path)
        if mismatched:
            raise ValueError(f'Refusing full render: per-group quota mismatch {mismatched}')
    index = DiversityIndex(summary.get('near_duplicate_threshold', .88), summary.get('max_per_layout_family', 8))
    for plan in plans:
        result = validate_catalog_plan(plan)
        if result['overall'] != 'PASS':
            raise ValueError(f"Invalid candidate: {result['errors']}")
        index.add(plan)
    selected = plans if preview is None else plans[:preview]
    render_2d = _load_renderer()
    Image, ImageDraw = _load_pillow()
    out = root / 'review'
    out.mkdir(parents=True, exist_ok=True)
    renderer_hash = hashlib.sha256(b''.join((Path(__file__).parent / n).read_bytes() for n in ('renderer_2d.py', 'curated_furniture.py', 'openings.py'))).hexdigest()
    manifest_path = out / 'manifest.json'
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    items = []
    for plan in selected:
        filename = f"{int(plan['plot']['width_ft'])}x{int(plan['plot']['depth_ft'])}_{plan['bedrooms']}bhk_{geometry_key(plan)[:12]}.png"
        digest = hashlib.sha256((json.dumps(plan, sort_keys=True) + renderer_hash).encode()).hexdigest()
        if previous.get('hashes', {}).get(filename) != digest or not (out / filename).exists():
            render_2d(plan, out / filename)
        items.append(dict(file=filename, hash=digest, design_id=plan['design_id']))
    sheets = []
    for start in range(0, len(items), 6):
        page = items[start:start + 6]
        name = f'contact_{start//6 + 1:02d}.png'
        sheets.append(name)
        if previous.get('images', [])[start:start+6] == page and (out/name).exists():
            continue
        sheet = Image.new('RGB', (1200, 960 * ((len(page)+1)//2)), '#fbfaf5')
        draw = ImageDraw.Draw(sheet)
        for n, entry in enumerate(page):
            with Image.open(out / entry['file']) as im:
                im.thumbnail((590, 910))
                x, y = (n%2)*600, (n//2)*960
                sheet.paste(im, (x+(600-im.width)//2, y+30))
                draw.text((x+12, y+10), entry['file'], fill='#1f1d1a')
        sheet.save(out / name)
    cards = ''.join(f'<article><a href="{html.escape(i["file"])}"><img src="{html.escape(i["file"])}"></a><p>{html.escape(i["design_id"])}</p></article>' for i in items)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Catalogue review</title><style>body{font:16px Arial;background:#fbfaf5;margin:24px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:24px}img{width:100%}p{overflow-wrap:anywhere}</style><h1>Concept candidates — visual review required</h1>'+f'<p>{len(plans)} / {summary["requested"]} pass automated checks; {len(items)} shown. Not production approved.</p><main>{cards}</main>', encoding='utf-8')
    report = dict(rendered=len(items), accepted=len(plans), requested=summary['requested'], production_ready=False, hashes={i['file']:i['hash'] for i in items}, images=items, contact_sheets=sheets, gallery=str(out/'index.html'), visual_review='pending')
    manifest_path.write_text(json.dumps(report, indent=2)+'\n')
    return report
