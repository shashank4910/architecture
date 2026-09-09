from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template_string, request, send_from_directory

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from house_plan_generator.plan_data import make_plan
from house_plan_generator.renderer_2d import render_2d
from house_plan_generator.validator import validate_plan

app = Flask(__name__)
OUTPUT_DIR = ROOT / "generated" / "ui"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"

HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>House Plan Generator</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 32px; background: #f4f1eb; color: #1f1d1a; }
    .container { max-width: 1100px; margin: 0 auto; }
    .card { background: white; border-radius: 12px; padding: 24px; box-shadow: 0 8px 20px rgba(0,0,0,0.08); }
    form { display: grid; gap: 16px; }
    .row { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
    label { display: grid; gap: 6px; font-weight: bold; }
    select, input, button { padding: 10px 12px; border-radius: 8px; border: 1px solid #ccc; font-size: 16px; }
    button { background: #1d3557; color: white; border: none; cursor: pointer; }
    .meta { margin-top: 18px; padding: 14px; background: #eef6ff; border-radius: 8px; }
    .image-wrap { margin-top: 20px; text-align: center; }
    img { max-width: 100%; border-radius: 12px; border: 1px solid #ddd; background: white; }
    .folder { font-weight: bold; }
    .folder-link { display: inline-block; margin-top: 8px; background: #e3f2fd; padding: 8px 10px; border-radius: 8px; text-decoration: none; color: #0d3b66; }
    .gallery { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-top: 18px; }
    .thumb { background: #f7f7f7; padding: 10px; border-radius: 10px; border: 1px solid #ddd; }
    .thumb img { width: 100%; height: auto; }
  </style>
</head>
<body>
  <div class="container">
    <h1>House Plan Generator</h1>
    <div class="card">
      <form method="post" action="/generate">
        <div class="row">
          <label>
            Width (ft)
            <select name="width">
              <option value="20" selected>20</option>
            </select>
          </label>
          <label>
            Depth (ft)
            <select name="depth">
              <option value="50" selected>50</option>
            </select>
          </label>
          <label>
            Facing
            <select name="facing">
              <option value="north" selected>North</option>
              <option value="east">East</option>
            </select>
          </label>
          <label>
            Bedrooms
            <select name="bedrooms">
              <option value="2">2</option>
              <option value="3" selected>3</option>
            </select>
          </label>
          <label>
            Quantity
            <input type="number" name="quantity" min="1" max="20" value="1">
          </label>
          <label>
            Batch name
            <input type="text" name="batch_name" value="bulk_run" maxlength="40">
          </label>
        </div>
        <button type="submit">Generate 2D images</button>
      </form>

      {% if meta %}
      <div class="meta">
        <div><strong>Status:</strong> {{ meta['overall'] }}</div>
        <div><strong>Design ID:</strong> {{ meta['design_id'] }}</div>
        <div class="folder"><strong>Folder:</strong> {{ meta['folder'] }}</div>
        <div><strong>Output folder:</strong> <a class="folder-link" href="/browse?folder={{ meta['folder_rel'] }}" target="_blank">Open folder</a></div>
        <div><strong>Image path:</strong> {{ meta['path'] }}</div>
        {% if meta['errors'] %}
        <div><strong>Errors:</strong> {{ meta['errors'] }}</div>
        {% endif %}
      </div>
      {% if images %}
      <div class="gallery">
        {% for image in images %}
        <div class="thumb">
          <a href="{{ image['href'] }}" target="_blank"><img src="{{ image['src'] }}" alt="{{ image['name'] }}"></a>
          <div>{{ image['name'] }}</div>
        </div>
        {% endfor %}
      </div>
      {% elif image_url %}
      <div class="image-wrap">
        <img src="{{ image_url }}" alt="Generated floor plan">
      </div>
      {% endif %}
      {% endif %}
    </div>
  </div>
</body>
</html>
"""


def _read_manifest() -> list[dict]:
    if not MANIFEST_PATH.exists():
        return []
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
        if isinstance(data, list):
            return data
        return list(data.get('items', []))
    except Exception:
        return []


def _safe_relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


@app.get('/')
def index():
    return render_template_string(HTML, meta=None, image_url='', images=[])


@app.get('/generated_ui/<path:filename>')
def serve_generated(filename: str):
    return send_from_directory(str(OUTPUT_DIR), filename)


@app.get('/browse')
def browse():
    folder = request.args.get('folder', 'generated/ui')
    folder_path = Path(folder)
    if not folder_path.is_absolute():
        folder_path = ROOT / folder_path
    folder_path = folder_path.resolve()
    if not folder_path.exists() or not folder_path.is_dir():
        folder_path = OUTPUT_DIR
    if not str(folder_path).startswith(str(ROOT.resolve())):
        folder_path = OUTPUT_DIR
    entries = []
    for child in sorted(folder_path.iterdir(), key=lambda p: p.name.lower()):
        rel = _safe_relative(child)
        if child.is_dir():
            entries.append({'name': child.name, 'type': 'folder', 'href': f'/browse?folder={rel}'})
        else:
            relative_file = child.relative_to(OUTPUT_DIR).as_posix()
            entries.append({'name': child.name, 'type': 'file', 'href': f'/generated_ui/{relative_file}'})
    return render_template_string('''
        <!doctype html>
        <html><head><meta charset="utf-8"><title>Output Folder</title>
        <style>body{font-family:Arial,sans-serif;margin:32px} a{display:block;padding:8px 12px;margin:6px 0;border:1px solid #ddd;border-radius:8px;text-decoration:none;color:#0d3b66} .path{font-weight:bold;margin-bottom:18px}</style>
        </head><body>
        <div class="path">Folder: {{ folder }}</div>
        {% for item in items %}
          <a href="{{ item.href }}">{{ item.name }} ({{ item.type }})</a>
        {% endfor %}
        </body></html>
    ''', folder=_safe_relative(folder_path), items=entries)


@app.post('/generate')
def generate():
    width = int(request.form.get('width', 20))
    depth = int(request.form.get('depth', 50))
    facing = (request.form.get('facing', 'north') or 'north').lower()
    bedrooms = int(request.form.get('bedrooms', 3))
    quantity = max(1, min(20, int(request.form.get('quantity', 1))))
    batch_name = (request.form.get('batch_name') or 'bulk_run').strip() or 'bulk_run'
    batch_name = ''.join(ch if ch.isalnum() or ch in {'_', '-'} else '_' for ch in batch_name)
    batch_dir = OUTPUT_DIR / batch_name
    batch_dir.mkdir(parents=True, exist_ok=True)

    generated = []
    manifest = _read_manifest()
    batch_results = []
    for idx in range(1, quantity + 1):
        serial = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        design_id = f'{batch_name}_{idx:02d}_{serial}_{width}x{depth}_{facing}_{bedrooms}bhk'
        output_path = batch_dir / f'{design_id}_2d.png'

        plan = make_plan(int(serial[-6:]), width, depth, facing, bedrooms)
        plan['design_id'] = design_id
        result = validate_plan(plan)
        render_2d(plan, output_path)
        relative_image_path = Path(batch_name) / output_path.name
        generated.append({
            'name': output_path.name,
            'src': f'/generated_ui/{relative_image_path.as_posix()}',
            'href': f'/generated_ui/{relative_image_path.as_posix()}',
        })
        batch_results.append(result)
        entry = {
            'design_id': design_id,
            'overall': result.get('overall', 'UNKNOWN'),
            'errors': result.get('errors', []),
            'path': str(output_path),
            'folder': str(batch_dir),
            'folder_rel': _safe_relative(batch_dir),
            'created_at': datetime.now().isoformat(timespec='seconds'),
        }
        manifest.append(entry)

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding='utf-8')

    pass_count = sum(1 for item in batch_results if item.get('overall') == 'PASS')
    meta = {
        'design_id': generated[0]['name'] if generated else batch_name,
        'overall': 'PASS' if pass_count == len(batch_results) and batch_results else 'PARTIAL',
        'errors': [],
        'folder': str(batch_dir),
        'folder_rel': _safe_relative(batch_dir),
        'path': str(batch_dir / generated[0]['name']) if generated else str(batch_dir),
    }
    image_url = generated[0]['src'] if generated else ''
    return render_template_string(HTML, meta=meta, image_url=image_url, images=generated[:6])


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
