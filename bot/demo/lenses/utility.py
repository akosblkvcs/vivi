"""Who blinded and damaged their own team, and how badly."""

from bot.demo.analysis import MatchContext


def utility_report(ctx: MatchContext) -> str:
    lines = ["Flash usage (own-team flashes are the embarrassing ones):"]
    for p in sorted(ctx.stats.players.values(), key=lambda p: p.teamflash_seconds, reverse=True):
        if not p.teamflash_count and not p.team_damage:
            continue
        lines.append(
            f"- {ctx.display(p.steamid, p.name)}: blinded teammates {p.teamflash_count}x "
            f"for {p.teamflash_seconds:.1f}s, team damage {p.team_damage}hp, "
            f"teamkills {p.teamkills}"
        )
    return "\n".join(lines) if len(lines) > 1 else "Nobody teamflashed or team-damaged."
