#!/usr/bin/env bash
# S18 wrongness levels (2026-10-24), configs/s18_pilot.yaml, Luna; u1_levels_plan.md A1, predictions H21.
# Budget: $0.25 for the calibration, then $1.25 for the full run (user, 2026-10-24). Each step has its own
# --max-cost-usd ceiling, and the ledger check refuses anything past the config's pilot_total_usd.
#   calibration: excusable_note, breach_note n = 10; open and rate on them; rate on the 40 harmless note runs.
#   full run: excusable and breach x note and cover, n = 40 (new runs); open and rate on every one; open on the 39
#   harmless cover/cover_loyal runs that told the lead (the S17-S19 reinterview asked only the silent ones).
cd "$(dirname "$0")/.." || exit 1
run() { .venv/bin/python -m upchain "$@"; }
C=configs/s18_pilot.yaml
case "${1:-full}" in
  calibration)
    run run --config $C --arm peer --condition excusable_note,breach_note --n 10 --model luna --max-cost-usd 0.12 \
      --parallel 4 --out results/s18_levels_cal --label s18-levels-calibration > results/s18_levels_cal.log 2>&1
    run reinterview --config $C --from results/s18_levels_cal --levels open,rate --prime --parallel 4 \
      --max-cost-usd 0.09 --out results/s18_levels_cal_reinterview --label s18-levels-calibration-reinterview \
      > results/s18_levels_cal_reinterview.log 2>&1
    run reinterview --config $C --from results/s18_peer --cells peer-note --levels rate --prime --parallel 4 \
      --max-cost-usd 0.07 --out results/s18_levels_rate_harmless --label s18-levels-rate-harmless \
      > results/s18_levels_rate_harmless.log 2>&1 ;;
  full)
    for c in peer-cover peer-cover_loyal; do for d in results/s18_peer/$c/gpt-6-luna/ep*; do
      [ -e "results/reinterview/s18/$c/gpt-6-luna/$(basename "$d")" ] || echo "$c/gpt-6-luna/$(basename "$d")"
    done; done > results/s18_levels_harmless_open.episodes
    run reinterview --config $C --from results/s18_peer --episodes results/s18_levels_harmless_open.episodes \
      --levels open --prime --parallel 4 --max-cost-usd 0.09 --out results/s18_levels_harmless_open \
      --label s18-levels-harmless-open > results/s18_levels_harmless_open.log 2>&1
    run run --config $C --arm peer --condition excusable_note,excusable_cover,breach_note,breach_cover --n 40 \
      --model luna --max-cost-usd 0.78 --parallel 6 --out results/s18_levels_full --label s18-levels-full \
      > results/s18_levels_full.log 2>&1
    run reinterview --config $C --from results/s18_levels_full --levels open,rate --prime --parallel 6 \
      --max-cost-usd 0.36 --out results/s18_levels_full_reinterview --label s18-levels-full-reinterview \
      > results/s18_levels_full_reinterview.log 2>&1 ;;
esac
