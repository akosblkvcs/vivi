import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from bot.config import DATA_DIR

Role = Literal["self", "friend", "unknown"]

ROSTER_PATH = DATA_DIR / "friends.json"


@dataclass(frozen=True)
class Person:
    """Someone the bot knows."""

    steamids: tuple[str, ...]
    name: str
    role: Role


class Roster:
    def __init__(self, people: list[Person]) -> None:
        self._by_id: dict[str, Person] = {}
        for person in people:
            for steamid in person.steamids:
                if steamid in self._by_id:
                    logging.warning("steamid %s listed twice in roster", steamid)
                self._by_id[steamid] = person

    def lookup(self, steamid: str) -> Person | None:
        return self._by_id.get(steamid)

    def role_of(self, steamid: str) -> Role:
        person = self._by_id.get(steamid)
        return person.role if person else "unknown"

    def display(self, steamid: str, ingame_name: str) -> str:
        """What the bot should call this player. Strangers keep their in-game name."""
        person = self._by_id.get(steamid)
        return person.name if person else ingame_name

    def __len__(self) -> int:
        return len({p.name for p in self._by_id.values()})


def _steamids(entry: dict[str, object]) -> tuple[str, ...]:
    """Accept either a single `steamid` or a list of `steamids`."""
    raw = entry.get("steamids") or entry.get("steamid")

    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, list):
        return tuple(str(item) for item in cast(list[object], raw))

    return ()


def load_roster(path: Path | None = None) -> Roster:
    target = path or ROSTER_PATH

    if not target.is_file():
        logging.warning("no roster at %s, treating everyone as a stranger", target)
        return Roster([])

    raw = json.loads(target.read_text(encoding="utf-8"))
    people: list[Person] = []

    for entry in raw["players"]:
        steamids = _steamids(entry)
        if not steamids:
            # Without an id there is nothing to match on, so the entry is inert.
            logging.warning("roster entry %r has no steamid and will be ignored", entry.get("name"))
            continue
        role = entry.get("role", "friend")
        if role not in ("self", "friend"):
            logging.warning("roster entry %r has unknown role %r, treating as friend", entry, role)
            role = "friend"
        people.append(
            Person(
                steamids=steamids,
                name=entry["name"],
                role=role,
            )
        )

    logging.info(
        "roster loaded: %d people, %d steamids", len(people), sum(len(p.steamids) for p in people)
    )
    return Roster(people)
