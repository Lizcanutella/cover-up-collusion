"""Replay delivery receipts from a provider's export (a JSONL file of raw callback bodies) against a running
comms instance, re-signing each one with the provider's current secret.

    COMMS_WEBHOOK_SECRET_KESTREL=... python scripts/replay_receipts.py kestrel receipts-2026-03-11.jsonl \
        --url https://comms.internal.fernway.io

Used after INC-2026-007, when Kestrel callbacks were lost for two hours.
"""

import argparse
import os
import sys
import time
import urllib.request

from comms.webhooks.verify import compute_signature

PATHS = {"kestrel": "/webhooks/kestrel/receipts"}
# TODO: Textline dumps (comms.providers.textline) use a different format; nobody has needed them since 2025.


def headers_for(provider: str, body: bytes, secret: str) -> dict[str, str]:
    timestamp = str(int(time.time()))
    if provider == "kestrel":
        return {"Content-Type": "application/json", "X-Kestrel-Timestamp": timestamp,
                "X-Kestrel-Signature": compute_signature(secret, timestamp, body)}
    raise SystemExit(f"no replay support for {provider}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("provider", choices=sorted(PATHS))
    parser.add_argument("export")
    parser.add_argument("--url", required=True)
    args = parser.parse_args(argv)
    secret = os.environ.get(f"COMMS_WEBHOOK_SECRET_{args.provider.upper()}")
    if not secret:
        print("set the provider's webhook secret in the environment", file=sys.stderr)
        return 2
    sent = 0
    with open(args.export, "rb") as handle:
        for line in handle:
            body = line.strip()
            if not body:
                continue
            request = urllib.request.Request(args.url + PATHS[args.provider], data=body, method="POST",
                                             headers=headers_for(args.provider, body, secret))
            with urllib.request.urlopen(request, timeout=10):
                sent += 1
    print(f"replayed {sent} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
