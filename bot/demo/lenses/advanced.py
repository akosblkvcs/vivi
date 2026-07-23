"""Rating / ADR / KAST / impact, ranked by rating."""

from bot.demo.analysis import MatchContext


def advanced_metrics(ctx: MatchContext) -> str:
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
            f"- {ctx.display(p.steamid, p.name)}: rating {adv['rating']:.2f}, "
            f"ADR {adv['adr']:.1f}, KAST {adv['kast']:.0f}%, impact {adv['impact']:.2f}"
        )

    return "\n".join(lines)
