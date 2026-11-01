"""Runtime settings for ledgerly, read from environment variables."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

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
        logger.warning("invalid LEDGERLY_LOG_LEVEL %r, falling back to INFO", level)
        level = "INFO"
    key = env.get("LEDGERLY_PAYMENTS_KEY", "")
    secret = env.get("LEDGERLY_PAYMENTS_SECRET", "")
    if not key or not secret:
        print("[config] payments credentials not set; gateway calls will fail", file=sys.stderr)
    settings = Settings(
        data_path=Path(env.get("LEDGERLY_DATA", "ledgerly-data.json")),
        log_level=level,
        base_currency=env.get("LEDGERLY_BASE_CURRENCY", "USD").upper(),
        payments_key=key,
        payments_secret=secret,
        smtp_host=env.get("LEDGERLY_SMTP_HOST", "localhost"),
        dry_run=env.get("LEDGERLY_DRY_RUN", "").lower() in ("1", "true", "yes"),
    )
    logger.debug("settings loaded: data_path=%s base=%s", settings.data_path, settings.base_currency)
    return settings
