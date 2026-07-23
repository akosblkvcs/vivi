"""Compare each player against their own past matches.

anomaly.py answers "who was the outlier in this lobby". This answers "was this
normal *for them*", which is a different and less repeatable question: the
comparison target moves every match, so the same joke cannot come back.
"""

import statistics
from dataclasses import dataclass

from bot import history
from bot.demo.analysis import MatchContext
from bot.demo.anomaly import METRICS, Metric

# Below this a mean is just the last couple of matches, and a deviation from it
# says nothing. Kept low so the feature starts paying off early.
MIN_MATCHES = 3

# Personal deviations are noisier than lobby ones, so demand a wider gap.
MIN_SIGMA = 1.5

# A record over a handful of matches is luck, not a story.
MIN_MATCHES_FOR_RECORD = 4

# A record has to beat the old one by a real margin. Without this, shaving 1hp
# off a personal best counts, and "0hp team damage, a new low" gets reported as
# though it were an event.
MIN_RECORD_MARGIN = 0.15

# One player breaking every record at once is noise, not a story. Keep only
# their most decisive ones.
MAX_RECORDS_PER_PLAYER = 3

# Over a handful of matches the standard deviation is barely estimated, so
# sigma can reach absurd values. Past this it is reported as a floor, to stop
# the model quoting "26 sigma" as though it meant something.
SIGMA_DISPLAY_CAP = 6.0

# Ten players against ten metrics can produce a hundred findings, which tells
# the model nothing about which one to write about. Keep the report to a
# readable shortlist.
MAX_DEVIATIONS = 18
MAX_RECORDS = 12

# The recap is about the friends. A stranger has to be a much bigger outlier
# than a friend to be worth one of the limited slots.
ROLE_WEIGHT = {"self": 1.0, "friend": 1.0, "unknown": 0.5}


@dataclass(frozen=True)
class Deviation:
    display: str
    role: str
    metric: Metric
    value: float
    mean: float
    sigma: float
    samples: int

    @property
    def is_flattering(self) -> bool | None:
        if self.metric.higher_is_better is None:
            return None
        return (self.sigma > 0) == self.metric.higher_is_better

    def render(self) -> str:
        direction = "above" if self.sigma > 0 else "below"
        magnitude = abs(self.sigma)
        shown = (
            f"over {SIGMA_DISPLAY_CAP:.0f}" if magnitude > SIGMA_DISPLAY_CAP else f"{magnitude:.1f}"
        )
        return (
            f"- {self.display} [{self.role}]: {self.metric.label} "
            f"{self.metric.fmt.format(self.value)} vs their own average "
            f"{self.metric.fmt.format(self.mean)} over {self.samples} past matches "
            f"— {shown} sigma {direction}"
        )


@dataclass(frozen=True)
class Record:
    display: str
    role: str
    metric: Metric
    value: float
    previous: float
    samples: int
    is_high: bool

    @property
    def margin(self) -> float:
        """How decisively the old record fell, relative to its own size."""
        return abs(self.value - self.previous) / (abs(self.previous) or 1.0)

    @property
    def is_flattering(self) -> bool | None:
        if self.metric.higher_is_better is None:
            return None
        return self.is_high == self.metric.higher_is_better

    def render(self) -> str:
        kind = "highest" if self.is_high else "lowest"
        return (
            f"- {self.display} [{self.role}]: {self.metric.label} "
            f"{self.metric.fmt.format(self.value)} is their {kind} in "
            f"{self.samples + 1} matches (previous {kind}: "
            f"{self.metric.fmt.format(self.previous)})"
        )


def _compare(
    ctx: MatchContext, past: dict[str, list[dict[str, float]]]
) -> tuple[list[Deviation], list[Record]]:
    deviations: list[Deviation] = []
    records: list[Record] = []

    for player in ctx.stats.players.values():
        matches = past.get(player.steamid, [])
        if len(matches) < MIN_MATCHES:
            continue
        display = ctx.display(player.steamid, player.name)
        role = ctx.roster.role_of(player.steamid)
        mine: list[Record] = []

        for metric in METRICS:
            # Older rows predate metrics added later; skip rather than treat a
            # missing key as a zero, which would invent a collapse.
            values = [m[metric.key] for m in matches if metric.key in m]
            if len(values) < MIN_MATCHES:
                continue
            now = metric.value(player, ctx.advanced)
            mean = statistics.fmean(values)

            try:
                spread = statistics.stdev(values)
            except statistics.StatisticsError:
                spread = 0.0
            if spread > 1e-9:
                sigma = (now - mean) / spread
                if abs(sigma) >= MIN_SIGMA:
                    deviations.append(
                        Deviation(display, role, metric, now, mean, sigma, len(values))
                    )

            if len(values) >= MIN_MATCHES_FOR_RECORD:
                broken: Record | None = None
                if now > max(values):
                    broken = Record(display, role, metric, now, max(values), len(values), True)
                elif now < min(values):
                    broken = Record(display, role, metric, now, min(values), len(values), False)
                if broken is not None and broken.margin >= MIN_RECORD_MARGIN:
                    mine.append(broken)

        mine.sort(key=lambda r: r.margin, reverse=True)
        records.extend(mine[:MAX_RECORDS_PER_PLAYER])

    deviations.sort(key=lambda d: abs(d.sigma) * ROLE_WEIGHT[d.role], reverse=True)
    records.sort(key=lambda r: r.margin * ROLE_WEIGHT[r.role], reverse=True)
    return deviations[:MAX_DEVIATIONS], records[:MAX_RECORDS]


def baseline_report(ctx: MatchContext) -> str:
    steamids = [p.steamid for p in ctx.stats.players.values()]
    past = history.past_metrics(steamids, ctx.demo_key)
    if not past:
        stored = history.match_count()
        if stored == 0:
            return (
                "No match history is available yet — either the database is not "
                "configured or this is the first match recorded. Use find_anomalies "
                "instead; personal comparisons will work once more matches are stored."
            )
        return (
            f"{stored} matches are stored, but none of them include these players. "
            "Use find_anomalies instead."
        )

    deviations, records = _compare(ctx, past)
    if not deviations and not records:
        return (
            f"Everyone in this match played close to their own usual level "
            f"(history covers {history.match_count()} matches). Nothing here is out "
            "of character — use find_anomalies for within-match comparisons."
        )

    lines = [
        "Each line compares a player to THEIR OWN past matches, not to this lobby.",
        "This is the strongest material available: it says whether tonight was",
        "unusual for that specific person.",
    ]

    for title, chosen in (
        ("WORSE THAN THEIR USUAL SELF", [d for d in deviations if d.is_flattering is False]),
        ("BETTER THAN THEIR USUAL SELF", [d for d in deviations if d.is_flattering is True]),
        ("DIFFERENT, DIRECTION UNCLEAR", [d for d in deviations if d.is_flattering is None]),
    ):
        if chosen:
            lines += ["", f"{title}:", *(d.render() for d in chosen)]

    for title, picked in (
        ("PERSONAL WORSTS", [r for r in records if r.is_flattering is False]),
        ("PERSONAL BESTS", [r for r in records if r.is_flattering is True]),
    ):
        if picked:
            lines += ["", f"{title}:", *(r.render() for r in picked)]

    return "\n".join(lines)
