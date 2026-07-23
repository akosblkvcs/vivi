"""Line of sight over the player position ticks.

awpy already records every player's position on every tick while it computes the
advanced metrics, and it ships a per-map collision mesh (a .tri file). Together
they answer a question the kill feed cannot: when a death went untraded, was a
teammate stood right there with a clear line to it and simply let it happen?
That turns "untraded" into "witnessed and ignored" — funnier, and much harder to
repeat match to match, since it depends on where everyone actually was.

The meshes come from `awpy get tris`. Without them, or if anything else goes
wrong, this reports nothing and the recap carries on — exactly like the advanced
metrics when their parse fails.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import polars as pl
from awpy.data import TRIS_DIR
from awpy.visibility import VisibilityChecker

if TYPE_CHECKING:
    from bot.demo.analysis import Kill

# Source units. A standing player's eyes sit ~64 units up; 52.5 units is a metre.
EYE_HEIGHT = 64.0
UNITS_PER_METRE = 52.5
# Past this a "witness" is really just someone who shared a sightline down a long
# lane. Under it, "stood there and watched" is a fair thing to say.
MAX_WITNESS_METRES = 20.0

# The only tick columns line of sight needs.
_TICK_COLS = ("tick", "steamid", "name", "side", "health", "X", "Y", "Z")

_Row = dict[str, Any]
_Frame = dict[str, _Row]


@dataclass
class WitnessedDeath:
    """An untraded death a living teammate had a clear line of sight to.

    Distance is from the witness to the dying teammate, in metres. When more than
    one teammate could see it, this holds the closest and counts the rest.
    """

    round_no: int
    victim_id: str
    victim_name: str
    killer_id: str
    killer_name: str
    weapon: str
    witness_id: str
    witness_name: str
    distance_m: float
    witness_count: int


def _load_checker(map_name: str) -> VisibilityChecker | None:
    tri = TRIS_DIR / f"{map_name}.tri"
    if not tri.is_file():
        logging.info("no collision mesh at %s; skipping line of sight", tri)
        return None
    try:
        return VisibilityChecker(path=tri)
    except Exception:
        logging.exception("could not build the visibility checker for %s", map_name)
        return None


def _positions_at(ticks: pl.DataFrame, wanted: set[int]) -> dict[int, _Frame]:
    """tick -> {steamid -> row}, for the given ticks only."""
    cols = [c for c in _TICK_COLS if c in ticks.columns]
    sub = ticks.select(cols).filter(pl.col("tick").is_in(list(wanted)))
    frames: dict[int, _Frame] = {}
    for row in sub.iter_rows(named=True):
        frames.setdefault(int(row["tick"]), {})[str(row["steamid"])] = row
    return frames


def _eye(row: _Row) -> tuple[float, float, float]:
    return (float(row["X"]), float(row["Y"]), float(row["Z"]) + EYE_HEIGHT)


def _metres(a: _Row, b: _Row) -> float:
    dx = float(a["X"]) - float(b["X"])
    dy = float(a["Y"]) - float(b["Y"])
    dz = float(a["Z"]) - float(b["Z"])
    return float((dx * dx + dy * dy + dz * dz) ** 0.5) / UNITS_PER_METRE


def _witnesses(
    checker: VisibilityChecker, frame: _Frame, kill: Kill, victim: _Row
) -> list[tuple[str, str, float]]:
    """Living teammates of the victim who had an unobstructed line to the death."""
    found: list[tuple[str, str, float]] = []
    for steamid, row in frame.items():
        if steamid == kill.victim_id or steamid == kill.killer_id:
            continue
        if row["side"] != victim["side"] or float(row["health"] or 0) <= 0:
            continue
        metres = _metres(row, victim)
        if metres > MAX_WITNESS_METRES:
            continue
        if checker.is_visible(_eye(row), _eye(victim)):
            found.append((steamid, str(row["name"]), metres))
    return found


def compute_witnessed(
    ticks: pl.DataFrame, kills: list[Kill], map_name: str
) -> list[WitnessedDeath]:
    """Find untraded deaths a living, nearby teammate had a clear line to.

    Line of sight is geometric: the teammate *could* see the death, not proof
    they were looking. Combined with proximity and the kill going untraded, that
    is enough to call it witnessed neglect.
    """
    untraded = [k for k in kills if not k.traded]
    if ticks.is_empty() or not untraded:
        return []
    checker = _load_checker(map_name)
    if checker is None:
        return []

    frames = _positions_at(ticks, {k.tick for k in untraded})
    results: list[WitnessedDeath] = []
    for kill in untraded:
        frame = frames.get(kill.tick)
        victim = frame.get(kill.victim_id) if frame else None
        if frame is None or victim is None:
            continue
        witnesses = _witnesses(checker, frame, kill, victim)
        if not witnesses:
            continue
        closest_id, closest_name, metres = min(witnesses, key=lambda w: w[2])
        results.append(
            WitnessedDeath(
                round_no=kill.round_no,
                victim_id=kill.victim_id,
                victim_name=kill.victim_name,
                killer_id=kill.killer_id,
                killer_name=kill.killer_name,
                weapon=kill.weapon,
                witness_id=closest_id,
                witness_name=closest_name,
                distance_m=metres,
                witness_count=len(witnesses),
            )
        )
    logging.info(
        "line of sight: %d of %d untraded deaths were witnessed", len(results), len(untraded)
    )
    return results
