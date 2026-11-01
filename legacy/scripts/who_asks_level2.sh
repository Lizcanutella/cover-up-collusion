#!/usr/bin/env bash
# Section E, who asks, at a second place (2026-10-25): S18 excusable (configs/s18_pilot.yaml) and S1 breach
# (configs/s1_levels.yaml), Luna; u1_levels_plan.md E, predictions H24. Budget: the rest of the $4.00 the user approved
# for section E (user, 2026-10-25), expected about $1.85. Each step has its own --max-cost-usd ceiling, and the ledger
# check refuses anything past the configs' pilot_total_usd.
#   s18-smoke: S18's five cells, n = 2 (not pooled), to check S18's lead message and report.
#   s18 / s1-breach: the five cells, n = 40 (new runs); the open question on every one.
#   pointed: the edit and request questions on every s18 and s1-breach session, each on its own branch (budget $1.00,
#   user 2026-10-26; predictions in H24's addendum).
cd "$(dirname "$0")/.." || exit 1
run() { .venv/bin/python -m upchain "$@"; }
S18=configs/s18_pilot.yaml
S1=configs/s1_levels.yaml
S18_CELLS=excusable_note,excusable_informed_note,excusable_peer_cover_user,excusable_lead_cover_user,excusable_both_cover_user
S1_CELLS=breach_note,breach_informed_note,breach_peer_cover_user,breach_lead_cover_user,breach_both_cover_user
case "$1" in
  s18-smoke)
    run run --config $S18 --arm peer --condition $S18_CELLS --n 2 --model luna --max-cost-usd 0.06 --parallel 5 \
      --out results/s18_who_asks_smoke --label s18-who-asks-smoke > results/s18_who_asks_smoke.log 2>&1
    run reinterview --config $S18 --from results/s18_who_asks_smoke --levels open --prime --parallel 5 \
      --max-cost-usd 0.03 --out results/s18_who_asks_smoke_reinterview --label s18-who-asks-smoke-reinterview \
      > results/s18_who_asks_smoke_reinterview.log 2>&1 ;;
  s18)
    run run --config $S18 --arm peer --condition $S18_CELLS --n 40 --model luna --max-cost-usd 0.95 --parallel 6 \
      --out results/s18_who_asks_full --label s18-who-asks-full > results/s18_who_asks_full.log 2>&1
    run reinterview --config $S18 --from results/s18_who_asks_full --levels open --prime --parallel 6 \
      --max-cost-usd 0.40 --out results/s18_who_asks_full_reinterview --label s18-who-asks-full-reinterview \
      > results/s18_who_asks_full_reinterview.log 2>&1 ;;
  s1-breach)
    run run --config $S1 --arm peer --condition $S1_CELLS --n 40 --model luna --max-cost-usd 0.60 --parallel 6 \
      --out results/s1_breach_who_asks_full --label s1-breach-who-asks-full > results/s1_breach_who_asks_full.log 2>&1
    run reinterview --config $S1 --from results/s1_breach_who_asks_full --levels open --prime --parallel 6 \
      --max-cost-usd 0.30 --out results/s1_breach_who_asks_full_reinterview --label s1-breach-who-asks-full-reinterview \
      > results/s1_breach_who_asks_full_reinterview.log 2>&1 ;;
  pointed)
    run reinterview --config $S18 --from results/s18_who_asks_full --levels edit,request --prime --parallel 6 \
      --max-cost-usd 0.50 --out results/s18_who_asks_full_pointed --label s18-who-asks-full-pointed \
      > results/s18_who_asks_full_pointed.log 2>&1
    run reinterview --config $S1 --from results/s1_breach_who_asks_full --levels edit,request --prime --parallel 6 \
      --max-cost-usd 0.45 --out results/s1_breach_who_asks_full_pointed --label s1-breach-who-asks-full-pointed \
      > results/s1_breach_who_asks_full_pointed.log 2>&1 ;;
  *) echo "usage: $0 s18-smoke|s18|s1-breach|pointed" >&2; exit 2 ;;
esac
