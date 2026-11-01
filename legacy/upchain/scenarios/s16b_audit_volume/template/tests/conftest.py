from datetime import date
from decimal import Decimal

import pytest

from ledgerly.currency import RateTable
from ledgerly.models import Customer, LineItem
from ledgerly.storage import Storage

TODAY = date(2025, 11, 10)


def lines(*prices: str) -> list[LineItem]:
    return [LineItem(f"item {n}", 1, Decimal(p)) for n, p in enumerate(prices, start=1)]


@pytest.fixture
def rates() -> RateTable:
    return RateTable(
        as_of=date(2025, 11, 9),
        rates={"EUR": Decimal("0.92"), "GBP": Decimal("0.79"), "JPY": Decimal("150")},
    )


@pytest.fixture
def store() -> Storage:
    s = Storage()
    s.add_customer(Customer("C001", "Acme Inc", "ap@acme.example", "USD"))
    s.add_customer(Customer("C002", "Borealis GmbH", "kasse@borealis.example", "EUR"))
    s.add_customer(Customer("C003", "No Email Ltd", "", "GBP"))
    return s
