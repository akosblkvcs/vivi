"""Coercion helpers for demo cells.

Values arrive from demoparser2 as numpy scalars, NaN, or None depending on the
column and the row, so every read needs narrowing before it can be used.
"""

import math
from typing import SupportsFloat, SupportsIndex


def as_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, SupportsFloat):
        number = float(value)
        return default if math.isnan(number) else number
    return default


def as_int(value: object, default: int = 0) -> int:
    if isinstance(value, SupportsIndex):
        return int(value)
    number = as_float(value, math.nan)
    return default if math.isnan(number) else int(number)


def as_steamid(value: object) -> str | None:
    """Normalise a steamid cell; demo events leave it NaN for world kills."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return str(value) or None
