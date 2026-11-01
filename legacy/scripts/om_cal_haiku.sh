#!/usr/bin/env bash
# Haiku 5.5 calibration (plan C9), run alongside Qwen's (C8), 2026-10-26: the same cells as scripts/other_models.sh cal,
# in its own script so that the running Qwen job's script is not edited under it. Haiku's open questions cost more
# relative to its sessions than Qwen's, so they get their own ceilings.
cd "$(dirname "$0")/.." || exit 1
run() { .venv/bin/python -m upchain "$@"; }
D=configs/other_models; M=haiku; OUT=results/om_cal_$M
run run --config $D/s1_levels.yaml --arm peer --condition harmless_note,excusable_note,breach_note --n 10 \
  --seed-start 0 --model $M --max-cost-usd 0.15 --parallel 6 --out $OUT/s1 --label "om-cal-$M-s1" > $OUT.s1.log 2>&1
run run --config $D/s18_pilot.yaml --arm peer --condition note,excusable_note,breach_note --n 10 \
  --seed-start 0 --model $M --max-cost-usd 0.28 --parallel 6 --out $OUT/s18 --label "om-cal-$M-s18" > $OUT.s18.log 2>&1
run run --config $D/s1_ask_lead.yaml --arm handle --condition excusable_lead_note,breach_lead_note --n 10 \
  --seed-start 0 --model $M --max-cost-usd 0.10 --parallel 6 --out $OUT/h25 --label "om-cal-$M-h25" > $OUT.h25.log 2>&1
for part in s1:s1_levels:0.08 s18:s18_pilot:0.15 h25:s1_ask_lead:0.05; do
  IFS=: read -r P C CAP <<< "$part"
  run reinterview --config $D/$C.yaml --from $OUT/$P --levels open --prime --parallel 6 --max-cost-usd "$CAP" \
    --out $OUT/${P}_reinterview --label "om-cal-$M-$P-reinterview" > $OUT.${P}_reinterview.log 2>&1
done
