# House Plan Product — complete continuation handoff

Written 2026-09-10. The user explicitly stopped the expensive agent to conserve credits and requested this detailed handoff for a cheaper coding agent. **Coding stopped with an unfinished, untested bulk-generator update.** This document is a handoff, not a claim that the update works or that 300 plans are ready.

## 1. Start here: current truth

- Local repository: `C:\Users\Admin\house-plan-generator`.
- Remote: `https://github.com/shashank4910/architecture.git`.
- Branch observed: `master`.
- Last observed local HEAD: `1ac7e18 Initial commit`, preceded by `94178e9 feat: add bulk generation folder browser to UI` and `ef86cdd feat: add privacy-safe plan validation and local UI`.
- Several bulk-generator changes are UNCOMMITTED. Do not reset or overwrite them.
- No push, remote fetch, full regression run, or bulk image review was completed during this resumed turn.
- Two earlier curated concepts, C01 and C02, were manually authored as canonical JSON and rendered with Python. They were not successful outputs from the random/bulk generator. The user liked an image, but do not turn that into approval of an entire catalogue or every technical detail.
- The experimental solver has low yield. Many attempts are UNKNOWN within a time limit, or have geometry that cannot be furnished acceptably. Do not remove validation or pad with mirrors to reach 300.
- No new bulk images were generated during this resumed turn. Cached candidate JSON files exist; numerical PASS does not mean visually reviewed.
- A compilation check passed after fixing the catalogue syntax and adding solver hints, **before** the latest `catalog_outputs.py` and CLI replacement were written. Those latest files have not been compiled or tested.

The next agent's job is to finish and test the safe generation pipeline, inspect a small explicit preview, update the documentation/log, and push all relevant changes plus this handoff to GitHub. The user already authorized the GitHub push. Do not ask for redundant approval. Do not claim success if generation still underfills.

## 2. User working rules — critical

Read repository `AGENTS.md`. Its rules include:

- Keep explanations short and plain; conserve tokens.
- Generate images only for an agreed task. No speculative variants, hidden batches, or unused previews.
- Inspect every generated image and make it visible to the user by displaying/opening/linking it.
- Reuse unchanged images; do not rerender just for comparisons.
- Stay within agreed scope.

The latest user instruction is to STOP coding now and prepare this handoff. A next agent should resume only when assigned continuation. Do not launch background work from this stopped turn.

Use local tools and existing scripts. Avoid paid AI calls, large parallel experiments, repeated tests without changes, and verbose status dumps. No subagents were authorized. The user chose a cheaper agent because this task was exhausting credits.

Secrets: `.env`, `.env.local`, `.env.txt` may exist. Never read their values into output, stage them, or commit them. Do not upload the old output cache wholesale.

## 3. Product and architectural requirements

The product is a commercial-looking catalogue of **conceptual**, Vastu-oriented Indian residential house plans. Each eventually needs an attractive furnished 2D plan and a matching premium 3D cutaway.

Source of truth is **canonical plan data/JSON**, not the Python renderer and not an AI image. JSON defines plot dimensions/facing, all rooms and geometry, entrance, parking, stairs, doors/windows, furniture and relevant relationships. Rendering must follow it exactly.

Current workflow: canonical JSON → architectural validation → existing Python 2D renderer → visual inspection. Preserve the existing warm-neutral rendering style, strong black outer walls, furniture, dimensions, north arrow, parking and bathroom/kitchen treatment. The main failure is bad planning, not a need to redesign the renderer.

Required checks:

1. Geometry, bounds, non-overlap and accounted-for space.
2. Room-access topology rooted at the real exterior entrance.
3. Privacy: **no bedroom accessed through another bedroom, ever**. An `ensuite` flag cannot legalize bedroom-to-bedroom access.
4. Common bathrooms accessible from common/circulation areas, not through bedrooms. A genuine explicit bedroom-to-bathroom ensuite is the only private bathroom exception.
5. Kitchen, dining, living and stairs sensibly accessible from common circulation.
6. Doors on actual shared walls, openings contained in the shared segment, usable width, clear swing and approach.
7. Usable room dimensions/proportions and furniture fit, with operating/approach space.
8. Real circulation, not merely connected rectangles.
9. Meaningful facing/orientation. Never change the facing label without real orientation design.
10. No large unexplained leftover spaces; store/utility must be useful.
11. Genuine architectural diversity. Mirroring, renaming, timestamps, palette changes, minor dimension shifts or furniture movement do not create new designs.
12. Human visual inspection of contact sheets and individual plans where needed. Numerical PASS alone is insufficient.

Review priority: correctness → privacy/access → proportions → diversity → readability → commercial presentation. Full coverage does not prove good architecture, adequate ventilation, legal setbacks or structural feasibility.

## 4. Exact catalogue targets

Total 300, **100 per plot size**, with **39 stores/utilities = 13%**. `data/catalog_targets.json` is the new target configuration.

| Plot | BHK | No store | With usable store | Total |
|---|---:|---:|---:|---:|
| 20×50 | 2 | 51 | 9 | 60 |
| 20×50 | 3 | 40 | 0 | 40 |
| 30×40 | 2 | 35 | 5 | 40 |
| 30×40 | 3 | 50 | 10 | 60 |
| 30×50 | 3 | 55 | 10 | 65 |
| 30×50 | 4 | 30 | 5 | 35 |
| Total | | 261 | 39 | 300 |

This preserves the original BHK mix and approximates the original selective storage counts (about 10/15/15) with 9/15/15. Do not force storage into every layout. Current new solver supports **north-facing only**. Other facings require actual design work; do not mirror or relabel these as different orientations.

## 5. Earlier implementation and why it failed

Legacy `plan_data.py` / `make_plan()` create template variants. The previous `scripts/generate_300_2d_batch.py` created repeated templates, mirrored X/Y by index, even changed facing labels independently, deleted output buckets before generating, and rendered without the new quality gate. This is exactly the behaviour the user objected to.

That CLI file has now been replaced in the working tree, but **root `app.py` still uses the legacy unsafe generation flow**. Its `/generate` calls `make_plan`, obtains legacy validation, renders even failed results, and only shows the first six images. Do not recommend the current UI for safe new bulk generation until fixed.

`PROJECT_CONTEXT.md` is stale: it says the Python pipeline is the source of truth, implies older samples passing equals correctness, and contains an overly broad bedroom suite exception. Rewrite these claims. Earlier passing results do not establish catalogue quality.

## 6. Previously completed curated work

Files to retain and use as regression examples:

- `plans/curated/C01_north_20x50_2bhk.json`
- `plans/curated/C02_north_20x50_2bhk.json`
- `plans/curated/README.md`, `C02_REVIEW.md`
- `scripts/render_curated_concept.py` (default C01, supports explicit plan/output)
- `scripts/compare_curated_concepts.py`
- `src/house_plan_generator/openings.py`: explicit start-offset convention plus legacy compatibility; `door_swing()` supports end hinges.
- `src/house_plan_generator/curated_furniture.py`: draw exact canonical furniture footprints.
- `src/house_plan_generator/concept_review.py`: shared-wall openings, entrance-rooted routes, furniture/swing/clearance checks, stair fit. Currently recognizes horizontal stair orientation for fit checks.
- `src/house_plan_generator/validator.py`: fixed ensuite loophole, root-based private-safe access, and a circulation room named Bedroom Lobby being misclassified.
- `renderer_2d.py`: uses explicit furniture lists, explicit opening intervals, label controls and clipped hatch treatment.
- `tests/test_curated_concept.py` and existing validator/match/renderer tests.

Earlier session evidence: **31 tests passed before the latest bulk changes**. This is historical, not the current verification result.

Previously shown deliverable copies are in:
`C:\Users\Admin\Documents\Codex\2026-09-10\create-an-image-of\outputs\C01\`
and `...\outputs\C02\`.

## 7. New bulk modules: exact current responsibilities

### `bulk_layouts.py`

CP-SAT experimental geometry search using OR-Tools, added dependency `ortools>=9.10,<10` in `requirements.txt`. It was installed into the local `.venv` in the earlier work. Numpy is used by diversity checking and is currently available through the solver dependency; consider declaring it explicitly because it is directly imported.

API: `solve_layout(width, depth, beds, store=False, seed=1, timeout=6, hint=None)`.

- One-foot integer coordinate grid. Domain constants are written in doubled units and converted to feet.
- NoOverlap2D plus sum of all room areas equal plot area.
- Common-area adjacency constraints require at least 4 ft shared segment; actual doors/furniture are assembled later.
- Parking north left/right, 9 or 10 by 16 ft.
- Master anchored southwest; kitchen touches east edge with centroid in southern half.
- Hall(s) connected to living/dining; bedroom access from common rooms; common baths access halls.
- Bedrooms/living/kitchen require exterior contact. Interior bathrooms may explicitly require mechanical roof exhaust.
- Circulation area bounded at 18% of plot.
- Seed changes actual anchor objectives/strategy options; does not mirror finished plans.
- Combined living/dining for selected 3/4BHK cases, including 20-ft-wide 3BHK.
- Typical domain minima: master 10-ft dimensions /110 sq ft; secondary 9-ft dimensions /99 sq ft; stores 6×6 gross minimum; stair 8×13 or13×8.
- Hall minimum dimension capped at7ft; domains are concept design parameters, not building regulations.
- Latest changes: optional partial CP hint; hall2 allows depth22ft/area100sqft; galley kitchen aspect ratio up to2.2. Living/dining up to2.75; other nonhall rooms1.8.
- Two CP workers per attempt, regardless of outer worker count. Avoid oversubscribing the machine.
- Returns raw `rooms` keyed by ID with `[x,y,width,depth]`, entry and combined flag, or status without rooms when no feasible solution.
- UNKNOWN is a bounded-search timeout, not proof no design exists.

This approach has not demonstrated the yield or architectural diversity required for 300. Use a bounded pilot; if still weak, add genuinely different authored structural strategies rather than run indefinitely.

### `bulk_furnishing.py`

Fits explicit door/furniture geometry, rejecting candidates when recipes cannot fit.

- Clear bounds reserve .75ft at exterior boundaries and .25ft at internal boundaries.
- Door options use actual touching clear-wall intervals, 3ft/2.75ft widths, both hinges, endpoint/midpoint/quarter-foot offsets.
- Incoming openings are projected into both rooms for approach checks.
- Furniture must lie in clear bounds, not overlap other furniture or declared clearances, and clear approaches/swing envelopes.
- Master bed 5×6.5ft; secondary beds try 5ft then **3.5ft single width**. Explicit disclosure required; not every secondary room supports a double bed.
- Bed side clearances1.5ft, foot2.5ft; wardrobe run≥3ft with2.5ft operating space.
- Bathroom: 3×3 shower, WC1.6×2.4, basin1.6×1.4, approach clearances, rotated recipes.
- Kitchen L counters + fridge; minimum3ft work zone target.
- Living/combined living-dining/separate dining recipes; dining has4 chairs.
- Storage shelves1.25ft deep with2.5ft aisle; min5ft clear room dimension.
- Stair: dogleg,16 risers over9ft floor height,10in going,3ft flights/landings; horizontal/reverse metadata; doors must enter landing.
- `walkable()` uses .25ft grid and conservative2.5ft square footprint to join common-room door approaches around furniture.

Known limitations: common-door connectivity is not exhaustive movement/usability verification. Dining chair pull-out/occupation space is not fully modelled. Do not present it as comprehensive clearance certification. Visual inspection and better checks remain important.

### `bulk_assembly.py`

API: `assemble_layout(raw, width, depth, beds, with_store, seed)` → `(plan, error)`.

- Converts geometry into canonical rooms, names, roles and kinds.
- Searches common spanning-tree door arrangements (bounded attempts).
- Places noncommon room doors from common spaces, then fits furniture.
- Rejects failed furniture/common circulation.
- Adds exterior windows and explicit mechanical-exhaust assumption for interior baths.
- Adds labels on sampled free floor positions; font sizes18 room/11 dimensions.
- Stores canonical furniture, clearance and stair data.
- Runs `review_concept()` before acceptance.
- Does not set final content ID/family; catalogue does that.
- Hall3 in authored seeds works through common circulation role detection.

### `catalog_diversity.py`

- Normalizes functional room roles.
- `geometry_key`: role+rectangles hashed, invariant under X/Y mirrors; ignores names, IDs, timestamps and style.
- Raster: two pixels/ft with role cells. `DiversityIndex` compares all four flip orientations; ≥.88 matching role area rejects near duplicates.
- `family_key`: coarse thirds-of-plot functional zones plus role access edges; mirror invariant.
- Max8 per family per plot size.
- Similarity comparison applies across BHK/store groups of the same size, so adding one store to otherwise identical geometry may still be rejected. This is intentional.
- This is a filter, not a proof of architectural diversity. Coarse family fingerprints and thresholds need evaluation against visually reviewed pairs.

### `catalog_validation.py`

- Catches malformed/nonfinite geometry.
- Incorporates `review_concept` checks.
- Verifies actual vs declared bedroom/bath counts, explicit offsets and north facing.
- Requires role-appropriate furniture, actual usable stores, four chairs in combined living/dining, windows/exhaust assumptions, common routes and opening approaches, contained clearances and tested stair configuration.
- Always `production_ready=False` even on PASS.
- Recheck role spoofing, missing geometry/IDs, stairs, window placement, all furniture clearances and assumptions in tests. Existing code is not a security or exhaustive architectural proof.

### `catalog.py`

New bounded/resumable orchestration, replacing old implementation.

`generate_catalog(requested=300, root=None, max_attempts=120, seconds=8, workers=2, config_path=..., progress=None)`:

- Loads target quotas; rejects mismatched totals/store count/duplicate group keys.
- Default output `generated/catalog_v2`.
- Reloads accepted JSON from `plans/`, revalidates and deduplicates before continuing.
- Tries authored structural seeds once; then bounded round-robin solver jobs across outstanding quota groups.
- Partial feasible geometry becomes solver hint. Hint never bypasses quality/diversity gates.
- Persists `search_state.json` and `generation_report.json` with next seed, attempts, rejection reasons, exact per-group shortfall and status.
- Accepted filenames use plot/BHK/store + geometry hash, not timestamps as fake uniqueness.
- Status INCOMPLETE unless all300 accepted; then READY_FOR_VISUAL_REVIEW, not approved.
- `write_catalog_outputs()` delegates to new renderer wrapper.
- `generate_and_write_catalog()` refuses a full render of an incomplete bank.

Latest fixed issues: extra parenthesis in seed loop; `_job` previously called a missing `hint` parameter, now added.

Remaining implementation concerns to fix/test:

1. `accept()` rewrites JSON and resets `catalog_status` on resume; do not destroy valid review evidence. Store review evidence keyed to canonical content and renderer hash; invalidate only when content changes.
2. Deterministic IDs must not leave duplicate files if a resumed file had another name. Do not delete user work silently; detect/report or migrate explicitly.
3. Malformed existing JSON should give actionable diagnostics.
4. Bootstrap attempts and solver attempts are different; report them clearly.
5. Summary distinct-family count uses size+family keys; document meaning.
6. Render gate must independently verify quotas, not merely trust count300 in supplied summary.
7. Handle config changes/resume without allowing overquota plans or stale review approval.

### `catalog_outputs.py` — JUST WRITTEN, NOT TESTED

- Validates the bank and diversity before any rendering.
- Incomplete full render refused; explicit positive preview count allowed.
- Uses canonical JSON + renderer source hash to cache PNGs.
- Creates gallery showing every selected image, plus contact sheets six per page.
- Writes review manifest with selected image hashes and pending review.
- Contact sheets reuse existing PNGs, not AI generation; caches unchanged sheet pages.
- HTML states automated count and not production approved.

Test actual imports, renderer integration, empty/partial banks, renderer failure handling, cache invalidation, quota validation, and stale old review files. Do not let a manifest imply visual approval. It currently only retains selected image cache entries, so changing preview selections may rerender previously cached files unnecessarily; improve if needed without broad redesign.

### `scripts/generate_300_2d_batch.py` — JUST REPLACED, NOT TESTED

New arguments: `--output`, `--max-attempts`, `--seconds`, `--workers`, mutually exclusive `--preview N` / `--render`.

- Default searches JSON only; no image generation without explicit mode.
- No destructive reset, transforms, timestamp padding, or facing relabels.
- Returns exit code2 for INCOMPLETE, including successful partial previews. Document this expected status.
- Full render only invoked when summary is complete.
- Validate invalid preview arguments BEFORE spending time searching (currently preview check is downstream).

## 8. Available experimental candidate evidence

Ignored local `work/` contains experiments; do not commit it wholesale.

`candidate_13.json`: earlier solver 20×50 2BHK with store. Previously passed new numerical gate. Room rectangles:

```
parking  0,0,9,16       living   9,0,11,11
dining   7,29,13,8      kitchen 13,11,7,11
stairs  12,37,8,13      bath    13,22,7,7
master   0,37,12,13     bed2     0,16,9,13
hall     9,11,4,18      store    0,29,7,8
```

Kitchen is toward the upper east; inspect Vastu orientation claims rather than conceal an exception. This cached candidate is not proof it satisfies the latest solver's domain constraints.

`candidate_29.json`: earlier solver30×40 2BHK with store, previously passed numerical gate:

```
parking 0,0,10,16       living 10,0,12,16
dining 22,28,8,12       kitchen22,20,8,8
stairs 22,0,8,13        bath   15,33,7,7
master 0,29,15,11       bed2    0,16,15,13
hall  15,16,7,17       store  22,13,8,7
```

`candidate_100.json` through `candidate_103.json`: four assembled authored30×50 seed variants, previously all passed quality individually. They are NOT four proven diverse catalogue entries. Expect near-duplicate rejection between related variants.

`data/structural_seeds.json` stores their raw geometry and group specs, so these seeds are reproducible without ignored work files. Base4BHK:

```
parking [0,0,9,16]       living [9,0,21,16] combined
stairs  [0,16,8,13]      hall   [8,16,7,13]
hall2   [11,29,4,21]     kitchen[23,16,7,13]
bath1   [15,16,8,7]      bath2  [15,23,8,6]
master  [0,39,11,11]     bed2   [0,29,11,10]
bed3    [15,29,15,11]    bed4   [15,40,15,10]
```

3BHK version changes oldbed2 into dining, renumbers other beds and disables combined living/dining. Store version narrows east upper bedroom to `[21,29,9,11]`, adds store`[15,33,6,7]` and hall3`[15,29,6,4]`. Both store and bedroom have independent hallway access; secondary single-bed fallback was necessary.

There are other `raw_*.json` and probe scripts in `work/`. Many are failed/intermediate. Do not treat them as accepted. If retaining cached candidates for reproducibility, revalidate then copy only selected canonical JSON into a specifically tracked pilot directory, recording provenance and pending visual review.

## 9. Renderer issues to fix BEFORE new bulk previews

Keep existing visual style. `curated_furniture.py` currently does not faithfully draw all new orientation metadata:

1. Beds only special-case east; other orientations are drawn as south. Implement north/west/south/east headboards and appropriately placed pillows inside exact footprints, including single beds.
2. Sofa cushions assume vertical orientation even for rotated horizontal sofas. Draw along its long axis.
3. WC `rotation` is stored as quarter-turn0..3 but ignored by renderer. Rotate tank/bowl treatment without changing footprint.
4. Shelves need recognizable shelf treatment.
5. Stairs currently draw only vertical `flight_x_ft` / `flight_y_ft`. New stairs include `orientation`, `reverse`, `clear_bounds_ft`; use a local-coordinate transform for tread lines/arrows and actual landing direction. Keep legacy C01/C02 fields supported. Geometric validator knowing horizontal stairs does not mean renderer supports them.
6. Check counter hob/sink symbols stay inside short rotated counters.
7. Inspect labels, especially staircase/bathrooms and narrow halls, against furniture/treads/doors. Automatic empty-cell placement is not sufficient evidence of readability.

Do not rerender C01/C02 merely for reassurance; use numeric/mock drawing regression checks first and rerender only if a relevant change needs visual inspection.

## 10. Exact ordered implementation plan for the next agent

### Step A — establish a safe baseline

Read AGENTS and this handoff. Run `git status --short`, inspect diffs, locate any nested AGENTS instructions. Preserve current edits. Do not reveal secrets. Check `.venv` interpreter and dependencies. Compile current files. Run existing tests once and record current result, not historical31.

Example PowerShell commands from repository root:

```
.venv\Scripts\python.exe -m compileall -q src scripts app.py
$env:PYTHONPATH = 'src'
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Adapt to actual test runner/config if needed. Do not assume pytest installed. Add direct dependency declarations used by shipped code. Remove unused imports/format new modules for maintainability, avoiding unrelated changes.

### Step B — finish correctness and safe orchestration

Fix issues listed in sections7 and9. Keep explicit validation failures; do not catch them and render anyway. Ensure no successful report can represent wrong BHK counts,39 incorrectly labelled stores, mirrored plans, or a300-count bank with wrong size quotas. Add stricter checks when failures reveal real omissions.

Create focused tests:

- Config total300, each plot100, stores39, exact BHK mix.
- Exact mirrors/renames/style changes rejected; tiny dimensional changes rejected as near duplicates.
- Clearly distinct layouts accepted; family cap enforced.
- Bedroom-to-bedroom and common bathroom-through-bedroom access rejected even with misleading metadata.
- Door outside shared segment, furniture/swing/approach collision, blocked common route rejected.
- Store label alone insufficient; real shelving and usable dimensions needed.
- Wrong declared BHK and malformed/nonfinite geometry rejected.
- Bounded underfill produces INCOMPLETE and exact shortfall; resume does not clone or erase review evidence.
- Full rendering refuses incomplete/wrong-quota/invalid banks before renderer is called.
- Preview renders only requested accepted count; every rendered item appears in gallery; unchanged renders cached.
- Rotated drawing elements remain in authored footprints; staircase transformation matches orientation/landing.

Prefer fixtures from curated JSON/structural seeds and mocks for rendering or solver calls. Do not generate test images nobody will see. Avoid testing only implementation details or hundreds of redundant variants.

### Step C — fix Flask UI entry point

Root `app.py` must stop calling unsafe legacy `make_plan` for commercial bulk output. Suggested minimal design: read a validated persisted candidate bank, filter exact plot/BHK/facing, apply validation/diversity, check requested quantity BEFORE rendering. If insufficient, return422 with available count and clear explanation; no silent duplicates/fallback or relabelled orientation.

Expose supported20×50/30×40/30×50 and relevant2/3/4BHK choices, north facing only until genuinely supported. Show every requested output, remove `generated[:6]`. Reuse unchanged canonical renders. Keep all images labelled as concepts pending required review.

Also fix `/browse`: string `startswith(ROOT)` is not path containment and files outside OUTPUT_DIR currently cause `relative_to` errors. Restrict to resolved allowed output root using Path containment. Keep this bounded; no UI redesign required.

Test insufficient bank, unsupported input, failed validation and complete visible image list with mocked renderer.

### Step D — small bounded JSON pilot, then inspect images

Start bootstrap without solver search, e.g.:

```
.venv\Scripts\python.exe scripts/generate_300_2d_batch.py --max-attempts 0
```

Inspect report and accepted geometry. Related seeds may collapse to1 due to diversity, which is correct. Revalidate cached20×50/30×40 examples if useful; preserve their provenance and do not call them newly solved.

If needed, run one modest explicitly bounded solver pilot, e.g.12 attempts at8 seconds with2 outer workers. There is additional furnishing/validation time. Record yield and failures. Do not repeatedly extend search merely to manufacture a good count.

Only after renderer fixes, render up to3–6 accepted candidates with `--max-attempts 0 --preview N`. **Inspect every generated PNG**; contact sheet for overview, full size for architectural/readability detail. Show/link all outputs. Record assistant inspection separately from user or professional approval, keyed to content/image hashes. Do not claim the entire catalogue approved.

If quality remains bad, save concrete rejection findings and revise structural strategies. A useful deliverable is a tested fail-closed pipeline plus honest shortfall. Do not declare the user's300-image goal completed with a handful of examples.

### Step E — build real diversity only after pilot quality

The long-term solution likely needs a curated library of genuinely different planning strategies per plot/BHK group, with constrained geometry search within each. Ideas to explore as real designs, not metadata labels: central living spine, side circulation spine, front social/rear private zoning, split bedroom clusters, separate versus combined dining, different independent stair placement and entrance relationships. Courtyards/shafts require explicit exterior/void schema and validation, not leftover cells.

Evaluate plan pairs visually and by geometry/topology, maintain quota/strategy matrix, and expand gradually. Do not relax thresholds just to count variants as unique. Broaden supported facings only with real entrance/Vastu/geometry design and tests. If300 cannot be responsibly produced, report exact count and missing groups.

### Step F — documentation and GitHub

Update README with real commands/status. Rewrite PROJECT_CONTEXT around canonical JSON and actual validated-bank workflow. Remove stale statements that imply UI/legacy generator is safe or all samples production ready. Append dated `logs/project_log.txt` with changes, tests, actual accepted/rendered/reviewed counts, limitations and next work. Preserve this AI_HANDOFF, adding a dated continuation outcome rather than leaving false pending status.

`.gitignore` currently excludes all PNGs, `generated/`, most `plans/*`, `work/`, `.venv`, validation/experiments. Curated plans are explicitly allowed. If publishing a reviewed pilot, add narrowly scoped exceptions for `plans/catalog_pilot/` and selected review assets under a documentation directory. Do not force-add all generated images or old invalid300 batches.

Fetch remote, compare local/upstream, handle any remote changes without force push. Stage only relevant source/tests/config/docs and selected reviewed canonical/image assets. Exclude secrets, caches, environments and raw debug experiments. Commit and `git push origin master` (or follow the actual checked branch/upstream if changed). User authorized push. Verify remote HEAD matches the new commit and report the link. If blocked, report actual error, never claim pushed.

Final user message should be short: what changed, verification result, accepted count versus300, visible preview link if any, GitHub commit link. No inflated completeness claims.

## 11. Future AI 3D phase — not current coding scope

After an approved2D exists: canonical JSON → approved beautiful2D → AI3D using that **single2D as the ONLY visual reference**. User also described an AI-polished2D route; if used, verify it still matches canonical JSON before3D.

- Never send old Python3D render.
- Never send contact sheets or multiple competing plan references.
-3D must contain ZERO text: no room labels, dimensions, title, north arrow, CAD annotations or fake writing.
- Warm materials, realistic furniture/kitchen/bathroom/staircase, parking/car, premium real-estate cutaway presentation.
- Model intended for experiments: `black-forest-labs/flux.2-klein-4b` via OpenRouter.
- User-supplied intended endpoint: `https://openrouter.ai/api/v1/images`, references via `input_references`, target4:3.
- These API details were not verified during this resumed work. Verify current official API contract before implementation; do not spend paid credits testing guesses.
- No3D generation or paid API calls are needed to finish the current bulk code handoff.

## 12. Working-tree snapshot at stop

Observed modifications before writing this handoff:

```
 M requirements.txt
 M scripts/generate_300_2d_batch.py
 M src/house_plan_generator/bulk_assembly.py
 M src/house_plan_generator/bulk_furnishing.py
 M src/house_plan_generator/bulk_layouts.py
 M src/house_plan_generator/catalog.py
?? data/
?? src/house_plan_generator/catalog_diversity.py
?? src/house_plan_generator/catalog_outputs.py
?? src/house_plan_generator/catalog_validation.py
```

This document is also new/uncommitted. Earlier changes appear to have been committed into local1ac7e18 while the expensive agent was interrupted. Do not attribute or undo that commit. Remote synchronization remains unverified.

**First concrete next action when continuation is authorized: compile the latest files, run existing tests, then repair the renderer orientation support and safe-bank UI before any preview generation.**
