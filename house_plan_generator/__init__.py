"""Compatibility package that points to the centralized src implementation."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "house_plan_generator"
__path__ = [str(SRC)] + list(__path__)
