# House Plan Generator

A deterministic Python project for generating and validating conceptual Indian residential house-plan catalogues. The **canonical plan JSON is the single source of truth**; the Python renderer and any later AI imagery are presentation layers that must follow the JSON exactly, never the other way around.

The pipeline is **fail-closed**: a plan that fails validation is rejected, never rendered anyway. The catalogue is **not complete or approved** — the bounded solver has not yet produced a proven accepted bank, so the pipeline honestly reports an incomplete status with the exact per-group shortfall.

## Supported scope

Only the following are supported today. Anything else requires real design work and is not faked by mirroring or relabelling:

- **Plot sizes:** 20x50, 30x40, 30x50
- **BHK:** 2, 3, 4 (per the quota mix in `data/catalog_targets.json`)
- **Facing:** north only

## What this project contains

- Canonical validators, diversity checks, bulk pipeline and renderers under `src/house_plan_generator/`
- The bulk catalogue orchestration: `catalog.py` (`generate_catalog`), `catalog_validation.py` (release gate), `catalog_diversity.py` (duplicate/mirror/near-duplicate/family filters), `catalog_outputs.py` (render gate that re-validates the whole bank before any render)
- The 2D renderer `renderer_2d.py` and orientation-aware furniture drawing `curated_furniture.py`
- Tracked curated regression fixtures under `plans/curated/` (C01, C02)
- Bulk CLI `scripts/generate_300_2d_batch.py`
- Tests under `tests/`

## Core architecture

The canonical JSON plan is the source of truth. Each plan carries plot dimensions/facing, room geometry, doors, windows, stairs, parking, furniture and relationships. Validation (`validate_catalog_plan`, wrapping `review_concept` plus geometry/BHK/furniture/ventilation/stair checks) enforces at least:

- geometry stays in bounds, no overlaps, space is accounted for
- room-access topology rooted at the real exterior entrance
- **no bedroom is ever accessed through another bedroom** — an `ensuite` flag cannot legalize bedroom-to-bedroom access
- the only private-bathroom exception is a genuine explicit bedroom-to-bathroom ensuite
- doors on real shared walls with usable width, clear swing and approach
- role-appropriate furniture that fits with operating/approach clearances
- genuine diversity: mirrors, renames, timestamps, palette or tiny dimension shifts are rejected

`validate_catalog_plan` always reports `production_ready=False`, even on PASS. Numerical PASS is not visual or professional approval.

## Requirements

Local development uses a Windows `.venv` with `Pillow`, `Flask`, `python-dotenv`, `ortools>=9.10,<10` and `numpy` (see `requirements.txt`). The renderer, Flask UI and CP-SAT solver require these packages; only stdlib-based checks (compileall, the validator and orientation tests) run without them.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Commands

All commands are run from the repository root. Set `PYTHONPATH` to `src` first (PowerShell shown; use the equivalent on other shells).

**Compile check:**

```powershell
.\.venv\Scripts\python.exe -m compileall -q src scripts app.py
```

**Run the full test suite:**

```powershell
$env:PYTHONPATH = 'src'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The stdlib-only subset (no Pillow/OR-Tools/Flask) that runs anywhere:

```powershell
$env:PYTHONPATH = 'src'
python -m unittest tests.test_validator tests.test_renderer_orientation -v
```

**Bootstrap the catalogue (JSON search only, no images):**

```powershell
.\.venv\Scripts\python.exe scripts\generate_300_2d_batch.py --max-attempts 0
```

`--max-attempts 0` runs only the authored structural seeds with no solver search. Inspect `generated/catalog_v2/generation_report.json` and `search_state.json` for accepted geometry and the exact per-group shortfall.

**Preview a small explicit number of accepted candidates as PNGs:**

```powershell
.\.venv\Scripts\python.exe scripts\generate_300_2d_batch.py --max-attempts 0 --preview N
```

`--preview N` renders exactly N accepted candidates (a positive count). Then **inspect every PNG produced**, both the contact sheet and full-size, for architectural correctness and readability.

**Exit codes:** the CLI returns **exit code 2 for INCOMPLETE** — including a successful partial preview when the full bank of 300 is not yet accepted. Exit code 2 is the expected, honest status until the solver produces a complete, reviewed bank; it is not a crash.

## Status

- The generation pipeline is **fail-closed**: validation failures are never rendered.
- The catalogue is **not complete and not approved**. The solver has not yet produced a proven accepted bank; the pipeline reports INCOMPLETE with the exact shortfall.
- Solver yield and architectural diversity are unproven at the target of 300 (100 per plot size).
- The Flask UI (`app.py`) now serves only a validated persisted bank; it no longer renders unvalidated legacy output.

## Safety rules

- The canonical JSON is the source of truth. AI outputs are never the ground truth for geometry.
- Do not claim plans are construction-ready or architect-approved.
- Vastu guidance is conceptual only.
- Never commit secrets (`.env*`) or wholesale `generated/`/`work/` caches.
- North-facing only until real orientation design exists; never mirror or relabel to fake diversity.
