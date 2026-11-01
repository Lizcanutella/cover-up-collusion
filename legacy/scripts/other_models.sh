#!/usr/bin/env bash
# Other models on Luna's frozen set (u1_freeze_protocol.md, "Freeze for other models"; u1_levels_plan.md C), 2026-10-26.
# Configs: configs/other_models/, copies of the frozen Luna configs with only the budget cap changed.
#   smoke MODEL CEILING: n = 2 on one cell or two of each role, with the user's open question on every run:
#     S1 peer excusable_note, excusable_cover, lead_cover_user (worker_1); S18 peer excusable_note, excusable_cover
#     (worker_1); H25 handle excusable_one_asks, breach_lead_note (the lead). CEILING is the model's whole smoke,
#     split S1 35 %, S18 35 %, H25 10 %, open questions 20 % (a third per part).
cd "$(dirname "$0")/.." || exit 1
run() { .venv/bin/python -m upchain "$@"; }
D=configs/other_models
case "$1" in
  smoke)
    M=$2; CAP=$3; [ -n "$M" ] && [ -n "$CAP" ] || { echo "usage: $0 smoke MODEL CEILING" >&2; exit 2; }
    OUT=results/om_smoke_$M
    share() { python3 -c "print(round($CAP * $1, 4))"; }
    Q=$(share 0.0667)
    run run --config $D/s1_levels.yaml --arm peer --condition excusable_note,excusable_cover,lead_cover_user --n 2 \
      --model "$M" --max-cost-usd "$(share 0.35)" --parallel 6 --out $OUT/s1 --label "om-smoke-$M-s1" > $OUT.s1.log 2>&1
    run run --config $D/s18_pilot.yaml --arm peer --condition excusable_note,excusable_cover --n 2 \
      --model "$M" --max-cost-usd "$(share 0.35)" --parallel 4 --out $OUT/s18 --label "om-smoke-$M-s18" > $OUT.s18.log 2>&1
    run run --config $D/s1_ask_lead.yaml --arm handle --condition excusable_one_asks,breach_lead_note --n 2 \
      --model "$M" --max-cost-usd "$(share 0.10)" --parallel 4 --out $OUT/h25 --label "om-smoke-$M-h25" > $OUT.h25.log 2>&1
    for part in s1:s1_levels s18:s18_pilot h25:s1_ask_lead; do
      run reinterview --config $D/${part#*:}.yaml --from $OUT/${part%%:*} --levels open --prime --parallel 6 \
        --max-cost-usd "$Q" --out $OUT/${part%%:*}_reinterview --label "om-smoke-$M-${part%%:*}-reinterview" \
        > $OUT.${part%%:*}_reinterview.log 2>&1
    done ;;
  part)
    # One part of the smoke again, after its sessions aborted on a ceiling were moved to results/om_smoke_errored/
    # (2026-10-26, $0.80 more approved by the user): only the missing seeds run, the rest are skipped as existing.
    M=$2; P=$3; CAP=$4; OUT=results/om_smoke_$M
    case "$P" in
      s1) C=s1_levels; A=peer; CELLS=excusable_note,excusable_cover,lead_cover_user ;;
      s18) C=s18_pilot; A=peer; CELLS=excusable_note,excusable_cover ;;
      h25) C=s1_ask_lead; A=handle; CELLS=excusable_one_asks,breach_lead_note ;;
      *) echo "part is s1, s18 or h25" >&2; exit 2 ;;
    esac
    run run --config $D/$C.yaml --arm $A --condition $CELLS --n 2 --model "$M" --max-cost-usd "$CAP" --parallel 6 \
      --out $OUT/$P --label "om-smoke-$M-$P-rerun" > $OUT.$P.rerun.log 2>&1 ;;
  ask)
    # The open question on a part's sessions that have none yet (finished interviews are skipped as existing).
    M=$2; P=$3; CAP=$4; OUT=results/om_smoke_$M
    case "$P" in s1) C=s1_levels ;; s18) C=s18_pilot ;; h25) C=s1_ask_lead ;; *) exit 2 ;; esac
    run reinterview --config $D/$C.yaml --from $OUT/$P --levels open --prime --parallel 6 --max-cost-usd "$CAP" \
      --out $OUT/${P}_reinterview --label "om-smoke-$M-$P-reinterview-rerun" > $OUT.${P}_reinterview.rerun.log 2>&1 ;;
  cal)
    # Note-only calibration of each level (plan C8), n = 10, seeds 0-9, with the user's open question on every run:
    # S1 and S18 at all three levels (worker_1), H25's two lead_note cells (the lead). Ceilings per part are given;
    # each part's open questions get a fifth of its ceiling.
    M=$2; S1CAP=$3; S18CAP=$4; H25CAP=$5; OUT=results/om_cal_$M
    [ -n "$H25CAP" ] || { echo "usage: $0 cal MODEL S1CAP S18CAP H25CAP" >&2; exit 2; }
    fifth() { python3 -c "print(round($1 / 5, 4))"; }
    run run --config $D/s1_levels.yaml --arm peer --condition harmless_note,excusable_note,breach_note --n 10 \
      --seed-start 0 --model "$M" --max-cost-usd "$S1CAP" --parallel 6 --out $OUT/s1 --label "om-cal-$M-s1" \
      > $OUT.s1.log 2>&1
    run run --config $D/s18_pilot.yaml --arm peer --condition note,excusable_note,breach_note --n 10 \
      --seed-start 0 --model "$M" --max-cost-usd "$S18CAP" --parallel 6 --out $OUT/s18 --label "om-cal-$M-s18" \
      > $OUT.s18.log 2>&1
    run run --config $D/s1_ask_lead.yaml --arm handle --condition excusable_lead_note,breach_lead_note --n 10 \
      --seed-start 0 --model "$M" --max-cost-usd "$H25CAP" --parallel 6 --out $OUT/h25 --label "om-cal-$M-h25" \
      > $OUT.h25.log 2>&1
    for part in s1:s1_levels:$S1CAP s18:s18_pilot:$S18CAP h25:s1_ask_lead:$H25CAP; do
      IFS=: read -r P C CAP <<< "$part"
      run reinterview --config $D/$C.yaml --from $OUT/$P --levels open --prime --parallel 6 \
        --max-cost-usd "$(fifth "$CAP")" --out $OUT/${P}_reinterview --label "om-cal-$M-$P-reinterview" \
        > $OUT.${P}_reinterview.log 2>&1
    done ;;
  full)
    # Full run on the frozen 23-cell set (u1_freeze_protocol.md, "Cuts for the deadline"), n per cell, seeds 0..n-1,
    # the user's open question on every run. Cells per family can be narrowed after calibration with the env vars
    # S1_CELLS, S18_CELLS, H25_CELLS (comma-separated; empty skips the family). One ceiling per family for the
    # sessions and one for each family's open questions.
    M=$2; N=$3; S1CAP=$4; S18CAP=$5; H25CAP=$6; QCAP=$7; OUT=results/om_full_$M
    [ -n "$QCAP" ] || { echo "usage: $0 full MODEL N S1CAP S18CAP H25CAP QCAP" >&2; exit 2; }
    : "${S1_CELLS=harmless_note,harmless_cover,excusable_note,excusable_cover,breach_note,breach_cover,informed_note,peer_cover_user,lead_cover_user,both_cover_user}"
    : "${S18_CELLS=note,cover,excusable_note,excusable_cover,breach_note,breach_cover,excusable_peer_cover_user,excusable_lead_cover_user,excusable_both_cover_user}"
    : "${H25_CELLS=excusable_lead_note,excusable_one_asks,breach_lead_note,breach_one_asks}"
    for fam in s1:s1_levels:peer:$S1CAP:$S1_CELLS s18:s18_pilot:peer:$S18CAP:$S18_CELLS h25:s1_ask_lead:handle:$H25CAP:$H25_CELLS; do
      IFS=: read -r P C A CAP CELLS <<< "$fam"
      [ -n "$CELLS" ] || continue
      run run --config $D/$C.yaml --arm $A --condition "$CELLS" --n "$N" --seed-start 0 --model "$M" \
        --max-cost-usd "$CAP" --parallel 6 --out $OUT/$P --label "om-full-$M-$P" > $OUT.$P.log 2>&1
      run reinterview --config $D/$C.yaml --from $OUT/$P --levels open --prime --parallel 6 --max-cost-usd "$QCAP" \
        --out $OUT/${P}_reinterview --label "om-full-$M-$P-reinterview" > $OUT.${P}_reinterview.log 2>&1
    done ;;
  *) echo "usage: $0 smoke MODEL CEILING | cal MODEL S1CAP S18CAP H25CAP | full MODEL N S1CAP S18CAP H25CAP QCAP | part MODEL s1|s18|h25 CEILING | ask MODEL s1|s18|h25 CEILING" >&2; exit 2 ;;
esac
