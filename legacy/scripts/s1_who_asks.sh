#!/usr/bin/env bash
# S1 section E, who asks (2026-10-25), configs/s1_levels.yaml, Luna, the excusable level; u1_levels_plan.md E,
# predictions H23. Budget: $4.00 for the whole of it (user, 2026-10-25), expected about $0.75. Each step has its own
# --max-cost-usd ceiling, and the ledger check refuses anything past the config's pilot_total_usd.
#   smoke: the five cells, n = 2 (not pooled), to check that the lead's message reaches a model worker_1.
#   full: the five cells, n = 40 (new runs); the open question on every one.
#   pointed: the edit and request questions on every full-run session, each on its own branch.
cd "$(dirname "$0")/.." || exit 1
run() { .venv/bin/python -m upchain "$@"; }
C=configs/s1_levels.yaml
CELLS=excusable_note,informed_note,peer_cover_user,lead_cover_user,both_cover_user
case "${1:-full}" in
  smoke)
    run run --config $C --arm peer --condition $CELLS --n 2 --model luna --max-cost-usd 0.06 --parallel 5 \
      --out results/s1_who_asks_smoke --label s1-who-asks-smoke > results/s1_who_asks_smoke.log 2>&1
    run reinterview --config $C --from results/s1_who_asks_smoke --levels open --prime --parallel 5 \
      --max-cost-usd 0.03 --out results/s1_who_asks_smoke_reinterview --label s1-who-asks-smoke-reinterview \
      > results/s1_who_asks_smoke_reinterview.log 2>&1 ;;
  full)
    run run --config $C --arm peer --condition $CELLS --n 40 --model luna --max-cost-usd 0.70 --parallel 6 \
      --out results/s1_who_asks_full --label s1-who-asks-full > results/s1_who_asks_full.log 2>&1
    run reinterview --config $C --from results/s1_who_asks_full --levels open --prime --parallel 6 \
      --max-cost-usd 0.40 --out results/s1_who_asks_full_reinterview --label s1-who-asks-full-reinterview \
      > results/s1_who_asks_full_reinterview.log 2>&1 ;;
  pointed)  # the user's pointed questions, edit and request, each on its own branch (user, 2026-10-25)
    run reinterview --config $C --from results/s1_who_asks_full --levels edit,request --prime --parallel 6 \
      --max-cost-usd 0.60 --out results/s1_who_asks_full_pointed --label s1-who-asks-full-pointed \
      > results/s1_who_asks_full_pointed.log 2>&1 ;;
esac
