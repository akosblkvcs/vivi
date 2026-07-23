"""Postgres connection and schema management."""

import logging
from collections.abc import Generator
from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import DictRow, dict_row

from bot import config

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
    metrics   jsonb NOT NULL,
    PRIMARY KEY (demo_key, steamid)
);

CREATE INDEX IF NOT EXISTS player_matches_steamid_idx ON player_matches (steamid);
"""


@contextmanager
def connect() -> Generator[Connection[DictRow] | None]:
    """Yield a connection, or None when no database is configured."""
    url = config.database_url()
    if url is None:
        yield None
        return
    with Connection[DictRow].connect(url, row_factory=dict_row) as conn:
        yield conn


def init_schema() -> bool:
    """Create the tables if they are missing. Safe to call on every startup."""
    try:
        with connect() as conn:
            if conn is None:
                logging.info("DATABASE_URL is not set, match history disabled")
                return False

            conn.execute(DDL)

        logging.info("match history schema is ready")
        return True
    except Exception:
        logging.exception("could not prepare the match history schema")
        return False
