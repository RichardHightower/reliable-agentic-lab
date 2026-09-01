"""Deterministic exit check for the ticket enhancer plugin.

`check_fields.py` decides whether a ticket is ready, a fact computed from the
Judge's report. This script decides the other exits SPEC.md names: budget
spent, a dollar cap when the CLI reports spend, and a stable failure (two
rounds in a row find exactly the same gaps). Given this round's
{round, budget, signature, previous_signature, usd, max_usd}, it computes
{stop, reason} itself. The skill must not decide these by prose.

Usage:
    python3 check_stop.py '{"round": 2, "budget": 3, "signature": ["value"], "previous_signature": ["value"]}'
    echo '{...}' | python3 check_stop.py
"""

from __future__ import annotations

import json
import sys


def check(
    round_: int,
    budget: int,
    signature: list[str],
    previous_signature: list[str] | None,
    usd: float = 0.0,
    max_usd: float | None = None,
) -> dict:
    if previous_signature is not None and signature == previous_signature:
        return {"stop": True, "reason": "same signature two rounds running"}
    if max_usd is not None and usd >= max_usd:
        return {"stop": True, "reason": "cost budget spent"}
    if round_ + 1 >= budget:
        return {"stop": True, "reason": "budget spent"}
    return {"stop": False, "reason": None}


def main() -> None:
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    payload = json.loads(raw)
    max_usd = payload.get("max_usd")
    result = check(
        payload["round"],
        payload["budget"],
        payload["signature"],
        payload.get("previous_signature"),
        usd=float(payload.get("usd") or 0.0),
        max_usd=None if max_usd is None else float(max_usd),
    )
    print(json.dumps(result))


def demo() -> None:
    assert check(0, 3, ["value"], None) == {"stop": False, "reason": None}
    assert check(1, 3, ["value"], ["other"]) == {"stop": False, "reason": None}
    assert check(1, 3, ["value"], ["value"]) == {
        "stop": True,
        "reason": "same signature two rounds running",
    }
    assert check(2, 3, ["value"], ["other"]) == {"stop": True, "reason": "budget spent"}
    assert check(0, 3, ["value"], None, usd=2.0, max_usd=2.0) == {
        "stop": True,
        "reason": "cost budget spent",
    }
    # No dollar figure from the CLI means the round budget is the only spend
    # control. Do not invent a cap the platform cannot measure.
    assert check(0, 3, ["value"], None, usd=9.0, max_usd=None) == {
        "stop": False,
        "reason": None,
    }
    print("check_stop: all demo assertions passed")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo()
    else:
        main()
