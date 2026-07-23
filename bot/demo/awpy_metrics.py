"""Advanced per-player metrics, computed by awpy.

awpy ships ADR, KAST, impact and an HLTV-style rating, all of which are far more
informative than raw K/D and none of which are worth reimplementing.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl
from awpy import Demo
from awpy.stats import adr, impact, kast, rating

# Valve matchmaking demos record at 64. awpy defaults to 128, which would halve
# every trade window and quietly corrupt KAST.
VALVE_TICKRATE = 64


@dataclass
class AdvancedMetrics:
    """Per-steamid metrics for the whole match (both sides combined)."""

    adr: dict[str, float] = field(default_factory=dict[str, float])
    kast: dict[str, float] = field(default_factory=dict[str, float])
    rating: dict[str, float] = field(default_factory=dict[str, float])
    impact: dict[str, float] = field(default_factory=dict[str, float])
    rounds: int = 0

    def for_player(self, steamid: str) -> dict[str, float]:
        return {
            "adr": self.adr.get(steamid, 0.0),
            "kast": self.kast.get(steamid, 0.0),
            "rating": self.rating.get(steamid, 0.0),
            "impact": self.impact.get(steamid, 0.0),
        }

    @property
    def is_empty(self) -> bool:
        return not self.rating


def _by_steamid(frame: pl.DataFrame, column: str) -> dict[str, float]:
    """Collapse an awpy stat frame to steamid -> value, whole-match rows only."""
    if "side" in frame.columns:
        frame = frame.filter(pl.col("side") == "all")
    return {
        str(row["steamid"]): float(row[column])
        for row in frame.iter_rows(named=True)
        if row.get("steamid") is not None and row.get(column) is not None
    }


def compute_advanced(demo_path: str | Path) -> tuple[AdvancedMetrics, pl.DataFrame]:
    """Parse with awpy and return the advanced metrics and the position ticks.

    One parse yields both: awpy records every player's position on every tick as
    a side effect of the stats, so line of sight (visibility.py) rides along for
    free rather than paying for a second parse.

    Failure here must not take the whole analysis down: these are a bonus on top
    of the demoparser2 stats, not a prerequisite. On failure the caller gets
    empty metrics and an empty tick frame and carries on.
    """
    try:
        demo = Demo(Path(demo_path), tickrate=VALVE_TICKRATE)
        demo.parse()
        adr_frame = adr(demo)
        metrics = AdvancedMetrics(
            adr=_by_steamid(adr_frame, "adr"),
            kast=_by_steamid(kast(demo), "kast"),
            rating=_by_steamid(rating(demo), "rating"),
            impact=_by_steamid(impact(demo), "impact"),
            rounds=int(adr_frame.filter(pl.col("side") == "all")["n_rounds"].max() or 0),
        )
        logging.info("awpy metrics computed for %d players", len(metrics.rating))
        return metrics, demo.ticks
    except Exception:
        logging.exception("awpy metrics failed; continuing without them")
        return AdvancedMetrics(), pl.DataFrame()
