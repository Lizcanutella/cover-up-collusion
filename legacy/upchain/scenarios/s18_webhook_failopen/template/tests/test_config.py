from comms.config import Settings


def test_from_env_reads_per_provider_webhook_secrets():
    settings = Settings.from_env({
        "COMMS_ENV": "production",
        "COMMS_WEBHOOK_SECRET_KESTREL": "a",
        "COMMS_WEBHOOK_SECRET_POSTWELL": "b",
        "COMMS_WEBHOOK_SECRET_UNUSED": "",
    })
    assert settings.environment == "production"
    assert settings.webhook_secrets == {"kestrel": "a", "postwell": "b"}


def test_defaults():
    settings = Settings.from_env({})
    assert settings.sms_provider == "kestrel" and settings.webhook_tolerance_seconds == 300
