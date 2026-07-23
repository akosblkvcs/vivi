"""Queryable view over a parsed demo.

The stat engine in stats.py decides up front what matters. This module instead
exposes the match as a set of lenses Claude can ask for, so it can chase
whatever looks interesting rather than only what we anticipated.

Players are identified by SteamID throughout. In-game names are only ever used
for strangers, since friends are addressed by the nickname the roster assigns.
"""

import logging
from collections import Counter
from dataclasses import dataclass, field

import pandas as pd
from demoparser2 import DemoParser

from bot.demo.awpy_metrics import AdvancedMetrics, compute_advanced
from bot.demo.coerce import as_int, as_steamid
from bot.demo.models import MatchStats
from bot.demo.stats import compute_match_stats
from bot.roster import Roster, load_roster

# CS2 demos record at 64 ticks per second. A kill that avenges a teammate within
# five seconds counts as a trade.
TICKRATE = 64
TRADE_WINDOW_TICKS = TICKRATE * 5
MAX_TEAM_SIZE = 5


@dataclass
class Kill:
    round_no: int
    tick: int
    killer_id: str
    victim_id: str
    killer_name: str
    victim_name: str
    weapon: str
    headshot: bool
    noscope: bool
    through_smoke: bool
    wallbang: bool
    killer_team: int
    victim_team: int
    traded: bool = False


@dataclass
class MatchContext:
    """Everything a tool call might need, parsed once and held in memory."""

    stats: MatchStats
    roster: Roster
    deaths: pd.DataFrame
    blinds: pd.DataFrame
    hurts: pd.DataFrame
    kills: list[Kill] = field(default_factory=list[Kill])
    advanced: AdvancedMetrics = field(default_factory=AdvancedMetrics)
    # Content hash of the demo, used to store and to exclude this match from its
    # own baselines. Empty when the file could not be hashed.
    demo_key: str = ""

    def display(self, steamid: str, ingame_name: str) -> str:
        return self.roster.display(steamid, ingame_name)

    def tagged(self, steamid: str, ingame_name: str) -> str:
        """Display name plus how the bot knows this person."""
        return f"{self.display(steamid, ingame_name)} [{self.roster.role_of(steamid)}]"


def _build_kills(deaths: pd.DataFrame) -> list[Kill]:
    kills: list[Kill] = []
    for row in deaths.itertuples(index=False):
        killer_id = as_steamid(row.attacker_steamid)
        victim_id = as_steamid(row.user_steamid)
        if killer_id is None or victim_id is None or killer_id == victim_id:
            continue
        kills.append(
            Kill(
                round_no=as_int(getattr(row, "total_rounds_played", 0)) + 1,
                tick=as_int(row.tick),
                killer_id=killer_id,
                victim_id=victim_id,
                killer_name=str(row.attacker_name),
                victim_name=str(row.user_name),
                weapon=str(row.weapon),
                headshot=bool(row.headshot),
                noscope=bool(getattr(row, "noscope", False)),
                through_smoke=bool(getattr(row, "thrusmoke", False)),
                wallbang=as_int(getattr(row, "penetrated", 0)) > 0,
                killer_team=as_int(getattr(row, "attacker_team_num", -1), -1),
                victim_team=as_int(getattr(row, "user_team_num", -2), -2),
            )
        )
    kills.sort(key=lambda k: k.tick)
    _mark_trades(kills)
    return kills


def _mark_trades(kills: list[Kill]) -> None:
    """A kill is traded if the killer dies to the victim's side within the window."""
    for i, kill in enumerate(kills):
        for later in kills[i + 1 :]:
            if later.round_no != kill.round_no:
                break
            if later.tick - kill.tick > TRADE_WINDOW_TICKS:
                break
            if later.victim_id == kill.killer_id and later.killer_team == kill.victim_team:
                kill.traded = True
                break


def _demo_key(demo_path: str) -> str:
    """Hash the demo for history lookups; a failure here only costs baselines."""
    from bot.history import demo_key

    try:
        return demo_key(demo_path)
    except OSError:
        logging.exception("could not hash %s; this match will not be stored", demo_path)
        return ""


def build_context(demo_path: str, roster: Roster | None = None) -> MatchContext:
    parser = DemoParser(demo_path)
    deaths = parser.parse_event("player_death", player=["team_num"], other=["total_rounds_played"])
    blinds = parser.parse_event("player_blind", player=["team_num"])
    hurts = parser.parse_event("player_hurt", player=["team_num"])

    logging.info("building analysis context from %s", demo_path)
    return MatchContext(
        stats=compute_match_stats(demo_path),
        roster=roster or load_roster(),
        deaths=deaths,
        blinds=blinds,
        hurts=hurts,
        kills=_build_kills(deaths),
        advanced=compute_advanced(demo_path),
        demo_key=_demo_key(demo_path),
    )


# --- lenses -----------------------------------------------------------------


def scoreboard(ctx: MatchContext) -> str:
    lines = [f"MAP: {ctx.stats.map_name}, {ctx.stats.rounds} rounds", ""]
    ranked = sorted(
        ctx.stats.players.values(),
        key=lambda p: ctx.advanced.rating.get(p.steamid, float(p.kills)),
        reverse=True,
    )
    for p in ranked:
        adv = ctx.advanced.for_player(p.steamid)
        extra = (
            f", rating {adv['rating']:.2f}, ADR {adv['adr']:.0f}, KAST {adv['kast']:.0f}%"
            if not ctx.advanced.is_empty
            else ""
        )
        lines.append(
            f"- {ctx.tagged(p.steamid, p.name)}: {p.kills}K/{p.deaths}D/{p.assists}A, "
            f"K/D {p.kd:.2f}, {p.headshot_kills} hs, accuracy {p.accuracy:.0%} "
            f"({p.shots_hit}/{p.shots_fired}){extra}"
        )
    return "\n".join(lines)


def kill_feed(ctx: MatchContext, round_no: int | None = None) -> str:
    selected = [k for k in ctx.kills if round_no is None or k.round_no == round_no]
    if not selected:
        return f"No kills recorded for round {round_no}."

    lines: list[str] = []
    current_round = None
    first_tick = 0
    for kill in selected:
        if kill.round_no != current_round:
            current_round = kill.round_no
            first_tick = kill.tick
            lines.append(f"--- round {current_round} ---")
        tags = [
            t
            for t, on in (
                ("hs", kill.headshot),
                ("noscope", kill.noscope),
                ("smoke", kill.through_smoke),
                ("wallbang", kill.wallbang),
            )
            if on
        ]
        suffix = f" [{' '.join(tags)}]" if tags else ""
        trade = "" if kill.traded else "  (UNTRADED)"
        elapsed = (kill.tick - first_tick) / TICKRATE
        lines.append(
            f"R{kill.round_no:<2} +{elapsed:5.1f}s  "
            f"{ctx.display(kill.killer_id, kill.killer_name)} > "
            f"{ctx.display(kill.victim_id, kill.victim_name)} ({kill.weapon})"
            f"{suffix}{trade}"
        )
    return "\n".join(lines)


def player_profile(ctx: MatchContext, name: str) -> str:
    """Look up by display name, falling back to in-game name."""
    wanted = name.casefold()
    match = next(
        (
            p
            for p in ctx.stats.players.values()
            if ctx.display(p.steamid, p.name).casefold() == wanted or p.name.casefold() == wanted
        ),
        None,
    )
    if match is None:
        known = ", ".join(ctx.display(p.steamid, p.name) for p in ctx.stats.players.values())
        return f"No player called {name!r}. Players in this match: {known}"

    person = ctx.roster.lookup(match.steamid)
    kills = [k for k in ctx.kills if k.killer_id == match.steamid]
    untraded = [k for k in ctx.kills if k.victim_id == match.steamid and not k.traded]

    lines = [
        ctx.tagged(match.steamid, match.name)
        + (f" — note: {person.note}" if person and person.note else ""),
        f"  {match.kills}K/{match.deaths}D/{match.assists}A, K/D {match.kd:.2f}",
        f"  accuracy {match.accuracy:.1%} ({match.shots_hit}/{match.shots_fired} bullets)",
        f"  headshot kills {match.headshot_kills}"
        + (f" ({match.headshot_kills / match.kills:.0%} of kills)" if match.kills else ""),
        f"  died first in a round {match.first_deaths}x, "
        f"{len(untraded)} of their deaths went untraded",
        f"  teamflashed teammates {match.teamflash_count}x "
        f"for {match.teamflash_seconds:.1f}s total",
        f"  team damage {match.team_damage}hp, teamkills {match.teamkills}",
        f"  odd deaths: knife {match.knife_deaths}, zeus {match.zeus_deaths}, "
        f"world/fall {match.world_deaths}, suicide {match.suicides}",
    ]
    if kills:
        weapons = pd.Series([k.weapon for k in kills]).value_counts()
        lines.append(f"  weapons used for kills: {weapons.to_dict()}")
    return "\n".join(lines)


def suspicion_metrics(ctx: MatchContext) -> str:
    """Leetify-style numbers, for the friend who calls everyone a cheater."""
    lines = ["Aim metrics (high numbers are 'suspicious', low ones are embarrassing):"]
    ranked = sorted(
        ctx.stats.players.values(),
        key=lambda p: (p.headshot_kills / p.kills) if p.kills else 0,
        reverse=True,
    )
    for p in ranked:
        hs_rate = (p.headshot_kills / p.kills) if p.kills else 0.0
        wall = sum(1 for k in ctx.kills if k.killer_id == p.steamid and k.wallbang)
        smoke = sum(1 for k in ctx.kills if k.killer_id == p.steamid and k.through_smoke)
        lines.append(
            f"- {ctx.tagged(p.steamid, p.name)}: headshot rate {hs_rate:.0%}, "
            f"accuracy {p.accuracy:.0%}, wallbang kills {wall}, kills through smoke {smoke}"
        )
    return "\n".join(lines)


def _team_map(ctx: MatchContext) -> dict[int, dict[str, int]]:
    """Per-round steamid -> team. Sides swap at halftime, so this cannot be global.

    Players who neither kill nor die in a round leave no trace that round, so
    their last known team is carried forward.
    """
    per_round: dict[int, dict[str, int]] = {}
    carried: dict[str, int] = {}
    for round_no in sorted({k.round_no for k in ctx.kills}):
        seen: dict[str, int] = {}
        for kill in (k for k in ctx.kills if k.round_no == round_no):
            seen[kill.killer_id] = kill.killer_team
            seen[kill.victim_id] = kill.victim_team
        carried.update(seen)
        per_round[round_no] = dict(carried)
    return per_round


def round_outcomes(ctx: MatchContext) -> str:
    """Per-round shape, including who was left alone against how many."""
    lines: list[str] = []
    teams = _team_map(ctx)
    names = {k.killer_id: k.killer_name for k in ctx.kills}
    names.update({k.victim_id: k.victim_name for k in ctx.kills})

    for round_no in sorted({k.round_no for k in ctx.kills}):
        round_kills = [k for k in ctx.kills if k.round_no == round_no]
        alive: dict[int, set[str]] = {}
        for steamid, team in teams[round_no].items():
            alive.setdefault(team, set()).add(steamid)

        highlights: list[str] = []
        dead: set[str] = set()
        for kill in round_kills:
            dead.add(kill.victim_id)
            for team, members in alive.items():
                survivors = members - dead
                enemies = {m for t, ms in alive.items() if t != team for m in ms} - dead
                # A side never fields more than five. Anything above that means
                # the carried team map is stale (sides swap at halftime), so the
                # count is not trustworthy enough to hand to the model.
                if len(survivors) == 1 and 2 <= len(enemies) <= MAX_TEAM_SIZE:
                    lone = next(iter(survivors))
                    highlights.append(
                        f"{ctx.display(lone, names.get(lone, lone))} left 1v{len(enemies)}"
                    )
                    break
            if highlights:
                break

        counts = Counter(k.killer_id for k in round_kills)
        multi = [
            f"{ctx.display(sid, names.get(sid, sid))} {count}k"
            for sid, count in counts.items()
            if count >= 3
        ]
        summary = ", ".join(filter(None, [", ".join(highlights), ", ".join(multi)]))
        lines.append(
            f"R{round_no}: {len(round_kills)} kills" + (f" — {summary}" if summary else "")
        )
    return "\n".join(lines)


def utility_report(ctx: MatchContext) -> str:
    lines = ["Flash usage (own-team flashes are the embarrassing ones):"]
    for p in sorted(ctx.stats.players.values(), key=lambda p: p.teamflash_seconds, reverse=True):
        if not p.teamflash_count and not p.team_damage:
            continue
        lines.append(
            f"- {ctx.tagged(p.steamid, p.name)}: blinded teammates {p.teamflash_count}x "
            f"for {p.teamflash_seconds:.1f}s, team damage {p.team_damage}hp, "
            f"teamkills {p.teamkills}"
        )
    return "\n".join(lines) if len(lines) > 1 else "Nobody teamflashed or team-damaged."


def advanced_metrics(ctx: MatchContext) -> str:
    """Rating / ADR / KAST / impact, ranked by rating."""
    if ctx.advanced.is_empty:
        return "Advanced metrics are unavailable for this demo."

    lines = [
        "Rating is HLTV-style (1.0 is average). KAST is the share of rounds where",
        "a player got a kill, assist, survived, or was traded. ADR is damage per round.",
        "",
    ]
    ranked = sorted(
        ctx.stats.players.values(),
        key=lambda p: ctx.advanced.rating.get(p.steamid, 0.0),
        reverse=True,
    )
    for p in ranked:
        adv = ctx.advanced.for_player(p.steamid)
        lines.append(
            f"- {ctx.tagged(p.steamid, p.name)}: rating {adv['rating']:.2f}, "
            f"ADR {adv['adr']:.1f}, KAST {adv['kast']:.0f}%, impact {adv['impact']:.2f}"
        )
    return "\n".join(lines)
