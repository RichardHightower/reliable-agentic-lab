"""Deterministic exit check for the ticket enhancer.

`check_fields.py` decides whether a ticket is ready, a fact computed from the
Judge's report. This script decides the three loop exits: done, cost, and max
turns. A repeated missing-field signature is stuck work. It is not an exit.
Stuck work burns turns or dollars until one of those three fires.

Given {done, turns, max_turns, spent_usd, max_usd}, it computes {stop, reason}
itself. The skill must not decide these by prose, the same reason
check_fields.py exists: a stop condition trusted to a model's own judgment is
a stop condition a model can talk itself past.

Usage:
    python3 check_stop.py '{"done": false, "turns": 2, "max_turns": 3, "spent_usd": 0.4, "max_usd": 2.0}'
    echo '{...}' | python3 check_stop.py
"""

from __future__ import annotations

import json
import sys


def check(
    *,
    done: bool,
    turns: int,
    max_turns: int,
    spent_usd: float = 0.0,
    max_usd: float = 2.0,
) -> dict:
    """Three exits, and no fourth. Done first, then cost, then max turns."""
    if done:
        return {"stop": True, "reason": "done"}
    if spent_usd >= max_usd:
        return {"stop": True, "reason": "cost"}
    if turns + 1 >= max_turns:
        return {"stop": True, "reason": "max turns"}
    return {"stop": False, "reason": None}


def main() -> None:
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    payload = json.loads(raw)
    result = check(
        done=bool(payload.get("done")),
        turns=int(payload["turns"]),
        max_turns=int(payload["max_turns"]),
        spent_usd=float(payload.get("spent_usd", 0.0)),
        max_usd=float(payload.get("max_usd", 2.0)),
    )
    print(json.dumps(result))


def demo() -> None:
    assert check(done=False, turns=0, max_turns=3) == {"stop": False, "reason": None}
    assert check(done=False, turns=1, max_turns=3, spent_usd=0.4, max_usd=2.0) == {
        "stop": False,
        "reason": None,
    }
    assert check(done=True, turns=0, max_turns=3) == {"stop": True, "reason": "done"}
    # Done beats a spent cost cap and a spent turn cap.
    assert check(done=True, turns=2, max_turns=3, spent_usd=9.0, max_usd=2.0) == {
        "stop": True,
        "reason": "done",
    }
    assert check(done=False, turns=0, max_turns=3, spent_usd=2.0, max_usd=2.0) == {
        "stop": True,
        "reason": "cost",
    }
    # Cost beats max turns when both would fire.
    assert check(done=False, turns=2, max_turns=3, spent_usd=2.0, max_usd=2.0) == {
        "stop": True,
        "reason": "cost",
    }
    # round 2 is the third round (0-indexed); turns + 1 == max_turns spends it
    assert check(done=False, turns=2, max_turns=3, spent_usd=0.1, max_usd=2.0) == {
        "stop": True,
        "reason": "max turns",
    }
    print("check_stop: all demo assertions passed")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo()
    else:
        main()
