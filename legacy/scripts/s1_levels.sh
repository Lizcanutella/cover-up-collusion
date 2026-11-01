#!/usr/bin/env bash
# S1 wrongness levels (2026-10-25), configs/s1_levels.yaml (experiment 5's settings), Luna; u1_levels_plan.md A2,
# predictions H22. Budget: $0.20 for the calibration, then $1.00 for the full run (user, 2026-10-25). Each step has
# its own --max-cost-usd ceiling, and the ledger check refuses anything past the config's pilot_total_usd.
#   calibration: harmless_note, excusable_note, breach_note n = 10; the open question on each.
#   full run: the three levels x note and cover, n = 40 (new runs); the open question on every one.
cd "$(dirname "$0")/.." || exit 1
run() { .venv/bin/python -m upchain "$@"; }
C=configs/s1_levels.yaml
case "${1:-full}" in
  calibration)
    run run --config $C --arm peer --condition harmless_note,excusable_note,breach_note --n 10 --model luna \
      --max-cost-usd 0.13 --parallel 6 --out results/s1_levels_cal --label s1-levels-calibration \
      > results/s1_levels_cal.log 2>&1
    run reinterview --config $C --from results/s1_levels_cal --levels open --prime --parallel 6 --max-cost-usd 0.06 \
      --out results/s1_levels_cal_reinterview --label s1-levels-calibration-reinterview \
      > results/s1_levels_cal_reinterview.log 2>&1 ;;
  full)
    run run --config $C --arm peer \
      --condition harmless_note,harmless_cover,excusable_note,excusable_cover,breach_note,breach_cover --n 40 \
      --model luna --max-cost-usd 0.65 --parallel 6 --out results/s1_levels_full --label s1-levels-full \
      > results/s1_levels_full.log 2>&1
    run reinterview --config $C --from results/s1_levels_full --levels open --prime --parallel 6 --max-cost-usd 0.33 \
      --out results/s1_levels_full_reinterview --label s1-levels-full-reinterview \
      > results/s1_levels_full_reinterview.log 2>&1 ;;
esac
