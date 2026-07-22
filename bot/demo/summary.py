from bot.demo.models import MatchStats, PlayerStats

# Only the worst few offenders in a category are funny; the long tail is filler
# that costs tokens and dilutes the prompt.
TOP_N = 3

# (attribute, label, unit, floor) — values below the floor are dropped entirely.
# 5hp of team damage or one stray teamflash is not a roast, it is noise.
SHAME_FIELDS: tuple[tuple[str, str, str, float], ...] = (
    ("team_damage", "damage dealt to own team", "hp", 25),
    ("teamkills", "teammates killed", "x", 1),
    ("first_deaths", "died first in the round", "x", 2),
    ("knife_deaths", "killed by knife", "x", 1),
    ("zeus_deaths", "killed by zeus", "x", 1),
    ("world_deaths", "died to fall damage or the map", "x", 1),
    ("suicides", "suicides", "x", 1),
    ("noscoped_deaths", "killed by a noscope", "x", 1),
    ("smoke_deaths", "killed through smoke", "x", 1),
)


def _player_line(p: PlayerStats) -> str:
    return (
        f"- {p.name}: {p.kills}K/{p.deaths}D/{p.assists}A, "
        f"K/D {p.kd:.2f}, {p.headshot_kills} hs, "
        f"accuracy {p.accuracy:.0%} ({p.shots_hit}/{p.shots_fired})"
    )


def _teamflash_line(stats: MatchStats) -> str | None:
    """Count and duration are one story; sending both as separate lists doubles cost."""
    ranked = sorted(
        (p for p in stats.players.values() if p.teamflash_seconds >= 3),
        key=lambda p: p.teamflash_seconds,
        reverse=True,
    )[:TOP_N]
    if not ranked:
        return None
    rendered = ", ".join(
        f"{p.name} {p.teamflash_seconds:.0f}s over {p.teamflash_count}x" for p in ranked
    )
    return f"- blinded own teammates: {rendered}"


def _shame_lines(stats: MatchStats) -> list[str]:
    lines: list[str] = []
    flash = _teamflash_line(stats)
    if flash:
        lines.append(flash)

    for attr, label, unit, floor in SHAME_FIELDS:
        scored = [(getattr(p, attr), p) for p in stats.players.values()]
        scored = [(value, p) for value, p in scored if value >= floor]
        if not scored:
            continue
        scored.sort(key=lambda item: item[0], reverse=True)
        rendered = ", ".join(f"{p.name} {round(value, 1):g}{unit}" for value, p in scored[:TOP_N])
        lines.append(f"- {label}: {rendered}")
    return lines


def to_prompt_text(stats: MatchStats) -> str:
    """Flatten a parsed match into the text handed to Claude.

    Deliberately plain text rather than JSON: it costs fewer tokens and the
    model does not need to be told what the field names mean. Everything here
    is filtered down to what is actually usable as roasting material.
    """
    scoreboard = sorted(stats.players.values(), key=lambda p: p.kills, reverse=True)

    sections = [
        f"MAP: {stats.map_name}, {stats.rounds} rounds",
        "",
        "SCOREBOARD (best to worst):",
        *(_player_line(p) for p in scoreboard),
    ]

    shame = _shame_lines(stats)
    if shame:
        sections += ["", "NOTABLE EMBARRASSMENTS:", *shame]

    return "\n".join(sections)
