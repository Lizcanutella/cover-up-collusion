#!/usr/bin/env bash
# Weaker C5 (2026-10-21), configs/c5_precedent.yaml: teammate_precedent and self_precedent, a handoff note that says
# client.py was migrated but no longer lists retry.py and signing.py as still to do. Compared with C5's *_original
# and none_original cells (results/c5). Seed 0 of each was the smoke test ($0.036). Budget $0.80; ceiling $0.76.
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/c5p
.venv/bin/python -m upchain run --model luna --config configs/c5_precedent.yaml --out results/c5p --arm inherit \
  --condition teammate_precedent,self_precedent --seed-start 1 --n 14 --parallel 6 --max-cost-usd 0.76 \
  --label "c5p: precedent note" > logs/c5p/batch.log 2>&1
echo "c5p: $(grep -c ' ep[0-9]*: ' logs/c5p/batch.log) episodes, $(tail -n 1 logs/c5p/batch.log)"
