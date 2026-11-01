#!/usr/bin/env bash
# C3b (2026-10-21), configs/c3b_informed.yaml: the recruit arm, `informed` (the insider's objective names VENDORED.md
# and says no sign-off has been given). Compared with C3 `free` (results/c3). Seed 0 was the smoke test ($0.012).
# Budget $0.50 for C3b; ceiling $0.48.
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/c3b
.venv/bin/python -m upchain run --model luna --config configs/c3b_informed.yaml --out results/c3b --arm recruit \
  --condition informed --seed-start 1 --n 19 --parallel 4 --max-cost-usd 0.48 \
  --label "c3b: informed insider" > logs/c3b/batch.log 2>&1
echo "c3b: $(grep -c ' ep[0-9]*: ' logs/c3b/batch.log) episodes, $(tail -n 1 logs/c3b/batch.log)"
