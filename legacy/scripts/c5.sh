#!/usr/bin/env bash
# C5 (2026-10-21), configs/c5_inherit.yaml: a solo Luna agent inherits a half-done vendor/ migration, six cells
# (teammate / self / none x original / tampered VENDORED.md). Seed 0 of every cell was the smoke test ($0.12), so
# this runs seeds 1-14. Budget $3.00 for C5; ceiling $2.80.
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/c5
.venv/bin/python -m upchain run --model luna --config configs/c5_inherit.yaml --out results/c5 --arm inherit \
  --condition teammate_original,teammate_tampered,self_original,self_tampered,none_original,none_tampered \
  --seed-start 1 --n 14 --parallel 6 --max-cost-usd 2.80 --label "c5: inherit a half-done violation" \
  > logs/c5/batch.log 2>&1
echo "c5: $(grep -c ' ep[0-9]*: ' logs/c5/batch.log) episodes, $(tail -n 1 logs/c5/batch.log)"
