#!/usr/bin/env bash
# Experiment 6 (2026-10-20), configs/exp6.yaml: every experiment 5 session (results/exp5) branched four times, one
# interview level per branch (prompts.INTERVIEW_LEVELS: open, review, edit, request). Luna, as in the sessions.
# The smoke test (--limit 1, results/exp6) ran first; its episode is skipped here. Budget $1.00, ceiling $0.95.
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/exp6
.venv/bin/python -m upchain reinterview --config configs/exp6.yaml --from results/exp5 --out results/exp6 \
  --parallel 6 --max-cost-usd "${1:-0.95}" --label "exp6: four levels on exp5" > logs/exp6/reinterview.log 2>&1
echo "$(grep -c ': [0-9]* answer' logs/exp6/reinterview.log) episodes; $(tail -n 1 logs/exp6/reinterview.log)"
