"""Print each episode's message thread, with protected writes interleaved (for reading team episodes by hand).

    python analysis/threads.py RESULTS_DIR [WIDTH] [SKIP_CHANNELS]  # e.g. results/runs/lead-breach_no_request 400 task
"""

import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
width = int(sys.argv[2]) if len(sys.argv) > 2 else 400
skip = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else {"task"}
for ep in sorted(p.parent for p in root.rglob("events.jsonl")):
    events = [json.loads(line) for line in (ep / "events.jsonl").read_text().splitlines()]
    score = json.loads((ep / "score.json").read_text()) if (ep / "score.json").exists() else {}
    print(f"######### {ep.relative_to(root)}  outcome={score.get('outcome')}  protected={list(score.get('protected_changes', {}))}"
          f"  acted_first={score.get('wrote_before_escalating')}  cost=${score.get('cost_usd') or 0:.4f}")
    writes = None
    for e in events:
        if e.get("kind") == "tool" and e.get("ok") and e.get("protected") and e.get("tool") in ("write_file", "edit_file", "delete_file"):
            if writes and writes[0] == e["actor"]:
                writes[1] += 1
                continue
            if writes:
                print(f"  [..] {writes[0]} WROTE protected x{writes[1]}")
            writes = [e["actor"], 1]
            continue
        if e.get("kind") == "message" and e["channel"] not in skip:
            if writes:
                print(f"  [..] {writes[0]} WROTE protected x{writes[1]}")
                writes = None
            print(f"  [{e['seq']}] {e['channel']} {e.get('sender')}->{e.get('recipient')}: {e['text'][:width]!r}")
    if writes:
        print(f"  [..] {writes[0]} WROTE protected x{writes[1]}")
