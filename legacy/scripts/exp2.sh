#!/usr/bin/env bash
# Experiment 2 (2026-10-19), two parts run together. Seeds 0-1 of each first cell were the smoke test (same config).
#  a) DeepSeek V4.1 Flash as the lead in the handle arm (configs/exp1.yaml, obeying worker): soft_owner, soft_prereq.
#  b) The worker-softening arm: a Luna worker_1, a scripted lead assigning vendor/ neutrally or after pushing
#     "whole repository" (results/exp2).
# Ceilings sum to $0.58.
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/exp2
run() {  # log name, then upchain run args
  local name=$1; shift
  .venv/bin/python -m upchain run --config configs/exp1.yaml --parallel 4 "$@" --label "exp2: $name" > "logs/exp2/$name.log" 2>&1
  echo "$name: $(grep -c ' ep[0-9]*: ' "logs/exp2/$name.log") episodes, $(tail -n 1 "logs/exp2/$name.log")"
}
run deepseek_owner --model deepseek --out results/exp1 --arm handle --condition soft_owner --seed-start 2 --n 8 --max-cost-usd 0.14 &
run deepseek_prereq --model deepseek --out results/exp1 --arm handle --condition soft_prereq --n 10 --max-cost-usd 0.14 &
run soften_pushed --model luna --out results/exp2 --arm soften --condition pushed --seed-start 2 --n 13 --max-cost-usd 0.15 &
run soften_neutral --model luna --out results/exp2 --arm soften --condition neutral --n 15 --max-cost-usd 0.15 &
wait
.venv/bin/python -m upchain spend | tail -n 1
