from datetime import date
from decimal import Decimal

import pytest

from ledgerly.currency import (
    UnknownCurrency,
    check_staleness,
    convert,
    load_rates,
    save_rates,
)
from scripts.backfill_fx_rates import latest_table, read_rows


def test_same_currency_is_identity(rates):
    assert convert(Decimal("12.34"), "USD", "USD", rates) == Decimal("12.34")


def test_eur_to_usd(rates):
    assert convert(Decimal("100"), "EUR", "USD", rates) == Decimal("108.70")


def test_cross_rate_via_base(rates):
    assert convert(Decimal("92"), "EUR", "GBP", rates) == Decimal("79.00")


def test_unknown_currency_raises(rates):
    with pytest.raises(UnknownCurrency):
        convert(Decimal("1"), "USD", "CHF", rates)


def test_staleness(rates):
    assert check_staleness(rates, date(2025, 11, 10)) is False
    assert check_staleness(rates, date(2025, 11, 20)) is True


def test_rates_roundtrip_and_backfill(tmp_path, rates):
    path = tmp_path / "rates.json"
    save_rates(rates, path)
    assert load_rates(path).rates == rates.rates

    csv_path = tmp_path / "rates.csv"
    csv_path.write_text(
        "date,currency,rate\n"
        "2025-10-01,EUR,0.90\n"
        "2025-10-02,EUR,0.91\n"
        "2025-10-02,JPY,149.5\n"
        "not-a-date,GBP,0.8\n"
    )
    table = latest_table(read_rows(str(csv_path)))
    assert table.as_of == date(2025, 10, 2)
    assert table.rates == {"EUR": Decimal("0.91"), "JPY": Decimal("149.5")}
