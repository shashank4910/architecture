# C02: front stair and two double bedrooms

Status: authored concept, visually reviewed and ready for user comparison. It is
not construction-ready or catalogue-approved. C01 is preserved as the first
prototype; this is a separately authored JSON plan, not a bulk-generator output.

## Design arrangement

The northwest terrace stair and northeast car porch flank a separate pedestrian
entry. The stair can be reached before entering the living room. Living and dining
occupy the middle of the house. A compact shared lobby serves the bathroom,
kitchen and two independent rear bedrooms.

The front staircase and middle living/dining arrangement are substantive changes
from C01's front living, middle staircase and full-width rear bedroom corridor.
Both concepts retain a rear bedroom pair; this is a useful second strategy, not
evidence that the whole catalogue now has sufficient diversity.

## Like-for-like comparison

All sizes below use the same wall allowances. Printed plan room sizes are planning
cells, while estimated clear dimensions reserve 9 inches at the plot perimeter
and 3 inches on each side of internal centerlines.

| Item | C01 | C02 |
|---|---|---|
| Plot/facing | 20 x 50 ft, north | 20 x 50 ft, north |
| Master, estimated clear | 10 x 10 ft | 9 x 13 ft |
| Bedroom 2, estimated clear | 8 x 10 ft, single bed | 9 x 13 ft, double bed |
| Bedroom beds | One double and one single | Two 5 x 6.5 ft doubles |
| Master bedside space | 2.5 ft each side | 2 ft each side |
| Bedroom wardrobes | 3.1 ft run and 4 ft run | Two 5 ft runs |
| Kitchen, estimated clear | 7 x 9.5 ft | 5.5 x 7.5 ft |
| Bathrooms | One common | One common |
| Stair access | Through living and dining | Direct from front entry |
| Dedicated circulation cells | 120 sq ft | 101.5 sq ft |
| Living, estimated clear | 10 x 15 ft | 10 x 14.5 ft |
| Dining, estimated clear | 11 x 8.5 ft | 8 x 11.5 ft |

Dedicated circulation decreases by 18.5 sq ft, or 15.4%. This includes the entry
passage in C02. It does not count every walking route within living/dining as a
separate corridor, and should not be presented as a 15.4% improvement in total
usable area. The extra bedroom area also comes partly from a smaller kitchen and
other room-area changes.

## Visual inspection and corrections

- Traced separate exterior-to-bedroom, bathroom, kitchen, dining and stair routes.
  None passes through another bedroom, bathroom or kitchen.
- Authored full-size double beds and wardrobes; checked 2 ft bedside space and
  2.5 ft wardrobe operating space. Bedroom doors swing into their rooms.
- Rehinged the entrance door to the parking side so the open leaf does not sit
  in front of the stair opening.
- Checked the kitchen as a compact single-cook layout: L-shaped counters, a
  separate fridge footprint and a 3.25 x 3 ft declared working area. The fridge
  operating area shares this working floor and assumes one user at a time.
- Corrected the sink symbol overflowing its short counter and checked room labels
  on the revised image. The original palette and rendering style are retained.
- Retained one common bathroom. A second bathroom has not been squeezed into
  these bedroom or kitchen areas.

## Assessment and remaining limitations

C02 is stronger for a household wanting two double-bed rooms and direct entry-to-
terrace-stair access. C01 has a materially larger kitchen and more master bedside
space. C02 therefore offers a different tradeoff, not a universal upgrade.

The entry passage is approximately 3 ft clear and relatively long; it is functional
circulation rather than furnished living space. The stair assumes a 9 ft
floor-to-floor height, sixteen 6.75 in risers and 10 in goings. Headroom, structure,
upper-floor arrival and local stair requirements remain unresolved.

No required site setbacks are deducted. Side and rear ventilation depends on
legally available open air. A party-wall or blocked-rear site needs redesign.
Southwest master and northwest stair follow the selected Vastu preferences;
the kitchen remains east-central and there is no dedicated northeast puja room.

The numerical review checks specified geometry, access and clearance conditions.
It does not certify every furnished walking path, daylight performance, statutory
compliance or professional architectural approval. No 3D reference was generated.

## Reproduce from the project root

```powershell
.\.venv\Scripts\python.exe scripts/render_curated_concept.py --plan plans/curated/C02_north_20x50_2bhk.json --output generated/curated/C02
.\.venv\Scripts\python.exe -m unittest -q tests/test_validator.py tests/test_match_validator.py tests/test_renderer.py tests/test_curated_concept.py
```
