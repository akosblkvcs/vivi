"""Statistical outlier detection over a parsed match.

The point is that nobody has to write down what is interesting. Each metric is
compared against the rest of the lobby, and whatever deviates hardest is what
gets surfaced. A match where everyone played evenly produces few anomalies; a
match where someone fell apart produces obvious ones, without a watchlist.
"""

import statistics
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from bot.demo.awpy_metrics import AdvancedMetrics
from bot.demo.models import PlayerStats

if TYPE_CHECKING:
    from bot.demo.analysis import MatchContext

# Deviations smaller than this are noise in a ten-player sample.
MIN_SIGMA = 1.2

# A metric needs a few players before a mean and deviation mean anything.
MIN_SAMPLE = 4


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


@dataclass(frozen=True)
class Anomaly:
    display: str
    role: str
    metric: Metric
    value: float
    mean: float
    sigma: float

    @property
    def is_flattering(self) -> bool | None:
        """Whether deviating this way makes the player look good, if it can be said."""
        if self.metric.higher_is_better is None:
            return None
        return (self.sigma > 0) == self.metric.higher_is_better

    def render(self) -> str:
        direction = "above" if self.sigma > 0 else "below"
        return (
            f"- {self.display} [{self.role}]: {self.metric.label} "
            f"{self.metric.fmt.format(self.value)} vs lobby average "
            f"{self.metric.fmt.format(self.mean)} — {abs(self.sigma):.1f} sigma {direction}"
        )


def find_anomalies(ctx: MatchContext, min_sigma: float = MIN_SIGMA) -> list[Anomaly]:
    """Rank every player-metric pair by how far it sits from the lobby norm."""
    players = list(ctx.stats.players.values())
    if len(players) < MIN_SAMPLE:
        return []

    found: list[Anomaly] = []
    for metric in METRICS:
        values = [metric.value(p, ctx.advanced) for p in players]
        mean = statistics.fmean(values)
        try:
            spread = statistics.stdev(values)
        except statistics.StatisticsError:
            continue
        # Everyone identical: no outliers exist, and dividing would explode.
        if spread < 1e-9:
            continue

        for player, value in zip(players, values, strict=True):
            sigma = (value - mean) / spread
            if abs(sigma) < min_sigma:
                continue
            found.append(
                Anomaly(
                    display=ctx.display(player.steamid, player.name),
                    role=ctx.roster.role_of(player.steamid),
                    metric=metric,
                    value=value,
                    mean=mean,
                    sigma=sigma,
                )
            )

    found.sort(key=lambda a: abs(a.sigma), reverse=True)
    return found


def anomaly_report(ctx: MatchContext, min_sigma: float = MIN_SIGMA) -> str:
    anomalies = find_anomalies(ctx, min_sigma)
    if not anomalies:
        return (
            "Nothing in this match deviates meaningfully from the lobby average. "
            "Everyone played about as well, or as badly, as everyone else."
        )

    damning = [a for a in anomalies if a.is_flattering is False]
    flattering = [a for a in anomalies if a.is_flattering is True]
    ambiguous = [a for a in anomalies if a.is_flattering is None]

    lines = [
        "Each line is one player-metric pair that deviates from this lobby's average.",
        "Sigma is how many standard deviations away it sits: bigger means more unusual.",
    ]
    if damning:
        lines += ["", "UNUSUALLY BAD:", *(a.render() for a in damning)]
    if flattering:
        lines += ["", "UNUSUALLY GOOD:", *(a.render() for a in flattering)]
    if ambiguous:
        lines += [
            "",
            "UNUSUAL, BUT COULD MEAN EITHER (work out which from the other tools):",
            *(a.render() for a in ambiguous),
        ]
    return "\n".join(lines)
