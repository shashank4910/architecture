# Indian House Plan Generator: Project Context

## Project Goal

Build a future digital product containing downloadable bundles of conceptual Indian residential house plans. The product is not yet a live storefront; it is a deterministic plan-generation, validation and rendering pipeline that is still being proven out.

Current phase:
- bounded, resumable canonical geometry search
- strict fail-closed room-access, privacy and furniture-fit validation
- diversity filtering against mirrors and near-duplicates
- a render gate that re-validates the whole bank before producing any image
- a browser UI that serves only a validated persisted bank

## Hard Constraints

- **The canonical plan JSON is the source of truth.** The Python renderer is NOT the source of truth, and neither is any AI-generated image. Rendering must follow the JSON exactly.
- AI is never the source of truth for room geometry.
- Plans are conceptual and not construction-ready.
- Do not treat Vastu as a legal or engineering guarantee.
- Do not add paid external APIs without explicit user approval.
- Never commit secrets (`.env*`) or wholesale `generated/`/`work/` caches.
- North-facing only until real orientation design exists; never mirror or relabel to fake diversity.

## Environment

Workspace: a local Windows checkout with a `.venv` virtual environment.

Key dependencies (see `requirements.txt`): Flask, Pillow, python-dotenv, ortools>=9.10,<10, numpy.

## Canonical + Validated-Bank Workflow

The source of truth is the canonical plan JSON. Correctness is established by the fail-closed validators and by human visual review — **not** by the Python renderer, and **not** by the fact that some older sample happened to pass. Older passing samples do not equal correctness, and there is no standing "sample validation run passed" claim: every bank must be re-validated by the current gate.

The active pipeline:

1. `catalog.py` `generate_catalog(...)` runs a bounded, resumable search: authored structural seeds first, then bounded solver jobs across outstanding quota groups. It reloads accepted JSON, revalidates and deduplicates on resume, and persists `search_state.json` + `generation_report.json` with the exact per-group shortfall. It refuses to declare completion until all requested plans are accepted, and `generate_and_write_catalog()` refuses a full render of an incomplete bank.
2. `catalog_validation.py` `validate_catalog_plan()` is the release gate: it wraps `review_concept` plus geometry/BHK/furniture/ventilation/stair checks and always reports `production_ready=False`.
3. `catalog_diversity.py` rejects duplicates and mirrors, near-duplicates (>=0.88 role-area overlap across four flips) and over-full families (>8 per family per plot size).
4. `catalog_outputs.py` `render_catalog(...)` is the render gate: it re-validates the whole bank and diversity before any render, refuses to fully render an incomplete bank, allows an explicit positive preview, caches PNGs by canonical-plan + renderer-source hash, and builds galleries/contact sheets. A manifest never implies visual approval.
5. `app.py` (Flask UI) now serves only a validated persisted bank, filtered by supported plot/BHK/north facing, checking the requested quantity before rendering. It no longer renders unvalidated legacy output. Do not treat the UI as safe for anything outside the validated bank.

### Access and privacy rule (exact)

- **No bedroom is ever accessed through another bedroom.** An `ensuite` flag cannot legalize bedroom-to-bedroom access.
- The **only** private-bathroom exception is a genuine explicit bedroom-to-bathroom ensuite. There is no broad "bedroom suite" exception.
- Common bathrooms, kitchen, dining, living and stairs must be reachable from common/circulation areas, never through a bedroom.
- A common function room must not be isolated behind a private room.

## Main Source Files

- `src/house_plan_generator/catalog.py`: bounded/resumable catalogue orchestration
- `src/house_plan_generator/catalog_validation.py`: fail-closed release gate
- `src/house_plan_generator/catalog_diversity.py`: mirror/near-duplicate/family filters (imports numpy)
- `src/house_plan_generator/catalog_outputs.py`: render gate, gallery and contact sheets
- `src/house_plan_generator/bulk_layouts.py` / `bulk_assembly.py` / `bulk_furnishing.py`: CP-SAT geometry search, canonical assembly, explicit furniture/door fitting
- `src/house_plan_generator/concept_review.py` / `validator.py`: shared-wall openings, entrance-rooted routes, privacy/access, furniture/swing/clearance and stair-fit checks
- `src/house_plan_generator/renderer_2d.py` / `curated_furniture.py`: deterministic 2D renderer and orientation-aware furniture drawing
- `plans/curated/`: tracked C01/C02 canonical JSON used as regression fixtures
- `scripts/generate_300_2d_batch.py`: bulk CLI (JSON search, bootstrap, preview)
- `data/catalog_targets.json`, `data/structural_seeds.json`: quota config and reproducible seeds
- `tests/`: unittest modules

## Output Locations

Runtime output is gitignored:

- `generated/catalog_v2/` (search state, generation report, review manifest, gallery, contact sheets)
- `generated/ui/` (UI-served renders)

## Current Status

- The pipeline is fail-closed and reports INCOMPLETE with the exact shortfall until a full, reviewed bank exists.
- The solver has produced no proven accepted catalogue yet; solver yield and diversity are unproven at 300 (100 per plot size).
- The UI serves only the validated bank.
- `curated_furniture.py` now draws the orientation metadata (bed heads N/W/S/E, rotated sofas, WC quarter-turns, shelves, short rotated counters, and horizontal/reverse stairs) inside authored footprints, with pure-geometry regression tests.

## Operational Notes

- Use the validated bank + render gate for any catalogue output. The UI is only safe for the validated bank.
- Use the backend validators for architectural correctness checks; numerical PASS is not visual or professional approval.
- Keep AI imagery as a presentation layer only, never the ground truth.
- Log file: `logs/project_log.txt`.
