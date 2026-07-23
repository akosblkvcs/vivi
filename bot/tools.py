"""Tools Claude can call while investigating a match.

Docstrings are the tool descriptions the model sees, so they say *when* to reach
for each lens, not just what it returns.
"""

from bot.demo import analysis
from bot.demo.analysis import MatchContext
from bot.demo.anomaly import anomaly_report
from bot.demo.baseline import baseline_report

_current: MatchContext | None = None


def set_context(ctx: MatchContext | None) -> None:
    global _current
    _current = ctx


def _ctx() -> MatchContext:
    if _current is None:
        raise RuntimeError("no match context is loaded")
    return _current


def get_scoreboard() -> str:
    """Overall per-player totals: kills, deaths, assists, K/D, headshots, accuracy.

    Each player is tagged [self], [friend] or [unknown]. Start here to see the
    shape of the match before drilling into anything specific.
    """
    return analysis.scoreboard(_ctx())


def get_kill_feed(round_number: int | None = None) -> str:
    """Chronological kill-by-kill log, optionally for a single round.

    Each line shows the round, seconds into the round, killer, victim, weapon,
    and tags for headshot / noscope / smoke / wallbang. Kills that were never
    avenged are marked UNTRADED. Use this to find stories the totals hide:
    someone dying first over and over, a teammate failing to trade, a player
    losing a duel to the same enemy repeatedly. Call with no argument for the
    whole match, or with a round number to zoom in.
    """
    return analysis.kill_feed(_ctx(), round_number)


def get_player_profile(name: str) -> str:
    """Everything known about one player: aim, deaths, utility misuse, odd deaths.

    Use after something in the scoreboard or kill feed looks worth pursuing.
    Also returns any note the bot stores about that person.
    """
    return analysis.player_profile(_ctx(), name)


def get_round_outcomes() -> str:
    """Per-round shape: kill counts, multi-kills (3k+), and 1vN situations.

    Use this to find clutches and heroic rounds worth praising, not just failures.
    """
    return analysis.round_outcomes(_ctx())


def get_utility_report() -> str:
    """Who blinded and damaged their own team, and how badly.

    Teamflashes and team damage are reliable roasting material.
    """
    return analysis.utility_report(_ctx())


def get_suspicion_metrics() -> str:
    """Leetify-style aim numbers: headshot rate, accuracy, wallbangs, smoke kills.

    Use when someone's aim looks either implausibly good (mock them for cheating)
    or genuinely dreadful (mock them for that instead).
    """
    return analysis.suspicion_metrics(_ctx())


def find_anomalies() -> str:
    """Statistical outliers: what actually stands out in this match, computed not guessed.

    Every player-metric pair is compared against the lobby average and ranked by
    how many standard deviations it sits away, split into unusually bad and
    unusually good. THIS IS THE BEST STARTING POINT for finding material —
    it tells you what is genuinely unusual about this specific match rather than
    what is merely true of every match. Follow up with the kill feed or a player
    profile to find out why an outlier happened.
    """
    return anomaly_report(_ctx())


def compare_to_history() -> str:
    """How each player did against THEIR OWN past matches, not against this lobby.

    This is the strongest material there is: it distinguishes "he is bad" from
    "he was bad tonight", and it names personal bests and personal worsts. Call
    it alongside find_anomalies — an outlier that is also unusual for that
    person is far more interesting than one that is just how they always play.
    Returns a note instead if too little history has been recorded yet.
    """
    return baseline_report(_ctx())


def get_advanced_metrics() -> str:
    """Rating, ADR, KAST and impact for every player, ranked.

    These say far more about who actually played well than kills do. A player
    with a high kill count but low KAST was dying pointlessly; a player with low
    kills but high ADR was doing the damage someone else finished off. Reach for
    this before deciding who to praise or roast.
    """
    return analysis.advanced_metrics(_ctx())


ALL_TOOLS = (
    find_anomalies,
    compare_to_history,
    get_scoreboard,
    get_advanced_metrics,
    get_kill_feed,
    get_player_profile,
    get_round_outcomes,
    get_utility_report,
    get_suspicion_metrics,
)
