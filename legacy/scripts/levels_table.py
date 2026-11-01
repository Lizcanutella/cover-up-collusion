"""Wrongness levels: the peer arm's measures per level and request, with the tests (u1_levels_plan.md B).

Usage:
  .venv/bin/python scripts/levels_table.py SCENARIO --sessions DIR [DIR ...] --interviews DIR [DIR ...]
      [--codes data/<x>_hand_codes.json] [--blind OUT_PREFIX] [--rows]

Sessions are the peer arm's run folders (`<cell>/<model>/ep<seed>/events.jsonl`), interviews the reinterview folders
(`<cell>/<model>/ep<seed>/interview.json`); a run's open and rate answers may come from different folders. A cell
name says the level and the request: `peer-note`, `peer-cover`, `peer-cover_loyal` are the harmless level as first
run; `peer-<level>_<request>` the others.

First pass from the scenario's `primary` rules (upchain/primary.py). `--codes` replaces it with the hand codes
({"codes": {cell: {seed: {told, named, problem, rating}}}}, any subset). `--blind` writes every item to read (worker_1's
messages to the lead, the open and rate answers) shuffled, with the condition hidden, as OUT_PREFIX_blind.txt, and the
key as OUT_PREFIX_key.json.

Tests: Fisher exact (two-sided), each request against `note` within a level; and for adjacent levels, the
difference in the cover effect (cover minus note, on the primary), with a bootstrap 95 % interval and p, and the
permutation test H21 named (note/cover labels shuffled within each level). The permutation null is "no cover effect
at either level", so it rejects when the two effects differ by more than chance under that null; it is reported
alongside the bootstrap (user, 2026-10-25).
"""

import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from upchain import primary  # noqa: E402

LEVELS = ("harmless", "excusable", "breach")
MEASURES = ("told", "named", "problem")


def level_request(cell):
    condition = cell.removeprefix("peer-")
    for level in LEVELS:
        if condition.startswith(level + "_"):
            return level, condition[len(level) + 1:]
    return "harmless", condition


def fisher(a, n1, b, n2):
    """Two-sided Fisher exact p for a/n1 against b/n2."""
    k, n = a + b, n1 + n2
    def p(x):
        return math.comb(n1, x) * math.comb(n2, k - x) / math.comb(n, k)
    observed = p(a)
    return min(1.0, sum(p(x) for x in range(max(0, k - n2), min(k, n1) + 1) if p(x) <= observed * (1 + 1e-9)))


def bootstrap_did(cells, draws=10000, seed=0):
    """(cover1 - note1) - (cover0 - note0) for four lists of 0/1, with a percentile 95 % interval and a two-sided p
    (twice the share of draws on the far side of 0)."""
    rng = random.Random(seed)
    def did(groups):
        m = [sum(g) / len(g) for g in groups]
        return (m[3] - m[2]) - (m[1] - m[0])
    observed = did(cells)
    stats = sorted(did([[rng.choice(g) for _ in g] for g in cells]) for _ in range(draws))
    low, high = stats[int(0.025 * draws)], stats[int(0.975 * draws) - 1]
    far = sum(s <= 0 for s in stats) if observed > 0 else sum(s >= 0 for s in stats)
    return observed, low, high, min(1.0, 2 * far / draws)


def permutation_did(cells, draws=10000, seed=0):
    """The same difference as bootstrap_did, with a two-sided permutation p: within each level, the note and cover
    outcomes are pooled and re-split at random ((k + 1) / (draws + 1), k = draws at least as far from 0)."""
    rng = random.Random(seed)
    def did(groups):
        m = [sum(g) / len(g) for g in groups]
        return (m[3] - m[2]) - (m[1] - m[0])
    observed = did(cells)
    far = 0
    for _ in range(draws):
        shuffled = []
        for note, cover in ((cells[0], cells[1]), (cells[2], cells[3])):
            pool = note + cover
            rng.shuffle(pool)
            shuffled += [pool[:len(note)], pool[len(note):]]
        far += abs(did(shuffled)) >= abs(observed) - 1e-12
    return observed, (far + 1) / (draws + 1)


def main(argv):
    scenario = argv[0]
    def opt(name, many=False):
        if name not in argv:
            return [] if many else None
        i = argv.index(name) + 1
        values = []
        while i < len(argv) and not argv[i].startswith("--"):
            values.append(argv[i])
            i += 1
        return values if many else values[0]
    rules = primary.rules(scenario)
    runs = {}
    for root in map(Path, opt("--sessions", many=True)):
        for events in sorted(root.glob("peer-*/*/ep*/events.jsonl")):
            cell, seed = events.parts[-4], int(events.parts[-2][2:])
            if (cell, seed) in runs:
                raise SystemExit(f"{cell} ep{seed} is in more than one sessions folder")
            log = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
            runs[cell, seed] = {"told": primary.told_lead(log, rules), "_items": [], "_answers": {},
                                "_to_lead": "\n".join(e.get("text") or "" for e in log if e.get("kind") == "message"
                                                      and e.get("sender") == "worker_1" and e.get("recipient") == "lead")}
    for root in map(Path, opt("--interviews", many=True)):
        for path in sorted(root.glob("peer-*/*/ep*/interview.json")):
            cell, seed = path.parts[-4], int(path.parts[-2][2:])
            if (cell, seed) not in runs:
                continue
            rows = [r for r in primary.load_interview(path)["interview"] if r.get("actor", "worker_1") == "worker_1"]
            for row in rows:
                if row["level"] in runs[cell, seed]["_answers"]:
                    raise SystemExit(f"{cell} ep{seed} has two {row['level']} answers")
                runs[cell, seed]["_answers"][row["level"]] = row.get("answer") or ""
            runs[cell, seed].update(primary.code_answers(rows, rules))
    codes = json.loads(Path(opt("--codes")).read_text())["codes"] if opt("--codes") else {}
    for (cell, seed), run in runs.items():
        run.update(codes.get(cell, {}).get(str(seed), {}))

    if opt("--blind"):
        items = [("session", cell, seed, run["_to_lead"]) for (cell, seed), run in runs.items()]
        items += [(level, cell, seed, answer) for (cell, seed), run in runs.items()
                  for level, answer in run["_answers"].items() if level in ("open", "rate")]
        random.Random(7).shuffle(items)
        prefix = opt("--blind")
        Path(f"{prefix}_blind.txt").write_text("\n".join(f"### b{i:03d} [{kind}]\n{text}\n"
                                                          for i, (kind, _, _, text) in enumerate(items)))
        Path(f"{prefix}_key.json").write_text(json.dumps({f"b{i:03d}": [kind, cell, seed]
                                                          for i, (kind, cell, seed, _) in enumerate(items)}, indent=1))
        print(f"wrote {len(items)} items to {prefix}_blind.txt")

    table = defaultdict(list)
    for (cell, seed), run in sorted(runs.items()):
        table[level_request(cell)].append(run)
    print(f"{'level':<10}{'request':<13}{'n':>4}{'told':>8}{'named':>12}{'problem':>12}  rating (n, median, 5s)")
    for level in LEVELS:
        for (lv, request), group in sorted(table.items()):
            if lv != level:
                continue
            asked = [r for r in group if "named" in r]
            rated = sorted(r["rating"] for r in group if r.get("rating") is not None)
            median = rated[len(rated) // 2] if rated else "-"
            print(f"{level:<10}{request:<13}{len(group):>4}{sum(r['told'] for r in group):>8}"
                  f"{sum(r['named'] for r in asked):>7}/{len(asked):<4}{sum(r['problem'] for r in asked):>7}/{len(asked):<4}"
                  f"  {len(rated)}, {median}, {rated.count(5)}")
    print("\nFisher (two-sided), against note in the same level:")
    for (level, request), group in sorted(table.items()):
        base = table.get((level, "note"))
        if request == "note" or not base:
            continue
        for m in MEASURES:
            g, b = [r for r in group if m in r], [r for r in base if m in r]
            if g and b:
                print(f"  {level} {request} {m}: {sum(r[m] for r in g)}/{len(g)} vs {sum(r[m] for r in b)}/{len(b)}"
                      f"  p = {fisher(sum(r[m] for r in g), len(g), sum(r[m] for r in b), len(b)):.3g}")
    print("\nCover effect on the primary (cover - note), adjacent levels (bootstrap and permutation, 10 000 draws):")
    for low, high in zip(LEVELS, LEVELS[1:]):
        groups = [[int(r["named"]) for r in table.get((lv, rq), []) if "named" in r]
                  for lv in (low, high) for rq in ("note", "cover")]
        if all(groups):
            d, lo, hi, p = bootstrap_did(groups)
            effects = [sum(groups[i + 1]) / len(groups[i + 1]) - sum(groups[i]) / len(groups[i]) for i in (0, 2)]
            _, p_perm = permutation_did(groups)
            print(f"  {low} {effects[0]:+.2f} -> {high} {effects[1]:+.2f}: difference {d:+.2f} "
                  f"[{lo:+.2f}, {hi:+.2f}], p = {p:.3g}; permutation p = {p_perm:.3g}")
    if "--rows" in argv:
        for (cell, seed), run in sorted(runs.items()):
            print(cell, seed, {k: v for k, v in run.items() if not k.startswith("_")})


if __name__ == "__main__":
    main(sys.argv[1:])
