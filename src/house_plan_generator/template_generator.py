"""Strategy-driven template generator.

Replaces unrestricted CP-SAT search with a small library of hand-authored
"master templates". Each master template fixes the architectural strategy:
the room topology, the coarse zoning (which band/column a room lives in), the
room relationships (ensuite ownership, entry room) and a set of *approved*
parameters that may vary only within safe ranges. The generator enumerates
parameter combinations, materialises exact-tiling geometry, and then runs the
existing fail-closed gates (exact tiling -> assemble_layout -> validate_catalog_plan
-> DiversityIndex) before a candidate is ever accepted or rendered.

Design guarantees:
- Exact tiling is structural, not searched: the plot is divided into horizontal
  bands whose depths sum to the plot depth, and each band into columns whose
  widths sum to that band's width. Approved parameters only move interior split
  lines, so every materialised layout tiles the plot with no gaps or overlaps.
- Nothing here weakens a gate. It reuses assemble_layout, validate_catalog_plan
  and DiversityIndex exactly as the catalogue pipeline does.
- The generator never mirrors, relabels, or nudges an accepted plan to fake a
  new one; diversity is enforced by the existing DiversityIndex.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass, field
from typing import Callable

from .bulk_assembly import assemble_layout
from .catalog_validation import validate_catalog_plan
from .catalog_diversity import DiversityIndex


# --------------------------------------------------------------------------- #
# Master-template schema
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class MasterTemplate:
    """A fixed architectural strategy with only approved variable parameters.

    Attributes:
        template_id: stable identifier, also the seed_id prefix.
        strategy: human-readable description of the fixed strategy.
        width, depth: plot size in feet.
        bedrooms: declared BHK.
        store: whether the group requires a usable store.
        entry: room id where the exterior entrance sits.
        combined_living_dining: whether living doubles as dining.
        ensuite: optional {bath_id: bedroom_id} ensuite ownership.
        params: ordered mapping of parameter name -> tuple of approved values.
        layout: callable(params) -> {room_id: [x, y, w, d]} that MUST tile the
            plot exactly for every approved parameter combination.
    """

    template_id: str
    strategy: str
    width: float
    depth: float
    bedrooms: int
    store: bool
    entry: str
    combined_living_dining: bool
    params: dict
    layout: Callable[[dict], dict]
    ensuite: dict = field(default_factory=dict)
    valid: Callable[[dict], bool] = None

    def group_key(self):
        return (self.width, self.depth, self.bedrooms, self.store)

    def raw(self, values):
        return {
            "status": "AUTHORED_SEED",
            "entry": self.entry,
            "combined_living_dining": self.combined_living_dining,
            "ensuite": dict(self.ensuite),
            "rooms": self.layout(values),
        }

    def combinations(self):
        """Deterministic ordered parameter combinations passing the valid guard."""
        names = list(self.params)
        for combo in itertools.product(*[self.params[n] for n in names]):
            values = dict(zip(names, combo))
            if self.valid is None or self.valid(values):
                yield values


# --------------------------------------------------------------------------- #
# Exact-tiling validation (structural safety net for template authors)
# --------------------------------------------------------------------------- #
def tiling_error(rooms, width, depth):
    """Return an error string if the rooms do not tile the plot exactly."""
    scale = 2  # half-foot cells
    expected = {(x, y) for x in range(round(width * scale)) for y in range(round(depth * scale))}
    occupied = set()
    for room_id, rect in rooms.items():
        x, y, w, d = (round(float(v) * scale) for v in rect)
        if w <= 0 or d <= 0:
            return f"{room_id}: non-positive rectangle {rect}"
        cells = {(ix, iy) for ix in range(x, x + w) for iy in range(y, y + d)}
        if occupied & cells:
            return f"{room_id}: overlaps another room"
        occupied |= cells
    if occupied != expected:
        return f"plot not tiled exactly: covered {len(occupied)} of {len(expected)} cells"
    return None


def _assembly_seed(template_id, values):
    payload = json.dumps([template_id, sorted(values.items())], separators=(",", ":"))
    return int(hashlib.sha256(payload.encode()).hexdigest()[:8], 16)


# --------------------------------------------------------------------------- #
# Bounded generation against the existing gates
# --------------------------------------------------------------------------- #
def generate_from_template(template, index, max_candidates=10, existing_reasons=None):
    """Try up to ``max_candidates`` parameter combinations through every gate.

    ``index`` is a shared DiversityIndex already seeded with the accepted bank so
    new candidates are checked against everything already accepted. Accepted
    plans are added to the index so a single call never emits near-duplicates of
    each other. Returns (accepted_plans, report).
    """
    accepted = []
    attempts = 0
    reasons = {}
    for values in template.combinations():
        if attempts >= max_candidates:
            break
        attempts += 1
        rooms = template.layout(values)
        tile_err = tiling_error(rooms, template.width, template.depth)
        if tile_err:
            reasons[f"tiling"] = reasons.get("tiling", 0) + 1
            continue
        raw = template.raw(values)
        seed = _assembly_seed(template.template_id, values)
        plan, err = assemble_layout(raw, template.width, template.depth,
                                    template.bedrooms, template.store, seed)
        if err:
            reasons[f"assemble:{err}"] = reasons.get(f"assemble:{err}", 0) + 1
            continue
        geom_hash = hashlib.sha256(json.dumps(rooms, sort_keys=True).encode()).hexdigest()[:12]
        plan.update(
            design_id=f"{template.template_id}_{geom_hash}",
            template_id=template.template_id,
            layout_strategy=template.strategy,
            generation_source="strategy_template_generator",
            template_parameters=values,
        )
        validation = validate_catalog_plan(plan)
        if validation["overall"] != "PASS":
            key = f"validate:{validation['errors'][0] if validation['errors'] else 'FAIL'}"
            reasons[key] = reasons.get(key, 0) + 1
            continue
        reason, score = index.check(plan)
        if reason:
            reasons[f"diversity:{reason}"] = reasons.get(f"diversity:{reason}", 0) + 1
            continue
        index.add(plan)
        accepted.append(plan)

    report = {
        "template_id": template.template_id,
        "group": {"width": template.width, "depth": template.depth,
                  "bedrooms": template.bedrooms, "store": template.store},
        "candidates_attempted": attempts,
        "accepted": len(accepted),
        "rejections": reasons,
    }
    return accepted, report
