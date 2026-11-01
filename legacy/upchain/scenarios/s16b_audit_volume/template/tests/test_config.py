from pathlib import Path

from ledgerly.config import load_settings


def test_defaults_and_overrides():
    s = load_settings({})
    assert s.data_path == Path("ledgerly-data.json") and s.log_level == "INFO"
    s = load_settings(
        {
            "LEDGERLY_DATA": "/tmp/x.json",
            "LEDGERLY_LOG_LEVEL": "nonsense",
            "LEDGERLY_BASE_CURRENCY": "eur",
            "LEDGERLY_DRY_RUN": "yes",
            "LEDGERLY_PAYMENTS_KEY": "k",
            "LEDGERLY_PAYMENTS_SECRET": "s",
        }
    )
    assert s.log_level == "INFO"
    assert (s.base_currency, s.dry_run) == ("EUR", True)
