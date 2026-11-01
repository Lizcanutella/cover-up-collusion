#!/usr/bin/env bash
# Experiment 7 (2026-10-20), configs/exp7.yaml: the lead asks worker_1 (prompts.LEAD_ASKS: open, edit) as the reply
# to its finish call, on every experiment 5 peer session (results/exp5). The smoke test (peer-cover ep0) ran first and
# is skipped here. Budget $1.00 for this experiment, ceiling $0.95.
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/exp7
.venv/bin/python -m upchain reinterview --config configs/exp7.yaml --from results/exp5 --out results/exp7 --mode lead \
  --cells peer-note,peer-cover,peer-cover_loyal --parallel 6 --max-cost-usd "${1:-0.95}" \
  --label "exp7: the lead asks, on exp5 peer sessions" > logs/exp7/reinterview.log 2>&1
echo "$(grep -c ': [0-9]* answer' logs/exp7/reinterview.log) episodes; $(tail -n 1 logs/exp7/reinterview.log)"
