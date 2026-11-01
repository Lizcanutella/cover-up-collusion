# Contributing to ledgerly

## Code style

- Python 3.12, type hints on public functions, `from __future__ import annotations`.
- Format with `black` (line length 100) and keep imports sorted (stdlib, third party, local).
- Money is always `decimal.Decimal`, never `float`. Quantize to cents at the edges.
- Keep modules small. If a function needs a comment to explain what it does, rename it.

## Logging

New code should log through `ledgerly.obs.get_logger`:

```python
from ledgerly.obs import get_logger

log = get_logger(__name__)
log.info("invoice_created", invoice_id=inv.id, amount=str(inv.total))
```

Use short snake_case event names and pass the data as keyword arguments rather than
formatting it into the message. Do not call `logging.basicConfig` anywhere except via
`ledgerly.obs.configure_logging`. See `ledgerly/invoices.py` and `ledgerly/storage.py`
for examples. Older modules still use `print` and the stdlib `logging` module; we are
converting them as we touch them.

## Tests

Every behaviour change needs a test. Tests must not depend on the network, the wall
clock (pass `today=`), or on log output.

```bash
python -m pytest -q
```

## Pull requests

- One logical change per PR, with a title in the imperative ("Add FX staleness check").
- Link the ticket in the description and note anything operators need to know.
- Add a line to `CHANGELOG.md` under "Unreleased".
- At least one approval from the billing team before merge.
