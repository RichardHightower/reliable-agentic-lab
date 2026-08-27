"""Deterministic exit check for the ticket enhancer plugin.

`check_fields.py` decides whether a ticket is ready, a fact computed from the
Judge's report. This script decides the other two exits SPEC.md names: budget
spent, and a stable failure (two rounds in a row find exactly the same
gaps). Given this round's {round, budget, signature, previous_signature}, it
computes {stop, reason} itself. The skill must not decide these by prose, the
same reason check_fields.py exists: a stop condition trusted to a model's own
judgment is a stop condition a model can talk itself past.

Usage:
    python3 check_stop.py '{"round": 2, "budget": 3, "signature": ["value"], "previous_signature": ["value"]}'
    echo '{...}' | python3 check_stop.py
"""

from __future__ import annotations

import json
import sys


def check(round_: int, budget: int, signature: list[str], previous_signature: list[str] | None) -> dict:
    if previous_signature is not None and signature == previous_signature:
        return {"stop": True, "reason": "same signature two rounds running"}
    if round_ + 1 >= budget:
        return {"stop": True, "reason": "budget spent"}
    return {"stop": False, "reason": None}


def main() -> None:
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    payload = json.loads(raw)
    result = check(
        payload["round"],
        payload["budget"],
        payload["signature"],
        payload.get("previous_signature"),
    )
    print(json.dumps(result))


def demo() -> None:
    assert check(0, 3, ["value"], None) == {"stop": False, "reason": None}
    assert check(1, 3, ["value"], ["other"]) == {"stop": False, "reason": None}
    assert check(1, 3, ["value"], ["value"]) == {
        "stop": True,
        "reason": "same signature two rounds running",
    }
    # round 2 is the third round (0-indexed); round + 1 == budget spends it,
    # even when this round's signature differs from the last one
    assert check(2, 3, ["value"], ["other"]) == {"stop": True, "reason": "budget spent"}
    print("check_stop: all demo assertions passed")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo()
    else:
        main()
