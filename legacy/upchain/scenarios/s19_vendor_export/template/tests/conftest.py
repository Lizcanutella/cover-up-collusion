from datetime import datetime, timezone
from pathlib import Path

import pytest

from casework.config import Settings
from casework.store import TicketStore

FIXTURE = Path(__file__).parent / "fixtures" / "tickets.json"

# A Monday, just after the weekly jobs' slot. The fixture's tickets run from 8 Sep to 18 Oct 2026.
NOW = datetime(2026, 10, 19, 6, 0, tzinfo=timezone.utc)


@pytest.fixture
def store() -> TicketStore:
    s = TicketStore.connect()
    s.load_json(FIXTURE)
    return s


@pytest.fixture
def settings() -> Settings:
    return Settings(postmark_token="pm-test-token", lumen_api_key="lk_test_123", pseudonym_key=b"test-key")


@pytest.fixture
def now() -> datetime:
    return NOW
