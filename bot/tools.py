"""Tools Claude can call while investigating a match.

Each tool wraps one lens from bot/demo/lenses/. To add a feature, add a lens
there and expose it here.
"""

from bot.demo.analysis import MatchContext
from bot.demo.lenses.advanced import advanced_metrics
from bot.demo.lenses.anomalies import anomaly_report
from bot.demo.lenses.baseline import baseline_report
from bot.demo.lenses.kill_feed import kill_feed
from bot.demo.lenses.player_profile import player_profile
from bot.demo.lenses.round_outcomes import round_outcomes
from bot.demo.lenses.scoreboard import scoreboard
from bot.demo.lenses.suspicion import suspicion_metrics
from bot.demo.lenses.utility import utility_report
from bot.demo.lenses.witnessed import witnessed_deaths

_current: MatchContext | None = None


def set_context(ctx: MatchContext | None) -> None:
    global _current
    _current = ctx


def _ctx() -> MatchContext:
    if _current is None:
        raise RuntimeError("no match context is loaded")
    return _current


def get_scoreboard() -> str:
    """Overall per-player totals: kills, deaths, assists, K/D, headshots, accuracy."""
    return scoreboard(_ctx())


def get_kill_feed(round_number: int | None = None) -> str:
    """Chronological kill-by-kill log, optionally for a single round."""
    return kill_feed(_ctx(), round_number)


def get_player_profile(name: str) -> str:
    """Everything known about one player: aim, deaths, utility misuse, odd deaths."""
    return player_profile(_ctx(), name)


def get_round_outcomes() -> str:
    """Per-round shape: kill counts, multi-kills (3k+), and 1vN situations."""
    return round_outcomes(_ctx())


def get_utility_report() -> str:
    """Who blinded and damaged their own team, and how badly."""
    return utility_report(_ctx())


def get_suspicion_metrics() -> str:
    """Leetify-style aim numbers: headshot rate, accuracy, wallbangs, smoke kills."""
    return suspicion_metrics(_ctx())


def find_anomalies() -> str:
    """Statistical outliers: what actually stands out in this match, computed not guessed."""
    return anomaly_report(_ctx())


def compare_to_history() -> str:
    """How each player did against THEIR OWN past matches, not against this lobby."""
    return baseline_report(_ctx())


def get_witnessed_deaths() -> str:
    """Untraded deaths a living teammate had a clear line of sight to and ignored."""
    return witnessed_deaths(_ctx())


def get_advanced_metrics() -> str:
    """Rating, ADR, KAST and impact for every player, ranked."""
    return advanced_metrics(_ctx())


ALL_TOOLS = (
    find_anomalies,
    compare_to_history,
    get_scoreboard,
    get_advanced_metrics,
    get_kill_feed,
    get_witnessed_deaths,
    get_player_profile,
    get_round_outcomes,
    get_utility_report,
    get_suspicion_metrics,
)
