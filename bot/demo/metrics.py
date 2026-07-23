"""The per-player metrics the lenses rank and compare on.

Shared building block: the anomalies lens compares these across the lobby, the
baseline lens compares them against a player's own history, and history.py stores
them. Defining them once keeps those three in lockstep.
"""

from collections.abc import Callable
from dataclasses import dataclass

from bot.demo.awpy_metrics import AdvancedMetrics
from bot.demo.models import PlayerStats


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    value: Callable[[PlayerStats, AdvancedMetrics], float]
    # None means the metric has no honest direction: bullets fired is high when
    # someone sprays wildly and low when they were dead all match, and neither
    # deserves praise. Those get reported without a verdict attached.
    higher_is_better: bool | None
    fmt: str = "{:.1f}"


METRICS: tuple[Metric, ...] = (
    Metric("rating", "rating", lambda p, a: a.rating.get(p.steamid, 0.0), True, "{:.2f}"),
    Metric("adr", "ADR", lambda p, a: a.adr.get(p.steamid, 0.0), True, "{:.0f}"),
    Metric("kast", "KAST", lambda p, a: a.kast.get(p.steamid, 0.0), True, "{:.0f}%"),
    Metric("accuracy", "accuracy", lambda p, _: p.accuracy * 100, True, "{:.0f}%"),
    Metric(
        "headshot_rate",
        "headshot rate",
        lambda p, _: (p.headshot_kills / p.kills * 100) if p.kills else 0.0,
        True,
        "{:.0f}%",
    ),
    Metric("kd", "K/D", lambda p, _: p.kd, True, "{:.2f}"),
    Metric("shots_fired", "bullets fired", lambda p, _: float(p.shots_fired), None, "{:.0f}"),
    Metric(
        "teamflash_seconds",
        "seconds spent blinding teammates",
        lambda p, _: p.teamflash_seconds,
        False,
        "{:.1f}s",
    ),
    Metric(
        "team_damage", "damage to own team", lambda p, _: float(p.team_damage), False, "{:.0f}hp"
    ),
    Metric(
        "first_deaths", "times dying first in a round", lambda p, _: float(p.first_deaths), False
    ),
)
