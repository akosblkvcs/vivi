"""Match history saver in Postgres."""

import logging
from typing import TYPE_CHECKING

from psycopg.types.json import Jsonb

from bot.db import connect

if TYPE_CHECKING:
    from bot.demo.analysis import MatchContext


def record_match(ctx: MatchContext) -> bool:
    """Store this match's per-player metrics for the roster."""
    from bot.demo.metrics import METRICS

    if not ctx.demo_key:
        return False
    try:
        with connect() as conn:
            if conn is None:
                return False

            known = [
                p for p in ctx.stats.players.values() if ctx.roster.role_of(p.steamid) != "unknown"
            ]

            if not known:
                logging.info("match %s has no roster players; nothing stored", ctx.demo_key)
                return False

            conn.execute(
                "INSERT INTO matches (demo_key, map_name, rounds) VALUES (%s, %s, %s) "
                "ON CONFLICT (demo_key) DO NOTHING",
                (ctx.demo_key, ctx.stats.map_name, ctx.stats.rounds),
            )

            for player in known:
                metrics = {m.key: m.value(player, ctx.advanced) for m in METRICS}
                conn.execute(
                    "INSERT INTO player_matches (demo_key, steamid, name, metrics) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (demo_key, steamid) DO UPDATE "
                    "SET name = EXCLUDED.name, metrics = EXCLUDED.metrics",
                    (ctx.demo_key, player.steamid, player.name, Jsonb(metrics)),
                )

        logging.info("recorded match %s (%d roster players)", ctx.demo_key, len(known))
        return True
    except Exception:
        logging.exception("could not record this match")
        return False


def past_metrics(steamids: list[str], exclude_key: str) -> dict[str, list[dict[str, float]]]:
    """Every earlier match for these players, newest first."""
    if not steamids:
        return {}
    try:
        with connect() as conn:
            if conn is None:
                return {}
            rows = conn.execute(
                "SELECT pm.steamid, pm.metrics FROM player_matches pm "
                "JOIN matches m ON m.demo_key = pm.demo_key "
                "WHERE pm.steamid = ANY(%s) AND pm.demo_key <> %s "
                "ORDER BY m.played_at DESC",
                (steamids, exclude_key),
            ).fetchall()
    except Exception:
        logging.exception("could not read match history")
        return {}

    history: dict[str, list[dict[str, float]]] = {}
    for row in rows:
        history.setdefault(str(row["steamid"]), []).append(row["metrics"])

    return history


def match_count() -> int:
    try:
        with connect() as conn:
            if conn is None:
                return 0

            row = conn.execute("SELECT count(*) AS n FROM matches").fetchone()

            return int(row["n"]) if row else 0
    except Exception:
        logging.exception("could not count stored matches")
        return 0
