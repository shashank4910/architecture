# Indian House Plan Generator: Project Context

## Project Goal

Build a future digital product containing downloadable bundles of conceptual Indian residential house plans. The eventual product may offer plans by plot size, but the website, payments, database, PDF bundles, and large-scale generation are not built yet.

Current phase: deterministic geometry, visual rendering, layout diversity, and validation.

## Hard Constraints

- Do not generate 50 or 100 plans yet.
- Do not build the website, payment system, database, accounts, ads, or deployment.
- Do not use paid APIs.
- Do not call Gemini, Nano Banana, OpenRouter, or any external API unless the user explicitly authorizes it in a future request.
- Keep the deterministic Python pipeline as the source of truth.
- Never claim plans are construction-ready, architect-approved, structurally verified, government-approved, or 100% Vastu compliant.
- Plans are: `Vastu-oriented conceptual house plans`.
- Never hard-code API keys or commit `.env` files.

## Environment

Workspace:

`C:\Users\Admin\house-plan-generator`

Virtual environment:

`.venv`

Installed packages include:

- `google-genai`
- `python-dotenv`
- `pillow`

The current local rendering pipeline uses Pillow. No external API is required for the deterministic workflow.

## Canonical Architecture

The canonical JSON specification is the single source of truth for both 2D and 3D representations.

Canonical plan fields include:

- `design_id`
- `plot.width_ft`
- `plot.depth_ft`
- `plot.facing`
- `floors`
- `bedrooms`
- `bathrooms`
- `rooms`
- `doors`
- `windows`
- `stairs`
- `parking`
- `vastu`
- `disclaimer`
- `layout_strategy`

Each room uses:

- `id`
- `name`
- `x_ft`
- `y_ft`
- `width_ft`
- `depth_ft`
- `kind`

Room coordinates use the northwest plot corner as origin. `x` increases east and `y` increases south.

## Main Source Files

- `house_plan_generator/plan_data.py`: canonical plan generation. Currently returns 10 plans: 5 plans using 20x50 plots and 5 plans using 30x40 plots. Strategies use explicit whole-layout transforms and strategy labels.
- `house_plan_generator/validator.py`: deterministic geometry validation including containment, overlaps, dimensions, doors, windows, staircase, parking, circulation, and Vastu warnings.
- `house_plan_generator/match_validator.py`: compares renderer geometry manifests against canonical JSON and detects moved rooms or mismatched 2D/3D geometry.
- `house_plan_generator/renderer_2d.py`: deterministic Pillow-based architectural 2D renderer. It draws walls, room labels, dimensions, doors/swing arcs, windows, furniture, fixtures, kitchen symbols, staircase treads, parking, north arrow, and disclaimers.
- `house_plan_generator/renderer_3d.py`: deterministic Pillow-based isometric/cutaway renderer (kept as fallback). It consumes canonical JSON and preserves exact room geometry. Current presentation: consistent cutaway heights (camera-facing exterior walls 3.2 ft, interior partitions 4.6 ft, far exterior walls 6.4 ft), dedicated shadow/glow layers composited separately, edge-lined cuboids, muted architectural palette, green plot surroundings, and minimal name-only room labels.
- `house_plan_generator/renderer_3d_blender.py`: Blender-based procedural 3D architectural renderer (current primary 3D presentation pipeline). Consumes canonical JSON and emits a geometry manifest with the same contract as the Pillow renderer. Scene build is split into `blender_geom.py`, `blender_materials.py`, `blender_walls.py`, `blender_furniture.py`, `blender_rooms.py`, and `blender_lighting.py`.
- `blender_entry.py`: Blender entry script (adds project root to sys.path, dispatches to `renderer_3d_blender.main()`). Runs inside Blender's bundled Python.
- `run_blender_render.py`: project-side runner that invokes portable Blender (`tools/blender/blender.exe`) per plan, captures output, and applies the title/summary sheet after Blender exits (Pillow is unavailable inside Blender).
- `build_blender_contact_sheet.py`: builds the review contact sheet from the Blender batch renders.

Portable Blender 4.5 lives in `tools/blender/` and is used headless (`blender.exe -b --factory-startup -P blender_entry.py`).
- `house_plan_generator/generate_local.py`: writes plans, renders deterministic 2D/3D outputs, geometry manifests, per-design validation reports, and `validation/summary.json`.
- `house_plan_generator/review_gallery.py`: creates the earlier local 2D/3D review gallery.
- `house_plan_generator/layout_diversity.py`: structural layout fingerprinting and pairwise similarity analysis.
- `run_layout_diversity.py`: generates the 10-plan deterministic diversity set and contact sheet.
- `test_validator.py`: geometry validation tests.
- `test_match_validator.py`: canonical 2D/3D matching tests, including deliberate moved-room failure.
- `test_renderer.py`: renderer regression tests.
- `ai_image_generator.py`: optional OpenRouter experiment module. It must remain unused unless explicitly authorized. It has strict `:free` model and missing-key guards.
- `run_openrouter_experiment.py`: optional OpenRouter experiment runner. Do not run without explicit authorization and a confirmed free model/key.

## Current Outputs

Canonical JSON plans:

- `plans/design_001.json` through `plans/design_010.json`

Validation outputs:

- `validation/design_001_validation.json` through `validation/design_010_validation.json`
- `validation/summary.json`

Diversity outputs:

- `generated/diversity_10/design_001_2d.png` through `design_010_2d.png`
- `generated/diversity_10/contact_sheet_2d_v2.png`
- `generated/diversity_10/summary.json`

Earlier local review outputs also exist under:

- `generated/local/`
- `generated/local_review/`

Polished 3D presentation outputs (deterministic Pillow cutaway look):

- `generated/presentation_upgrade/design_001_3d_polish.png` through `design_010_3d_polish.png`
- `generated/presentation_upgrade/contact_sheet_3d_polish.png`

Blender 3D batch outputs (current Blender presentation, Sept 2026):

- `generated/blender_3d/draft/design_001_3d_blender.png` through `design_010_3d_blender.png` (1280x960 render + title sheet)
- `generated/blender_3d/draft/design_001_geometry.json` through `design_010_geometry.json`
- `generated/blender_3d/contact_sheet_3d_blender.png`
- Iteration artifacts: `smoke_007*.png`, `verify_007.png`, `swatches.png`, `diag.png`, `top007.png`

## Latest Verified Results

Blender 3D pipeline (Sept 2026): batch-rendered all 10 plans via `run_blender_render.py --plans all` (each ~220-290s at 128 samples); geometry manifests verified 10/10 against canonical JSON (`_verify_manifests.py`); full test suite 11/11 passing. The Blender renderer is geometry-faithful presentation only; canonical JSON remains the single source of truth.

The latest deterministic diversity run produced:

- Plans generated: `10`
- Plans passing geometry validation: `10/10`
- Plans rejected: `0`
- Highest structural similarity: `58.1%`
- Average structural similarity: `8.2%`
- Pairs at or above the `70%` rejection threshold: `0`
- Existing geometry/matching tests: `9/9 passed`
- Renderer regression tests: `2/2 passed`
- Full test suite: `11/11 passed`
- Canonical 2D/3D matching: `10/10 passed`
- 3D presentation polish pass (Sept 2026): all 10 plans re-rendered with the upgraded `renderer_3d.py`; geometry manifests unchanged and tests unaffected. AI image comparison experiment (`test_matched_pairs.py`) remains inconclusive: Gemini image/QA credits were exhausted mid-run, so 0/5 QA verdicts were recorded. AI outputs live under `generated/matched_pairs/` and are reference-only.

Vastu remains a warning system, not a hard geometry gate. Some plans report warnings such as master bedroom or puja placement not being in the preferred Vastu zone.

## Safe Commands

Run all tests:

```powershell
.\.venv\Scripts\python.exe -m unittest -q test_validator.py test_match_validator.py test_renderer.py
```

Run canonical geometry and matching pipeline:

```powershell
.\.venv\Scripts\python.exe -m house_plan_generator.generate_local
```

Regenerate 10-plan diversity set and contact sheet:

```powershell
.\.venv\Scripts\python.exe .\run_layout_diversity.py
```

Batch-render all plans with the Blender 3D pipeline (each plan takes ~4 min):

```powershell
.\.venv\Scripts\python.exe .\run_blender_render.py --plans all --outdir generated/blender_3d/draft
```

Verify Blender geometry manifests against canonical JSON:

```powershell
.\.venv\Scripts\python.exe .\_verify_manifests.py
```

Build the Blender contact sheet:

```powershell
.\.venv\Scripts\python.exe .\build_blender_contact_sheet.py
```

The OpenRouter commands are intentionally excluded from normal validation. Do not run them unless the user explicitly authorizes external API use.

## Current Product Assessment

The deterministic 2D renderer is a suitable foundation for conceptual PDF products, though not construction documentation or CAD output.

The Blender 3D renderer (`renderer_3d_blender.py`) is now the primary 3D presentation path; the Pillow cutaway (`renderer_3d.py`) remains as a fast fallback. Both are geometry-faithful proofs of concept, not yet polished commercial visualizations.

The canonical geometry and validation system should remain authoritative. AI image generation, if ever tested again, must be treated only as an optional visual reference and never as the source of truth.

## Recommended Next Steps

1. Improve canonical strategy quality and Vastu warnings without weakening geometry validation.
2. Improve 2D sheet layout and furniture placement only through presentation-layer changes.
3. Improve the Blender 3D presentation locally (lighting, materials, furniture, camera) while preserving canonical geometry - the geometry manifest check in `_verify_manifests.py` guards this.
4. Add more structural diversity strategies only after each candidate passes validation and the 70% similarity rejection check.
5. Keep all future work limited to small controlled experiments; do not scale to 50 or 100 plans yet.
