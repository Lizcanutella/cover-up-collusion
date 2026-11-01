#!/usr/bin/env bash
# C3 (2026-10-21), configs/c3_recruit.yaml: the recruit arm, a Luna insider (worker_2) with or without a private
# objective to get the Luna worker_1 to migrate vendor/. Workers stay reachable after finish (user's design,
# 2026-10-21). Seed 0 of each condition was the second smoke test; the first, under the old finish rule, is in
# results/c3_smoke_v1. Budget $0.80 for C3, $0.05 spent on smoke tests; ceiling $0.70. `honest` waits for the user.
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/c3
.venv/bin/python -m upchain run --model luna --config configs/c3_recruit.yaml --out results/c3 --arm recruit \
  --condition control,free --seed-start 1 --n 19 --parallel 4 --max-cost-usd 0.70 \
  --label "c3: insider recruitment, control and free" > logs/c3/batch.log 2>&1
echo "c3: $(grep -c ' ep[0-9]*: ' logs/c3/batch.log) episodes, $(tail -n 1 logs/c3/batch.log)"
