import os
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def debug_mode() -> bool:
    raw = os.environ.get("DEBUG", "").strip().lower()
    return raw == "true"


def dev_id() -> int | None:
    raw = os.environ.get("DEV_DISCORD_ID", "").strip()
    return int(raw) if raw.isdigit() else None


def channel_id() -> int | None:
    raw = os.environ.get("CHANNEL_ID", "").strip()
    return int(raw) if raw.isdigit() else None


def database_url() -> str | None:
    return os.environ.get("DATABASE_URL", "").strip() or None


def demo_resolver() -> str | None:
    """Command that prints a demo URL for a share code (see bot/demo/download.py)."""
    return os.environ.get("DEMO_RESOLVER", "").strip() or None
