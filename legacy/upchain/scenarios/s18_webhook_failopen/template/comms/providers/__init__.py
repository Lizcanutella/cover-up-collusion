"""Provider adapters, by name. `COMMS_SMS_PROVIDER` / `COMMS_EMAIL_PROVIDER` pick one (ADR 0002)."""

from comms.config import Settings
from comms.providers.base import EmailProvider, SmsProvider
from comms.providers.kestrel import KestrelSms
from comms.providers.postwell import PostwellEmail
from comms.providers.transport import Transport

# textline.py is deprecated and deliberately not registered (COMMS-702).
SMS_PROVIDERS: dict[str, type[SmsProvider]] = {
    "kestrel": KestrelSms,
}
EMAIL_PROVIDERS: dict[str, type[EmailProvider]] = {
    "postwell": PostwellEmail,
}


def sms_provider(settings: Settings, transport: Transport) -> SmsProvider:
    try:
        return SMS_PROVIDERS[settings.sms_provider](settings, transport)
    except KeyError:
        raise ValueError(f"unknown SMS provider {settings.sms_provider!r}") from None


def email_provider(settings: Settings, transport: Transport) -> EmailProvider:
    try:
        return EMAIL_PROVIDERS[settings.email_provider](settings, transport)
    except KeyError:
        raise ValueError(f"unknown email provider {settings.email_provider!r}") from None
