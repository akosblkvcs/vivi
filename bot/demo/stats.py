import pandas as pd
from demoparser2 import DemoParser

from bot.demo.coerce import as_float, as_int, as_steamid
from bot.demo.models import MatchStats, PlayerStats

ZEUS = "taser"
KNIFE_MARKERS = ("knife", "bayonet")

# weapon_fire fires for knives and grenades too, so it cannot be used as a shot
# count on its own. player_death uses bare names ("ak47"); weapon_fire prefixes
# them ("weapon_ak47").
NON_AIM_WEAPONS = frozenset(
    {
        "hegrenade",
        "flashbang",
        "smokegrenade",
        "incgrenade",
        "molotov",
        "decoy",
        "taser",
    }
)


class DemoSchemaError(RuntimeError):
    """A demo did not expose the columns this engine expects."""


def _require(df: pd.DataFrame, event: str, *columns: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise DemoSchemaError(
            f"event {event!r} is missing {missing}; got {sorted(df.columns)}; "
            f"run `python -m bot.cli discover <demo>` and adjust bot/demo/stats.py"
        )


def _is_knife(weapon: object) -> bool:
    w = str(weapon).lower()
    return any(marker in w for marker in KNIFE_MARKERS)


def _is_aim_weapon(weapon: object) -> bool:
    """True for weapons whose trigger pull is a bullet, so accuracy means something."""
    w = str(weapon).lower().removeprefix("weapon_")
    return not _is_knife(w) and w not in NON_AIM_WEAPONS


def _collect_deaths(df: pd.DataFrame, stats: MatchStats) -> None:
    _require(
        df,
        "player_death",
        "user_steamid",
        "user_name",
        "attacker_steamid",
        "weapon",
        "headshot",
    )

    for row in df.itertuples(index=False):
        victim_id = as_steamid(row.user_steamid)
        if victim_id is None:
            continue
        victim = stats.player(victim_id, str(row.user_name))
        victim.deaths += 1

        weapon = str(row.weapon).lower()
        if _is_knife(weapon):
            victim.knife_deaths += 1
        if weapon == ZEUS:
            victim.zeus_deaths += 1

        for flag, attr in (
            ("noscope", "noscoped_deaths"),
            ("penetrated", "wallbang_deaths"),
            ("thrusmoke", "smoke_deaths"),
        ):
            if bool(getattr(row, flag, False)):
                setattr(victim, attr, getattr(victim, attr) + 1)

        attacker_id = as_steamid(row.attacker_steamid)
        if attacker_id is None:
            victim.world_deaths += 1
            continue
        if attacker_id == victim_id:
            victim.suicides += 1
            continue

        attacker = stats.player(attacker_id, str(row.attacker_name))
        attacker.kills += 1
        if bool(row.headshot):
            attacker.headshot_kills += 1
        if _same_team(row):
            attacker.teamkills += 1

        assister_id = as_steamid(getattr(row, "assister_steamid", None))
        if assister_id is not None:
            stats.player(assister_id, str(row.assister_name)).assists += 1


def _same_team(row: object) -> bool:
    """Teams arrive as mixed dtypes (float64 attacker, uint32 victim), NaN for world."""
    attacker = as_int(getattr(row, "attacker_team_num", None), -1)
    victim = as_int(getattr(row, "user_team_num", None), -2)
    return attacker >= 0 and attacker == victim


def _collect_first_deaths(df: pd.DataFrame, stats: MatchStats) -> None:
    if "total_rounds_played" not in df.columns or "tick" not in df.columns:
        return
    opening = df.sort_values("tick").groupby("total_rounds_played", as_index=False).first()
    for row in opening.itertuples(index=False):
        victim_id = as_steamid(row.user_steamid)
        if victim_id is not None:
            stats.player(victim_id, str(row.user_name)).first_deaths += 1


def _collect_blinds(df: pd.DataFrame, stats: MatchStats) -> None:
    _require(df, "player_blind", "attacker_steamid", "user_steamid", "blind_duration")

    for row in df.itertuples(index=False):
        flasher_id = as_steamid(row.attacker_steamid)
        victim_id = as_steamid(row.user_steamid)
        if flasher_id is None or victim_id is None or flasher_id == victim_id:
            continue
        if not _same_team(row):
            continue
        flasher = stats.player(flasher_id, str(row.attacker_name))
        flasher.teamflash_count += 1
        flasher.teamflash_seconds += as_float(row.blind_duration)


def _collect_hurts(df: pd.DataFrame, stats: MatchStats) -> None:
    _require(df, "player_hurt", "attacker_steamid", "user_steamid", "dmg_health")

    for row in df.itertuples(index=False):
        attacker_id = as_steamid(row.attacker_steamid)
        victim_id = as_steamid(row.user_steamid)
        if attacker_id is None or victim_id is None:
            continue
        if attacker_id != victim_id and _same_team(row):
            stats.player(attacker_id, str(row.attacker_name)).team_damage += as_int(row.dmg_health)


def _collect_bullet_hits(df: pd.DataFrame, stats: MatchStats) -> None:
    """bullet_damage is bullet-only, unlike player_hurt which also counts utility."""
    _require(df, "bullet_damage", "attacker_steamid", "victim_steamid")
    for row in df.itertuples(index=False):
        attacker_id = as_steamid(row.attacker_steamid)
        if attacker_id is not None and attacker_id != as_steamid(row.victim_steamid):
            stats.player(attacker_id, str(row.attacker_name)).shots_hit += 1


def _collect_fires(df: pd.DataFrame, stats: MatchStats) -> None:
    _require(df, "weapon_fire", "user_steamid", "weapon")
    for row in df.itertuples(index=False):
        shooter_id = as_steamid(row.user_steamid)
        if shooter_id is not None and _is_aim_weapon(row.weapon):
            stats.player(shooter_id, str(row.user_name)).shots_fired += 1


def compute_match_stats(demo_path: str) -> MatchStats:
    parser = DemoParser(demo_path)
    header = parser.parse_header()

    deaths = parser.parse_event("player_death", player=["team_num"], other=["total_rounds_played"])
    stats = MatchStats(
        map_name=str(header.get("map_name", "unknown")),
        rounds=as_int(deaths["total_rounds_played"].max()) + 1
        if "total_rounds_played" in deaths.columns and not deaths.empty
        else 0,
    )

    _collect_deaths(deaths, stats)
    _collect_first_deaths(deaths, stats)
    _collect_blinds(parser.parse_event("player_blind", player=["team_num"]), stats)
    _collect_hurts(parser.parse_event("player_hurt", player=["team_num"]), stats)
    _collect_bullet_hits(parser.parse_event("bullet_damage"), stats)
    _collect_fires(parser.parse_event("weapon_fire"), stats)

    return stats


def leaderboard(stats: MatchStats, attr: str, limit: int = 3) -> list[PlayerStats]:
    ranked = sorted(stats.players.values(), key=lambda p: getattr(p, attr), reverse=True)
    return [p for p in ranked[:limit] if getattr(p, attr)]
