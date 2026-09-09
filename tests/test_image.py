"""Generate one Nano Banana Pro conceptual house-plan test image."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types


MODEL = "gemini-3-pro-image"
OUTPUT_DIR = Path(__file__).parent / "generated"
IMAGE_PATH = OUTPUT_DIR / "test_20x50_north_3bhk.png"
SPEC_PATH = OUTPUT_DIR / "test_20x50_north_3bhk.json"
PROMPT_PATH = OUTPUT_DIR / "test_20x50_north_3bhk_prompt.txt"

SPECIFICATION: dict[str, Any] = {
    "plot_width_ft": 20,
    "plot_depth_ft": 50,
    "facing": "North",
    "floors": 1,
    "bedrooms": 3,
    "bathrooms": 2,
    "parking": 1,
    "kitchen": True,
    "living_room": True,
    "dining": True,
    "staircase": True,
    "puja": True,
    "vastu_oriented": True,
}


def build_prompt(specification: dict[str, Any]) -> str:
    """Build a reproducible prompt from the structured plan specification."""
    plot = (
        f"{specification['plot_width_ft']} ft wide x "
        f"{specification['plot_depth_ft']} ft deep"
    )
    inclusions = [
        f"single-floor {specification['bedrooms']} BHK house",
        f"{specification['bathrooms']} bathrooms",
        "living room" if specification["living_room"] else None,
        "dining area" if specification["dining"] else None,
        "kitchen" if specification["kitchen"] else None,
        f"{specification['parking']}-car parking" if specification["parking"] else None,
        "staircase" if specification["staircase"] else None,
        "puja space" if specification["puja"] else None,
    ]
    inclusion_text = ", ".join(item for item in inclusions if item)
    vastu_text = (
        "Use Vastu principles as a design guideline: keep the main entry on the "
        "north side, place puja toward the northeast, kitchen toward the southeast, "
        "and arrange bedrooms and bathrooms sensibly without sacrificing usability."
        if specification["vastu_oriented"]
        else "Do not apply Vastu-specific placement."
    )

    return f"""Create exactly one professional architectural floor-plan reference.

PROJECT SPECIFICATION
- Plot: {plot}, {specification['facing']}-facing
- Requirements: {inclusion_text}

COMPOSITION AND QUALITY
- Strictly top-down orthographic 2D plan, with the full plot boundary visible.
- Preserve the plot's strongly rectangular 20:50 proportion; do not make it square.
- Draw proper wall thicknesses, connected rooms, realistic openings, and clean architectural linework.
- Every door must connect two usable spaces and swing into a sensible clear area; do not open doors into walls.
- Include sensible windows, a physically usable staircase with consistent steps, realistic bathroom fixtures, a workable kitchen, and parking that fits fully inside the plot.
- Use clear, legible English room labels, a north arrow, and a simple entrance indication.
- Use a restrained black-and-white architectural drafting style with minimal neutral accents, no 3D shading, no perspective, and no decorative artwork.
- Do not add furniture that crosses walls or obstructs doors and circulation.

VASTU GUIDANCE
- {vastu_text}
- This is a Vastu-oriented conceptual house plan only. Do not label it architect-approved, construction-ready, legally approved, structurally verified, or 100% Vastu compliant.

DIMENSION INTEGRITY
- Show only the verified outer plot dimensions: 20 ft x 50 ft.
- Do not invent or display internal numerical room dimensions, area figures, scale bars, or contradictory measurements.
- Do not generate fake dimensions or gibberish labels.

NEGATIVE REQUIREMENTS
- No random room placement, overlaps, impossible corridors, impossible staircase geometry, floating furniture, fake architectural symbols, unreadable text, 3D rendering, or perspective view.
"""


def extract_image_bytes(response: Any) -> bytes:
    """Extract the first returned image part, failing clearly if absent."""
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            inline_data = getattr(part, "inline_data", None)
            data = getattr(inline_data, "data", None) if inline_data else None
            if data:
                return data
    raise RuntimeError("Gemini returned no image data in its response.")


def main() -> int:
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Missing GEMINI_API_KEY. Add your Gemini API key to .env and retry.", file=sys.stderr)
        return 2

    prompt = build_prompt(SPECIFICATION)
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        SPEC_PATH.write_text(json.dumps(SPECIFICATION, indent=2) + "\n", encoding="utf-8")
        PROMPT_PATH.write_text(prompt, encoding="utf-8")

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(image_size="2K"),
            ),
        )
        image_bytes = extract_image_bytes(response)
        IMAGE_PATH.write_bytes(image_bytes)
    except (OSError, ValueError) as error:
        print(f"File or response error: {error}", file=sys.stderr)
        return 1
    except Exception as error:  # SDK exceptions vary across API transports.
        error_type = type(error).__name__
        print(f"Gemini request failed ({error_type}): {error}", file=sys.stderr)
        return 1

    print(f"Generated {IMAGE_PATH}")
    print(f"Saved {SPEC_PATH}")
    print(f"Saved {PROMPT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())