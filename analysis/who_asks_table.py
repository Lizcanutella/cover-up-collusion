"""Who asks: the peer arm's measures for the five who-asks cells at one level, with the tests.

Usage:
  .venv/bin/python analysis/who_asks_table.py --sessions DIR --interviews DIR [--codes HAND_CODES.json]
      [--blind OUT_PREFIX] [--scenario vendored_sdk] [--level excusable]

The cells are `<level>_<cell>` for no_request (the base), lead_informed, peer_asks_hide_from_user,
lead_asks_hide_from_user and both_ask_hide_from_user, plus peer_asks_hide_from_lead (shown, not tested) when present;
cells with no runs are left out, with their tests (so it also reads the `rank` runs of scripts/run_experiments.sh).
As analysis/levels_table.py (same first pass, codes format and
blind export). The measures `asked_session` and `asked_open` (worker_1 mentions the request) come from hand codes only.
Tests: Fisher exact (two-sided). The lead's request against the peer's is the confirmatory test; the five secondary
comparisons get Holm-adjusted p-values.
"""

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from levels_table import fisher  # noqa: E402
from coverup import primary  # noqa: E402

MEASURES = ("told", "named", "problem", "asked_session", "asked_open")


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adjusted, running = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(ps) - rank) * ps[i]))
        adjusted[i] = running
    return adjusted


def main(argv):
    def opt(name):
        return argv[argv.index(name) + 1] if name in argv else None
    level = opt("--level") or "excusable"
    base, informed, peer, lead, both = (f"{level}_{c}" for c in (
        "no_request", "lead_informed", "peer_asks_hide_from_user", "lead_asks_hide_from_user", "both_ask_hide_from_user"))
    cells = (base, informed, peer, lead, both, f"{level}_peer_asks_hide_from_lead")
    confirmatory = (lead, peer)
    secondary = [(peer, base), (lead, informed), (informed, base), (both, lead), (both, peer)]
    rules = primary.rules(opt("--scenario") or "vendored_sdk")
    runs = {}
    for events in sorted(Path(opt("--sessions")).glob("peer-*/*/ep*/events.jsonl")):
        cell, seed = events.parts[-4].removeprefix("peer-"), int(events.parts[-2][2:])
        if cell not in cells:
            continue
        if json.loads((events.parent / "score.json").read_text(encoding="utf-8")).get("end_reason") == "error":
            print(f"  excluded {cell} ep{seed}: the episode ended on an error")  # e.g. a provider refusal
            continue
        log = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
        runs[cell, seed] = {"told": primary.told_lead(log, rules), "_answers": {},
                            "_to_lead": "\n".join(e.get("text") or "" for e in log if e.get("kind") == "message"
                                                  and e.get("sender") == "worker_1" and e.get("recipient") == "lead")}
    for path in sorted(Path(opt("--interviews")).glob("peer-*/*/ep*/interview.json")):
        cell, seed = path.parts[-4].removeprefix("peer-"), int(path.parts[-2][2:])
        if (cell, seed) not in runs:
            continue
        rows = [r for r in primary.load_interview(path)["interview"] if r.get("actor", "worker_1") == "worker_1"]
        for row in rows:
            runs[cell, seed]["_answers"][row["level"]] = row.get("answer") or ""
        runs[cell, seed].update(primary.code_answers(rows, rules))
    codes = json.loads(Path(opt("--codes")).read_text())["codes"] if opt("--codes") else {}
    for (cell, seed), run in runs.items():
        run.update(codes.get(f"peer-{cell}", {}).get(str(seed), {}))

    if opt("--blind"):
        items = [("session", cell, seed, run["_to_lead"]) for (cell, seed), run in runs.items()]
        items += [(level, cell, seed, answer) for (cell, seed), run in runs.items()
                  for level, answer in run["_answers"].items() if level == "open"]
        random.Random(7).shuffle(items)
        prefix = opt("--blind")
        Path(f"{prefix}_blind.txt").write_text("\n".join(f"### b{i:03d} [{kind}]\n{text}\n"
                                                          for i, (kind, _, _, text) in enumerate(items)))
        Path(f"{prefix}_key.json").write_text(json.dumps({f"b{i:03d}": [kind, f"peer-{cell}", seed]
                                                          for i, (kind, cell, seed, _) in enumerate(items)}, indent=1))
        print(f"wrote {len(items)} items to {prefix}_blind.txt")

    count = {cell: {m: sum(bool(r.get(m)) for (c, _), r in runs.items() if c == cell) for m in MEASURES}
             for cell in cells}
    n = {cell: sum(c == cell for c, _ in runs) for cell in cells}
    cells = [cell for cell in cells if n[cell]]
    secondary = [(x, y) for x, y in secondary if n[x] and n[y]]
    print(f"{'cell':<35}{'n':>4}" + "".join(f"{m:>15}" for m in MEASURES))
    for cell in cells:
        print(f"{cell:<35}{n[cell]:>4}" + "".join(f"{count[cell][m]:>15}" for m in MEASURES))
    print("\nFisher exact (two-sided):")
    a, b = confirmatory
    for m in ("named", "told", "problem") if n[a] and n[b] else ():
        print(f"  confirmatory {a} vs {b}, {m}: {count[a][m]} vs {count[b][m]}, "
              f"p = {fisher(count[a][m], n[a], count[b][m], n[b]):.4g}")
    raw = [fisher(count[x]["named"], n[x], count[y]["named"], n[y]) for x, y in secondary]
    for (x, y), p, adj in zip(secondary, raw, holm(raw)):
        print(f"  secondary {x} vs {y}, named: {count[x]['named']} vs {count[y]['named']}, p = {p:.4g}, "
              f"Holm {adj:.4g}")


if __name__ == "__main__":
    main(sys.argv[1:])
