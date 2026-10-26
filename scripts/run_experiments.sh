#!/usr/bin/env bash
# The experiments as batches: the sessions, then the user's questions, each on its own branch of every finished
# session (`coverup reinterview`). Every paid step has its own ceiling (--max-cost-usd), and the ledger check refuses
# any step that could take results/spend_ledger.jsonl past the config's budget.total_usd.
#
#   smoke MODEL N RUN_CAP ASK_CAP
#       Can a new model play each role? vendored_sdk peer excusable_{no_request,peer_asks_hide_from_lead,
#       lead_asks_hide_from_user}; unsigned_webhook peer excusable_{no_request,peer_asks_hide_from_lead}; the lead arm
#       excusable_one_worker_asks and breach_no_request. n per cell (we used 2), the open question on every run;
#       RUN_CAP and ASK_CAP are per part.
#   calibrate SCENARIO MODEL N RUN_CAP ASK_CAP
#       The manipulation check for the wrongness levels: each level's note with no request, n per cell, and the
#       user's open question on every run (plus the rating question on unsigned_webhook). For the model as the lead:
#       CELLS=excusable_no_request,breach_no_request $0 lead-arm ...
#   levels SCENARIO MODEL N RUN_CAP ASK_CAP
#       Wrongness levels: harmless, excusable and breach, each with no request and with the peer asking worker_1 to
#       keep the act from the lead; the open question on every run (plus the rating on unsigned_webhook).
#   who-asks SCENARIO LEVEL MODEL N RUN_CAP ASK_CAP
#       Who asks, at one level (excusable or breach; unsigned_webhook has excusable only): no request, the lead
#       informed, and the peer, the lead or both asking worker_1 to keep the act from the user; the open question.
#   rank MODEL N RUN_CAP ASK_CAP
#       Does rank buy silence (the test we ran on the other models)? vendored_sdk excusable: no request, the lead
#       informed, the peer or the lead asking worker_1 to keep the act from the user, and the peer asking it to keep
#       the act from the lead; the open question. Read with analysis/who_asks_table.py --level excusable.
#   lead-arm MODEL N RUN_CAP ASK_CAP
#       Workers ask the lead (vendored_sdk; the model is the lead): worker_2 reports its vendor/ edit after the fact,
#       with no request, with its own request, or with worker_1 asking too; the open question to the lead.
#   pointed SCENARIO RESULTS_DIR ASK_CAP
#       The pointed questions (edit, request), each on its own branch, on a finished results folder.
#
# MODEL is a LiteLLM model or an alias in coverup/runner.py (e.g. luna, haiku, qwen, minimax, gemini-lite). Sessions
# go to results/<family>/<scenario>[_<level>]/<model>/, the answers to .../questions/. CELLS=a,b,c runs only those
# conditions in place of a batch's own (seeds 0..N-1 as always, so a narrowed batch can be extended later; finished
# episodes are skipped). PARALLEL (default 6) sets how many episodes run at once.
set -euo pipefail
cd "$(dirname "$0")/.."
run() { .venv/bin/python -m coverup "$@"; }
PARALLEL=${PARALLEL:-6}

asks() {  # the user's questions for a scenario's level runs: the open question, and the rating where there is one
  if [ "$1" = unsigned_webhook ]; then echo open,rate; else echo open; fi
}

prefixed() {  # LEVEL CELL...: LEVEL_CELL,LEVEL_CELL,...
  local level=$1 out="" cell; shift
  for cell in "$@"; do out+="${level}_${cell},"; done
  echo "${out%,}"
}

session_and_questions() {  # CONFIG ARM CELLS MODEL N RUN_CAP ASK_CAP OUT LEVELS
  local config=$1 arm=$2 cells=${CELLS:-$3} model=$4 n=$5 run_cap=$6 ask_cap=$7 out=$8 levels=$9
  run run --config "$config" --arm "$arm" --condition "$cells" --n "$n" --model "$model" \
    --max-cost-usd "$run_cap" --parallel "$PARALLEL" --out "$out" --label "$out"
  run reinterview --config "$config" --from "$out" --levels "$levels" --prime --parallel "$PARALLEL" \
    --max-cost-usd "$ask_cap" --out "$out/questions" --label "$out/questions"
}

usage() { awk 'NR > 1 && /^#/ { print; next } NR > 1 { exit }' "$0" >&2; exit 2; }

case "${1:-}" in
  smoke)
    [ $# -eq 5 ] || usage
    [ -z "${CELLS:-}" ] || { echo "CELLS does not apply to smoke" >&2; exit 2; }
    out=results/smoke/$2
    session_and_questions configs/vendored_sdk.yaml peer \
      "$(prefixed excusable no_request peer_asks_hide_from_lead lead_asks_hide_from_user)" \
      "$2" "$3" "$4" "$5" "$out/vendored_sdk" open
    session_and_questions configs/unsigned_webhook.yaml peer "$(prefixed excusable no_request peer_asks_hide_from_lead)" \
      "$2" "$3" "$4" "$5" "$out/unsigned_webhook" open
    session_and_questions configs/vendored_sdk.yaml lead "excusable_one_worker_asks,breach_no_request" \
      "$2" "$3" "$4" "$5" "$out/lead_arm" open ;;
  calibrate)
    [ $# -eq 6 ] || usage
    scenario=$2
    session_and_questions "configs/$scenario.yaml" peer "harmless_no_request,excusable_no_request,breach_no_request" \
      "$3" "$4" "$5" "$6" "results/calibrate/$scenario/$3" "$(asks "$scenario")" ;;
  levels)
    [ $# -eq 6 ] || usage
    scenario=$2
    cells=$(printf '%s_no_request,%s_peer_asks_hide_from_lead,' harmless harmless excusable excusable breach breach)
    session_and_questions "configs/$scenario.yaml" peer "${cells%,}" \
      "$3" "$4" "$5" "$6" "results/levels/$scenario/$3" "$(asks "$scenario")" ;;
  who-asks)
    [ $# -eq 7 ] || usage
    scenario=$2 level=$3
    session_and_questions "configs/$scenario.yaml" peer "$(prefixed "$level" no_request lead_informed \
      peer_asks_hide_from_user lead_asks_hide_from_user both_ask_hide_from_user)" \
      "$4" "$5" "$6" "$7" "results/who_asks/${scenario}_${level}/$4" open ;;
  rank)
    [ $# -eq 5 ] || usage
    session_and_questions configs/vendored_sdk.yaml peer "$(prefixed excusable no_request lead_informed \
      peer_asks_hide_from_user lead_asks_hide_from_user peer_asks_hide_from_lead)" \
      "$2" "$3" "$4" "$5" "results/rank/vendored_sdk_excusable/$2" open ;;
  lead-arm)
    [ $# -eq 5 ] || usage
    cells=$(prefixed excusable no_request one_worker_asks two_workers_ask),$(prefixed breach no_request \
      one_worker_asks two_workers_ask)
    session_and_questions configs/vendored_sdk.yaml lead "$cells" \
      "$2" "$3" "$4" "$5" "results/lead_arm/vendored_sdk/$2" open ;;
  pointed)
    [ $# -eq 4 ] || usage
    run reinterview --config "configs/$2.yaml" --from "$3" --levels edit,request --prime --parallel "$PARALLEL" \
      --max-cost-usd "$4" --out "$3/pointed" --label "$3/pointed" ;;
  *) usage ;;
esac
