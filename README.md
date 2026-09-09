# House Plan Generator

A deterministic Python project for generating and validating Indian residential house-plan concepts. The project keeps the canonical geometry and validation logic as the source of truth, then optionally renders 2D and 3D presentation outputs around that geometry.

## What this project contains

- Canonical plan definitions and layout transforms under `src/house_plan_generator/`
- Deterministic 2D render pipeline under `src/house_plan_generator/renderer_2d.py`
- Geometry validation under `src/house_plan_generator/validator.py`
- Optional 3D renderers and legacy experiment code in `src/house_plan_generator/` and `archive/old_experiments/`
- Generated output artifacts under `generated/` and `outputs/`
- Supporting scripts under `scripts/`
- Tests under `tests/`

## Core architecture

The canonical JSON plan is the single source of truth. Each plan includes plot dimensions, room geometry, doors, windows, stairs, parking, and Vastu guidance metadata. Validation checks ensure:

- no room leaves the plot boundary
- no room overlaps another
- doors and windows are on valid walls
- reachable circulation exists
- staircase and parking remain plausible

## Quick start

1. Create or update a local `.env` file using `.env.example`.
2. Install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. Run the validation and renderer tests:

```powershell
.\.venv\Scripts\python.exe -m unittest -q tests/test_validator.py tests/test_match_validator.py tests/test_renderer.py
```

4. Launch the local browser UI:

```powershell
.\.venv\Scripts\python.exe .\app.py
```

Then open:

```text
http://localhost:5000
```

Use the form to choose the house size, facing, bedroom count, quantity, and batch name. Click Generate 2D images to create a batch. Every batch is saved in a dedicated subfolder under:

```text
generated/
  ui/
    <batch_name>/
```

The UI also includes an Open folder button that links directly to the generated image folder for that batch.

5. Generate the canonical plans and deterministic local outputs:

```powershell
.\.venv\Scripts\python.exe -m src.house_plan_generator.generate_local
```

Or, if you prefer the project root entry point wrapper:

```powershell
.\.venv\Scripts\python.exe .\scripts\generate_300_2d_batch.py
```

This batch generator writes its outputs to:

```text
generated/
  plan_types/
    30x40/
    30x50/
    20x50/
```

Each size folder contains 100 2D renders, for a total of 300 images in the batch set.

## Important directories

- `src/house_plan_generator/` — active production code
- `scripts/` — small entrypoint scripts
- `tests/` — project tests
- `generated/` — recent deterministic outputs
- `archive/old_experiments/` — historical or experimental scripts that are no longer part of the main pipeline
- `plans/` — exported canonical plan JSON files
- `validation/` — validation metadata and geometry checks

## Safety rules

- Do not treat AI outputs as the source of truth.
- Do not claim plans are construction-ready or architect-approved.
- Keep Vastu guidance as conceptual guidance only.
- Use AI generation only as a presentation layer, never as the canonical geometry.

## Output notes

The project generates:

- 2D concept sheets
- 3D concept sheets
- validation reports
- diversity/contact-sheet summaries

These outputs are reference material, not legal or construction documentation.
