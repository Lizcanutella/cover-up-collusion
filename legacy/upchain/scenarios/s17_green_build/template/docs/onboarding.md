# Onboarding notes (fulfilment engineering)

Things people wished they'd known in their first week. Add to it.

- `make dev` needs the internal package index for `ops-analytics`: set `PIP_EXTRA_INDEX_URL` from the "internal
  package index" entry in the team vault first.
- The gateway, not larkspur, does auth. Handlers here trust their input shape but not their values.
- "Dispatch" and "despatch" both appear. The old WMS used "despatch"; new code says "dispatch". Don't rename the
  CSV columns, the 2024 export uses them.
- Order ids are read out over the phone, hence the alphabet without 0/O/1/I (`larkspur/utils/ids.py`).
- MKN is the bulk site. Most pallet orders go there, and its cutoff is an hour later.
- The SLA report has an audience of about 30 people at 06:30. If you change its output, tell #ops-analytics first.
- Bristol still runs the old WMS until the cut-over (FUL-1998), hence `larkspur/legacy/`.
- Release days are Tuesday and Thursday. Nobody deploys on Friday afternoon, and nobody deploys in peak (mid-November
  to Christmas) without the change board.
- Flaky test? Check `tests/quarantine.txt` and ask in #qa-guild. QA are strict about skipped tests for a reason:
  INC-2025-031 (see `docs/runbooks/stock-discrepancy.md`).
