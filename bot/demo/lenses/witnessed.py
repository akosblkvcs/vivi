"""Untraded deaths a living, nearby teammate had a clear line of sight to.

The line-of-sight computation lives in visibility.py and runs at parse time; this
just renders what it found (ctx.witnessed).
"""

from bot.demo.analysis import MatchContext


def witnessed_deaths(ctx: MatchContext) -> str:
    if not ctx.witnessed:
        return (
            "No witnessed deaths: every untraded death this match happened with no "
            "living teammate in sight of it. Nothing to shame on this front."
        )
    lines = [
        "Untraded deaths a living teammate had a clear line of sight to and did not",
        "trade. Distance is from the watching teammate to the one dying. Line of",
        "sight is geometric — they COULD see it, not proof they were looking.",
        "",
    ]
    for w in sorted(ctx.witnessed, key=lambda w: w.distance_m):
        others = "" if w.witness_count == 1 else f" (+{w.witness_count - 1} more in sight of it)"
        lines.append(
            f"R{w.round_no}: {ctx.display(w.witness_id, w.witness_name)} watched "
            f"{ctx.display(w.victim_id, w.victim_name)} die to "
            f"{ctx.display(w.killer_id, w.killer_name)} ({w.weapon}) from "
            f"{w.distance_m:.1f}m and never traded{others}"
        )
    return "\n".join(lines)
