#!/usr/bin/env bash
# Experiment 5 (2026-10-20), configs/exp5.yaml (interview after the session), Luna, conditions interleaved per seed.
#   5a: F2b, the handle arm's after-the-fact reports with and without the cover request; the lead is interviewed.
#   5b: F2a between peers, the peer arm; the model worker_1 gets worker_2's note (no request / request / request in
#       team terms) and is interviewed.
# Seed 0 of every condition was the smoke test (same config). Ceilings sum to $0.92 of the $0.98 left.
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/exp5
run() {  # arm, conditions, ceiling
  .venv/bin/python -m upchain run --model luna --config configs/exp5.yaml --out results/exp5 --arm "$1" \
    --condition "$2" --seed-start 1 --n 39 --parallel 4 --max-cost-usd "$3" --label "exp5: $1" > "logs/exp5/$1.log" 2>&1
  echo "$1: $(grep -c ' ep[0-9]*: ' "logs/exp5/$1.log") episodes, $(tail -n 1 "logs/exp5/$1.log")"
}
run handle post_stop,post_stop_cover,post_prereq,post_prereq_cover 0.36 & run peer note,cover,cover_loyal 0.56 & wait
.venv/bin/python -m upchain spend --config configs/exp5.yaml | tail -n 1
