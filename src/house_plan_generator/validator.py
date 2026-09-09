from __future__ import annotations

from collections import defaultdict, deque

VALID_SIDES = {"north", "south", "east", "west"}


def _rect(room):
    return (room["x_ft"], room["y_ft"], room["x_ft"] + room["width_ft"], room["y_ft"] + room["depth_ft"])


def _touches(a, b, side):
    ax1, ay1, ax2, ay2 = _rect(a)
    bx1, by1, bx2, by2 = _rect(b)
    if side == "north":
        return ay1 == by2 and max(ax1, bx1) < min(ax2, bx2)
    if side == "south":
        return ay2 == by1 and max(ax1, bx1) < min(ax2, bx2)
    if side == "west":
        return ax1 == bx2 and max(ay1, by1) < min(ay2, by2)
    return ax2 == bx1 and max(ay1, by1) < min(ay2, by2)


def _opening_on_wall(room, opening, width=0):
    side = opening.get("side")
    offset = opening.get("offset_ft")
    opening_width = opening.get("width_ft", width)
    if side not in VALID_SIDES or not isinstance(offset, (int, float)) or opening_width <= 0:
        return False
    span = room["width_ft"] if side in {"north", "south"} else room["depth_ft"]
    return 0 <= offset and offset + opening_width <= span


def _room_category(room):
    room_id = str(room.get("id", ""))
    if room_id in {"master", "bed2", "bed3", "bed4"} or "bedroom" in room.get("name", "").lower():
        return "private"
    if room_id in {"puja", "study", "family", "lounge"} or room.get("kind") in {"puja", "study"}:
        return "semi_private"
    if room_id in {"living", "dining", "kitchen", "corridor", "circulation", "foyer", "entry", "staircase"} or room.get("kind") in {"circulation", "kitchen"}:
        return "common"
    if room_id in {"bath1", "bath2", "bathroom", "store", "utility", "laundry"} or room.get("kind") in {"bathroom", "utility", "store"}:
        return "service"
    return "common"


def _is_ensuite_connection(door, source_room, target_room):
    """A private-to-private door is only allowed when the suite relationship is explicit.

    A bedroom may be a true ensuite of another bedroom only when the metadata says so
    (for example, room['ensuite_of'] == 'master' or vice versa). A generic door flag by
    itself is not enough, because that would allow accidental bedroom-through-bedroom access.
    """
    if not source_room or not target_room:
        return False
    source_id = source_room.get("id")
    target_id = target_room.get("id")
    if source_room.get("ensuite_of") == target_id or target_room.get("ensuite_of") == source_id:
        return True
    if bool(door.get("ensuite")) and bool(source_room.get("private_suite")):
        return True
    if bool(door.get("ensuite")) and bool(target_room.get("private_suite")):
        return True
    return False


def _build_access_graph(plan, by_id):
    graph = defaultdict(set)
    for door in plan.get("doors", []):
        source = door.get("room_id")
        target = door.get("connects_to")
        if source is None or source not in by_id:
            continue
        if target == "exterior":
            graph[source].add("exterior")
            graph["exterior"].add(source)
        elif target in by_id:
            graph[source].add(target)
            graph[target].add(source)
    return graph


def _room_has_private_safe_access(graph, target_id, private_room_ids, common_room_ids):
    if target_id in {"exterior"}:
        return True
    start_nodes = ({"exterior"} | common_room_ids) - {target_id}
    queue = deque(start_nodes)
    visited = set(start_nodes)
    while queue:
        node = queue.popleft()
        if node == target_id:
            return True
        for neighbor in graph.get(node, set()):
            if neighbor in visited:
                continue
            if neighbor in private_room_ids and neighbor != target_id:
                continue
            if neighbor in {"bath1", "bath2", "bathroom", "store", "utility", "laundry"} and neighbor != target_id:
                continue
            visited.add(neighbor)
            queue.append(neighbor)
    return False


def _validate_access_privacy(plan, by_id, graph):
    errors = []
    private_room_ids = {room_id for room_id, room in by_id.items() if _room_category(room) == "private"}
    service_room_ids = {room_id for room_id, room in by_id.items() if _room_category(room) == "service"}
    common_room_ids = {room_id for room_id, room in by_id.items() if _room_category(room) == "common"}
    for door in plan.get("doors", []):
        source_id = door.get("room_id")
        target_id = door.get("connects_to")
        if source_id not in by_id or target_id not in by_id:
            continue
        source_room = by_id[source_id]
        target_room = by_id[target_id]
        source_cat = _room_category(source_room)
        target_cat = _room_category(target_room)
        if source_cat == "private" and target_cat == "private" and not _is_ensuite_connection(door, source_room, target_room):
            errors.append(f"door {door.get('id')}: private-private access is not allowed")
        if source_cat == "private" and target_cat == "service" and not _is_ensuite_connection(door, source_room, target_room):
            errors.append(f"door {door.get('id')}: bedroom cannot access service room directly unless it is an ensuite")
        if source_cat == "service" and target_cat == "private" and not _is_ensuite_connection(door, source_room, target_room):
            errors.append(f"door {door.get('id')}: bathroom or service room cannot access a bedroom unless marked as ensuite")
        if source_cat == "private" and target_id == "staircase":
            errors.append(f"door {door.get('id')}: staircase should not be accessed through a bedroom")

    for room_id, room in by_id.items():
        category = _room_category(room)
        if room.get("ensuite_of"):
            continue
        if category == "private" or room_id in {"staircase", "bath1", "bath2", "bathroom", "kitchen", "living", "dining"}:
            if not _room_has_private_safe_access(graph, room_id, private_room_ids, common_room_ids):
                if category == "private":
                    errors.append(f"room {room_id}: private room is accessed through another private room or has no common-area access")
                elif room_id in {"staircase"}:
                    errors.append(f"room staircase: staircase must be reachable from circulation/common area")
                elif room_id in {"bath1", "bath2", "bathroom"}:
                    errors.append(f"room {room_id}: bathroom is not reachable from common circulation without passing through a private room")
                elif room_id in {"kitchen", "living", "dining"}:
                    errors.append(f"room {room_id}: common area is only reachable through a private room")
    return errors


def validate_plan(plan):
    errors, warnings = [], []
    plot = plan.get("plot", {})
    width, depth = plot.get("width_ft"), plot.get("depth_ft")
    if not isinstance(width, (int, float)) or not isinstance(depth, (int, float)) or width <= 0 or depth <= 0:
        errors.append("invalid plot dimensions")
        return _result(plan, errors, warnings)
    rooms = plan.get("rooms", [])
    ids = [room.get("id") for room in rooms]
    if any(not room_id for room_id in ids) or len(ids) != len(set(ids)):
        errors.append("duplicate or missing room IDs")
    by_id = {room.get("id"): room for room in rooms}
    intentional = {tuple(pair) for pair in plan.get("intentional_shared_areas", [])}
    for room in rooms:
        if room.get("width_ft", 0) <= 0 or room.get("depth_ft", 0) <= 0:
            errors.append(f"{room.get('id')}: non-positive dimensions")
        x, y, x2, y2 = _rect(room)
        if x < 0 or y < 0 or x2 > width or y2 > depth:
            errors.append(f"{room.get('id')}: outside plot boundary")
        if room.get("width_ft", 0) < 3 or room.get("depth_ft", 0) < 3:
            warnings.append(f"{room.get('id')}: unusually small room")
    for index, first in enumerate(rooms):
        for second in rooms[index + 1:]:
            x_overlap = min(_rect(first)[2], _rect(second)[2]) - max(_rect(first)[0], _rect(second)[0])
            y_overlap = min(_rect(first)[3], _rect(second)[3]) - max(_rect(first)[1], _rect(second)[1])
            if x_overlap > 0 and y_overlap > 0 and (first["id"], second["id"]) not in intentional and (second["id"], first["id"]) not in intentional:
                errors.append(f"rooms overlap: {first['id']} and {second['id']}")
    usable_area = width * depth
    room_area = sum(room.get("width_ft", 0) * room.get("depth_ft", 0) for room in rooms if room.get("kind") != "parking")
    if room_area > usable_area:
        errors.append("room area exceeds plot area")
    elif room_area < usable_area * 0.25:
        warnings.append("suspiciously low plot utilization")

    graph = defaultdict(set)
    for door in plan.get("doors", []):
        room_id, target, side = door.get("room_id"), door.get("connects_to"), door.get("side")
        room = by_id.get(room_id)
        if room is None:
            errors.append(f"door {door.get('id')}: unknown room")
            continue
        if not _opening_on_wall(room, door, 2):
            errors.append(f"door {door.get('id')}: invalid wall position")
        if target == "exterior":
            if not ((side == "north" and room["y_ft"] == 0) or (side == "south" and room["y_ft"] + room["depth_ft"] == depth) or (side == "west" and room["x_ft"] == 0) or (side == "east" and room["x_ft"] + room["width_ft"] == width)):
                errors.append(f"door {door.get('id')}: exterior door is not on plot boundary")
            graph[room_id].add("exterior")
            graph["exterior"].add(room_id)
        elif target not in by_id:
            errors.append(f"door {door.get('id')}: unknown target {target}")
        else:
            if not _touches(room, by_id[target], side):
                errors.append(f"door {door.get('id')}: {room_id} does not border {target} on {side}")
            graph[room_id].add(target)
            graph[target].add(room_id)
    for window in plan.get("windows", []):
        room = by_id.get(window.get("room_id"))
        if room is None or not _opening_on_wall(room, window, window.get("width_ft", 0)):
            errors.append(f"window {window.get('id')}: invalid room or wall position")
            continue
        x, y, x2, y2 = _rect(room)
        side = window.get("side")
        exterior = (side == "north" and y == 0) or (side == "south" and y2 == depth) or (side == "west" and x == 0) or (side == "east" and x2 == width)
        if not exterior and not window.get("permitted_internal", False):
            errors.append(f"window {window.get('id')}: not on exterior wall")
    for stair in plan.get("stairs", []):
        room = by_id.get(stair.get("room_id"))
        if room is None or room.get("kind") != "staircase" or stair.get("width_ft", 0) <= 0 or stair.get("depth_ft", 0) <= 0:
            errors.append(f"staircase {stair.get('id')}: invalid geometry")
        if not stair.get("entrance_door_id"):
            errors.append(f"staircase {stair.get('id')}: missing entrance")
    for item in plan.get("parking", []):
        room = by_id.get(item.get("room_id"))
        if room is None or room.get("kind") != "parking" or item.get("width_ft", 0) < 8 or item.get("depth_ft", 0) < 15:
            errors.append(f"parking {item.get('id')}: implausible dimensions or room")

    reachable = set()
    queue = deque(["exterior"])
    while queue:
        current = queue.popleft()
        if current in reachable:
            continue
        reachable.add(current)
        queue.extend(graph[current] - reachable)
    required_rooms = [room["id"] for room in rooms if room.get("kind") not in {"parking", "circulation"}]
    isolated = [room_id for room_id in required_rooms if room_id not in reachable]
    if isolated:
        errors.append(f"isolated rooms: {', '.join(isolated)}")
    access_errors = _validate_access_privacy(plan, by_id, graph)
    errors.extend(access_errors)
    vastu = validate_vastu(plan)
    warnings.extend(vastu["issues"] if vastu["status"] != "PASS" else [])
    return _result(plan, errors, warnings, vastu)


def validate_vastu(plan):
    rooms = {room["id"]: room for room in plan.get("rooms", [])}
    issues = []
    def zone(room):
        cx = room["x_ft"] + room["width_ft"] / 2
        cy = room["y_ft"] + room["depth_ft"] / 2
        w, d = plan["plot"]["width_ft"], plan["plot"]["depth_ft"]
        horizontal = "west" if cx < w / 3 else "east" if cx > 2 * w / 3 else "center"
        vertical = "north" if cy < d / 3 else "south" if cy > 2 * d / 3 else "center"
        return vertical + "-" + horizontal
    if "puja" in rooms and zone(rooms["puja"]) != "north-east":
        issues.append("puja is not in preferred north-east zone")
    if "kitchen" in rooms and zone(rooms["kitchen"]) not in {"south-east", "center-east"}:
        issues.append("kitchen is not in preferred south-east or suitable east zone")
    if "master" in rooms and zone(rooms["master"]) != "south-west":
        issues.append("master bedroom is not in preferred south-west zone")
    return {"status": "PASS" if not issues else "WARNING", "issues": issues}


def _result(plan, errors, warnings, vastu=None):
    return {
        "design_id": plan.get("design_id"), "plot_valid": not any("plot" in error or "boundary" in error for error in errors),
        "room_overlap": any("overlap" in error for error in errors),
        "rooms_inside_plot": not any("outside plot" in error for error in errors),
        "doors_valid": not any("door" in error for error in errors),
        "windows_valid": not any("window" in error for error in errors),
        "stairs_valid": not any("staircase" in error for error in errors),
        "parking_valid": not any("parking" in error for error in errors),
        "circulation_valid": not any("isolated" in error for error in errors),
        "access_valid": not any("private" in error or "bathroom" in error or "staircase" in error for error in errors),
        "privacy_valid": not any("private-private" in error or "bathroom cannot access" in error or "bedroom cannot access" in error for error in errors),
        "room_proportions_valid": True,
        "vastu": vastu or {"status": "FAIL", "issues": []}, "overall": "PASS" if not errors else "FAIL",
        "errors": errors, "warnings": warnings,
    }
