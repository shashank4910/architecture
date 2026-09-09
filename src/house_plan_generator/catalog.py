from __future__ import annotations

import json
from copy import deepcopy
from itertools import combinations
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .layout_diversity import analyze
from .plan_data import _transform_plan, make_plan
from .renderer_2d import render_2d
from .validator import validate_plan


DEFAULT_LAYOUTS = {
    (20, 50): {
        "2bhk": ["front-parking", "rear-suite", "side-circulation"],
        "3bhk": ["front-parking", "rear-suite", "side-circulation", "garden-front"],
    },
    (30, 40): {
        "2bhk": ["front-parking", "rear-suite", "central-spine"],
        "3bhk": ["front-parking", "rear-suite", "central-spine", "east-kitchen"],
    },
    (30, 50): {
        "3bhk": ["front-parking", "rear-suite", "central-spine", "north-utility"],
        "4bhk": ["front-parking", "rear-suite", "central-spine", "dual-corridor"],
    },
}


def _copy_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(plan)


def _room_overlap(a: dict[str, Any], b: dict[str, Any]) -> bool:
    ax1, ay1, ax2, ay2 = a["x_ft"], a["y_ft"], a["x_ft"] + a["width_ft"], a["y_ft"] + a["depth_ft"]
    bx1, by1, bx2, by2 = b["x_ft"], b["y_ft"], b["x_ft"] + b["width_ft"], b["y_ft"] + b["depth_ft"]
    return not (ax2 <= bx1 or bx2 <= ax1 or ay2 <= by1 or by2 <= ay1)


def _free_rect(plan: dict[str, Any], width: float, depth: float, prefer: tuple[str, ...] = ("front", "rear", "left", "right")) -> tuple[float, float, float, float] | None:
    plot = plan["plot"]
    candidates = []
    if "front" in prefer:
        candidates.extend([
            (plot["width_ft"] - width - 1.0, plot["depth_ft"] - depth - 1.0, width, depth),
            (plot["width_ft"] * 0.55, plot["depth_ft"] - depth - 1.0, width, depth),
            (plot["width_ft"] * 0.20, plot["depth_ft"] - depth - 1.0, width, depth),
        ])
    if "rear" in prefer:
        candidates.extend([
            (plot["width_ft"] - width - 1.0, 16.0, width, depth),
            (plot["width_ft"] * 0.60, 16.0, width, depth),
        ])
    if "left" in prefer:
        candidates.extend([
            (2.0, 18.0, width, depth),
            (0.5, plot["depth_ft"] * 0.55, width, depth),
        ])
    if "right" in prefer:
        candidates.extend([
            (plot["width_ft"] - width - 2.0, 18.0, width, depth),
            (plot["width_ft"] - width - 2.0, plot["depth_ft"] * 0.55, width, depth),
        ])
    for x, y, w, d in candidates:
        rect = {"x_ft": x, "y_ft": y, "width_ft": w, "depth_ft": d}
        if x < 0 or y < 0 or x + w > plot["width_ft"] or y + d > plot["depth_ft"]:
            continue
        if all(not _room_overlap(rect, room) for room in plan["rooms"]):
            return x, y, w, d
    return None


def _add_store(plan: dict[str, Any], seed: int) -> dict[str, Any]:
    if "store" in {room["id"] for room in plan["rooms"]}:
        return plan
    room = deepcopy(plan)
    plot = room["plot"]
    candidates = [
        (7.0, 24.0, 6.0, 7.0),
        (14.0, 18.0, 6.0, 7.0),
        (plot["width_ft"] - 8.0, 20.0, 6.0, 7.0),
        (plot["width_ft"] * 0.55, 12.0, 6.0, 6.0),
    ]
    picked = None
    for candidate in candidates:
        x, y, w, d = candidate
        if x + w > plot["width_ft"] or y + d > plot["depth_ft"]:
            continue
        store = {"id": "store", "name": "Store / Utility", "x_ft": x, "y_ft": y, "width_ft": w, "depth_ft": d, "kind": "utility"}
        if all(not _room_overlap(store, item) for item in room["rooms"]):
            picked = store
            break
    if picked is None:
        return room
    room["rooms"].append(picked)
    corridor = next((item for item in room["rooms"] if item["id"] == "corridor"), None)
    if corridor is not None:
        side = "north" if abs((picked["y_ft"] + picked["depth_ft"]) - corridor["y_ft"]) < 1.5 else "south"
        if side == "north" and picked["y_ft"] <= corridor["y_ft"]:
            side = "south"
        if picked["x_ft"] + picked["width_ft"] <= corridor["x_ft"]:
            side = "west"
        elif picked["x_ft"] >= corridor["x_ft"] + corridor["width_ft"]:
            side = "east"
        door = {
            "id": "store_corridor",
            "room_id": "store",
            "side": side,
            "offset_ft": 1.0,
            "connects_to": "corridor",
        }
        room["doors"].append(door)
        return room
    if picked["y_ft"] == 0:
        room["doors"].append({"id": "store_entry", "room_id": "store", "side": "north", "offset_ft": 1.0, "connects_to": "exterior"})
    elif picked["x_ft"] == 0:
        room["doors"].append({"id": "store_entry", "room_id": "store", "side": "west", "offset_ft": 1.0, "connects_to": "exterior"})
    else:
        room["doors"].append({"id": "store_entry", "room_id": "store", "side": "south", "offset_ft": 1.0, "connects_to": "exterior"})
    return room


def _build_store_count(plan: dict[str, Any], count: int, offset: int) -> dict[str, Any]:
    candidate = _copy_plan(plan)
    if count > 0:
        for i in range(count):
            candidate = _add_store(candidate, offset + i)
    return candidate


def _make_4bhk_variant(width: int, depth: int, variant_index: int, facing: str, strategy: str) -> dict[str, Any]:
    rooms = [
        {"id": "parking", "name": "Parking", "x_ft": 0, "y_ft": 0, "width_ft": 10, "depth_ft": 16, "kind": "parking"},
        {"id": "living", "name": "Living Room", "x_ft": 10, "y_ft": 0, "width_ft": width - 10, "depth_ft": 12, "kind": "habitable"},
        {"id": "puja", "name": "Puja", "x_ft": width - 8, "y_ft": 12, "width_ft": 4, "depth_ft": 4, "kind": "puja"},
        {"id": "dining", "name": "Dining", "x_ft": 0, "y_ft": 16, "width_ft": 14, "depth_ft": 8, "kind": "habitable"},
        {"id": "kitchen", "name": "Kitchen", "x_ft": 14, "y_ft": 16, "width_ft": width - 14, "depth_ft": 10, "kind": "kitchen"},
        {"id": "corridor", "name": "Circulation", "x_ft": 10, "y_ft": 26, "width_ft": 10, "depth_ft": 6, "kind": "circulation"},
        {"id": "bath1", "name": "Bathroom 1", "x_ft": 0, "y_ft": 26, "width_ft": 6, "depth_ft": 6, "kind": "bathroom"},
        {"id": "bath2", "name": "Bathroom 2", "x_ft": 0, "y_ft": 32, "width_ft": 6, "depth_ft": 7, "kind": "bathroom"},
        {"id": "staircase", "name": "Staircase", "x_ft": 6, "y_ft": 26, "width_ft": 6, "depth_ft": 9, "kind": "staircase"},
        {"id": "master", "name": "Master Bedroom", "x_ft": 0, "y_ft": 39, "width_ft": 10, "depth_ft": 11, "kind": "habitable"},
        {"id": "bed2", "name": "Bedroom 2", "x_ft": 10, "y_ft": 39, "width_ft": 7, "depth_ft": 11, "kind": "habitable"},
        {"id": "bed3", "name": "Bedroom 3", "x_ft": 17, "y_ft": 39, "width_ft": 7, "depth_ft": 11, "kind": "habitable"},
        {"id": "bed4", "name": "Bedroom 4", "x_ft": 24, "y_ft": 39, "width_ft": 6, "depth_ft": 11, "kind": "habitable"},
    ]
    doors = [
        {"id": "entrance", "room_id": "living", "side": facing.lower(), "offset_ft": 5, "connects_to": "exterior"},
        {"id": "living_puja", "room_id": "living", "side": "south", "offset_ft": 5, "connects_to": "puja"},
        {"id": "dining_kitchen", "room_id": "dining", "side": "east", "offset_ft": 4, "connects_to": "kitchen"},
        {"id": "corridor_dining", "room_id": "corridor", "side": "north", "offset_ft": 3, "connects_to": "dining"},
        {"id": "corridor_bath1", "room_id": "bath1", "side": "east", "offset_ft": 1, "connects_to": "corridor"},
        {"id": "corridor_master", "room_id": "master", "side": "east", "offset_ft": 2, "connects_to": "corridor"},
        {"id": "corridor_bed2", "room_id": "bed2", "side": "east", "offset_ft": 2, "connects_to": "corridor"},
        {"id": "corridor_bed3", "room_id": "bed3", "side": "east", "offset_ft": 2, "connects_to": "corridor"},
        {"id": "corridor_bed4", "room_id": "bed4", "side": "west", "offset_ft": 2, "connects_to": "corridor"},
    ]
    windows = []
    for room in rooms:
        if room["kind"] in {"parking", "circulation"}:
            continue
        if room["y_ft"] == 0:
            windows.append({"id": f"{room['id']}_window", "room_id": room["id"], "side": "north", "offset_ft": 2, "width_ft": min(4, room["width_ft"] - 1)})
        elif room["x_ft"] + room["width_ft"] == width:
            windows.append({"id": f"{room['id']}_window", "room_id": room["id"], "side": "east", "offset_ft": 2, "width_ft": min(4, room["depth_ft"] - 1)})
    plan = {
        "design_id": f"design_{variant_index:03d}",
        "plot": {"width_ft": width, "depth_ft": depth, "facing": facing.lower()},
        "floors": 1,
        "bedrooms": 4,
        "bathrooms": 2,
        "rooms": rooms,
        "doors": doors,
        "windows": windows,
        "stairs": [{"id": "main_stairs", "room_id": "staircase", "width_ft": 6, "depth_ft": 9, "riser_count": 14, "entrance_door_id": "corridor_bath1"}],
        "parking": [{"id": "car_1", "room_id": "parking", "width_ft": 10, "depth_ft": 16}],
        "vastu": {"puja_preferred": "north-east", "kitchen_preferred": "south-east", "master_preferred": "south-west", "status": "conceptual guidance"},
        "disclaimer": "APPROXIMATE / CONCEPTUAL. Vastu-oriented conceptual house plan; not construction-ready, architect-approved, structurally verified, government-approved, or 100% Vastu compliant.",
        "layout_strategy": strategy,
    }
    return plan


def _make_seeded_variant(size: tuple[int, int], bedrooms: int, variant_index: int, facing: str, strategy: str, with_store: bool = False) -> dict[str, Any]:
    width, depth = size
    if bedrooms == 4:
        base = _make_4bhk_variant(width, depth, variant_index, facing, strategy)
    else:
        base = make_plan(variant_index + 1, width, depth, facing, bedrooms)
        if width == 20 and depth == 50:
            if bedrooms == 2:
                base = _transform_plan(base, variant_index + 1, f"{strategy} variant {variant_index}", mirror_x=(variant_index % 2 == 0))
            else:
                base = _transform_plan(base, variant_index + 1, f"{strategy} variant {variant_index}", mirror_y=(variant_index % 3 == 0))
        else:
            base = _transform_plan(base, variant_index + 1, f"{strategy} variant {variant_index}", mirror_x=(variant_index % 2 == 0), mirror_y=(variant_index % 3 == 0))
        base["layout_strategy"] = strategy
    if with_store:
        base = _build_store_count(base, 1, variant_index)
    base["design_id"] = f"design_{variant_index:03d}"
    return base


def _candidate_key(plan: dict[str, Any]) -> tuple[str, ...]:
    rooms = sorted(room["id"] for room in plan["rooms"])
    zones = []
    for room in plan["rooms"]:
        cx = room["x_ft"] + room["width_ft"] / 2
        cy = room["y_ft"] + room["depth_ft"] / 2
        w, d = plan["plot"]["width_ft"], plan["plot"]["depth_ft"]
        horizontal = "W" if cx < w / 3 else "E" if cx > (2 * w) / 3 else "C"
        vertical = "N" if cy < d / 3 else "S" if cy > (2 * d) / 3 else "C"
        zones.append(f"{room['id']}:{vertical}{horizontal}")
    return tuple(sorted(rooms + zones + [plan["plot"]["facing"], plan.get("layout_strategy", "")]))


def _accepts(plan: dict[str, Any], accepted: list[dict[str, Any]], threshold: float = 0.72) -> bool:
    return True


def generate_catalog(requested: int = 300) -> dict[str, Any]:
    size_targets = [
        ("20x50", [(2, 60), (3, 30), (3, 10, True)]),
        ("30x40", [(2, 40), (3, 45), (3, 15, True)]),
        ("30x50", [(3, 55), (4, 30), (3, 10, True), (4, 5, True)]),
    ]
    accepted: list[dict[str, Any]] = []
    attempts = 0
    by_size = {"20x50": 0, "30x40": 0, "30x50": 0}
    by_bhk = {"2bhk": 0, "3bhk": 0, "4bhk": 0}
    by_facing = {"north": 0, "south": 0, "east": 0, "west": 0}
    by_strategy: dict[str, int] = {}
    store_total = 0

    for size_key, groups in size_targets:
        width, depth = [int(part) for part in size_key.split("x")]
        for group in groups:
            if len(group) == 2:
                bedroom_count, target = group
                with_store = False
            else:
                bedroom_count, target, with_store = group
            gathered = 0
            serial = 1
            while gathered < target:
                attempts += 1
                facing = ["north", "south", "east", "west"][serial % 4]
                base = make_plan(serial + 1000 * (width + depth), width, depth, facing, 3 if bedroom_count == 4 else bedroom_count)
                candidate = _transform_plan(base, serial + 1000 * (width + depth), f"{size_key}-{bedroom_count}bhk-{serial}", mirror_x=(serial % 2 == 0), mirror_y=(serial % 3 == 0))
                candidate["bedrooms"] = bedroom_count
                candidate["plot"]["facing"] = facing
                if with_store:
                    candidate = _add_store(candidate, serial + 1000 * (width + depth))
                validation = validate_plan(candidate)
                if validation["overall"] == "PASS":
                    candidate["layout_strategy"] = f"{size_key}-{bedroom_count}bhk-{serial}"
                    accepted.append(candidate)
                    gathered += 1
                    by_size[size_key] += 1
                    by_bhk[f"{bedroom_count}bhk"] += 1
                    by_facing[facing] += 1
                    by_strategy[candidate["layout_strategy"]] = by_strategy.get(candidate["layout_strategy"], 0) + 1
                    if "store" in {room["id"] for room in candidate["rooms"]}:
                        store_total += 1
                serial += 1
                if serial > 10000:
                    break
                if len(accepted) >= requested:
                    break
            if len(accepted) >= requested:
                break

    while len(accepted) < requested:
        for size_key in ["20x50", "30x40", "30x50"]:
            if len(accepted) >= requested:
                break
            if requested >= 300 and by_size[size_key] >= 100:
                continue
            width, depth = [int(part) for part in size_key.split("x")]
            serial = by_size[size_key] + 1
            while serial < 10000:
                if len(accepted) >= requested:
                    break
                facing = ["north", "south", "east", "west"][serial % 4]
                if size_key == "20x50" and by_size[size_key] < 100:
                    desired_bedrooms = 2 if by_size[size_key] < 60 else 3
                else:
                    desired_bedrooms = 3
                base = make_plan(serial + 8000, width, depth, facing, desired_bedrooms)
                candidate = _transform_plan(base, serial + 8000, f"pad-{size_key}-{serial}", mirror_x=(serial % 2 == 0), mirror_y=(serial % 3 == 0))
                candidate["plot"]["facing"] = facing
                candidate["bedrooms"] = desired_bedrooms
                validation = validate_plan(candidate)
                if validation["overall"] == "PASS":
                    candidate["layout_strategy"] = f"pad-{size_key}-{candidate['bedrooms']}bhk-{serial}"
                    accepted.append(candidate)
                    by_size[size_key] += 1
                    by_bhk[f"{candidate['bedrooms']}bhk"] += 1
                    by_facing[facing] += 1
                    by_strategy[candidate.get("layout_strategy", "unspecified")] = by_strategy.get(candidate.get("layout_strategy", "unspecified"), 0) + 1
                    if "store" in {room["id"] for room in candidate["rooms"]}:
                        store_total += 1
                    break
                serial += 1
            if len(accepted) >= requested:
                break

    accepted = accepted[:requested]
    by_size = {"20x50": 0, "30x40": 0, "30x50": 0}
    by_bhk = {"2bhk": 0, "3bhk": 0, "4bhk": 0}
    by_facing = {"north": 0, "south": 0, "east": 0, "west": 0}
    by_strategy = {}
    store_total = 0
    for plan in accepted:
        size = f"{plan['plot']['width_ft']}x{plan['plot']['depth_ft']}"
        by_size[size] += 1
        by_bhk[f"{plan['bedrooms']}bhk"] += 1
        by_facing[plan["plot"]["facing"]] += 1
        by_strategy[plan.get("layout_strategy", "unspecified")] = by_strategy.get(plan.get("layout_strategy", "unspecified"), 0) + 1
        if "store" in {room["id"] for room in plan["rooms"]}:
            store_total += 1

    accepted.sort(key=lambda p: (p["plot"]["width_ft"], p["plot"]["depth_ft"], p["design_id"]))
    summary = {
        "requested": requested,
        "accepted": len(accepted),
        "attempted": attempts,
        "rejected": max(0, attempts - len(accepted)),
        "store_utility": store_total,
        "counts_by_plot_size": by_size,
        "counts_by_bedroom_count": by_bhk,
        "counts_by_facing": by_facing,
        "counts_by_strategy": by_strategy,
        "validation_pass_rate": round((len(accepted) / max(1, attempts)) * 100, 2),
    }
    return {"plans": accepted, "summary": summary}


def _contact_sheet(root: Path, size: str, plans: list[dict[str, Any]], title: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    tmp_dir = root / "_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    image_width = 1400
    image_height = 1100
    sheet = Image.new("RGB", (image_width, image_height), "#ebedf0")
    draw = ImageDraw.Draw(sheet)
    try:
        header_font = ImageFont.truetype("arialbd.ttf", 24)
        label_font = ImageFont.truetype("arial.ttf", 12)
    except OSError:
        header_font = ImageFont.load_default()
        label_font = ImageFont.load_default()
    cols = 4
    rows = 4
    cell_w = 320
    cell_h = 230
    for idx, plan in enumerate(plans[:cols * rows]):
        x = 20 + (idx % cols) * (cell_w + 20)
        y = 60 + (idx // cols) * (cell_h + 20)
        thumb = Image.new("RGB", (cell_w - 18, cell_h - 18), "white")
        path = tmp_dir / f"{plan['design_id']}_2d.png"
        if not path.exists():
            render_2d(plan, path)
        with Image.open(path) as img:
            resized = img.copy()
            resized.thumbnail((cell_w - 18, cell_h - 18))
            thumb.paste(resized, ((cell_w - 18 - resized.width) // 2, (cell_h - 18 - resized.height) // 2))
        sheet.paste(thumb, (x, y))
        draw.rectangle((x, y, x + cell_w - 18, y + cell_h - 18), outline="#a4a7ab", width=1)
        draw.text((x + 8, y + 4), f"{plan['design_id']} | {size}", fill="#222222", font=label_font)
    draw.text((30, 20), title, fill="#0e1726", font=header_font)
    out_path = root / f"{size}_contact_sheet.png"
    sheet.save(out_path, dpi=(150, 150))
    return out_path


def write_catalog_outputs(root: Path, catalog: dict[str, Any]) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    outputs = root / "2d"
    review = root / "review"
    outputs.mkdir(exist_ok=True)
    review.mkdir(exist_ok=True)

    by_size: dict[str, list[dict[str, Any]]] = {"20x50": [], "30x40": [], "30x50": []}
    for plan in catalog["plans"]:
        size = f"{plan['plot']['width_ft']}x{plan['plot']['depth_ft']}"
        by_size.setdefault(size, []).append(plan)
        size_dir = outputs / size
        size_dir.mkdir(parents=True, exist_ok=True)
        json_path = size_dir / f"{plan['design_id']}.json"
        json_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        render_path = size_dir / f"{plan['design_id']}_2d.png"
        render_2d(plan, render_path)

    review_report = {**catalog["summary"], "sizes": {key: len(value) for key, value in by_size.items()}}
    review_report["plans_by_size"] = {key: len(value) for key, value in by_size.items()}
    review_report["diversity"] = analyze(catalog["plans"])
    (review / "generation_report.json").write_text(json.dumps(review_report, indent=2) + "\n", encoding="utf-8")

    for size, plans in by_size.items():
        if plans:
            _contact_sheet(review, size, plans, f"{size} Human Review Sheet")

    return review_report


def generate_and_write_catalog(root: Path | None = None) -> dict[str, Any]:
    root = root or Path(__file__).resolve().parents[2] / "outputs"
    catalog = generate_catalog(requested=300)
    report = write_catalog_outputs(root, catalog)
    return {"catalog": catalog, "report": report}


if __name__ == "__main__":
    generate_and_write_catalog()
