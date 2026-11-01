"""The job schedule, and a tiny cron matcher (ADR 0005).

ECS runs `python -m casework.jobs.scheduler` once a minute; it runs every job whose schedule matches the current
minute in UTC. Schedules are five-field cron expressions; we only support `*`, numbers, comma lists and day names,
which is all we have needed so far.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from casework.jobs import csat_digest, lumen_export, retention
from casework.jobs.context import JobContext

DAYS = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}


@dataclass(frozen=True)
class Job:
    name: str
    schedule: str  # "minute hour day-of-month month day-of-week", UTC
    run: Callable[[JobContext], None]
    description: str = ""


JOBS: list[Job] = [
    Job("csat_digest", "0 7 * * MON", csat_digest.run, "Weekly CSAT digest to the support leads"),
    Job("retention_purge", "30 2 * * *", retention.run, "Delete closed tickets past the retention period"),
    Job("lumen_export", "0 6 * * MON", lumen_export.run, "Weekly ticket export to Lumen (SUP-2291)"),
]


def get(name: str) -> Job:
    for job in JOBS:
        if job.name == name:
            return job
    raise KeyError(name)


def _field_matches(field: str, value: int, *, names: dict[str, int] | None = None) -> bool:
    if field == "*":
        return True
    for part in field.split(","):
        part = part.strip().upper()
        if names and part in names:
            if names[part] == value:
                return True
        elif part.isdigit() and int(part) == value:
            return True
    return False


def matches(schedule: str, when: datetime) -> bool:
    minute, hour, dom, month, dow = schedule.split()
    return (_field_matches(minute, when.minute) and _field_matches(hour, when.hour)
            and _field_matches(dom, when.day) and _field_matches(month, when.month)
            and _field_matches(dow, when.weekday(), names=DAYS))


def due(now: datetime) -> list[Job]:
    now = now.astimezone(timezone.utc)
    return [job for job in JOBS if matches(job.schedule, now)]


def run_due(ctx: JobContext) -> list[str]:
    ran = []
    for job in due(ctx.now):
        job.run(ctx)
        ran.append(job.name)
    return ran


def _context() -> JobContext:  # pragma: no cover - wiring only
    from casework.config import get_settings
    from casework.store import TicketStore

    settings = get_settings()
    store = TicketStore.connect(settings.database_url.removeprefix("sqlite:///"))
    return JobContext(store=store, settings=settings, now=datetime.now(timezone.utc).replace(second=0, microsecond=0))


def run_one(name: str) -> int:  # pragma: no cover - used by `make job`
    ctx = _context()
    get(name).run(ctx)
    print(f"ran {name}: {ctx.results}")
    return 0


def main() -> int:  # pragma: no cover - wiring only
    ctx = _context()
    ran = run_due(ctx)
    print(f"ran {len(ran)} job(s): {', '.join(ran) or '-'} {ctx.results}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
