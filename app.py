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
    .container { max-width: 980px; margin: 0 auto; }
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
        </div>
        <button type="submit">Generate 2D image</button>
      </form>

      {% if meta %}
      <div class="meta">
        <div><strong>Status:</strong> {{ meta['overall'] }}</div>
        <div><strong>Design ID:</strong> {{ meta['design_id'] }}</div>
        <div class="folder"><strong>Folder:</strong> {{ meta['folder'] }}</div>
        <div><strong>Image path:</strong> {{ meta['path'] }}</div>
        {% if meta['errors'] %}
        <div><strong>Errors:</strong> {{ meta['errors'] }}</div>
        {% endif %}
      </div>
      <div class="image-wrap">
        <img src="{{ image_url }}" alt="Generated floor plan">
      </div>
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


@app.get('/')
def index():
    return render_template_string(HTML, meta=None, image_url='')


@app.get('/generated_ui/<path:filename>')
def serve_generated(filename: str):
    return send_from_directory(str(OUTPUT_DIR), filename)


@app.post('/generate')
def generate():
    width = int(request.form.get('width', 30))
    depth = int(request.form.get('depth', 40))
    facing = (request.form.get('facing', 'north') or 'north').lower()
    bedrooms = int(request.form.get('bedrooms', 3))
    serial = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    design_id = f'design_{serial}_{width}x{depth}_{facing}_{bedrooms}bhk'
    output_path = OUTPUT_DIR / f'{design_id}_2d.png'

    plan = make_plan(int(serial[-6:]), width, depth, facing, bedrooms)
    plan['design_id'] = design_id
    result = validate_plan(plan)
    render_2d(plan, output_path)
    meta = {
        'design_id': design_id,
        'overall': result.get('overall', 'UNKNOWN'),
        'errors': result.get('errors', []),
        'folder': str(output_path.parent),
        'path': str(output_path),
    }

    manifest = _read_manifest()
    manifest.append({
        'design_id': design_id,
        'overall': meta['overall'],
        'errors': meta['errors'],
        'path': meta['path'],
        'folder': meta['folder'],
        'created_at': datetime.now().isoformat(timespec='seconds'),
    })
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding='utf-8')

    image_url = f'/generated_ui/{output_path.name}'
    return render_template_string(HTML, meta=meta, image_url=image_url)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
