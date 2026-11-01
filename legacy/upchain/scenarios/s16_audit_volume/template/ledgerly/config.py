"""Runtime settings for ledgerly, read from environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ledgerly.obs import get_logger

log = get_logger(__name__)

_VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}


@dataclass(frozen=True)
class Settings:
    data_path: Path
    log_level: str = "INFO"
    base_currency: str = "USD"
    payments_key: str = ""
    payments_secret: str = ""
    smtp_host: str = "localhost"  # TODO: validate this looks like a hostname
    dry_run: bool = False


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env
    level = env.get("LEDGERLY_LOG_LEVEL", "INFO").upper()
    if level not in _VALID_LEVELS:
        log.warning("invalid_log_level", value=level, fallback="INFO")
        level = "INFO"
    key = env.get("LEDGERLY_PAYMENTS_KEY", "")
    secret = env.get("LEDGERLY_PAYMENTS_SECRET", "")
    if not key or not secret:
        log.warning("payments_credentials_missing", detail="gateway calls will fail")
    settings = Settings(
        data_path=Path(env.get("LEDGERLY_DATA", "ledgerly-data.json")),
        log_level=level,
        base_currency=env.get("LEDGERLY_BASE_CURRENCY", "USD").upper(),
        payments_key=key,
        payments_secret=secret,
        smtp_host=env.get("LEDGERLY_SMTP_HOST", "localhost"),
        dry_run=env.get("LEDGERLY_DRY_RUN", "").lower() in ("1", "true", "yes"),
    )
    log.debug(
        "settings_loaded",
        data_path=str(settings.data_path),
        base_currency=settings.base_currency,
    )
    return settings
