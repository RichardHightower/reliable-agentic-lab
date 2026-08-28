#!/usr/bin/env python3
"""Sign a GitHub-shaped JSON body with GITHUB_WEBHOOK_SECRET. Smoke tests use this."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys


def main() -> int:
    secret = (os.environ.get("GITHUB_WEBHOOK_SECRET") or "").encode()
    if not secret:
        print("GITHUB_WEBHOOK_SECRET is empty", file=sys.stderr)
        return 1
    body = sys.stdin.buffer.read()
    if not body:
        body = json.dumps(
            {
                "action": "opened",
                "issue": {
                    "number": 1,
                    "title": "[T001] smoke",
                    "body": "id: T001",
                    "labels": [],
                },
            }
        ).encode()
    digest = hmac.new(secret, body, hashlib.sha256).hexdigest()
    sys.stdout.buffer.write(body)
    print(f"\nsha256={digest}", file=sys.stderr)
    print(f"X-Hub-Signature-256: sha256={digest}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
