"""Per-round shape: multi-kills and who was left alone against how many."""

from collections import Counter

from bot.demo.analysis import MAX_TEAM_SIZE, MatchContext


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
