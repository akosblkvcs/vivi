"""Everything known about one player: aim, deaths, utility misuse, odd deaths."""

import pandas as pd

from bot.demo.analysis import MatchContext


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

    kills = [k for k in ctx.kills if k.killer_id == match.steamid]
    untraded = [k for k in ctx.kills if k.victim_id == match.steamid and not k.traded]

    lines = [
        ctx.display(match.steamid, match.name),
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
