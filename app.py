from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Flask and Pillow/renderer_2d are imported lazily (see _flask() / _render_2d)
# so this module and its pure helpers stay importable in environments where
# those packages are not installed (mirrors the lazy-import pattern adopted in
# catalog_outputs.py and catalog_diversity.py).

# Directory the catalogue pipeline persists accepted canonical JSON into.
BANK_DIR = ROOT / "generated" / "catalog_v2" / "plans"
# Everything served to the browser lives under this single allowed output root.
OUTPUT_DIR = ROOT / "generated" / "ui"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"

# Only these plot sizes / bedroom counts are backed by validated candidates.
# Derived from data/catalog_targets.json; north facing only until real design work.
SUPPORTED_SIZES = {
    (20, 50): [2, 3],
    (30, 40): [2, 3],
    (30, 50): [3, 4],
}
SUPPORTED_FACINGS = {"north"}
CONCEPT_LABEL = "Concept pending required visual review"

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
    .notice { margin-top: 18px; padding: 14px; background: #fdeaea; border-radius: 8px; color: #7a1f1f; }
    .concept-note { margin-top: 12px; padding: 12px; background: #fff6e5; border-radius: 8px; color: #6b4b0c; font-weight: bold; }
    .image-wrap { margin-top: 20px; text-align: center; }
    img { max-width: 100%; border-radius: 12px; border: 1px solid #ddd; background: white; }
    .folder { font-weight: bold; }
    .folder-link { display: inline-block; margin-top: 8px; background: #e3f2fd; padding: 8px 10px; border-radius: 8px; text-decoration: none; color: #0d3b66; }
    .gallery { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-top: 18px; }
    .thumb { background: #f7f7f7; padding: 10px; border-radius: 10px; border: 1px solid #ddd; }
    .thumb img { width: 100%; height: auto; }
    .thumb .concept { font-size: 13px; color: #6b4b0c; margin-top: 6px; }
  </style>
</head>
<body>
  <div class="container">
    <h1>House Plan Generator</h1>
    <div class="card">
      <form method="post" action="/generate">
        <div class="row">
          <label>
            Plot size (ft)
            <select name="size">
              <option value="20x50" selected>20 x 50</option>
              <option value="30x40">30 x 40</option>
              <option value="30x50">30 x 50</option>
            </select>
          </label>
          <label>
            Facing
            <select name="facing">
              <option value="north" selected>North</option>
            </select>
          </label>
          <label>
            Bedrooms
            <select name="bedrooms">
              <option value="2">2</option>
              <option value="3" selected>3</option>
              <option value="4">4</option>
            </select>
          </label>
          <label>
            Quantity
            <input type="number" name="quantity" min="1" max="20" value="1">
          </label>
        </div>
        <button type="submit">Show validated concepts</button>
      </form>

      {% if notice %}
      <div class="notice">{{ notice }}</div>
      {% endif %}

      {% if meta %}
      <div class="meta">
        <div><strong>Requested:</strong> {{ meta['requested'] }}</div>
        <div><strong>Available validated concepts:</strong> {{ meta['available'] }}</div>
        <div><strong>Plot:</strong> {{ meta['size'] }} &middot; <strong>Facing:</strong> {{ meta['facing'] }} &middot; <strong>Bedrooms:</strong> {{ meta['bedrooms'] }}</div>
        <div class="folder"><strong>Folder:</strong> {{ meta['folder'] }}</div>
        <div><strong>Output folder:</strong> <a class="folder-link" href="/browse?folder={{ meta['folder_rel'] }}" target="_blank">Open folder</a></div>
      </div>
      <div class="concept-note">{{ concept_label }}. Not production approved.</div>
      {% endif %}

      {% if images %}
      <div class="gallery">
        {% for image in images %}
        <div class="thumb">
          <a href="{{ image['href'] }}" target="_blank"><img src="{{ image['src'] }}" alt="{{ image['name'] }}"></a>
          <div>{{ image['name'] }}</div>
          <div class="concept">{{ concept_label }}</div>
        </div>
        {% endfor %}
      </div>
      {% endif %}
    </div>
  </div>
</body>
</html>
"""

BROWSE_HTML = """
        <!doctype html>
        <html><head><meta charset="utf-8"><title>Output Folder</title>
        <style>body{font-family:Arial,sans-serif;margin:32px;background:#f4f1eb} a{display:block;padding:8px 12px;margin:6px 0;border:1px solid #ddd;border-radius:8px;text-decoration:none;color:#0d3b66} .path{font-weight:bold;margin-bottom:18px}</style>
        </head><body>
        <div class="path">Folder: {{ folder }}</div>
        {% for item in items %}
          <a href="{{ item.href }}">{{ item.name }} ({{ item.type }})</a>
        {% endfor %}
        </body></html>
"""


def _flask():
    """Lazy Flask import so this module stays importable without Flask."""
    import flask
    return flask


def _render_2d():
    """Lazy renderer import so this module stays importable without Pillow."""
    from house_plan_generator.renderer_2d import render_2d
    return render_2d


def _renderer_hash() -> str:
    """Hash of the renderer source files, used to invalidate cached PNGs when
    the renderer changes (mirrors catalog_outputs.render_catalog)."""
    parts = ("renderer_2d.py", "curated_furniture.py", "openings.py")
    base = SRC / "house_plan_generator"
    return hashlib.sha256(b"".join((base / n).read_bytes() for n in parts)).hexdigest()


def _read_manifest() -> list:
    if not MANIFEST_PATH.exists():
        return []
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        return list(data.get("items", []))
    except Exception:
        return []


def resolve_within(requested, root: Path = OUTPUT_DIR) -> Path:
    """Resolve a requested folder and clamp it to ``root`` using real Path
    containment (never str.startswith). Returns ``root`` for anything that is
    not the root itself or a descendant of it, or that does not exist."""
    root = root.resolve()
    if requested is None:
        return root
    candidate = Path(requested)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    candidate = candidate.resolve()
    if candidate != root and root not in candidate.parents:
        return root
    if not candidate.exists() or not candidate.is_dir():
        return root
    return candidate


def _safe_relative(path: Path, base: Path = ROOT) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.name


def iter_bank_plans(bank_dir: Path = BANK_DIR) -> list:
    """Load accepted canonical JSON from the persisted candidate bank.

    Never generates plans; returns [] when the bank has not been produced."""
    bank_dir = Path(bank_dir)
    if not bank_dir.exists():
        return []
    plans = []
    for path in sorted(bank_dir.glob("*.json")):
        try:
            plans.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return plans


def filter_bank(plans, width: int, depth: int, facing: str, bedrooms: int) -> list:
    """Exact-match filter on plot size + facing + BHK. No relabeling."""
    facing = (facing or "").lower()
    matched = []
    for plan in plans:
        plot = plan.get("plot", {})
        if int(plot.get("width_ft", -1)) != int(width):
            continue
        if int(plot.get("depth_ft", -1)) != int(depth):
            continue
        if str(plot.get("facing", "")).lower() != facing:
            continue
        if int(plan.get("bedrooms", -1)) != int(bedrooms):
            continue
        matched.append(plan)
    return matched


def select_validated(plans):
    """Re-run the release gate and diversity index over a filtered set and
    return only the plans that pass both. Fail-closed: a plan that fails
    validation or is a duplicate/near-duplicate is dropped, never rendered."""
    from house_plan_generator.catalog_diversity import DiversityIndex
    from house_plan_generator.catalog_validation import validate_catalog_plan

    index = DiversityIndex()
    accepted = []
    for plan in plans:
        result = validate_catalog_plan(plan)
        if result.get("overall") != "PASS":
            continue
        reason, _ = index.check(plan)
        if reason:
            continue
        index.add(plan)
        accepted.append(plan)
    return accepted


def render_selection(plans, batch_dir: Path):
    """Render each plan, reusing cached PNGs keyed by plan+renderer-source hash
    so identical plans are not re-rendered (mirrors catalog_outputs)."""
    from house_plan_generator.catalog_diversity import geometry_key

    render_2d = _render_2d()
    batch_dir.mkdir(parents=True, exist_ok=True)
    renderer_hash = _renderer_hash()
    cache_path = batch_dir / "render_cache.json"
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    except (OSError, json.JSONDecodeError):
        cache = {}
    if not isinstance(cache, dict):
        cache = {}

    images = []
    new_cache = {}
    for plan in plans:
        width = int(plan["plot"]["width_ft"])
        depth = int(plan["plot"]["depth_ft"])
        filename = f"{width}x{depth}_{plan.get('bedrooms')}bhk_{geometry_key(plan)[:12]}.png"
        output_path = batch_dir / filename
        digest = hashlib.sha256((json.dumps(plan, sort_keys=True) + renderer_hash).encode()).hexdigest()
        if cache.get(filename) != digest or not output_path.exists():
            render_2d(plan, output_path)
        new_cache[filename] = digest
        relative = _safe_relative(output_path, OUTPUT_DIR)
        images.append({
            "name": filename,
            "src": f"/generated_ui/{relative}",
            "href": f"/generated_ui/{relative}",
            "design_id": plan.get("design_id", filename),
        })
    cache_path.write_text(json.dumps(new_cache, indent=2), encoding="utf-8")
    return images


def create_app():
    flask = _flask()
    app = flask.Flask(__name__)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    @app.get("/")
    def index():
        return flask.render_template_string(
            HTML, meta=None, images=[], notice=None, concept_label=CONCEPT_LABEL
        )

    @app.get("/generated_ui/<path:filename>")
    def serve_generated(filename: str):
        return flask.send_from_directory(str(OUTPUT_DIR), filename)

    @app.get("/browse")
    def browse():
        folder_path = resolve_within(flask.request.args.get("folder", "generated/ui"))
        entries = []
        for child in sorted(folder_path.iterdir(), key=lambda p: p.name.lower()):
            if child.is_dir():
                rel = _safe_relative(child)
                entries.append({"name": child.name, "type": "folder", "href": f"/browse?folder={rel}"})
            else:
                # Only list files that live under OUTPUT_DIR so relative_to is safe.
                resolved = child.resolve()
                out = OUTPUT_DIR.resolve()
                if resolved != out and out not in resolved.parents:
                    continue
                relative_file = resolved.relative_to(out).as_posix()
                entries.append({"name": child.name, "type": "file", "href": f"/generated_ui/{relative_file}"})
        return flask.render_template_string(
            BROWSE_HTML, folder=_safe_relative(folder_path), items=entries
        )

    @app.post("/generate")
    def generate():
        form = flask.request.form
        size = (form.get("size", "20x50") or "20x50").lower().strip()
        facing = (form.get("facing", "north") or "north").lower().strip()
        try:
            bedrooms = int(form.get("bedrooms", 3))
            quantity = int(form.get("quantity", 1))
        except (TypeError, ValueError):
            return _reject("Quantity and bedrooms must be whole numbers.")
        try:
            width_s, depth_s = size.split("x", 1)
            width, depth = int(width_s), int(depth_s)
        except (TypeError, ValueError):
            return _reject(f"Unsupported plot size '{size}'.")

        quantity = max(1, min(20, quantity))

        # Reject unsupported inputs before touching the bank or the renderer.
        if facing not in SUPPORTED_FACINGS:
            return _reject(
                f"Facing '{facing}' is not supported. Only north-facing concepts are available."
            )
        if (width, depth) not in SUPPORTED_SIZES:
            return _reject(f"Unsupported plot size '{size}'.")
        if bedrooms not in SUPPORTED_SIZES[(width, depth)]:
            return _reject(
                f"{bedrooms} BHK is not available for a {width}x{depth} plot."
            )

        # Validated-bank flow: filter, re-validate, dedup, THEN compare quantity.
        matched = filter_bank(iter_bank_plans(), width, depth, facing, bedrooms)
        validated = select_validated(matched)
        available = len(validated)
        if quantity > available:
            return _insufficient(quantity, available, size, facing, bedrooms)

        batch_dir = OUTPUT_DIR / f"{width}x{depth}_{facing}_{bedrooms}bhk"
        images = render_selection(validated[:quantity], batch_dir)

        manifest = _read_manifest()
        for image in images:
            manifest.append({
                "design_id": image["design_id"],
                "file": image["name"],
                "concept_status": CONCEPT_LABEL,
                "production_ready": False,
                "path": str(batch_dir / image["name"]),
                "folder": str(batch_dir),
                "folder_rel": _safe_relative(batch_dir),
            })
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        meta = {
            "requested": quantity,
            "available": available,
            "size": f"{width} x {depth}",
            "facing": facing,
            "bedrooms": bedrooms,
            "folder": str(batch_dir),
            "folder_rel": _safe_relative(batch_dir),
        }
        return flask.render_template_string(
            HTML, meta=meta, images=images, notice=None, concept_label=CONCEPT_LABEL
        )

    def _reject(message: str):
        return (
            flask.render_template_string(
                HTML, meta=None, images=[], notice=message, concept_label=CONCEPT_LABEL
            ),
            400,
        )

    def _insufficient(requested: int, available: int, size: str, facing: str, bedrooms: int):
        message = (
            f"Requested {requested} concept(s) but only {available} validated "
            f"{size} {facing}-facing {bedrooms} BHK concept(s) are available. "
            f"No duplicates are fabricated and no fallback generation is performed."
        )
        return (
            flask.render_template_string(
                HTML, meta=None, images=[], notice=message, concept_label=CONCEPT_LABEL
            ),
            422,
        )

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000, debug=True)
