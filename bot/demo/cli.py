import argparse

from demoparser2 import DemoParser

from bot.demo.stats import compute_match_stats, leaderboard

INTERESTING_EVENTS = ("player_death", "player_blind", "player_hurt", "weapon_fire")


def discover(demo_path: str) -> None:
    """Dump what this demo actually exposes, so stats.py can be matched to reality."""
    parser = DemoParser(demo_path)

    print("== header ==")
    for key, value in parser.parse_header().items():
        print(f"  {key}: {value}")

    print("\n== available events ==")
    events = parser.list_game_events()
    print("  " + ", ".join(sorted(events)))

    for event in INTERESTING_EVENTS:
        if event not in events:
            print(f"\n== {event} == NOT PRESENT in this demo")
            continue
        extras = {"player": ["team_num"]} if event != "weapon_fire" else {}
        if event == "player_death":
            extras["other"] = ["total_rounds_played"]
        df = parser.parse_event(event, **extras)
        print(f"\n== {event} == {len(df)} rows")
        print("  columns:", sorted(df.columns))
        if not df.empty:
            print("  first row:")
            for column, cell in df.iloc[0].items():
                print(f"    {column} = {cell!r}")


def show_stats(demo_path: str) -> None:
    stats = compute_match_stats(demo_path)
    print(f"{stats.map_name} — {stats.rounds} rounds, {len(stats.players)} players\n")

    header = f"{'player':<20} {'K':>3} {'D':>3} {'A':>3} {'K/D':>5} {'acc':>5}"
    print(header)
    print("-" * len(header))
    for p in sorted(stats.players.values(), key=lambda p: p.kills, reverse=True):
        print(
            f"{p.name[:20]:<20} {p.kills:>3} {p.deaths:>3} {p.assists:>3} "
            f"{p.kd:>5.2f} {p.accuracy:>5.1%}"
        )

    print("\n== shame board ==")
    boards = (
        ("teamflash_seconds", "vakította a csapatot (mp)"),
        ("team_damage", "team damage"),
        ("first_deaths", "halt meg elsőként"),
        ("knife_deaths", "késelve"),
        ("zeus_deaths", "zeusolva"),
        ("world_deaths", "leesett/world"),
    )
    for attr, label in boards:
        top = leaderboard(stats, attr)
        if not top:
            continue
        entries = ", ".join(f"{p.name} ({getattr(p, attr):g})" for p in top)
        print(f"  {label}: {entries}")


def show_summary(demo_path: str) -> None:
    """Print exactly the text that gets handed to Claude."""
    from bot.demo.summary import to_prompt_text

    print(to_prompt_text(compute_match_stats(demo_path)))


def show_roast(demo_path: str) -> None:
    from dotenv import load_dotenv

    from bot.demo.analysis import build_context
    from bot.roast import generate_roast

    load_dotenv()
    print(generate_roast(build_context(demo_path)))


def show_players(demo_path: str) -> None:
    """List every player with their SteamID and how the roster classifies them."""
    from bot.demo.analysis import build_context

    ctx = build_context(demo_path)
    for p in sorted(ctx.stats.players.values(), key=lambda p: p.name.casefold()):
        shown = ctx.display(p.steamid, p.name)
        role = ctx.roster.role_of(p.steamid)
        alias = "" if shown == p.name else f"  -> {shown}"
        print(f"{p.name:<16} {p.steamid:<20} [{role}]{alias}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="bot.demo.cli")
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("stats", "discover", "summary", "roast", "players"):
        sub.add_parser(name).add_argument("demo")

    args = ap.parse_args()
    handlers = {
        "discover": discover,
        "stats": show_stats,
        "summary": show_summary,
        "roast": show_roast,
        "players": show_players,
    }
    handlers[args.command](args.demo)


if __name__ == "__main__":
    main()
