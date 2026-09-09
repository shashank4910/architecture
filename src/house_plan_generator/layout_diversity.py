from __future__ import annotations

from itertools import combinations

THRESHOLD = 0.70


def _zone(room, plot):
    cx = room["x_ft"] + room["width_ft"] / 2
    cy = room["y_ft"] + room["depth_ft"] / 2
    horizontal = "W" if cx < plot["width_ft"] / 3 else "E" if cx > 2 * plot["width_ft"] / 3 else "C"
    vertical = "N" if cy < plot["depth_ft"] / 3 else "S" if cy > 2 * plot["depth_ft"] / 3 else "C"
    return vertical + horizontal


def layout_fingerprint(plan):
    plot = plan["plot"]
    by_id = {room["id"]: room for room in plan["rooms"]}
    ordered = sorted(plan["rooms"], key=lambda room: (room["y_ft"], room["x_ft"]))
    adjacency = sorted(f"{door['room_id']}->{door['connects_to']}" for door in plan["doors"] if door["connects_to"] != "exterior")
    windows = sorted(f"{item['room_id']}:{item['side']}" for item in plan["windows"])
    features = {
        f"sequence:{'>'.join(room['id'] for room in ordered)}",
        f"zones:{'>'.join(_zone(room, plot) for room in ordered)}",
        f"parking:{_zone(by_id['parking'], plot)}",
        f"staircase:{_zone(by_id['staircase'], plot)}",
        f"kitchen:{_zone(by_id['kitchen'], plot)}",
        f"living:{_zone(by_id['living'], plot)}",
        f"dining:{_zone(by_id['dining'], plot)}",
        f"bedrooms:{','.join(sorted(_zone(by_id[key], plot) for key in by_id if key.startswith('bed') or key == 'master'))}",
        f"bathrooms:{','.join(sorted(_zone(room, plot) for room in plan['rooms'] if room.get('kind') == 'bathroom'))}",
        f"entrance:{plan['doors'][0]['side']}:{plan['doors'][0]['offset_ft']}",
        f"adjacency:{'|'.join(adjacency)}",
        f"windows:{'|'.join(windows)}",
        f"strategy:{plan.get('layout_strategy', 'unspecified')}",
    }
    features.update(
        f"rect:{room['id']}:{room['x_ft']},{room['y_ft']},{room['width_ft']},{room['depth_ft']}"
        for room in plan["rooms"]
    )
    return features


def similarity(first, second):
    union = first | second
    return len(first & second) / len(union) if union else 1.0


def analyze(plans, threshold=THRESHOLD):
    fingerprints = {plan["design_id"]: sorted(layout_fingerprint(plan)) for plan in plans}
    pairs = []
    for first, second in combinations(plans, 2):
        score = similarity(set(fingerprints[first["design_id"]]), set(fingerprints[second["design_id"]]))
        pairs.append({"design_a": first["design_id"], "design_b": second["design_id"], "similarity": round(score, 3), "rejected": score >= threshold})
    rejected = [pair for pair in pairs if pair["rejected"]]
    scores = [pair["similarity"] for pair in pairs]
    return {
        "threshold": threshold,
        "fingerprints": fingerprints,
        "pairs": pairs,
        "rejected_pairs": rejected,
        "highest_similarity": max(scores) if scores else 0,
        "average_similarity": round(sum(scores) / len(scores), 3) if scores else 0,
        "any_pair_at_or_above_threshold": bool(rejected),
        "all_structurally_distinct": not rejected,
    }
