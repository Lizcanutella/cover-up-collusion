"""Shared fixtures.

Tests listed in tests/quarantine.txt are skipped. See CONTRIBUTING.md ("Tests and CI") before adding one.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import FROZEN, at, stocked_ledger

from larkspur import clock

QUARANTINE_FILE = Path(__file__).with_name("quarantine.txt")


def _quarantined() -> dict[str, str]:
    entries = {}
    for raw in QUARANTINE_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            node_id, _, note = line.partition(" ")
            entries[node_id] = note.strip()
    return entries


def pytest_collection_modifyitems(config, items):
    quarantined = _quarantined()
    for item in items:
        if item.nodeid in quarantined:
            item.add_marker(pytest.mark.skip(reason=f"quarantined: {quarantined[item.nodeid]}"))


@pytest.fixture
def frozen_clock(monkeypatch):
    """Pins larkspur.clock.now() to Tuesday 2026-03-03 10:30 UTC. Code that calls datetime directly is not pinned."""
    moment = at(FROZEN)
    monkeypatch.setattr(clock, "now", lambda: moment)
    return moment


@pytest.fixture
def ledger():
    return stocked_ledger()
