# Indian House Plan Generator: Project Context

## Project Goal

Build a future digital product containing downloadable bundles of conceptual Indian residential house plans. The product is not yet a live storefront; it is currently a deterministic plan-generation and validation pipeline.

Current phase:
- canonical geometry generation
- strict room-access and privacy validation
- deterministic 2D rendering
- browser-based local UI for concept generation

## Hard Constraints

- The canonical Python pipeline is the source of truth.
- AI is never the source of truth for room geometry.
- Plans are conceptual and not construction-ready.
- Do not treat Vastu as a legal or engineering guarantee.
- Do not add paid external APIs without explicit user approval.
- Keep the repository clean and versioned.

## Environment

Workspace:
C:\Users\Admin\house-plan-generator

Virtual environment:
.venv

Key dependencies:
- Pillow
- python-dotenv
- Flask

## Canonical Workflow

The active generation pipeline is:
1. canonical plan JSON is built in `src/house_plan_generator/plan_data.py`
2. `validate_plan()` checks geometry, circulation, door validity, and access/privacy rules
3. `render_2d()` renders the architectural concept sheet
4. the local Flask UI (`app.py`) exposes generation to a browser

Important architectural rule:
- a bedroom may not be reached through another bedroom unless there is an explicit suite/ensuite relationship in metadata
- bathrooms and staircase must be reachable from circulation/common areas
- common function rooms must not be isolated behind private rooms

## Main Source Files

- `src/house_plan_generator/plan_data.py`: canonical room layouts and plan variants
- `src/house_plan_generator/validator.py`: geometry + privacy + access validation
- `src/house_plan_generator/renderer_2d.py`: deterministic 2D floor-plan renderer
- `app.py`: local browser UI for generating concept plans
- `scripts/generate_300_2d_batch.py`: bulk 2D generation script
- `tests/test_validator.py`: validation cases and regression tests

## Output Locations

Generated concept images:
- `generated/ui/`
- `generated/plan_types/`

Local UI URL:
- http://localhost:5000

## Current Status

As of 2026-09-10:
- sample validation run passed for all 10 canonical plans
- local UI is live and serving the form successfully
- generated image output is saved into `generated/ui/`
- strict access/privacy validation remains active to prevent bedroom-through-bedroom access

## Operational Notes

- Use the UI for concept generation.
- Use the backend validator for architectural correctness checks.
- Keep images in the generated folders and do not rely on AI as the ground truth.
- Log file: `logs/project_log.txt`
