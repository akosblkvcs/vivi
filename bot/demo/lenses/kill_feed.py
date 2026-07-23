"""Chronological kill-by-kill log, with trade and special-kill tags."""

from bot.demo.analysis import TICKRATE, MatchContext


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
