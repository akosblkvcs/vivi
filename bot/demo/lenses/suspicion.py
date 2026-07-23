"""Leetify-style aim numbers, for the friend who calls everyone a cheater."""

from bot.demo.analysis import MatchContext


def suspicion_metrics(ctx: MatchContext) -> str:
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
            f"- {ctx.display(p.steamid, p.name)}: headshot rate {hs_rate:.0%}, "
            f"accuracy {p.accuracy:.0%}, wallbang kills {wall}, kills through smoke {smoke}"
        )
    return "\n".join(lines)
