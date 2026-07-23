"""Overall per-player totals, ranked by rating."""

from bot.demo.analysis import MatchContext


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
            f"- {ctx.display(p.steamid, p.name)}: {p.kills}K/{p.deaths}D/{p.assists}A, "
            f"K/D {p.kd:.2f}, {p.headshot_kills} hs, accuracy {p.accuracy:.0%} "
            f"({p.shots_hit}/{p.shots_fired}){extra}"
        )
    return "\n".join(lines)
