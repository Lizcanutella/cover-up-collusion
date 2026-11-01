#!/usr/bin/env bash
# Experiment 1 (2026-10-19): the handle arm at scale, Luna lead, obeying scripted worker, 40 episodes per report.
# soft seeds 0-1 were the smoke test (same config), so soft runs seeds 2-41. Ceilings sum to $0.42.
cd "$(dirname "$0")/.." || exit 1
run() {  # condition, seed start, n
  .venv/bin/python -m upchain run --model luna --config configs/exp1.yaml --out results/exp1 --arm handle \
    --condition "$1" --seed-start "$2" --n "$3" --parallel 4 --max-cost-usd 0.07 --label "exp1: $1" \
    > "logs/exp1/$1.log" 2>&1
  echo "$1: $(grep -c ' ep[0-9]*: ' "logs/exp1/$1.log") episodes, $(tail -1 "logs/exp1/$1.log")"
}
run full 0 40 & run soft 2 38 & run soft_stop 0 40 & wait
run soft_prereq 0 40 & run soft_owner 0 40 & run soft_fallback 0 40 & wait
.venv/bin/python -m upchain spend | tail -1
