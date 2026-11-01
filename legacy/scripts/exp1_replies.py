"""Every lead reply to worker_1 after its report, one line each, for hand-coding experiment 1.

    python scripts/exp1_replies.py [results/exp1] [WIDTH]
"""

import json
import sys
from pathlib import Path

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("results/exp1")
width = int(sys.argv[2]) if len(sys.argv) > 2 else 220
for ep in sorted(root.glob("handle-*/*/ep*"), key=lambda p: (p.parent.parent.name, int(p.name[2:]))):
    if not (ep / "score.json").exists():
        continue
    events = [json.loads(line) for line in (ep / "events.jsonl").read_text().splitlines()]
    score = json.loads((ep / "score.json").read_text())
    report = next(e["seq"] for e in events if e.get("channel") == "to_lead" and e.get("sender") == "worker_1")
    first_write = next((e["seq"] for e in events if e.get("kind") == "tool" and e.get("protected") and e.get("ok")
                        and e["tool"] == "write_file"), None)
    tag = f"{ep.parent.parent.name.removeprefix('handle-')} {ep.name}"
    print(f"{tag:20} edited={'Y' if score.get('protected_changes') else 'n'}")
    for e in events:
        if e["seq"] <= report:
            continue
        if e.get("channel") == "reply" and e.get("recipient") == "worker_1":
            mark = "*" if first_write and e["seq"] < first_write else " "
            print(f"   {mark}R {e['text'][:width]!r}")
        elif e.get("channel") == "ask_user":
            print(f"    U? {e['text'][:width]!r}")
        elif e.get("channel") == "assign" and "vendor" in e["text"]:
            print(f"    A>{e['recipient']} {e['text'][:width]!r}")
