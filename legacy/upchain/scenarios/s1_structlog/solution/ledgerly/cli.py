"""Command line entry point: ``python -m ledgerly.cli``."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from decimal import Decimal

from ledgerly.config import load_settings
from ledgerly.currency import default_table, load_rates
from ledgerly.invoices import create_invoice
from ledgerly.jobs.nightly import run_nightly
from ledgerly.models import LineItem
from ledgerly.notify import Notifier
from ledgerly.obs import configure_logging, get_logger
from ledgerly.reconcile import reconcile
from ledgerly.storage import Storage

log = get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ledgerly")
    parser.add_argument("--data", help="path of the JSON data file")
    parser.add_argument("--rates", help="path of an FX rates JSON file")
    parser.add_argument("--log-level", default="INFO")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="list invoices")
    create = sub.add_parser("create", help="create an invoice")
    create.add_argument("customer_id")
    create.add_argument("--line", action="append", required=True, help="description:qty:unit_price")
    sub.add_parser("reconcile", help="match pending payments to invoices")
    sub.add_parser("nightly", help="run the nightly job")
    return parser


def _emit(text: str) -> None:
    sys.stdout.write(text + "\n")


def _parse_line(spec: str) -> LineItem:
    description, qty, price = spec.rsplit(":", 2)
    return LineItem(description, int(qty), Decimal(price))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings()
    configure_logging(level=args.log_level)
    data_path = args.data or settings.data_path
    log.info("using_data_file", path=str(data_path))
    store = Storage(data_path)
    rates = load_rates(args.rates) if args.rates else default_table()
    log.debug("running_command", command=args.command)

    try:
        if args.command == "list":
            for inv in store.list_invoices():
                _emit(f"{inv.id}\t{inv.customer_id}\t{inv.total} {inv.currency}\t{inv.status}")
        elif args.command == "create":
            invoice = create_invoice(store, args.customer_id, [_parse_line(s) for s in args.line])
            store.save()
            _emit(invoice.id)
        elif args.command == "reconcile":
            result = reconcile(store, rates)
            store.save()
            _emit(f"matched={len(result.matched)} unmatched={len(result.unmatched)}")
        elif args.command == "nightly":
            notifier = Notifier(settings.smtp_host, dry_run=settings.dry_run)
            summary = run_nightly(store, rates, notifier, today=date.today())
            _emit(str(summary))
    except KeyError as exc:
        log.error("not_found", key=str(exc))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
