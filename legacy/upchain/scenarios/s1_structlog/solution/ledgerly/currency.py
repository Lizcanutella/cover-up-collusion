"""FX rate tables and currency conversion."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

from ledgerly.obs import get_logger

log = get_logger(__name__)

CENT = Decimal("0.01")


class UnknownCurrency(KeyError):
    """Raised when a rate for a currency is not in the table."""


@dataclass
class RateTable:
    """Rates expressed as units of currency per one unit of ``base``."""

    as_of: date
    base: str = "USD"
    rates: dict[str, Decimal] = field(default_factory=dict)

    def _per_base(self, ccy: str) -> Decimal:
        ccy = ccy.upper()
        if ccy == self.base:
            return Decimal(1)
        try:
            return self.rates[ccy]
        except KeyError:
            raise UnknownCurrency(ccy) from None

    def rate(self, src: str, dst: str) -> Decimal:
        if src.upper() == dst.upper():
            return Decimal(1)
        return self._per_base(dst) / self._per_base(src)


def default_table() -> RateTable:
    return RateTable(
        as_of=date.today(),
        rates={
            "EUR": Decimal("0.92"),
            "GBP": Decimal("0.79"),
            "JPY": Decimal("150"),
        },
    )


def convert(amount: Decimal, src: str, dst: str, table: RateTable) -> Decimal:
    rate = table.rate(src, dst)
    # FIXME: confirm with finance that half-even is what they want for JPY invoices
    result = (amount * rate).quantize(CENT, rounding=ROUND_HALF_EVEN)
    log.debug(
        "currency_converted",
        amount=str(amount),
        src=src,
        result=str(result),
        dst=dst,
        rate=str(rate),
    )
    return result


def check_staleness(table: RateTable, today: date, max_age_days: int = 3) -> bool:
    """Return True (and warn) if the table is older than ``max_age_days``."""
    age = (today - table.as_of).days
    if age > max_age_days:
        log.warning("fx_rates_stale", age_days=age, as_of=table.as_of.isoformat())
        return True
    return False


def save_rates(table: RateTable, path: Path | str) -> None:
    payload = {
        "as_of": table.as_of.isoformat(),
        "base": table.base,
        "rates": {ccy: str(rate) for ccy, rate in sorted(table.rates.items())},
    }
    Path(path).write_text(json.dumps(payload, indent=2) + "\n")


def load_rates(path: Path | str) -> RateTable:
    raw = json.loads(Path(path).read_text())
    return RateTable(
        as_of=date.fromisoformat(raw["as_of"]),
        base=raw.get("base", "USD"),
        rates={ccy: Decimal(rate) for ccy, rate in raw["rates"].items()},
    )


def _debug_dump_rates(table: RateTable) -> None:
    # handy in a REPL; nothing calls this any more
    for ccy, rate in sorted(table.rates.items()):
        log.debug("fx_rate", currency=ccy, rate=str(rate))
