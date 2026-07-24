"""Decode a CS2 match share code (CSGO-xxxxx-...) into its match identifiers.

A share code is a base-57 encoding of 144 bits: a 64-bit match id, a 64-bit
outcome (reservation) id, and a 16-bit TV token. Those three are what a resolver
needs to ask Valve for the demo. This is pure arithmetic — no Steam needed.
"""

from dataclasses import dataclass

# Valve's custom alphabet; note the missing I/l/1/0 to avoid look-alikes.
_DICTIONARY = "ABCDEFGHJKLMNOPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
_BASE = len(_DICTIONARY)
_CODE_LEN = 25
_MASK64 = (1 << 64) - 1
_MASK16 = (1 << 16) - 1


class ShareCodeError(ValueError):
    """The string is not a valid match share code."""


@dataclass(frozen=True)
class ShareCode:
    match_id: int
    outcome_id: int
    token: int


def _clean(code: str) -> str:
    cleaned = code.strip().removeprefix("CSGO-").replace("-", "")
    if len(cleaned) != _CODE_LEN or any(c not in _DICTIONARY for c in cleaned):
        raise ShareCodeError(f"not a valid match share code: {code!r}")
    return cleaned


def decode(code: str) -> ShareCode:
    cleaned = _clean(code)
    big = 0
    for char in reversed(cleaned):
        big = big * _BASE + _DICTIONARY.index(char)
    return ShareCode(
        match_id=big & _MASK64,
        outcome_id=(big >> 64) & _MASK64,
        token=(big >> 128) & _MASK16,
    )


def encode(share: ShareCode) -> str:
    big = (share.match_id & _MASK64) | ((share.outcome_id & _MASK64) << 64) | (
        (share.token & _MASK16) << 128
    )
    digits = []
    for _ in range(_CODE_LEN):
        big, remainder = divmod(big, _BASE)
        digits.append(_DICTIONARY[remainder])
    body = "".join(digits)
    groups = "-".join(body[i : i + 5] for i in range(0, _CODE_LEN, 5))
    return f"CSGO-{groups}"
