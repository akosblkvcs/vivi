import logging
import os

TRUTHY = {"1", "true", "yes", "on"}
FALSY = {"0", "false", "no", "off"}


def flag(name: str, *, default: bool = False) -> bool:
    """Parse a boolean env var, falling back to `default` on anything unrecognised.

    A value we cannot parse must not silently mean False — for DEBUG that would
    turn a typo into a public post.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in TRUTHY:
        return True
    if value in FALSY:
        return False
    logging.warning("%s=%r is not a boolean; using default %s", name, raw, default)
    return default


def debug_mode() -> bool:
    """When true, roasts go to the owner's DMs instead of the public channel.

    Defaults to True: an unset or misspelled DEBUG should send a roast to one
    person, not publish it to the whole server.
    """
    return flag("DEBUG", default=True)


def owner_id() -> int | None:
    raw = os.environ.get("OWNER_DISCORD_ID", "").strip()
    return int(raw) if raw.isdigit() else None


def channel_id() -> int | None:
    raw = os.environ.get("CHANNEL_ID", "").strip()
    return int(raw) if raw.isdigit() else None
