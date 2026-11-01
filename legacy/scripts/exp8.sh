#!/usr/bin/env bash
# Experiment 8 (2026-10-21), configs/exp8.yaml: experiment 5's peer arm (note, cover) and experiment 7's lead
# questions, with Luna at reasoning effort high. Seed 0 of each condition was the smoke test (same config), so this
# runs seeds 1-19. Budget $0.50 for this experiment; ceilings $0.30 + $0.08 on top of the smoke test's $0.01.
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/exp8
.venv/bin/python -m upchain run --model luna --config configs/exp8.yaml --out results/exp8 --arm peer \
  --condition note,cover --seed-start 1 --n 19 --parallel 4 --max-cost-usd 0.30 --label "exp8: peer at high" \
  > logs/exp8/peer.log 2>&1
echo "peer: $(grep -c ' ep[0-9]*: ' logs/exp8/peer.log) episodes, $(tail -n 1 logs/exp8/peer.log)"
.venv/bin/python -m upchain reinterview --config configs/exp8.yaml --from results/exp8 --out results/exp8_lead \
  --mode lead --cells peer-note,peer-cover --parallel 6 --max-cost-usd 0.08 \
  --label "exp8: the lead asks, at high" > logs/exp8/lead.log 2>&1
echo "lead asks: $(grep -c ': [0-9]* answer' logs/exp8/lead.log) episodes; $(tail -n 1 logs/exp8/lead.log)"
