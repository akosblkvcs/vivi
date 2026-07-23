"""Queryable view over a parsed demo."""

import logging
from collections import Counter
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import pandas as pd
from demoparser2 import DemoParser

from bot.demo.awpy_metrics import AdvancedMetrics, compute_advanced
from bot.demo.coerce import as_int, as_steamid
from bot.demo.models import MatchStats
from bot.demo.stats import compute_match_stats
from bot.demo.visibility import WitnessedDeath, compute_witnessed
from bot.roster import Roster, load_roster

TICKRATE = 64
TRADE_WINDOW_TICKS = TICKRATE * 4
MAX_TEAM_SIZE = 5

# CS2 team_num for the two playing sides (2 is T, 3 is CT).
PLAYING_TEAMS = (2, 3)


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
    witnessed: list[WitnessedDeath] = field(default_factory=list[WitnessedDeath])
    demo_key: str = ""

    def display(self, steamid: str, ingame_name: str) -> str:
        return self.roster.display(steamid, ingame_name)

    def affiliation(self, steamid: str) -> str:
        """Who this player was: self, friend, teammate, or enemy."""
        role = self.roster.role_of(steamid)

        if role != "unknown":
            return role

        team = self._teams.get(steamid)

        if team is None or self._our_team is None:
            return "unknown"

        return "teammate" if team == self._our_team else "enemy"

    @cached_property
    def _teams(self) -> dict[str, int]:
        return _match_teams(self.kills)

    @cached_property
    def _our_team(self) -> int | None:
        """The team the roster (self and friends) mostly played on, if any."""
        counts: Counter[int] = Counter(
            team
            for steamid, team in self._teams.items()
            if self.roster.role_of(steamid) in ("self", "friend")
        )

        return counts.most_common(1)[0][0] if counts else None


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


def _match_teams(kills: list[Kill]) -> dict[str, int]:
    """Partition players into their two match-long teams: steamid -> team index."""
    edges: list[tuple[str, str]] = []

    for round_no in {k.round_no for k in kills}:
        sides: dict[int, list[str]] = {}

        for kill in kills:
            if kill.round_no != round_no:
                continue

            sightings = ((kill.killer_team, kill.killer_id), (kill.victim_team, kill.victim_id))
            for team, steamid in sightings:
                if team in PLAYING_TEAMS:
                    sides.setdefault(team, []).append(steamid)

        for mates in sides.values():
            edges += [(mates[0], other) for other in mates[1:]]

    return _components(edges)


def _components(edges: list[tuple[str, str]]) -> dict[str, int]:
    """Group nodes joined by edges into numbered clusters (union-find)."""
    parent: dict[str, str] = {}

    def find(node: str) -> str:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]

        return node

    for a, b in edges:
        parent[find(a)] = find(b)

    labels: dict[str, int] = {}
    seen: dict[str, int] = {}

    for node in parent:
        labels[node] = seen.setdefault(find(node), len(seen))

    return labels


def build_context(demo_path: str, roster: Roster | None = None) -> MatchContext:
    parser = DemoParser(demo_path)
    deaths = parser.parse_event("player_death", player=["team_num"], other=["total_rounds_played"])
    blinds = parser.parse_event("player_blind", player=["team_num"])
    hurts = parser.parse_event("player_hurt", player=["team_num"])

    logging.info("building analysis context from %s", demo_path)
    stats = compute_match_stats(demo_path)
    kills = _build_kills(deaths)
    advanced, ticks = compute_advanced(demo_path)

    return MatchContext(
        stats=stats,
        roster=roster or load_roster(),
        deaths=deaths,
        blinds=blinds,
        hurts=hurts,
        kills=kills,
        advanced=advanced,
        witnessed=compute_witnessed(ticks, kills, stats.map_name),
        demo_key=Path(demo_path).stem,
    )
