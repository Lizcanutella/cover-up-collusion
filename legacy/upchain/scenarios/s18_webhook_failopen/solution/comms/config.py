"""Runtime settings. In production every value comes from a COMMS_* environment variable (see README.md)."""

import os
from dataclasses import dataclass, field

# One signing secret per provider: COMMS_WEBHOOK_SECRET_KESTREL, COMMS_WEBHOOK_SECRET_POSTWELL, ...
WEBHOOK_SECRET_PREFIX = "COMMS_WEBHOOK_SECRET_"


@dataclass(frozen=True)
class Settings:
    environment: str = "development"
    public_base_url: str = "http://localhost:8080"
    sms_provider: str = "kestrel"
    email_provider: str = "postwell"
    sender_id: str = "FERNWAY"
    email_from: str = "Fernway <no-reply@mail.fernway.io>"
    kestrel_api_key: str = ""
    kestrel_base_url: str = "https://api.kestrel-sms.com/v2"
    postwell_api_key: str = ""
    postwell_base_url: str = "https://api.postwell.io/v1"
    lyra_api_key: str = ""
    lyra_account_id: str = ""
    lyra_base_url: str = "https://api.lyra.dev/v3"
    webhook_secrets: dict[str, str] = field(default_factory=dict)  # provider name -> signing secret
    webhook_tolerance_seconds: int = 300
    sms_per_minute: int = 30  # per recipient; see comms/ratelimit.py
    max_send_attempts: int = 4
    http_timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls, environ=None) -> "Settings":
        env = os.environ if environ is None else environ
        secrets = {key[len(WEBHOOK_SECRET_PREFIX):].lower(): value for key, value in env.items()
                   if key.startswith(WEBHOOK_SECRET_PREFIX) and value}
        defaults = cls()
        return cls(
            environment=env.get("COMMS_ENV", defaults.environment),
            public_base_url=env.get("COMMS_PUBLIC_BASE_URL", defaults.public_base_url),
            sms_provider=env.get("COMMS_SMS_PROVIDER", defaults.sms_provider),
            email_provider=env.get("COMMS_EMAIL_PROVIDER", defaults.email_provider),
            sender_id=env.get("COMMS_SENDER_ID", defaults.sender_id),
            email_from=env.get("COMMS_EMAIL_FROM", defaults.email_from),
            kestrel_api_key=env.get("COMMS_KESTREL_API_KEY", ""),
            kestrel_base_url=env.get("COMMS_KESTREL_BASE_URL", defaults.kestrel_base_url),
            postwell_api_key=env.get("COMMS_POSTWELL_API_KEY", ""),
            postwell_base_url=env.get("COMMS_POSTWELL_BASE_URL", defaults.postwell_base_url),
            lyra_api_key=env.get("COMMS_LYRA_API_KEY", ""),
            lyra_account_id=env.get("COMMS_LYRA_ACCOUNT_ID", ""),
            lyra_base_url=env.get("COMMS_LYRA_BASE_URL", defaults.lyra_base_url),
            webhook_secrets=secrets,
            webhook_tolerance_seconds=int(env.get("COMMS_WEBHOOK_TOLERANCE_SECONDS", defaults.webhook_tolerance_seconds)),
            sms_per_minute=int(env.get("COMMS_SMS_PER_MINUTE", defaults.sms_per_minute)),
            max_send_attempts=int(env.get("COMMS_MAX_SEND_ATTEMPTS", defaults.max_send_attempts)),
            # TODO(rahul): COMMS_HTTP_TIMEOUT_SECONDS isn't set in any deploy yet; drop it if nobody needs it by Q1.
            http_timeout_seconds=float(env.get("COMMS_HTTP_TIMEOUT_SECONDS", defaults.http_timeout_seconds)),
        )
