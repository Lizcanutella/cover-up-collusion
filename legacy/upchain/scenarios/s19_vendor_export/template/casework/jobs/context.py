"""What a job gets when it runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from casework.config import Settings
from casework.store import TicketStore
from casework.vendors.http import Transport


@dataclass
class JobContext:
    store: TicketStore
    settings: Settings
    now: datetime
    transport: Transport | None = None  # None: real HTTP. Tests pass a RecordingTransport.
    results: dict[str, object] = field(default_factory=dict)  # jobs may leave a summary here for the run log
