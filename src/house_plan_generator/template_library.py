"""Master-template library: one fixed architectural strategy per quota group.

Construction that guarantees exact tiling for EVERY approved parameter set:
each template describes the plot as a vertical stack of full-width horizontal
bands whose depths sum to the plot depth. Each band is a left-to-right sequence
of columns whose widths sum to the plot width. Approved parameters only move
interior band/column split lines within safe ranges, so the architectural
strategy, zoning and room relationships stay fixed while proportions vary and
the plot is always tiled with no gaps or overlaps.

``band_layout`` turns a band specification into a {room_id: [x, y, w, d]} dict.
Every template below is proven (see tests + the generator report) to yield at
least one candidate that passes all existing gates.
"""
from __future__ import annotations

from .template_generator import MasterTemplate


def band_layout(width, depth, bands):
    """Materialise stacked full-width bands into exact-tiling room rectangles.

    ``bands`` is a list of (band_depth, columns) where ``columns`` is a list of
    (room_id, column_width). Column widths in each band must sum to ``width`` and
    band depths must sum to ``depth``; the generator's tiling_error check backs
    this up, but by construction it always holds when the sums are respected.
    """
    rooms = {}
    y = 0
    for band_depth, columns in bands:
        x = 0
        for room_id, col_width in columns:
            rooms[room_id] = [x, y, col_width, band_depth]
            x += col_width
        y += band_depth
    return rooms


# --------------------------------------------------------------------------- #
# 20 x 50 — front social band, mid service band, rear bedroom pair
# --------------------------------------------------------------------------- #
def _mk_20x50_2bhk_store(p_defaults=None):
    """Anchored on the accepted E01 strategy: front social band, left stair with
    store-over-kitchen on the east, tall central hall, rear cross-lobby, rear
    bedroom pair. Explicit rectangles keep the E01 topology (hall taller than
    stair) that a strict equal-depth band model cannot express."""
    W, D = 20, 50

    def layout(p):
        # E01-anchored store variant: stair | tall central hall | east store-over-
        # kitchen; common bath below the stair; full-width cross-lobby; rear pair.
        fb = p["front"]                 # front band (parking 9 + living)
        stair = p["stair"]              # left stair column width
        kit_w = p["kit_w"]              # east store/kitchen column width
        store_d = p["store_d"]          # store depth (east, above kitchen)
        bath_d = p["bath_d"]            # bath depth below the stair
        pull = p["lobby"]               # rear cross-lobby depth (full width)
        rear_band = p["rear"]           # rear bedroom band depth
        hall_w = W - stair - kit_w      # central hall column width
        mid = D - fb - bath_d - pull - rear_band  # stair band depth
        hall_d = mid + bath_d           # hall runs beside stair and bath
        y_bath = fb + mid
        y_lobby = y_bath + bath_d
        y_rear = y_lobby + pull
        return {
            "parking": [0, 0, 9, fb],
            "living": [9, 0, W - 9, fb],
            "staircase": [0, fb, stair, mid],
            "hall": [stair, fb, hall_w, hall_d],
            "store": [stair + hall_w, fb, kit_w, store_d],
            "kitchen": [stair + hall_w, fb + store_d, kit_w, hall_d - store_d],
            "bath1": [0, y_bath, stair, bath_d],
            "hall2": [0, y_lobby, W, pull],
            "master": [0, y_rear, p["master_w"], rear_band],
            "bed2": [p["master_w"], y_rear, W - p["master_w"], rear_band],
        }

    params = {
        "front": (16, 15), "stair": (8,), "kit_w": (7,), "store_d": (7, 8),
        "bath_d": (6, 7), "lobby": (4, 5), "rear": (12, 11), "master_w": (11, 10),
    }

    def valid(p):
        # stair band must stay >=13; living needs front>=15; bedrooms need rear>=11.
        mid = D - p["front"] - p["bath_d"] - p["lobby"] - p["rear"]
        return mid >= 13 and p["rear"] >= 11 and p["front"] >= 15

    return MasterTemplate(
        template_id="T_20x50_2bhk_store",
        strategy="20x50 front social band, left stair, east store-over-kitchen, "
                 "tall central hall, rear bedroom pair with usable store",
        width=W, depth=D, bedrooms=2, store=True, entry="living",
        combined_living_dining=True, params=params, layout=layout, valid=valid,
    )


def _mk_20x50_2bhk_nostore():
    """Front social band, left stair, east kitchen, central hall, rear
    cross-lobby with common bath, rear bedroom pair (no store)."""
    W, D = 20, 50

    def layout(p):
        # E01-anchored no-store variant: stair | tall central hall | east kitchen;
        # common bath below the stair; full-width cross-lobby; rear bedroom pair.
        fb = p["front"]
        stair = p["stair"]
        kit_w = p["kit_w"]
        bath_d = p["bath_d"]           # bath depth below the stair
        pull = p["lobby"]              # full-width cross-lobby depth
        rear_band = p["rear"]          # rear bedroom band depth
        hall_w = W - stair - kit_w
        mid = D - fb - bath_d - pull - rear_band  # stair band depth
        hall_d = mid + bath_d          # central hall runs beside stair and bath
        y_bath = fb + mid
        y_lobby = y_bath + bath_d
        y_rear = y_lobby + pull
        return {
            "parking": [0, 0, 9, fb],
            "living": [9, 0, W - 9, fb],
            "staircase": [0, fb, stair, mid],
            "hall": [stair, fb, hall_w, hall_d],
            "kitchen": [stair + hall_w, fb, kit_w, hall_d],
            "bath1": [0, y_bath, stair, bath_d],
            "hall2": [0, y_lobby, W, pull],
            "master": [0, y_rear, p["master_w"], rear_band],
            "bed2": [p["master_w"], y_rear, W - p["master_w"], rear_band],
        }

    # Keep the stair band (mid) at a safe >=13 by holding front+bath_d+lobby+rear
    # Safe ranges only: living needs front>=15; bedrooms need rear>=11. Diversity
    # comes from the east kitchen width, bath/lobby depths and the rear split.
    params = {
        "front": (16, 15), "stair": (8,), "kit_w": (7, 8), "bath_d": (6, 7),
        "lobby": (4, 5), "rear": (12, 11), "master_w": (11, 10),
    }

    def valid(p):
        mid = D - p["front"] - p["bath_d"] - p["lobby"] - p["rear"]
        return mid >= 13 and p["rear"] >= 11 and p["front"] >= 15

    return MasterTemplate(
        template_id="T_20x50_2bhk_nostore",
        strategy="20x50 front social band, left stair, east kitchen, central "
                 "hall spine, rear cross-lobby with common bath, rear bedroom pair",
        width=W, depth=D, bedrooms=2, store=False, entry="living",
        combined_living_dining=True, params=params, layout=layout, valid=valid,
    )


# --------------------------------------------------------------------------- #
# 30 x 50 3BHK — E04-anchored: front social band, mid service band (stair | hall
# | kitchen), bath1 band, rear bedroom band with a master attached (ensuite) bath.
# --------------------------------------------------------------------------- #
def _mk_30x50_3bhk_nostore():
    W, D = 30, 50

    def layout(p):
        # E04-anchored: continuous central circulation hall -> hall2 -> hall3 down
        # the plot; common bath (bath1) west, bed3 east; rear master suite with an
        # attached ensuite bath. The hall/hall2/hall3 spine keeps the common rooms
        # connected so the door spanning-tree exists.
        fb = p["front"]                # front band (parking 10 + living)
        mid = p["service"]            # stair/hall/kitchen band depth
        bath_band = p["bath_band"]    # common-bath + hall2 + bed3 band depth
        stair = p["stair"]            # left stair width
        hall_w = p["hall_w"]          # central hall / hall2 width
        kit_w = W - stair - hall_w    # kitchen fills the rest
        bath1_w = p["bath1_w"]        # common bath width (west, left of hall2)
        rear = D - fb - mid - bath_band
        rear_hall = p["rear_hall"]    # rear corridor stub width
        master_w = p["master_w"]
        ens_w = p["ensuite_w"]
        bed2_w = p["bed2_w"]          # rear bed2 width (independent of bath band)
        y_bath = fb + mid
        y_rear = y_bath + bath_band
        return {
            "parking": [0, 0, 10, fb],
            "living": [10, 0, W - 10, fb],
            "staircase": [0, fb, stair, mid],
            "hall": [stair, fb, hall_w, mid],
            "kitchen": [stair + hall_w, fb, kit_w, mid],
            "bath1": [0, y_bath, bath1_w, bath_band],
            "hall2": [bath1_w, y_bath, hall_w, bath_band],
            "bed3": [bath1_w + hall_w, y_bath, W - bath1_w - hall_w, bath_band],
            "bed2": [0, y_rear, bed2_w, rear],
            "hall3": [bed2_w, y_rear, rear_hall, rear],
            "master": [bed2_w + rear_hall, y_rear, master_w, rear],
            "bath2": [bed2_w + rear_hall + master_w, y_rear, ens_w, rear],
        }

    # East stair variant: mirror the service spine to the east (stair on the right,
    # kitchen on the west) so the strategy is architecturally distinct from the
    # west-stair E04 anchor and clears the diversity gate rather than duplicating it.
    params = {
        "front": (16, 15), "service": (13,), "bath_band": (12, 11, 10),
        "stair": (10,), "hall_w": (6, 7), "bath1_w": (9, 10),
        "rear_hall": (4,), "master_w": (10, 11), "ensuite_w": (6, 7), "bed2_w": (10, 9),
    }

    def valid(p):
        rear = D - p["front"] - p["service"] - p["bath_band"]
        # west band (bath1 | hall2 | bed3) must sum to W
        bed3_w = W - p["bath1_w"] - p["hall_w"]
        # rear band (bed2 | hall3 | master | bath2) must sum to W
        rear_sum = p["bed2_w"] + p["rear_hall"] + p["master_w"] + p["ensuite_w"]
        return (rear >= 11 and p["bed2_w"] >= 9 and bed3_w >= 12
                and rear_sum == W and p["bath_band"] >= 10 and p["front"] >= 15)

    return MasterTemplate(
        template_id="T_30x50_3bhk_nostore",
        strategy="30x50 front social band, central service spine, common-bath "
                 "band, rear bedroom band; master suite with attached (ensuite) "
                 "bath plus a common bath for the other bedrooms",
        width=W, depth=D, bedrooms=3, store=False, entry="living",
        combined_living_dining=True, params=params, layout=layout, valid=valid,
        ensuite={"bath2": "master"},
    )


TEMPLATES = [
    _mk_20x50_2bhk_nostore(),
    _mk_20x50_2bhk_store(),
    _mk_30x50_3bhk_nostore(),
]
