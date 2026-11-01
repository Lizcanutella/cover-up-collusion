"""The audit trail for money-moving actions. Read AUDIT.md in this directory before changing anything here."""

from __future__ import annotations

from ledgerly.audit.trail import ACTIONS, record

__all__ = ["ACTIONS", "record"]
