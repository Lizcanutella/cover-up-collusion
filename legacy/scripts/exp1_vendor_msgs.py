"""Every lead message to a worker that mentions vendor/, after worker_1's report, plus ask_user and the final
report's vendor sentences: the view used to hand-code experiment 1.

    python scripts/exp1_vendor_msgs.py CONDITION [WIDTH] [results/exp1]
"""

import json
import re
import sys
from pathlib import Path

cond = sys.argv[1]
width = int(sys.argv[2]) if len(sys.argv) > 2 else 170
root = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("results/exp1")
for ep in sorted((root / f"handle-{cond}").glob("*/ep*"), key=lambda p: int(p.name[2:])):
    events = [json.loads(line) for line in (ep / "events.jsonl").read_text().splitlines()]
    score = json.loads((ep / "score.json").read_text())
    report = next(e["seq"] for e in events if e.get("channel") == "to_lead" and e.get("sender") == "worker_1")
    writes = [e["seq"] for e in events if e.get("kind") == "tool" and e.get("protected") and e.get("ok")
              and e["tool"] == "write_file"]
    print(f"{ep.name} edited={'Y@' + str(writes[0]) if writes else 'n'}")
    for e in events:
        if e["seq"] <= report or e.get("sender") != "lead" and e.get("channel") != "user_reply":
            continue
        text = e.get("text", "")
        if e.get("channel") in ("reply", "assign") and re.search(r"vendor", text, re.IGNORECASE):
            print(f"  {e['seq']:>3} {e['channel'][:3]}>{e['recipient'][-1]} {text[:width]!r}")
        elif e.get("channel") == "ask_user":
            print(f"  {e['seq']:>3} ASK {text[:width]!r}")
        elif e.get("channel") == "final_report":
            vendor = " ".join(s for s in re.split(r"(?<=[.!?])\s+", text) if re.search(r"vendor|payments.sdk", s, re.IGNORECASE))
            print(f"  {e['seq']:>3} FIN {vendor[:width + 150]!r}")
