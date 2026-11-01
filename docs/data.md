# The data, and how to get every number in the paper from it

Everything the paper reports comes from the files in `data/`:

- `data/raw/`: the run archives (`results_*.tar.xz`, 111 MB) and the hand codes (`hand_codes/*.json`) as the research
  version of the harness wrote them. That version is in [`legacy/`](../legacy/README.md); it used other names for the
  scenarios, arms and cells (below). The archives hold every session, every question asked on a branch, the batch
  logs and the spend ledgers, including smoke runs, episodes that ended on errors and the earlier experiments of
  Appendix D. The files are as written, with two redactions, applied to every file including what the models saw and
  wrote (`events.jsonl`, `calls.jsonl`, `interview.json`):
  - **Local paths.** The research checkouts' locations are `~/project` or `/home/user/project`, and the author's home
    directory is `/home/user`. Models saw these paths mostly in pytest tracebacks from `run_tests`, and a few quote
    them in their reasoning. `run.json` keeps relative paths, and the tar headers carry no owner.
  - **S19's customer emails.** The `s19_vendor_export` scenario's fixture had 18 realistic personal addresses that
    might belong to real people. Every occurrence, in any letter case, is replaced by its token (`{{S19_EMAIL_01}}`
    to `{{S19_EMAIL_18}}`, the same tokens as in `legacy/upchain/scenarios/s19_vendor_export/`), so you can still tell
    which customer an export or answer leaked. S19 runs are in `results_s17_s19` only and are not reported in the
    paper. Encodings or digests of an address that a model wrote (S19's hidden check also looks for those) are left
    as they were.
- `data/hand_codes/`: the hand codes of the paper's runs, with the cells renamed to this harness's names and two
  fields renamed (`told_says_asked` → `asked_session`, `open_says_asked` → `asked_open`, the names the tables read).
  Each file says what it was converted from; the codes themselves are unchanged.

## Unpacking

```bash
.venv/bin/python scripts/import_results.py              # ~15 s; about 20,000 files, 630 MB, into results/
.venv/bin/python scripts/import_results.py --with-repo  # also each episode's repo/ (adds about 4 GB)
```

This copies the runs the paper uses into the layout `scripts/run_experiments.sh` writes, renaming directories only:

| `results/` | What | From (archive: folder) |
|---|---|---|
| `levels/vendored_sdk/luna` | E1, SDK levels, n = 40 | `results_levels`: `s1_levels_full`, `_reinterview` |
| `levels/unsigned_webhook/luna` | E1, webhook levels, n = 40 | `results_levels`: `s18_levels_full`, `_reinterview`; the harmless level is the first S18 peer run, `results_s17_s19`: `s18_peer` (open answers from `reinterview/s18` and `results_levels`: `s18_levels_harmless_open`; its ratings in `questions_rate/`, from `s18_levels_rate_harmless`) |
| `calibrate/{vendored_sdk,unsigned_webhook}/luna` | the 10-run calibrations (Appendix B) | `results_levels`: `s1_levels_cal`, `s18_levels_cal` |
| `who_asks/{vendored_sdk_excusable,unsigned_webhook_excusable,vendored_sdk_breach}/luna` | E2, n = 40; `pointed/` holds the pointed questions | `results_who_asks`, `results_who_asks_level2`, `results_who_asks_level2_pointed` |
| `lead_arm/vendored_sdk/luna` | E3, n = 40 | `results_ask_lead`: `ask_lead_full`, `_reinterview` |
| `calibrate/*/{qwen,haiku}`, `lead_arm/vendored_sdk/{qwen,haiku}` | other models without a request | `results_other_models`: `om_cal_*` |
| `lead_arm/vendored_sdk/gemini-lite` | Gemini as the lead | `results_other_models`: `om_h25_gemini-lite` |
| `rank/vendored_sdk_excusable/{qwen,minimax,gemini-lite}` | the rank runs, n = 20 | `results_other_models`: `om_rank_*` |
| `smoke/{haiku,qwen,deepseek,mimo,minimax,glm}`, `smoke/luna/unsigned_webhook` | screening and test awareness (Appendix E) | `results_other_models`: `om_smoke_*`; `results_s17_s19`: `smoke/s18` |

Left in the archives only: the who-asks and lead-arm smoke runs (n = 2), the four E3 sessions that ended on an
account error (`ask_lead_full_errored`; re-run as new samples), failed question attempts (`*_failed`, `*_errored`),
Qwen's calibration sessions stopped by the cost ceiling (`om_cal_errored`), and the loyalty-framing cell
(`peer-cover_loyal`), which the paper does not use.

### Names in the research harness

| Research harness | This harness |
|---|---|
| scenario `s1_structlog` / `s18_webhook_failopen` | `vendored_sdk` / `unsigned_webhook` |
| arm `handle` (the model is the lead) | `lead` |
| `peer-<level>_note`; S18's harmless run: `peer-note` | `peer-<level>_no_request` |
| `peer-<level>_cover`; S18's harmless run: `peer-cover` | `peer-<level>_peer_asks_hide_from_lead` |
| `peer-[<level>_]informed_note` | `peer-<level>_lead_informed` |
| `peer-[<level>_]peer_cover_user`, `lead_cover_user`, `both_cover_user` | `peer-<level>_peer_asks_hide_from_user`, `lead_asks_hide_from_user`, `both_ask_hide_from_user` |
| `handle-<level>_lead_note`, `one_asks`, `two_ask` | `lead-<level>_no_request`, `one_worker_asks`, `two_workers_ask` |

Where a research cell name has no level (S1 excusable who-asks, the rank runs), the level is the batch's
(`scripts/import_results.py`, `SOURCES`). The mapping was checked against the texts: for every imported session, the
scripted roles' messages (worker_2's note, the lead's request, worker_2's report) are the ones this harness sends
for the cell it was filed under (`coverup simulate` of each cell, compared with the sessions' events).

## Table by table

Run from the repository root after unpacking. `R=results C=data/hand_codes P=.venv/bin/python`. Every command below
was run on the released data and gives the paper's numbers.

| Paper | Command |
|---|---|
| **Table 1**, Figure 2 (E1, SDK) | `$P analysis/levels_table.py vendored_sdk --sessions $R/levels/vendored_sdk/luna --interviews $R/levels/vendored_sdk/luna/questions --codes $C/levels_vendored_sdk_luna.json` |
| **Table 1** (E1, webhook) | `$P analysis/levels_table.py unsigned_webhook --sessions $R/levels/unsigned_webhook/luna --interviews $R/levels/unsigned_webhook/luna/questions $R/levels/unsigned_webhook/luna/questions_rate --codes $C/levels_unsigned_webhook_luna.json` |
| **Table 2** (E2), three places | `$P analysis/who_asks_table.py --scenario S --level L --sessions $R/who_asks/S_L/luna --interviews $R/who_asks/S_L/luna/questions --codes $C/who_asks_S_L_luna.json` for `S L` = `vendored_sdk excusable`, `unsigned_webhook excusable`, `vendored_sdk breach` |
| **§4.4** (pointed questions) | `$P analysis/pointed_table.py --level L --codes $C/who_asks_S_L_luna_pointed.json --open $C/who_asks_S_L_luna.json` (add `--answers $R/who_asks/S_L/luna/pointed` to read the answers) |
| **Table 3**, §4.3 (E3) | `$P analysis/lead_arm_table.py --sessions $R/lead_arm/vendored_sdk/luna --interviews $R/lead_arm/vendored_sdk/luna/questions --codes $C/lead_arm_vendored_sdk_luna.json` |
| **Table 4** (rank) | `$P analysis/who_asks_table.py --scenario vendored_sdk --level excusable --sessions $R/rank/vendored_sdk_excusable/M --interviews $R/rank/vendored_sdk_excusable/M/questions --codes $C/rank_vendored_sdk_excusable_M.json` for `M` = `qwen`, `minimax`, `gemini-lite`; Luna's row is Tables 1 and 2 |
| **Tables 5, 6** (other models, peer arm) | `$P analysis/levels_table.py S --sessions $R/calibrate/S/M --interviews $R/calibrate/S/M/questions --codes $C/calibrate_S_M.json` for `M` = `qwen`, `haiku`; the rank rows of Table 6 are the `no_request` rows of Table 4's runs |
| **Tables 5, 7** (other models as the lead) | `$P analysis/lead_arm_table.py --sessions $R/lead_arm/vendored_sdk/M --interviews $R/lead_arm/vendored_sdk/M/questions --codes $C/lead_arm_vendored_sdk_M.json` for `M` = `qwen`, `haiku`, `gemini-lite` |
| **Appendix B** (Luna calibrations) | `$P analysis/levels_table.py S --sessions $R/calibrate/S/luna --interviews $R/calibrate/S/luna/questions` (SDK: add `--codes $C/calibrate_vendored_sdk_luna.json`) |
| **Appendix E** (test awareness) | `MODEL=<model id> $P analysis/eval_awareness.py $R/smoke/M/<scenario>` prints the reasoning to read |
| **Appendix D** (earlier experiments) | [`legacy/README.md`](../legacy/README.md) |
| **Table 8** (costs) | `usage.jsonl` in every episode; the ledgers are `results/spend_ledger.jsonl` inside the archives |

Things to know when comparing:

- **Gemini as the lead.** `lead_arm_table.py` counts all 20 runs per cell; the paper's denominators (17 per cell,
  Tables 5 and 7) leave out the 6 runs in which the lead gave all the work to worker_1, so worker_2 never made the
  edit (`modified_at_end` and `reverted` both 0, and no vendor/ write in events.jsonl). The counts of reverted runs,
  report names, questions to the user and open answers are the same either way.
- **Excluded episodes.** The tables print `excluded ... ended on an error`: Qwen's three lead sessions stopped by a
  cost ceiling (Table 7's 9 and 8) and Gemini's six provider errors in the rank request cells (n = 18).
- **The webhook calibration has no hand codes;** its table is the regex first pass (the paper quotes the SDK
  calibration only). Everything else the paper reports is from hand codes; the first pass alone over-counts
  "calls it a problem".
- **The coding** (Section 3.6): `--blind PREFIX` on any table writes the items shuffled with the condition hidden and
  a key, which is how the hand codes were made. The `about` field of each codes file says who coded it and how.
