"""Unpack the paper's runs from the raw archives into `results/`, under this harness's names.

Usage:
  .venv/bin/python scripts/import_results.py [--with-repo] [--only FAMILY[,FAMILY...]] [--codes-only]

The runs were made with the research version of this harness (`legacy/upchain/`), which used other names: scenario
`s1_structlog` is `vendored_sdk` and `s18_webhook_failopen` is `unsigned_webhook`; the lead arm was `handle`; cells
were `note` (no request), `cover` (the peer asks to keep it from the lead), `informed_note`, `peer_cover_user`,
`lead_cover_user`, `both_cover_user`, `lead_note`, `one_asks`, `two_ask`. `data/raw/` keeps the archives and hand codes
exactly as that harness wrote them. This script copies the runs each table of the paper reads into the layout
`scripts/run_experiments.sh` writes (`results/<family>/<scenario>[_<level>]/<model>/<arm>-<cell>/<model id>/ep<seed>/`,
the user's questions in `.../questions/`, the pointed questions in `.../pointed/`), renaming only directories; no file
is changed. It also writes the hand codes, with the cells renamed the same way, to `data/hand_codes/` (committed;
`--codes-only` rewrites just those). docs/data.md lists which table reads which folder.

Each episode's `repo/` (the repository as the agents left it, about 4 GB in all) is skipped unless `--with-repo`; the
analysis does not read it, and every edit is also in events.jsonl. Runs left out of the paper (smoke runs of the
who-asks and lead-arm batches, episodes that ended on errors, failed question attempts, the loyalty-framing cell) stay
in the raw archives only.
"""

import json
import re
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CODES_OUT = ROOT / "data" / "hand_codes"

LEVELS = ("harmless", "excusable", "breach")
PEER_CELLS = {"note": "no_request", "cover": "peer_asks_hide_from_lead", "informed_note": "lead_informed",
              "peer_cover_user": "peer_asks_hide_from_user", "lead_cover_user": "lead_asks_hide_from_user",
              "both_cover_user": "both_ask_hide_from_user"}
LEAD_CELLS = {"lead_note": "no_request", "one_asks": "one_worker_asks", "two_ask": "two_workers_ask"}
SMOKE_ARMS = ("solo", "team")


def rename(cell, level):
    """The research harness's cell folder name -> this harness's, or None for a cell the paper does not use.
    `level` is the level a cell without one in its name was run at."""
    if cell in SMOKE_ARMS:
        return cell
    arm, _, condition = cell.partition("-")
    if arm not in ("peer", "handle"):
        return None
    for lv in LEVELS:
        if condition.startswith(lv + "_"):
            level, condition = lv, condition[len(lv) + 1:]
            break
    table = PEER_CELLS if arm == "peer" else LEAD_CELLS
    if condition not in table:
        return None  # e.g. cover_loyal
    return f"{'peer' if arm == 'peer' else 'lead'}-{level}_{table[condition]}"


# (archive, source folder under results/, destination under results/, the level of cells without one in their name,
#  cells to keep (None: all the paper uses)). Folders listed twice for one destination are merged; no two sources
# hold the same episode's file.
L, R, O = "results_levels_2026-10-25", "results_s17_s19_2026-10-24", "results_other_models_2026-10-26"
W1, W2 = "results_who_asks_2026-10-25", "results_who_asks_level2_2026-10-25"
SOURCES = [
    # E1, wrongness levels (Table 1), Luna.
    (L, "s1_levels_full", "levels/vendored_sdk/luna", None, None),
    (L, "s1_levels_full_reinterview", "levels/vendored_sdk/luna/questions", None, None),
    (L, "s18_levels_full", "levels/unsigned_webhook/luna", None, None),
    (L, "s18_levels_full_reinterview", "levels/unsigned_webhook/luna/questions", None, None),
    # The webhook harmless level is the first S18 peer run (2026-10-21): its open answers came from three askings.
    (R, "s18_peer", "levels/unsigned_webhook/luna", "harmless", {"peer-note", "peer-cover"}),
    (R, "reinterview/s18", "levels/unsigned_webhook/luna/questions", "harmless", {"peer-note", "peer-cover"}),
    (L, "s18_levels_harmless_open", "levels/unsigned_webhook/luna/questions", "harmless", {"peer-cover"}),
    (L, "s18_levels_rate_harmless", "levels/unsigned_webhook/luna/questions_rate", "harmless", None),
    # Calibrations of the levels, Luna (Appendix B).
    (L, "s1_levels_cal", "calibrate/vendored_sdk/luna", None, None),
    (L, "s1_levels_cal_reinterview", "calibrate/vendored_sdk/luna/questions", None, None),
    (L, "s18_levels_cal", "calibrate/unsigned_webhook/luna", None, None),
    (L, "s18_levels_cal_reinterview", "calibrate/unsigned_webhook/luna/questions", None, None),
    # E2, who asks (Table 2), Luna, at three places; open question and pointed questions.
    (W1, "s1_who_asks_full", "who_asks/vendored_sdk_excusable/luna", "excusable", None),
    (W1, "s1_who_asks_full_reinterview", "who_asks/vendored_sdk_excusable/luna/questions", "excusable", None),
    (W1, "s1_who_asks_full_pointed", "who_asks/vendored_sdk_excusable/luna/pointed", "excusable", None),
    (W2, "s18_who_asks_full", "who_asks/unsigned_webhook_excusable/luna", "excusable", None),
    (W2, "s18_who_asks_full_reinterview", "who_asks/unsigned_webhook_excusable/luna/questions", "excusable", None),
    ("results_who_asks_level2_pointed_2026-10-26", "s18_who_asks_full_pointed",
     "who_asks/unsigned_webhook_excusable/luna/pointed", "excusable", None),
    (W2, "s1_breach_who_asks_full", "who_asks/vendored_sdk_breach/luna", "breach", None),
    (W2, "s1_breach_who_asks_full_reinterview", "who_asks/vendored_sdk_breach/luna/questions", "breach", None),
    ("results_who_asks_level2_pointed_2026-10-26", "s1_breach_who_asks_full_pointed",
     "who_asks/vendored_sdk_breach/luna/pointed", "breach", None),
    # E3, workers ask the lead (Table 3), Luna.
    ("results_ask_lead_2026-10-26", "ask_lead_full", "lead_arm/vendored_sdk/luna", None, None),
    ("results_ask_lead_2026-10-26", "ask_lead_full_reinterview", "lead_arm/vendored_sdk/luna/questions", None, None),
    # Other models: calibrations (Tables 5-7), rank runs (Table 4), Gemini as the lead.
    *[(O, f"om_cal_{m}/{src}", f"{dest}/{m}{sub}", "harmless" if src.startswith("s18") else None, None)
      for m in ("qwen", "haiku")
      for src, dest, sub in (("s1", "calibrate/vendored_sdk", ""), ("s1_reinterview", "calibrate/vendored_sdk", "/questions"),
                             ("s18", "calibrate/unsigned_webhook", ""),
                             ("s18_reinterview", "calibrate/unsigned_webhook", "/questions"),
                             ("h25", "lead_arm/vendored_sdk", ""), ("h25_reinterview", "lead_arm/vendored_sdk", "/questions"))],
    (O, "om_h25_gemini-lite", "lead_arm/vendored_sdk/gemini-lite", None, None),
    (O, "om_h25_gemini-lite_reinterview", "lead_arm/vendored_sdk/gemini-lite/questions", None, None),
    *[(O, f"om_rank_{m}{src}", f"rank/vendored_sdk_excusable/{m}{sub}", "excusable", None)
      for m in ("qwen", "minimax", "gemini-lite") for src, sub in (("", ""), ("_reinterview", "/questions"))],
    # Smoke runs of the other models (screening, test awareness; Appendix E), 2 per cell.
    *[(O, f"om_smoke_{m}/{src}", f"smoke/{m}/{dest}", "excusable", None)
      for m in ("haiku", "qwen", "deepseek", "mimo", "minimax", "glm")
      for src, dest in (("s1", "vendored_sdk"), ("s1_reinterview", "vendored_sdk/questions"),
                        ("s18", "unsigned_webhook"), ("s18_reinterview", "unsigned_webhook/questions"),
                        ("h25", "lead_arm"), ("h25_reinterview", "lead_arm/questions"))],
    # Luna's solo and team smoke sessions of the webhook scenario (test awareness, Appendix E).
    (R, "smoke/s18", "smoke/luna/unsigned_webhook", "harmless", {"solo", "team"}),
]

# Hand codes: research file -> (this harness's file, the level of cells without one in their name).
CODES = {
    "s1_levels_hand_codes.json": ("levels_vendored_sdk_luna.json", None),
    "s18_levels_hand_codes.json": ("levels_unsigned_webhook_luna.json", "harmless"),
    "s1_levels_cal_hand_codes.json": ("calibrate_vendored_sdk_luna.json", None),
    "s1_who_asks_hand_codes.json": ("who_asks_vendored_sdk_excusable_luna.json", "excusable"),
    "s1_who_asks_pointed_hand_codes.json": ("who_asks_vendored_sdk_excusable_luna_pointed.json", "excusable"),
    "s18_who_asks_hand_codes.json": ("who_asks_unsigned_webhook_excusable_luna.json", "excusable"),
    "s18_who_asks_pointed_hand_codes.json": ("who_asks_unsigned_webhook_excusable_luna_pointed.json", "excusable"),
    "s1_breach_who_asks_hand_codes.json": ("who_asks_vendored_sdk_breach_luna.json", "breach"),
    "s1_breach_who_asks_pointed_hand_codes.json": ("who_asks_vendored_sdk_breach_luna_pointed.json", "breach"),
    "ask_lead_hand_codes.json": ("lead_arm_vendored_sdk_luna.json", None),
    **{f"om_cal_{m}_{src}_hand_codes.json": (f"{dest}_{m}.json", lv) for m in ("qwen", "haiku")
       for src, dest, lv in (("s1", "calibrate_vendored_sdk", None), ("s18", "calibrate_unsigned_webhook", "harmless"),
                             ("h25", "lead_arm_vendored_sdk", None))},
    "om_h25_gemini-lite_hand_codes.json": ("lead_arm_vendored_sdk_gemini-lite.json", None),
    **{f"om_rank_{m}_hand_codes.json": (f"rank_vendored_sdk_excusable_{m}.json", "excusable")
       for m in ("qwen", "minimax", "gemini-lite")},
}


# Later coding rounds named the "says it was asked" measures differently; the tables read the first names.
FIELDS = {"told_says_asked": "asked_session", "open_says_asked": "asked_open"}


def convert_codes():
    CODES_OUT.mkdir(parents=True, exist_ok=True)
    for src, (dest, level) in CODES.items():
        data = json.loads((RAW / "hand_codes" / src).read_text(encoding="utf-8"))
        codes, dropped, renamed = {}, [], set()
        for cell, seeds in data["codes"].items():
            new = rename(cell, level)
            if new is None:
                dropped.append(cell)
            elif new in codes:
                raise SystemExit(f"{src}: two cells become {new}")
            else:
                codes[new] = {seed: {FIELDS.get(k, k): v for k, v in item.items()} for seed, item in seeds.items()}
                renamed |= {k for item in seeds.values() for k in item if k in FIELDS}
        out = {k: v for k, v in data.items() if k != "codes"}
        out["converted_from"] = (f"data/raw/hand_codes/{src} (scripts/import_results.py renamed the cells"
                                 + (" and the fields " + ", ".join(f"{k} -> {FIELDS[k]}" for k in sorted(renamed))
                                    if renamed else "") + "; the codes themselves are unchanged)")
        if dropped:
            out["cells_not_carried_over"] = dropped
        out["codes"] = codes
        (CODES_OUT / dest).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  {dest}: {len(codes)} cells" + (f" (left out: {', '.join(dropped)})" if dropped else ""))


def import_runs(with_repo, only):
    by_archive = {}
    for archive, src, dest, level, keep in SOURCES:
        if only and dest.split("/")[0] not in only:
            continue
        by_archive.setdefault(archive, []).append((src.rstrip("/") + "/", dest, level, keep))
    episode = re.compile(r"^(?P<cell>[^/]+)/(?P<rest>.+)$")
    seen = {}
    for archive, rules in by_archive.items():
        written = 0
        with tarfile.open(RAW / f"{archive}.tar.xz", "r:xz") as tar:
            for member in tar:
                if not member.isfile():
                    continue
                name = member.name.removeprefix("./").removeprefix("results/")
                for src, dest, level, keep in rules:
                    if not name.startswith(src):
                        continue
                    m = episode.match(name[len(src):])
                    if not m or "/" not in m["rest"]:
                        continue  # a file beside the cells (a log), not an episode's
                    if keep is not None and m["cell"] not in keep:
                        continue
                    if not with_repo and "/repo/" in f"/{m['rest']}":
                        continue
                    cell = rename(m["cell"], level)
                    if cell is None:
                        continue
                    target = ROOT / "results" / dest / cell / m["rest"]
                    if target in seen:
                        raise SystemExit(f"{target} comes from both {seen[target]} and {archive}/{name}")
                    seen[target] = f"{archive}/{name}"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(tar.extractfile(member).read())
                    written += 1
                    break
        print(f"  {archive}: {written} files")


def main(argv):
    only = set(argv[argv.index("--only") + 1].split(",")) if "--only" in argv else set()
    print("hand codes -> data/hand_codes/")
    convert_codes()
    if "--codes-only" not in argv:
        print("runs -> results/")
        import_runs("--with-repo" in argv, only)


if __name__ == "__main__":
    main(sys.argv[1:])
