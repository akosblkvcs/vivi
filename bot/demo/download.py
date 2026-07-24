"""Fetch a match demo from its share code.

The only step that needs Steam is turning a share code into a demo URL: that
requires the CS Game Coordinator, i.e. a logged-in account. Rather than bake that
fragile protocol in here, it is delegated to an operator-configured command
(DEMO_RESOLVER) that prints the demo URL for a share code. Everything else — the
decode, the download, the bz2 decompress — is plain and lives here.
"""

import bz2
import logging
import shlex
import subprocess
from pathlib import Path

import requests

from bot import config
from bot.demo.sharecode import decode

_RESOLVER_TIMEOUT = 120
_FETCH_TIMEOUT = 300
_CHUNK = 1 << 16


class DownloadError(RuntimeError):
    """The demo could not be fetched."""


def download_demo(share_code: str, dest_dir: Path) -> Path:
    """Resolve, download and decompress the demo for a share code.

    Returns the path to the ready-to-parse .dem. Raises ShareCodeError for a bad
    code and DownloadError for anything that goes wrong fetching it.
    """
    share = decode(share_code)  # validates the code and names the file
    url = _demo_url(share_code)
    dest = dest_dir / f"{share.match_id}.dem"
    logging.info("downloading demo %s", share.match_id)
    _fetch(url, dest)
    return dest


def _demo_url(share_code: str) -> str:
    resolver = config.demo_resolver()
    if not resolver:
        raise DownloadError(
            "no demo resolver configured; set DEMO_RESOLVER to a command that "
            "prints the demo URL for a share code"
        )
    try:
        # DEMO_RESOLVER is operator-supplied and the share code is validated, so
        # this is not shell-injectable; args are passed as a list, no shell.
        result = subprocess.run(  # noqa: S603
            [*shlex.split(resolver), share_code],
            capture_output=True,
            text=True,
            timeout=_RESOLVER_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise DownloadError(f"demo resolver failed to run: {exc}") from exc
    if result.returncode != 0:
        raise DownloadError(f"demo resolver failed: {result.stderr.strip() or result.returncode}")
    url = result.stdout.strip()
    if not url.startswith(("http://", "https://")):
        raise DownloadError(f"demo resolver returned no URL: {url!r}")
    return url


def _fetch(url: str, dest: Path) -> None:
    decompressor = bz2.BZ2Decompressor() if url.endswith(".bz2") else None
    try:
        with requests.get(url, stream=True, timeout=_FETCH_TIMEOUT) as response:
            response.raise_for_status()
            with dest.open("wb") as out:
                for chunk in response.iter_content(_CHUNK):
                    out.write(decompressor.decompress(chunk) if decompressor else chunk)
    except (requests.RequestException, OSError) as exc:
        dest.unlink(missing_ok=True)
        raise DownloadError(f"could not download demo: {exc}") from exc
