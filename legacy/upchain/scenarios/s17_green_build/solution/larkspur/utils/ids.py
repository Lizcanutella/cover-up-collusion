"""Identifiers. Order ids are what customers read out on the phone, so: short, dated, no ambiguous letters."""

from __future__ import annotations

import secrets

from larkspur import clock

_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # no 0/O, 1/I


def new_order_id(warehouse: str) -> str:
    stamp = clock.now().strftime("%y%m%d")
    suffix = "".join(secrets.choice(_ALPHABET) for _ in range(5))
    return f"{warehouse}-{stamp}-{suffix}"


def is_order_id(value: str) -> bool:
    parts = value.split("-")
    return (len(parts) == 3 and len(parts[0]) == 3 and parts[1].isdigit() and len(parts[1]) == 6
            and len(parts[2]) == 5 and all(c in _ALPHABET for c in parts[2]))
