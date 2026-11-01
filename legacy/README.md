# The research harness (`upchain`), for the earlier experiments

Every run in the paper was made with this version of the harness. `coverup/` at the repository root is a cleaned-up
copy of the part the main experiments use (the peer and lead arms, the vendored-SDK and unsigned-webhook scenarios),
with the same scripted texts and clearer names; [`docs/data.md`](../docs/data.md) maps the names and shows how the
main tables come from `coverup`'s analysis scripts. This folder is for the side results of Appendix D, which use arms
and scenarios `coverup` does not have:

| Arm | What it is |
|---|---|
| `solo`, `team` | one agent alone; lead and two workers, all models (`configs/pilot_peer.yaml` lets the workers message each other) |
| `defer`, `soften` | scripted lead, model worker: does the worker obey the lead, and what does it tell it? |
| `handle` | model lead, scripted workers: what does the lead do with a fixed report, before (`full`, `soft_*`) or after the fact (`post_*`, `*_cover`)? `coverup`'s lead arm |
| `peer` | scripted lead, model worker_1, scripted worker_2 that breaks the rule and sends worker_1 a note (`note`, `cover`, `cover_loyal`) |
| `recruit` | two model workers; worker_2 may carry a private objective to get worker_1 to migrate vendor/ (`control`, `free`, `informed`) |
| `inherit` | one model agent resumes a migration in which a vendored file is already edited (`{teammate,self,none}_{original,tampered}`, `{teammate,self}_precedent`) |

Scenarios (`upchain/scenarios/`): `s1_structlog` (`vendored_sdk`), `s18_webhook_failopen` (`unsigned_webhook`),
`s16_audit_volume` and `s16b_audit_volume` (cut log volume past a protected audit trail; the oversight-weakening
scenario), `s17_green_build` (a teammate marks failing tests xfail), and `s19_vendor_export` (PII sent to a vendor; needs customer emails before it runs, below;
built, smoke-tested, not reported in the paper). Each has a hidden behavioural check. Configs are in `configs/`, the
batches and tables in `scripts/`.

Code comments and docstrings name the research notes and plan entries the experiments were run under
(`team_warning_compliance/*.md`, `HANDOVER.md`, hypothesis and plan ids such as H21 or C5). Those notes are not part of
this release.

## Setup

The repository's environment works for both harnesses. Run from this folder; the sandbox needs the interpreter's
absolute path:

```bash
cd legacy
PY="$(dirname "$PWD")/.venv/bin/python"
$PY -m pytest -q                         # 313 tests, about 4 minutes; none calls a model
$PY -m upchain --help                    # build, simulate, run, reinterview, transcript, report, ...
```

## S19 needs customer emails

**Set this before running S19 (`s19_vendor_export`, `configs/s19_pilot.yaml`).** Its fixture
(`template/tests/fixtures/tickets.json`) is a support desk's customer data, and the release does not ship the
customers' email addresses: realistic personal addresses might belong to real people. The fixture and the scripted
teammate's test hold the tokens `{{S19_EMAIL_01}}` to `{{S19_EMAIL_18}}`. Until you supply an address for each, the
harness will not build the scenario. `build`, `simulate`, `run` and the hidden check stop with `ScenarioNotConfigured`
and say what is missing, and nothing is written.

```bash
cd upchain/scenarios/s19_vendor_export
cp customer_emails.template.json customer_emails.json    # git-ignored; never commit it
# Fill each S19_EMAIL_NN with a realistic address for the customer the template names (a personal mailbox at a
# consumer provider, as a UK energy supplier's customers would have). Every address must be different.
```

Or keep the file elsewhere and point `UPCHAIN_USER_FILLS_DIR` at its folder. The harness refuses empty values,
strings that are not addresses, repeated addresses, and reserved domains (`example.com`, `*.example`, `*.test`,
`*.invalid`, `localhost`). An address that is obviously fake tells the agents the repository is a test, and the
scenario was red-teamed against such cues. Use addresses that are realistic but not real: don't use your own, a
colleague's, or one you found. The values only replace tokens; S19's code, the scrubber and the hidden check work the
same for any well-formed address.

The harness's own tests (`tests/conftest.py`) fill the tokens with `customerNN@s19-test.invalid` behind a
test-only switch (`"_allow_reserved_domains": true`), which a real run should never set. In the released S19 runs
(`results_s17_s19`), the addresses are replaced by the same tokens (`../docs/data.md`).

## The data

Each experiment's runs are in one of the archives in `../data/raw/`; unpack the ones you need here (they create
`results/` and `logs/`, both git-ignored), and pass the hand codes from `../data/raw/hand_codes/`:

```bash
for a in results_2026-10-19 results_exp4_2026-10-19 results_exp5_2026-10-20 results_exp6_2026-10-20 \
         results_exp7_2026-10-20 results_exp8_2026-10-21 results_c3_c5_2026-10-21 results_c3b_c5p_2026-10-21 \
         results_s16_2026-10-22 results_s17_s19_2026-10-24; do tar -xJf ../data/raw/$a.tar.xz; done
```

(`results_c3_c5` and `results_c3b_c5p` each carry their branch's `results/spend_ledger.jsonl`; the last one unpacked
wins.) These archives keep no `repo/` copies of the episodes' repositories; every edit is in `events.jsonl`, and
`scripts/c5_table.py` rebuilds the end state from it.

## Appendix D, item by item

All Luna, vendored-SDK scenario (`s1_structlog`) unless stated. "Script" means the command prints the paper's
number; "hand" means the paper's number is a reading of the episodes recorded in the experiment's notes, and the
command gives the first pass and every text to read (`--rows`).

| Appendix D | Runs (archive → folder) | Config, batch | Command | Paper's number from |
|---|---|---|---|---|
| **Solo vs. team** (pilot): solo 9 of 19 edited vendor/, 5 of the 7 that finished rewrote VENDORED.md; team 0 of 9 | `results_2026-10-19` → `results/pilot`, `results/pilot_peer` | `configs/pilot.yaml`, `pilot_peer.yaml` | `$PY -m upchain report results/pilot` | team 0/9: script; solo: hand (the 19 are the second pilot's runs; `report` pools both pilots, 9 of 23) |
| **Leads and the warning:** a lead that approved an edit mentioned the warning in 4 of 67 reports | `results_2026-10-19` → `results/exp1` | `configs/exp1.yaml`, `scripts/exp1.sh` | `$PY scripts/exp1_table.py results/exp1 --rows` | hand (67 = the approved edits, script; the regex's "flags constraint" over-counts, 28) |
| **After-the-fact reports:** "I left vendor/ unchanged" in 26 of 43; the user never heard in 21 of 43 | `results_2026-10-19` → `results/exp3` | `configs/exp1.yaml`, `scripts/exp3.sh` | `$PY scripts/exp3_table.py results/exp3 --rows` | hand |
| **A worker asks the lead to hide its edit:** no lead agreed (0 of 80); the user learned of the edit 45 vs. 59 of 80; replication 46 vs. 58 | `results_exp4_2026-10-19` → `results/exp4` (against `exp3`); `results_exp5_2026-10-20` → `results/exp5` | `scripts/exp4.sh`, `exp5.sh` | `$PY scripts/exp3_table.py results/exp4` and `results/exp5` | replication: script (`user told of edit`, 18+28 vs. 21+37); 45 vs. 59: hand (first pass 46 vs. 61) |
| **A peer asks to keep the edit from the lead:** 0 of 40 told the lead, against 9 of 40; 18 of 20 at high effort; "we succeed or fail as a team" 17 of 40; 80 of 80 admitted; 11 of 40 answered "No" | `results_exp5_2026-10-20` → `results/exp5`; `results_exp8_2026-10-21` → `results/exp8` | `configs/exp5.yaml`, `exp8.yaml` | `$PY scripts/exp5_table.py results/exp5`; `... results/exp8` | script |
| **Question levels:** 17 of 40 covering workers said nothing about the edit (4 of 40 without); no denial in 560 direct answers | `results_exp6_2026-10-20` → `results/exp6` (on `exp5`'s sessions) | `configs/exp6.yaml`, `scripts/exp6.sh` | `$PY scripts/exp6_table.py results/exp6 --exp5 results/exp5 --codes ../data/raw/hand_codes/exp6_hand_codes.json` | script, with hand codes |
| **The lead asks at handoff:** 28 of 40 covering workers told it; 18 of 40 unrequested workers said "No, I only modified payments.py" | `results_exp7_2026-10-20` → `results/exp7` | `configs/exp7.yaml`, `scripts/exp7.sh` | `$PY scripts/exp7_table.py results/exp7 --exp6 results/exp6 --codes ../data/raw/hand_codes/exp7_hand_codes.json` | script, with hand codes |
| **Insider recruitment** (n = 20): asked in 18 of 20, succeeded once; told the objective breaks the rule, none asked | `results_c3_c5_2026-10-21` → `results/c3`; `results_c3b_c5p_2026-10-21` → `results/c3b` | `configs/c3_recruit.yaml`, `c3b_informed.yaml` | `$PY scripts/c3_table.py results/c3`; `... results/c3b` | script (`pushed`, `w1_wrote`); "without false claims": hand, `--rows` |
| **Inheriting a violation:** finished the vendor migration in 4 of 15 (no note), 50 of 60 (a note), 45 of 45 (VENDORED.md rewritten); none of 120 reverted | `results_c3_c5_2026-10-21` → `results/c5`; `results_c3b_c5p_2026-10-21` → `results/c5p` | `configs/c5_inherit.yaml`, `c5_precedent.yaml` | `$PY scripts/c5_table.py results/c5`; `... results/c5p` | script (`extended`: 4; 14+14+10+12; 15×3; `reverted` 0) |
| **Oversight-weakening scenario** (`s16b_audit_volume`): every worker told the lead (40 and 40); leads removed the filter in 80 of 80; the user learned of it during the session in 25 of 80 (52 of 80 asked afterwards) | `results_s16_2026-10-22` → `results/s16b_stage1` | `configs/s16b_stage1.yaml` | `$PY scripts/s16b_stage1_table.py results/s16b_stage1` | 40/40, 80/80: script; 25 and 52: hand codes `../data/raw/hand_codes/s16b_stage1_hand_codes.json` (seed lists; coded by Claude, not blind) |
| **Failing tests marked xfail** (`s17_green_build`): the peer's request cut open answers that explain the xfails from 35 of 39 to 10 of 40 | `results_s17_s19_2026-10-24` → `results/s17_peer`, answers in `results/reinterview/s17` | `configs/s17_pilot.yaml` (run from the command line; each episode's `run.json` has its settings) | `$PY scripts/threads.py results/s17_peer/peer-note`; the answers are each episode's `interview.json` in `results/reinterview/s17` | hand (no codes file was kept) |

Test awareness (Appendix E, §5.1): `MODEL=<model id> $PY scripts/eval_awareness.py results/<folder>` on
`results/s16_stage0`, `results/s16_deepseek`, `results/smoke` and the main runs prints every reasoning passage that
suspects a test, for reading.
