"""FX rate tables and currency conversion."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

logger = logging.getLogger(__name__)

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
    logger.debug("converted %s %s to %s %s at %s", amount, src, result, dst, rate)
    return result


def check_staleness(table: RateTable, today: date, max_age_days: int = 3) -> bool:
    """Return True (and warn) if the table is older than ``max_age_days``."""
    age = (today - table.as_of).days
    if age > max_age_days:
        logger.warning("fx rates are %d days old (as of %s)", age, table.as_of)
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
        print(f"{ccy}: {rate}")
