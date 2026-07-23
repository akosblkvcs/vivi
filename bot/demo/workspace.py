import logging
import shutil
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from bot.config import DATA_DIR


def demos_dir() -> Path:
    """Scratch space for demos. Transient: nothing here survives a successful parse."""
    path = DATA_DIR / "demos"
    path.mkdir(parents=True, exist_ok=True)
    return path


def free_bytes() -> int:
    return shutil.disk_usage(demos_dir()).free


@contextmanager
def scratch_demo(match_id: str) -> Generator[Path]:
    """Yield a per-match directory, then delete it however the block exits.

    Demos are ~200-250MB uncompressed and we only ever need them long enough to
    parse, so the cleanup runs on the error path too — a failed parse must not
    leave the disk full for the next match.
    """
    workdir = demos_dir() / match_id
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        yield workdir
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        logging.debug("cleaned scratch dir %s", workdir)


def purge_orphans() -> int:
    """Delete scratch dirs left behind by a crash. Call on startup."""
    removed = 0
    for child in demos_dir().iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
            removed += 1
    if removed:
        logging.info("purged %d orphaned demo dir(s)", removed)
    return removed
