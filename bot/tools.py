"""Tools Claude can call while investigating a match.

Docstrings are the tool descriptions the model sees, so they say *when* to reach
for each lens, not just what it returns.
"""

from bot.demo import analysis
from bot.demo.analysis import MatchContext

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


ALL_TOOLS = (
    get_scoreboard,
    get_kill_feed,
    get_player_profile,
    get_round_outcomes,
    get_utility_report,
    get_suspicion_metrics,
)
