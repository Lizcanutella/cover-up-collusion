"""Settings, read once from the environment.

In production the values come from AWS Secrets Manager through the task definition (see docs/runbook.md). Nothing
here should have a production default.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

# Only for local runs and tests. Production sets CASEWORK_PSEUDONYM_KEY; see ADR 0003 for rotation.
_DEV_PSEUDONYM_KEY = "dev-only-pseudonym-key"


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///casework-dev.db"
    environment: str = "dev"
    support_from_email: str = "help@ostraenergy.co.uk"
    postmark_token: str = ""
    postmark_stream: str = "outbound"
    lumen_api_key: str = ""
    lumen_base_url: str = "https://ingest.lumenhq.com"
    pseudonym_key: bytes = _DEV_PSEUDONYM_KEY.encode()
    retention_days: int = 730  # docs/privacy/retention.md
    csat_digest_to: str = "support-leads@ostraenergy.co.uk"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(f"CASEWORK_{name}", default)


def load_settings() -> Settings:
    defaults = Settings()
    settings = Settings(
        database_url=_env("DATABASE_URL", defaults.database_url),
        environment=_env("ENVIRONMENT", defaults.environment),
        support_from_email=_env("SUPPORT_FROM_EMAIL", defaults.support_from_email),
        postmark_token=_env("POSTMARK_TOKEN"),
        postmark_stream=_env("POSTMARK_STREAM", defaults.postmark_stream),
        lumen_api_key=_env("LUMEN_API_KEY"),
        lumen_base_url=_env("LUMEN_BASE_URL", defaults.lumen_base_url),
        pseudonym_key=_env("PSEUDONYM_KEY", _DEV_PSEUDONYM_KEY).encode(),
        retention_days=int(_env("RETENTION_DAYS", str(defaults.retention_days))),
        csat_digest_to=_env("CSAT_DIGEST_TO", defaults.csat_digest_to),
    )
    if settings.is_production and settings.pseudonym_key == _DEV_PSEUDONYM_KEY.encode():
        raise RuntimeError("CASEWORK_PSEUDONYM_KEY must be set in production")
    return settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
