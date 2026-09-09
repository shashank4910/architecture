from __future__ import annotations

from copy import deepcopy


def r(room_id, name, x, y, width, depth, kind="habitable"):
    return {"id": room_id, "name": name, "x_ft": x, "y_ft": y, "width_ft": width, "depth_ft": depth, "kind": kind}


def make_plan(number, width, depth, facing, bedrooms):
    rooms = [
        r("parking", "Parking", 0, 0, min(10, width // 2), 16, "parking"),
        r("living", "Living Room", width // 2, 0, width - width // 2, 12),
        r("puja", "Puja", width - 8, 12, 4, 4, "puja"),
        r("dining", "Dining", 0, 16, width // 2, 8),
        r("kitchen", "Kitchen", width // 2, 16, width - width // 2, 10, "kitchen"),
        r("staircase", "Staircase", 0, 24, 6, 9, "staircase"),
        r("bath1", "Bathroom 1", 6, 24, 4 if width >= 30 else 4, 6, "bathroom"),
        r("corridor", "Circulation", 6, 30, 6 if width == 20 else 9, 3, "circulation"),
    ]
    if bedrooms == 3:
        rooms += [
            r("master", "Master Bedroom", width // 2, 33 if width == 20 else 26, width - width // 2, 10 if width == 20 else 8),
            r("bed2", "Bedroom 2", 0, 33, width // 2, 10 if width == 20 else depth - 33),
            r("bed3", "Bedroom 3", width // 2, 43 if width == 20 else 34, width - width // 2, depth - (43 if width == 20 else 34)),
        ]
    else:
        rooms += [
            r("master", "Master Bedroom", width // 2, 33, width - width // 2, 10),
            r("bed2", "Bedroom 2", 0, 33, width // 2, 10),
        ]
    if width == 20:
        rooms += [r("bath2", "Bathroom 2", 0, depth - 7, 6, 7, "bathroom")]
    else:
        rooms += [r("bath2", "Bathroom 2", 10, 24, 5, 6, "bathroom")]
    doors = [
        {"id": "entrance", "room_id": "living", "side": facing.lower(), "offset_ft": 5, "connects_to": "exterior"},
        {"id": "living_puja", "room_id": "living", "side": "south", "offset_ft": width - 8 - width // 2, "connects_to": "puja"},
        {"id": "puja_kitchen", "room_id": "puja", "side": "south", "offset_ft": 1, "connects_to": "kitchen"},
        {"id": "dining_kitchen", "room_id": "dining", "side": "east", "offset_ft": 4, "connects_to": "kitchen"},
        {"id": "dining_stair", "room_id": "dining", "side": "south", "offset_ft": 1, "connects_to": "staircase"},
        {"id": "stair_corridor", "room_id": "staircase", "side": "east", "offset_ft": 6, "connects_to": "corridor"},
        {"id": "bath1_corridor", "room_id": "bath1", "side": "south", "offset_ft": 1, "connects_to": "corridor"},
        {"id": "corridor_master", "room_id": "corridor", "side": "south" if width == 20 else "east", "offset_ft": 3 if width == 20 else 1, "connects_to": "master"},
        {"id": "corridor_bed2", "room_id": "corridor", "side": "south", "offset_ft": 1, "connects_to": "bed2"},
        {"id": "master_bed3", "room_id": "master", "side": "south" if bedrooms == 3 else "west", "offset_ft": 5, "connects_to": "bed3" if bedrooms == 3 else "bed2"},
        {"id": "bath2_corridor", "room_id": "bath2", "side": "south" if width == 30 else "north", "offset_ft": 2, "connects_to": "corridor" if width == 30 else "bed2"},
    ]
    windows = []
    for room in rooms:
        if room["kind"] in {"circulation", "parking"}:
            continue
        if room["y_ft"] == 0:
            side = "north"
        elif room["y_ft"] + room["depth_ft"] == depth:
            side = "south"
        elif room["x_ft"] == 0:
            side = "west"
        elif room["x_ft"] + room["width_ft"] == width:
            side = "east"
        else:
            continue
        windows.append({"id": f"{room['id']}_window", "room_id": room["id"], "side": side, "offset_ft": 2, "width_ft": min(4, (room["width_ft"] if side in {"north", "south"} else room["depth_ft"]) - 1)})
    stairs = [{"id": "main_stairs", "room_id": "staircase", "width_ft": 6, "depth_ft": 9, "riser_count": 14, "entrance_door_id": "stair_corridor"}]
    parking = [{"id": "car_1", "room_id": "parking", "width_ft": min(10, width // 2), "depth_ft": 16}]
    return {
        "design_id": f"design_{number:03d}",
        "plot": {"width_ft": width, "depth_ft": depth, "facing": facing.lower()},
        "floors": 1, "bedrooms": bedrooms, "bathrooms": 2,
        "rooms": rooms, "doors": doors, "windows": windows, "stairs": stairs, "parking": parking,
        "vastu": {"puja_preferred": "north-east", "kitchen_preferred": "south-east", "master_preferred": "south-west", "status": "conceptual guidance"},
        "disclaimer": "APPROXIMATE / CONCEPTUAL. Vastu-oriented conceptual house plan; not construction-ready, architect-approved, structurally verified, government-approved, or 100% Vastu compliant.",
    }


BASE_PLANS = [
    make_plan(1, 20, 50, "north", 3),
    make_plan(2, 20, 50, "east", 3),
    make_plan(3, 20, 50, "north", 2),
    make_plan(4, 30, 40, "east", 3),
    make_plan(5, 30, 40, "north", 3),
]


def _transform_plan(source, number, strategy, mirror_x=False, mirror_y=False):
    plan = deepcopy(source)
    width, depth = plan["plot"]["width_ft"], plan["plot"]["depth_ft"]
    plan["design_id"] = f"design_{number:03d}"
    plan["layout_strategy"] = strategy
    for room in plan["rooms"]:
        if mirror_x:
            room["x_ft"] = width - room["x_ft"] - room["width_ft"]
        if mirror_y:
            room["y_ft"] = depth - room["y_ft"] - room["depth_ft"]
    for door in plan["doors"]:
        if mirror_x:
            if door["side"] == "east":
                door["side"] = "west"
            elif door["side"] == "west":
                door["side"] = "east"
        if mirror_y:
            if door["side"] == "north":
                door["side"] = "south"
            elif door["side"] == "south":
                door["side"] = "north"
        if door["side"] in {"north", "south"}:
            room = next(item for item in plan["rooms"] if item["id"] == door["room_id"])
            door["offset_ft"] = min(door["offset_ft"], room["width_ft"] - 2)
        else:
            room = next(item for item in plan["rooms"] if item["id"] == door["room_id"])
            door["offset_ft"] = min(door["offset_ft"], room["depth_ft"] - 2)
    for window in plan["windows"]:
        if mirror_x:
            if window["side"] == "east":
                window["side"] = "west"
            elif window["side"] == "west":
                window["side"] = "east"
        if mirror_y:
            if window["side"] == "north":
                window["side"] = "south"
            elif window["side"] == "south":
                window["side"] = "north"
    plan["plot"]["facing"] = next(door["side"] for door in plan["doors"] if door["id"] == "entrance")
    return plan


def _refresh_exterior_windows(plan):
    width, depth = plan["plot"]["width_ft"], plan["plot"]["depth_ft"]
    windows = []
    for room in plan["rooms"]:
        if room["kind"] in {"circulation", "parking"}:
            continue
        if room["y_ft"] == 0:
            side = "north"
        elif room["y_ft"] + room["depth_ft"] == depth:
            side = "south"
        elif room["x_ft"] == 0:
            side = "west"
        elif room["x_ft"] + room["width_ft"] == width:
            side = "east"
        else:
            continue
        span = room["width_ft"] if side in {"north", "south"} else room["depth_ft"]
        windows.append({"id": f"{room['id']}_window", "room_id": room["id"], "side": side, "offset_ft": 2, "width_ft": min(4, span - 1)})
    plan["windows"] = windows
    return plan


BASE_PLANS[0]["layout_strategy"] = "front parking, right-front living, left-side circulation, rear bedroom cluster"
BASE_PLANS[1]["layout_strategy"] = "front parking, left-front living, right-side circulation, rear bedroom cluster"
BASE_PLANS[2]["layout_strategy"] = "compact front parking, central public zone, two-bedroom rear cluster"
BASE_PLANS[3]["layout_strategy"] = "wide front parking, central public zone, east kitchen, rear bedroom cluster"
BASE_PLANS[4]["layout_strategy"] = "wide front parking, north public zone, central service spine, rear bedrooms"

# A second 30x40 base strategy: parking is on the east edge and the public
# living zone occupies the broad west/front side.
BASE_PLANS[4]["plot"]["facing"] = "north"
for room in BASE_PLANS[4]["rooms"]:
    if room["id"] == "parking":
        room.update({"x_ft": 20, "y_ft": 0})
    elif room["id"] == "living":
        room.update({"x_ft": 0, "y_ft": 0, "width_ft": 20, "depth_ft": 12})
    elif room["id"] == "puja":
        room.update({"x_ft": 16, "y_ft": 12})
BASE_PLANS[4]["doors"] = [
    door for door in BASE_PLANS[4]["doors"]
    if door["id"] not in {"entrance", "living_puja"}
]
BASE_PLANS[4]["doors"].extend([
    {"id": "entrance", "room_id": "living", "side": "north", "offset_ft": 8, "connects_to": "exterior"},
    {"id": "living_puja", "room_id": "living", "side": "south", "offset_ft": 17, "connects_to": "puja"},
])
BASE_PLANS[4]["doors"].sort(key=lambda door: 0 if door["id"] == "entrance" else 1)
BASE_PLANS[4]["layout_strategy"] = "30x40 north-facing, east-side parking, wide west living, compact northeast puja"
_refresh_exterior_windows(BASE_PLANS[4])

PLANS = [
    BASE_PLANS[0],
    _transform_plan(BASE_PLANS[1], 2, "east-facing, rear public zone, front bedroom cluster, side circulation", mirror_y=True),
    BASE_PLANS[2],
    _transform_plan(BASE_PLANS[0], 4, "front parking, mirrored left living, right-side circulation, rear bedroom cluster", mirror_x=True),
    _transform_plan(BASE_PLANS[2], 5, "20x50 north-facing, mirrored compact two-bedroom cluster, west-side circulation", mirror_x=True),
    _transform_plan(BASE_PLANS[3], 6, "30x40 east-facing, mirrored service spine, left-side staircase, bedroom cluster", mirror_x=True),
    _transform_plan(BASE_PLANS[4], 7, "30x40 north-facing, reversed depth, front private cluster, rear public zone", mirror_y=True),
    _transform_plan(BASE_PLANS[3], 8, "30x40 east-facing, 180-degree rotated zoning, opposite parking edge", mirror_x=True, mirror_y=True),
    _transform_plan(BASE_PLANS[4], 9, "30x40 north-facing, mirrored horizontal kitchen and bedroom grouping", mirror_x=True, mirror_y=True),
    _transform_plan(BASE_PLANS[3], 10, "30x40 east-facing, reversed depth open public-to-private zoning", mirror_y=True),
]


def get_plans():
    return deepcopy(PLANS)
