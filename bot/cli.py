import argparse
from pathlib import Path

from demoparser2 import DemoParser

from bot.demo.stats import compute_match_stats


def discover(demo_path: str) -> None:
    """Dump what this demo actually exposes, so stats.py can be matched to reality."""
    parser = DemoParser(demo_path)

    print("[HEADER]")
    for key, value in parser.parse_header().items():
        print(f"{key}: {value}")

    print("\n[AVAILABLE EVENTS]")
    events = parser.list_game_events()
    print(", ".join(sorted(events)))


def stats(demo_path: str) -> None:
    match_stats = compute_match_stats(demo_path)
    print(f"{match_stats.map_name} — {match_stats.rounds} rounds\n")

    header = f"{'player':<20} {'K':>3} {'D':>3} {'A':>3} {'K/D':>5} {'acc':>5}"
    print(header)
    print("-" * len(header))
    for p in sorted(match_stats.players.values(), key=lambda p: p.kills, reverse=True):
        print(
            f"{p.name[:20]:<20} {p.kills:>3} {p.deaths:>3} {p.assists:>3} "
            f"{p.kd:>5.2f} {p.accuracy:>5.1%}"
        )


def summary(demo_path: str) -> None:
    """Print exactly the text that gets handed to Claude."""
    from bot.demo.summary import to_prompt_text

    print(to_prompt_text(compute_match_stats(demo_path)))


def analyze(demo_path: str) -> None:
    """Run the full analysis and print the recap, exactly as the bot would post it."""
    from dotenv import load_dotenv

    from bot.analyze import generate_analysis
    from bot.demo.analysis import build_context

    load_dotenv()
    print(generate_analysis(build_context(demo_path)))


def witnessed(demo_path: str) -> None:
    """Print the untraded deaths a teammate had line of sight to."""
    from bot.demo.analysis import build_context
    from bot.demo.lenses.witnessed import witnessed_deaths

    print(witnessed_deaths(build_context(demo_path)))


def players(demo_path: str) -> None:
    """List every player with their SteamID and how they relate to the roster.

    Grouped self, friend, teammate, enemy, so it is easy to see who filled the
    party and who was on the other side.
    """
    from bot.demo.analysis import build_context

    ctx = build_context(demo_path)
    order = {"self": 0, "friend": 1, "teammate": 2, "enemy": 3, "unknown": 4}
    ranked = sorted(
        ctx.stats.players.values(),
        key=lambda p: (order.get(ctx.affiliation(p.steamid), 9), p.name.casefold()),
    )
    for p in ranked:
        shown = ctx.display(p.steamid, p.name)
        alias = "" if shown == p.name else f" -> {shown}"
        print(f"{p.name:<16} {p.steamid:<20} [{ctx.affiliation(p.steamid)}]{alias}")


def baselines(demo_path: str) -> None:
    """Print how this match compares to each player's stored history."""
    from dotenv import load_dotenv

    from bot import db
    from bot.demo.analysis import build_context
    from bot.demo.lenses.baseline import baseline_report

    load_dotenv()
    db.init_schema()
    print(baseline_report(build_context(demo_path)))


def demo_path(value: str) -> str:
    """Reject a missing demo before any subcommand runs."""
    if not value:
        raise argparse.ArgumentTypeError("no demo given, set DEMO in .env")
    if not Path(value).is_file():
        raise argparse.ArgumentTypeError(f"no such demo: {value}")
    return value


def main() -> None:
    ap = argparse.ArgumentParser(prog="bot.cli")
    sub = ap.add_subparsers(dest="command", required=True)
    commands = (discover, stats, summary, analyze, witnessed, players, baselines)
    handlers = {fn.__name__: fn for fn in commands}
    for name in handlers:
        sub.add_parser(name).add_argument("demo", type=demo_path)

    args = ap.parse_args()
    handlers[args.command](args.demo)


if __name__ == "__main__":
    main()
