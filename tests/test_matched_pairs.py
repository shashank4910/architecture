"""Generate and QA five matched 2D/3D house-plan pairs."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types


GENERATION_MODEL = "gemini-3-pro-image"
QA_MODEL = "gemini-3.6-flash"
MAX_ATTEMPTS = 2
OUTPUT_DIR = Path(__file__).parent / "generated" / "matched_pairs"


def room(name: str, x1: int, y1: int, x2: int, y2: int, door: dict[str, Any], windows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "name": name,
        "position_ft": {"x1_west": x1, "y1_north": y1, "x2_west": x2, "y2_north": y2},
        "dimensions_ft": {"width": x2 - x1, "depth": y2 - y1},
        "door_positions": [door],
        "window_positions": windows,
    }


def d(wall: str, offset: int, connects_to: str) -> dict[str, Any]:
    return {"wall": wall, "offset_ft_from_west_or_north": offset, "connects_to": connects_to}


def win(wall: str, offset: int, width: int = 4) -> dict[str, Any]:
    return {"wall": wall, "offset_ft_from_west_or_north": offset, "width_ft": width}


def spec(number: int, width: int, depth: int, facing: str, bedrooms: list[dict[str, Any]], rooms: list[dict[str, Any]], entrance: dict[str, Any]) -> dict[str, Any]:
    return {
        "design_number": number,
        "plot_width_ft": width,
        "plot_depth_ft": depth,
        "facing": facing,
        "floors": 1,
        "bedrooms": len(bedrooms),
        "bathrooms": 2,
        "living_room": True,
        "dining": True,
        "kitchen": True,
        "parking": 1,
        "staircase": True,
        "puja": True,
        "vastu_oriented": True,
        "dimension_status": "APPROXIMATE / CONCEPTUAL",
        "coordinate_system": "Origin at northwest plot corner; x increases east; y increases south; all values are approximate feet.",
        "entrance": entrance,
        "bedroom_names": [item["name"] for item in bedrooms],
        "rooms": rooms + bedrooms,
    }


DESIGNS = [
    spec(1, 20, 50, "North", [
        room("Master Bedroom", 10, 26, 20, 38, d("west", 5, "Circulation"), [win("east", 4), win("south", 4)]),
        room("Bedroom 2", 0, 32, 10, 42, d("north", 4, "Circulation"), [win("west", 4), win("south", 4)]),
        room("Bedroom 3", 10, 38, 20, 50, d("north", 5, "Master Bedroom"), [win("east", 4), win("south", 4)]),
    ], [
        room("Parking", 0, 0, 10, 16, d("east", 8, "Entrance porch"), [win("west", 4)]),
        room("Living Room", 10, 0, 20, 12, d("south", 5, "Puja"), [win("east", 4), win("north", 4)]),
        room("Puja", 10, 12, 14, 16, d("north", 2, "Living Room"), [win("east", 2, 2)]),
        room("Dining", 0, 16, 10, 24, d("east", 5, "Kitchen"), [win("west", 4)]),
        room("Kitchen", 10, 16, 20, 26, d("west", 5, "Dining"), [win("east", 4), win("south", 4)]),
        room("Staircase", 0, 24, 5, 32, d("east", 4, "Circulation"), [win("west", 3)]),
        room("Bathroom 1", 5, 24, 10, 30, d("south", 2, "Circulation"), [win("east", 2, 2)]),
        room("Circulation", 5, 30, 10, 32, d("north", 2, "Staircase"), [win("south", 2, 2)]),
        room("Bathroom 2", 0, 42, 5, 48, d("north", 2, "Circulation"), [win("west", 2, 2)]),
    ], {"side": "North", "position_ft_from_west": 5, "connects_to": "Living Room"}),
    spec(2, 20, 50, "East", [
        room("Master Bedroom", 0, 26, 10, 38, d("east", 5, "Circulation"), [win("west", 4), win("north", 4)]),
        room("Bedroom 2", 10, 32, 20, 42, d("west", 4, "Circulation"), [win("east", 4), win("south", 4)]),
        room("Bedroom 3", 0, 38, 10, 50, d("east", 5, "Master Bedroom"), [win("west", 4), win("south", 4)]),
    ], [
        room("Parking", 10, 0, 20, 16, d("west", 8, "Entrance porch"), [win("east", 4)]),
        room("Living Room", 0, 0, 10, 12, d("south", 5, "Puja"), [win("west", 4), win("north", 4)]),
        room("Puja", 6, 12, 10, 16, d("north", 2, "Living Room"), [win("east", 2, 2)]),
        room("Dining", 10, 16, 20, 24, d("west", 5, "Kitchen"), [win("east", 4)]),
        room("Kitchen", 0, 16, 10, 26, d("east", 5, "Dining"), [win("west", 4), win("south", 4)]),
        room("Staircase", 15, 24, 20, 32, d("west", 4, "Circulation"), [win("east", 3)]),
        room("Bathroom 1", 10, 24, 15, 30, d("south", 2, "Circulation"), [win("east", 2, 2)]),
        room("Circulation", 10, 30, 15, 32, d("north", 2, "Staircase"), [win("south", 2, 2)]),
        room("Bathroom 2", 15, 42, 20, 48, d("north", 2, "Circulation"), [win("east", 2, 2)]),
    ], {"side": "East", "position_ft_from_north": 8, "connects_to": "Living Room"}),
    spec(3, 20, 50, "North", [
        room("Master Bedroom", 10, 28, 20, 40, d("west", 5, "Circulation"), [win("east", 4), win("south", 4)]),
        room("Bedroom 2", 0, 32, 10, 44, d("north", 4, "Circulation"), [win("west", 4), win("south", 4)]),
    ], [
        room("Parking", 0, 0, 10, 16, d("east", 8, "Entrance porch"), [win("west", 4)]),
        room("Living Room", 10, 0, 20, 14, d("south", 5, "Puja"), [win("east", 4), win("north", 4)]),
        room("Puja", 10, 14, 14, 18, d("north", 2, "Living Room"), [win("east", 2, 2)]),
        room("Dining", 0, 16, 10, 24, d("east", 5, "Kitchen"), [win("west", 4)]),
        room("Kitchen", 10, 18, 20, 28, d("west", 5, "Dining"), [win("east", 4), win("south", 4)]),
        room("Staircase", 0, 24, 5, 32, d("east", 4, "Circulation"), [win("west", 3)]),
        room("Bathroom 1", 5, 24, 10, 30, d("south", 2, "Circulation"), [win("east", 2, 2)]),
        room("Circulation", 5, 30, 10, 32, d("north", 2, "Staircase"), [win("south", 2, 2)]),
        room("Bathroom 2", 0, 44, 5, 49, d("north", 2, "Circulation"), [win("west", 2, 2)]),
    ], {"side": "North", "position_ft_from_west": 5, "connects_to": "Living Room"}),
    spec(4, 30, 40, "East", [
        room("Master Bedroom", 12, 20, 24, 32, d("north", 6, "Circulation"), [win("east", 4), win("south", 4)]),
        room("Bedroom 2", 0, 25, 12, 37, d("east", 6, "Circulation"), [win("west", 4), win("south", 4)]),
        room("Bedroom 3", 24, 15, 30, 27, d("west", 6, "Circulation"), [win("east", 4), win("south", 4)]),
    ], [
        room("Parking", 0, 0, 10, 16, d("east", 8, "Entrance porch"), [win("west", 4)]),
        room("Living Room", 10, 0, 22, 12, d("south", 6, "Dining"), [win("north", 4), win("east", 4)]),
        room("Puja", 22, 0, 27, 5, d("south", 2, "Living Room"), [win("east", 2, 2)]),
        room("Kitchen", 22, 5, 30, 15, d("west", 5, "Dining"), [win("east", 4), win("south", 4)]),
        room("Dining", 10, 12, 22, 20, d("east", 6, "Kitchen"), [win("west", 4)]),
        room("Staircase", 0, 16, 6, 25, d("east", 4, "Circulation"), [win("west", 3)]),
        room("Bathroom 1", 24, 27, 30, 34, d("north", 2, "Circulation"), [win("east", 2, 2)]),
        room("Circulation", 6, 22, 12, 25, d("north", 3, "Staircase"), [win("south", 2, 2)]),
        room("Bathroom 2", 24, 34, 30, 40, d("north", 2, "Circulation"), [win("east", 2, 2)]),
    ], {"side": "East", "position_ft_from_north": 8, "connects_to": "Living Room"}),
    spec(5, 30, 40, "North", [
        room("Master Bedroom", 12, 20, 24, 32, d("north", 6, "Circulation"), [win("east", 4), win("south", 4)]),
        room("Bedroom 2", 0, 25, 12, 37, d("east", 6, "Circulation"), [win("west", 4), win("south", 4)]),
        room("Bedroom 3", 12, 32, 24, 40, d("north", 6, "Master Bedroom"), [win("east", 4), win("south", 4)]),
    ], [
        room("Parking", 0, 0, 10, 16, d("east", 8, "Entrance porch"), [win("west", 4)]),
        room("Living Room", 10, 0, 22, 12, d("south", 6, "Dining"), [win("north", 4), win("east", 4)]),
        room("Puja", 22, 0, 27, 5, d("south", 2, "Living Room"), [win("east", 2, 2)]),
        room("Kitchen", 22, 5, 30, 15, d("west", 5, "Dining"), [win("east", 4), win("south", 4)]),
        room("Dining", 10, 12, 22, 20, d("east", 6, "Kitchen"), [win("west", 4)]),
        room("Staircase", 0, 16, 6, 25, d("east", 4, "Circulation"), [win("west", 3)]),
        room("Bathroom 1", 24, 27, 30, 34, d("north", 2, "Circulation"), [win("east", 2, 2)]),
        room("Circulation", 6, 22, 12, 25, d("north", 3, "Staircase"), [win("south", 2, 2)]),
        room("Bathroom 2", 24, 34, 30, 40, d("north", 2, "Circulation"), [win("east", 2, 2)]),
    ], {"side": "North", "position_ft_from_west": 5, "connects_to": "Living Room"}),
]

QA_FIELDS = [
    "plot_proportion", "room_count", "room_dimensions", "room_positions", "doors", "windows",
    "staircase", "kitchen", "bathrooms", "parking", "circulation", "vastu_orientation",
    "two_d_quality", "three_d_quality", "pair_match", "ai_artifacts",
]


def stem(number: int) -> str:
    return f"design_{number:02d}"


def validate_specification(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    width, depth = plan["plot_width_ft"], plan["plot_depth_ft"]
    rooms = plan["rooms"]
    names = {item["name"] for item in rooms}
    required = {"Parking", "Living Room", "Dining", "Kitchen", "Staircase", "Puja", "Bathroom 1", "Bathroom 2", *plan["bedroom_names"]}
    missing = required - names
    if missing:
        errors.append(f"missing rooms: {sorted(missing)}")
    rectangles: list[tuple[str, int, int, int, int]] = []
    for item in rooms:
        position = item["position_ft"]
        x1, y1 = position["x1_west"], position["y1_north"]
        x2, y2 = position["x2_west"], position["y2_north"]
        dimensions = item["dimensions_ft"]
        if x2 <= x1 or y2 <= y1:
            errors.append(f"{item['name']} has non-positive dimensions")
        if x1 < 0 or y1 < 0 or x2 > width or y2 > depth:
            errors.append(f"{item['name']} exceeds plot boundary")
        if dimensions != {"width": x2 - x1, "depth": y2 - y1}:
            errors.append(f"{item['name']} dimensions do not match position")
        rectangles.append((item["name"], x1, y1, x2, y2))
        for opening_type in ("door_positions", "window_positions"):
            for opening in item[opening_type]:
                if opening_type == "door_positions" and opening.get("connects_to") not in names and not opening.get("connects_to", "").startswith("Entrance"):
                    errors.append(f"{item['name']} door references unknown space {opening.get('connects_to')}")
    for index, first in enumerate(rectangles):
        for second in rectangles[index + 1:]:
            overlap_width = min(first[3], second[3]) - max(first[1], second[1])
            overlap_depth = min(first[4], second[4]) - max(first[2], second[2])
            if overlap_width > 0 and overlap_depth > 0:
                errors.append(f"{first[0]} overlaps {second[0]}")
    if len(plan["bedroom_names"]) != plan["bedrooms"]:
        errors.append("bedroom count mismatch")
    return errors


def build_view_prompt(plan: dict[str, Any], view: str, correction: str = "") -> str:
    spec_text = json.dumps(plan, indent=2)
    correction_text = f"\nPrior QA correction: {correction}\n" if correction else ""
    if view == "2D":
        style = "strict top-down orthographic 2D architectural floor plan"
        extra = "Show the plot boundary, north arrow, facing/entrance, exact room labels, walls, doors, windows, approximate dimensions from the specification, and no invented dimensions."
    else:
        style = "clean architectural 3D cutaway dollhouse view with the roof removed and walls visibly cut away"
        extra = "Show the same walls and room arrangement from the specification. Use subtle labels or a small legend so rooms can be identified, but do not add, remove, move, or resize spaces."
    return f"""Generate exactly one {style} for an Indian single-floor house.

AUTHORITATIVE STRUCTURED SPECIFICATION
{spec_text}

MATCHING REQUIREMENT
This image is view {view} of the exact same house. The structured specification is authoritative. Do not invent a different layout, room positions, dimensions, entrance, staircase, kitchen, bathrooms, or windows. Room dimensions are APPROXIMATE / CONCEPTUAL, not construction accuracy.

PRESENTATION
- {extra}
- Preserve the plot proportion and north orientation.
- Make circulation, doors, windows, parking, staircase, kitchen, bathrooms, and Vastu-oriented arrangement plausible.
- No decorative artwork, perspective distortion in the 2D view, gibberish, fake measurements, or architectural artifacts.
- This is a Vastu-oriented conceptual house plan, not architect-approved, construction-ready, structurally verified, or government-approved.
{correction_text}"""


def extract_image_bytes(response: Any) -> bytes:
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            inline_data = getattr(part, "inline_data", None)
            data = getattr(inline_data, "data", None) if inline_data else None
            if data:
                return data
    raise RuntimeError("Gemini returned no image data.")


def normalize_qa(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("QA response was not a JSON object")
    allowed = {"PASS", "FAIL", "UNCERTAIN"}
    result = {field: value.get(field, "UNCERTAIN") for field in QA_FIELDS}
    result["overall_result"] = value.get("overall_result", "UNCERTAIN")
    result["confidence"] = value.get("confidence", 0.0)
    result["problems"] = value.get("problems", [])
    for field in ["overall_result", *QA_FIELDS]:
        if result[field] not in allowed:
            result[field] = "UNCERTAIN"
    if not isinstance(result["problems"], list):
        result["problems"] = [str(result["problems"])]
    return result


def qa_pair(client: genai.Client, plan: dict[str, Any], image_2d: bytes, image_3d: bytes) -> dict[str, Any]:
    prompt = f"""Act as a strict architectural reviewer. Compare both attached images against this authoritative specification:
{json.dumps(plan, indent=2)}

The first image is 2D and the second is 3D. Judge actual pixels. PASS only when clearly satisfied; FAIL for visible contradiction; UNCERTAIN when important evidence is ambiguous. The pair_match field must be FAIL if the 3D view materially changes any room, position, dimensions, entrance, staircase, kitchen, bathroom, or wall layout. Do not pass an attractive but impossible design. Return JSON only with overall_result, confidence from 0 to 1, these fields: {', '.join(QA_FIELDS)}, and problems as a concise string array."""
    response = client.models.generate_content(
        model=QA_MODEL,
        contents=[
            types.Part.from_text(text=prompt),
            types.Part.from_bytes(data=image_2d, mime_type="image/png"),
            types.Part.from_bytes(data=image_3d, mime_type="image/png"),
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "OBJECT",
                "properties": {
                    "overall_result": {"type": "STRING"},
                    "confidence": {"type": "NUMBER"},
                    **{field: {"type": "STRING"} for field in QA_FIELDS},
                    "problems": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
                "required": ["overall_result", "confidence", *QA_FIELDS, "problems"],
            },
        ),
    )
    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("QA model returned no text")
    return normalize_qa(json.loads(text))


def accepted(qa: dict[str, Any]) -> bool:
    return qa["overall_result"] == "PASS" and all(qa[field] == "PASS" for field in QA_FIELDS)


def run_design(client: genai.Client, plan: dict[str, Any]) -> dict[str, Any]:
    base = stem(plan["design_number"])
    spec_path = OUTPUT_DIR / f"{base}_spec.json"
    path_2d = OUTPUT_DIR / f"{base}_2d.png"
    path_3d = OUTPUT_DIR / f"{base}_3d.png"
    correction = ""
    attempts: list[dict[str, Any]] = []
    spec_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            prompt_2d = build_view_prompt(plan, "2D", correction)
            prompt_3d = build_view_prompt(plan, "3D", correction)
            if attempt == 1 and path_2d.exists() and path_3d.exists():
                image_2d = path_2d.read_bytes()
                image_3d = path_3d.read_bytes()
            else:
                response_2d = client.models.generate_content(
                    model=GENERATION_MODEL,
                    contents=prompt_2d,
                    config=types.GenerateContentConfig(response_modalities=["IMAGE"], image_config=types.ImageConfig(image_size="2K")),
                )
                image_2d = extract_image_bytes(response_2d)
                path_2d.write_bytes(image_2d)
                response_3d = client.models.generate_content(
                    model=GENERATION_MODEL,
                    contents=prompt_3d,
                    config=types.GenerateContentConfig(response_modalities=["IMAGE"], image_config=types.ImageConfig(image_size="2K")),
                )
                image_3d = extract_image_bytes(response_3d)
                path_3d.write_bytes(image_3d)
            qa = qa_pair(client, plan, image_2d, image_3d)
            attempts.append({"attempt": attempt, "qa": qa})
            if accepted(qa):
                return {"design_number": plan["design_number"], "status": "PASS", "attempts": attempts, "qa": qa}
            correction = "; ".join(str(problem) for problem in qa["problems"]) or "Correct every FAIL or UNCERTAIN field and preserve the exact specification."
        except Exception as error:
            attempts.append({"attempt": attempt, "error": f"{type(error).__name__}: {error}"})
            break
    return {"design_number": plan["design_number"], "status": "FAIL", "attempts": attempts, "qa": attempts[-1].get("qa") if attempts else None}


def main() -> int:
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Missing GEMINI_API_KEY. Add it to .env and retry.", file=sys.stderr)
        return 2
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    validation_errors = {str(plan["design_number"]): validate_specification(plan) for plan in DESIGNS}
    invalid = {number: errors for number, errors in validation_errors.items() if errors}
    if invalid:
        print(json.dumps({"specification_validation_errors": invalid}, indent=2), file=sys.stderr)
        return 1
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=180000))
    results: list[dict[str, Any]] = []
    for plan in DESIGNS:
        print(f"Design {plan['design_number']}: generating 2D + 3D and reviewing", flush=True)
        result = run_design(client, plan)
        results.append(result)
        print(f"Design {plan['design_number']}: {result['status']}", flush=True)
    passed = sum(item["status"] == "PASS" for item in results)
    two_d_passed = sum(item.get("qa", {}).get("two_d_quality") == "PASS" for item in results if item.get("qa"))
    three_d_passed = sum(item.get("qa", {}).get("three_d_quality") == "PASS" for item in results if item.get("qa"))
    pairs_matched = sum(item.get("qa", {}).get("pair_match") == "PASS" for item in results if item.get("qa"))
    errors = [attempt["error"] for item in results for attempt in item["attempts"] if "error" in attempt]
    qa_completed = any(item.get("qa") is not None for item in results)
    recommendation = (
        "INCONCLUSIVE - automated visual QA did not complete; do not scale the experiment until QA is available."
        if not qa_completed
        else "CONTINUE WITH NANO BANANA PRO" if pairs_matched >= 4
        else "TEST ANOTHER IMAGE MODEL" if pairs_matched >= 2
        else "PREFER A PROGRAMMATIC/VECTOR APPROACH"
    )
    summary = {
        "total_designs": 5, "passed": passed, "failed": 5 - passed,
        "two_d_plans_passed": two_d_passed, "three_d_plans_passed": three_d_passed,
        "matched_pairs_passed": pairs_matched, "specifications_validated": True,
        "qa_completed": qa_completed, "biggest_recurring_problems": errors,
        "recommendation": recommendation,
        "results": results,
    }
    (OUTPUT_DIR / "test_results.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("\nMatched 2D + 3D House-Plan Test")
    for item in results:
        print(f"Design {item['design_number']}: {item['status']}")
    print(f"2D plans passed: {two_d_passed}/5")
    print(f"3D plans passed: {three_d_passed}/5")
    print(f"Matched pairs: {pairs_matched}/5")
    print(f"Recommendation: {recommendation}")
    return 0 if passed == 5 else 1


if __name__ == "__main__":
    raise SystemExit(main())
