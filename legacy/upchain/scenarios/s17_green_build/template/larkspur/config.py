"""Settings, read once from the environment. Defaults are for local development."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Warehouse codes as used by the WMS and the carriers. MKN opened in 2025; BRS moves to the new WMS on the
# Bristol cut-over (FUL-1998).
WAREHOUSES = ("LDS", "BRS", "MKN")


@dataclass(frozen=True)
class Settings:
    database_url: str = "postgresql://larkspur@localhost:5432/larkspur"
    reservation_ttl_minutes: int = 30
    low_stock_alert_channel: str = "#stock-alerts"
    sla_report_recipients: tuple[str, ...] = ("ops-leads@tarnfield.co.uk",)
    legacy_dispatch_log: str = ""
    warehouses: tuple[str, ...] = field(default=WAREHOUSES)


def load() -> Settings:
    return Settings(
        database_url=os.environ.get("LARKSPUR_DATABASE_URL", Settings.database_url),
        reservation_ttl_minutes=int(os.environ.get("LARKSPUR_RESERVATION_TTL", Settings.reservation_ttl_minutes)),
        legacy_dispatch_log=os.environ.get("LARKSPUR_LEGACY_DISPATCH_LOG", ""),
    )
