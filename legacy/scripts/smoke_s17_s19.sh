#!/usr/bin/env bash
# Smoke tests for S17–S19 (2026-10-21; budget $2.20 approved by the user, shared by the three configs).
# A: Luna solo + team, 5 each per scenario. B: Luna peer arm, one episode per condition per scenario.
# C (DeepSeek solo, eval-awareness) is run separately.
set -u
cd "$(dirname "$0")/.."
for n in ${@:-s17 s18 s19}; do
  .venv/bin/python -m upchain run --config configs/${n}_pilot.yaml --arm solo --model luna --n 5 --parallel 5 \
    --max-cost-usd 0.25 --out results/smoke/$n --label smoke-A-$n-solo
  .venv/bin/python -m upchain run --config configs/${n}_pilot.yaml --arm team --model luna --n 5 --parallel 5 \
    --max-cost-usd 0.30 --out results/smoke/$n --label smoke-A-$n-team
  .venv/bin/python -m upchain run --config configs/${n}_pilot.yaml --arm peer --condition note,cover,cover_loyal \
    --model luna --n 1 --parallel 3 --max-cost-usd 0.05 --out results/smoke/$n --label smoke-B-$n-peer
done
