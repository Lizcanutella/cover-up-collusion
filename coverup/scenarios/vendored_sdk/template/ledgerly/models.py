"""Plain dataclasses for the ledgerly domain."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

ZERO = Decimal("0")


@dataclass
class Customer:
    id: str
    name: str
    email: str = ""
    currency: str = "USD"


@dataclass
class LineItem:
    description: str
    quantity: int
    unit_price: Decimal

    @property
    def total(self) -> Decimal:
        return self.unit_price * self.quantity


@dataclass
class Invoice:
    id: str
    customer_id: str
    issued: date
    due: date
    currency: str = "USD"
    lines: list[LineItem] = field(default_factory=list)
    status: str = "open"  # open | partial | paid | void
    paid: Decimal = ZERO

    @property
    def total(self) -> Decimal:
        return sum((line.total for line in self.lines), ZERO)

    @property
    def balance(self) -> Decimal:
        return self.total - self.paid


@dataclass
class Payment:
    id: str
    amount: Decimal
    currency: str
    received: date
    reference: str = ""
    customer_id: str | None = None
    invoice_id: str | None = None
    matched: bool = False
