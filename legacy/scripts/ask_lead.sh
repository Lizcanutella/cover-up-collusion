#!/usr/bin/env bash
# Workers ask the lead (2026-10-26), configs/s1_ask_lead.yaml, Luna as the lead; u1_levels_plan.md E, predictions
# H25. Budget: $0.75 for all of it (user, 2026-10-26), expected about $0.55. Each step has its own --max-cost-usd
# ceiling, and the ledger check refuses anything past the config's pilot_total_usd.
#   smoke: the six cells, n = 2 (not pooled), to check the reports, the second request and the lead's handling.
#   full: the six cells, n = 40 (new runs); the user's open question to the lead on every one.
cd "$(dirname "$0")/.." || exit 1
run() { .venv/bin/python -m upchain "$@"; }
C=configs/s1_ask_lead.yaml
CELLS=excusable_lead_note,excusable_one_asks,excusable_two_ask,breach_lead_note,breach_one_asks,breach_two_ask
case "$1" in
  smoke)
    run run --config $C --arm handle --condition $CELLS --n 2 --model luna --max-cost-usd 0.05 --parallel 6 \
      --out results/ask_lead_smoke --label ask-lead-smoke > results/ask_lead_smoke.log 2>&1
    run reinterview --config $C --from results/ask_lead_smoke --levels open --prime --parallel 6 \
      --max-cost-usd 0.02 --out results/ask_lead_smoke_reinterview --label ask-lead-smoke-reinterview \
      > results/ask_lead_smoke_reinterview.log 2>&1 ;;
  full)
    run run --config $C --arm handle --condition $CELLS --n 40 --model luna --max-cost-usd 0.50 --parallel 6 \
      --seed-start 0 --out results/ask_lead_full --label ask-lead-full > results/ask_lead_full.log 2>&1
    run reinterview --config $C --from results/ask_lead_full --levels open --prime --parallel 6 \
      --max-cost-usd 0.15 --out results/ask_lead_full_reinterview --label ask-lead-full-reinterview \
      > results/ask_lead_full_reinterview.log 2>&1 ;;
  *) echo "usage: $0 smoke|full" >&2; exit 2 ;;
esac
