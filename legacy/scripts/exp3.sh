#!/usr/bin/env bash
# Experiment 3 (2026-10-19): after-the-fact reports. Luna lead; scripted worker_1 migrates vendor/ first, then reports
# with a note taken from a real pushed Luna worker (post_stop, post_prereq) and reverts if told to. 40 per note;
# post_prereq seeds 0-1 were the smoke test (same config). Ceilings sum to $0.18.
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/exp3
run() {  # condition, seed start, n
  .venv/bin/python -m upchain run --model luna --config configs/exp1.yaml --out results/exp3 --arm handle \
    --condition "$1" --seed-start "$2" --n "$3" --parallel 4 --max-cost-usd 0.09 --label "exp3: $1" > "logs/exp3/$1.log" 2>&1
  echo "$1: $(grep -c ' ep[0-9]*: ' "logs/exp3/$1.log") episodes, $(tail -n 1 "logs/exp3/$1.log")"
}
run post_stop 0 40 & run post_prereq 2 38 & wait
.venv/bin/python -m upchain spend | tail -n 1
