"""Pack sizes. Suppliers sell in cases; we count in units."""

from __future__ import annotations


def round_up_to_case(units: int, case_size: int) -> int:
    if case_size <= 0:
        raise ValueError("case_size must be positive")
    return -(-units // case_size) * case_size


def cases(units: int, case_size: int) -> int:
    return round_up_to_case(units, case_size) // case_size
