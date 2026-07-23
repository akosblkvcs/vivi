"""Match history in Postgres, so a player can be compared against themselves.

Within-match z-scores only ever say who was worst *in this lobby*, which with the
same five friends starts to rhyme. A personal baseline is a target that moves
every match: "triple his own average" cannot be recycled, because the average
changed.

The whole module is inert without DATABASE_URL. Nothing here may take a roast
down — history is an enrichment, not a prerequisite.
"""

import hashlib
import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

if TYPE_CHECKING:
    from bot.demo.analysis import MatchContext

# Read in chunks: demos run to a few hundred MB and we only want a stable id.
HASH_CHUNK = 1 << 20

DDL = """
CREATE TABLE IF NOT EXISTS matches (
    demo_key   text PRIMARY KEY,
    map_name   text NOT NULL,
    rounds     integer NOT NULL,
    played_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS player_matches (
    demo_key  text NOT NULL REFERENCES matches (demo_key) ON DELETE CASCADE,
    steamid   text NOT NULL,
    name      text NOT NULL,
    -- Metrics live in jsonb keyed by anomaly.METRICS keys, so adding a metric
    -- needs no migration and old rows simply lack that key.
    metrics   jsonb NOT NULL,
    PRIMARY KEY (demo_key, steamid)
);

CREATE INDEX IF NOT EXISTS player_matches_steamid_idx ON player_matches (steamid);
"""


def database_url() -> str | None:
    return os.environ.get("DATABASE_URL", "").strip() or None


def demo_key(path: str | Path) -> str:
    """Content hash of a demo file.

    Hashing the bytes rather than the filename means the same match downloaded
    twice, or renamed, is still recognised as one match.
    """
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(HASH_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


@contextmanager
def _connect() -> Iterator[psycopg.Connection[dict[str, Any]] | None]:
    url = database_url()
    if url is None:
        yield None
        return
    with psycopg.connect(url, row_factory=dict_row) as conn:
        yield conn


def init_schema() -> bool:
    """Create the tables if they are missing. Safe to call on every startup."""
    try:
        with _connect() as conn:
            if conn is None:
                logging.info("DATABASE_URL is not set — match history is disabled")
                return False
            conn.execute(DDL)
        logging.info("match history schema is ready")
        return True
    except Exception:
        logging.exception("could not prepare the match history schema")
        return False


def record_match(ctx: MatchContext) -> bool:
    """Store this match's per-player metrics.

    Idempotent on demo_key, so re-roasting the same demo does not skew anyone's
    baseline. Rows are refreshed on conflict in case the metric set has grown
    since the match was first seen.
    """
    from bot.demo.anomaly import METRICS

    if not ctx.demo_key:
        return False
    try:
        with _connect() as conn:
            if conn is None:
                return False
            conn.execute(
                "INSERT INTO matches (demo_key, map_name, rounds) VALUES (%s, %s, %s) "
                "ON CONFLICT (demo_key) DO NOTHING",
                (ctx.demo_key, ctx.stats.map_name, ctx.stats.rounds),
            )
            for player in ctx.stats.players.values():
                metrics = {m.key: m.value(player, ctx.advanced) for m in METRICS}
                conn.execute(
                    "INSERT INTO player_matches (demo_key, steamid, name, metrics) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (demo_key, steamid) DO UPDATE "
                    "SET name = EXCLUDED.name, metrics = EXCLUDED.metrics",
                    (ctx.demo_key, player.steamid, player.name, Jsonb(metrics)),
                )
        logging.info("recorded match %s (%d players)", ctx.demo_key[:12], len(ctx.stats.players))
        return True
    except Exception:
        logging.exception("could not record this match; baselines will not include it")
        return False


def past_metrics(steamids: list[str], exclude_key: str) -> dict[str, list[dict[str, float]]]:
    """Every earlier match for these players, newest first.

    The current match is excluded by key rather than by ordering, so it does not
    matter whether it was recorded before or after this call.
    """
    if not steamids:
        return {}
    try:
        with _connect() as conn:
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
        with _connect() as conn:
            if conn is None:
                return 0
            row = conn.execute("SELECT count(*) AS n FROM matches").fetchone()
            return int(row["n"]) if row else 0
    except Exception:
        logging.exception("could not count stored matches")
        return 0
