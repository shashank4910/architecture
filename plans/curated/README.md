# Authored concept C01

This folder is a separate, manually designed pilot. `C01_north_20x50_2bhk.json`
is the source of truth; the bulk generator does not create or overwrite it.

Reproduce from the project root:

```powershell
.\.venv\Scripts\python.exe scripts/render_curated_concept.py
```

The command checks the JSON, stops on errors, and writes the furnished image,
geometry manifest and review JSON to `generated/curated/C01/`.

## Brief and design decisions

- North-facing 20 x 50 ft planning envelope, car porch, ground-floor 2BHK,
  four-seat dining, one common bathroom and internal terrace staircase.
- Front living buffers bedrooms from visitors. Dining is the shared distribution
  point. A separate passage bypasses the kitchen. The rear lobby independently
  serves both bedrooms and the common bathroom.
- Master has a 5 x 6.5 ft bed with 2.5 ft on both sides after the assumed wall
  reserve. Bedroom 2 has a full-length single bed and a 4 ft sliding wardrobe.
- The west end of the lobby contains linen storage rather than unexplained floor
  space. This is a cupboard, not a separate store room.
- Stair has two 3 ft flights, a return landing and an entrance landing. The assumed
  9 ft floor height gives sixteen 6.75 in risers, with seven 10 in goings per flight.
- Northeast prayer shelf and southwest master follow the stated Vastu preferences;
  the kitchen is east-central rather than strictly southeast. This compromise is
  explicit even though the legacy Vastu checker accepts east kitchens.

## Visual review performed

Inspected the full-size furnished sheet and corrected bedroom/bath labels,
kitchen entry versus counter placement, living-room bypass space, car boarding
space and the unused end of the lobby. Door leaves enter the rooms rather than
the shared passage. The master bedside clearances were balanced to 2.5 ft each.
The sheet retains the original warm palette, furniture language and wall style.

Estimated clear dimensions (feet, after conservative wall reserves): living
10 x 15; master 10 x 10; guest bedroom 8 x 10; kitchen 7 x 9.5; bathroom 7 x 5.5;
main passage 3.5 wide. Printed room dimensions are planning-cell sizes.

## Review status and remaining constraints

**Authored concept, ready for user review; not catalogue-approved.** Automated
checks cover room geometry, actual shared-wall door spans, entrance-rooted privacy
routes, furniture bounds/collisions, conservative swing envelopes, declared usage
clearances, corridor width, stair footprint, orientation and cell-area accounting.
They do not prove every furnished walking route or building-code compliance.

No statutory setbacks have been deducted. West/east windows assume legal access
to open air: this design needs revision for a party-wall site. Stair structure,
headroom, upper-floor arrival, ventilation adequacy and local site rules remain
unresolved. No structural or construction approval is implied.

The second bedroom is a single-bed child/guest room. There is one shared bathroom,
not two. The internal stair is for this household's terrace access, not an
independent rental-floor entrance. Car parking assumes a compact car with boarding
mainly on the east side and separate pedestrian access from the north.

No 3D image was generated at this stage. The next presentation step should use the
accepted individual 2D image as its sole visual reference, with no text in the 3D.
