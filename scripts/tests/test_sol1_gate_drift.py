"""Pin shared check-script behavior across every sol1_enhancer* port.

A checksum fails on a comment edit and teaches nothing. Group by behavior.
Expected exceptions live in one dict with the issue that records the reason.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOLUTIONS = ROOT / "solutions"

# Ports that deliberately differ, with the issue that records why.
# An empty set means no exceptions: every port must share the behavior.
DELIBERATE = {
    # none: #275 restored the failure-hash exit on deep_agents.
    "no_signature_exit": set(),
    # Skill-form ports measure cost only when the CLI reports spend
    # (max_usd in the payload). Python ports always have a dollar cap.
    # Both groups have the cost *check*. See #276.
    "no_cost_check": set(),
    # none: #277 made source_evidence required on every port.
    "no_source_evidence": set(),
}


def _ports() -> list[Path]:
    return sorted(p for p in SOLUTIONS.glob("sol1_enhancer*") if p.is_dir())


def _port_of(path: Path) -> str:
    for parent in path.parents:
        if parent.parent == SOLUTIONS and parent.name.startswith("sol1_enhancer"):
            return parent.name
    raise AssertionError(f"not under a sol1 port: {path}")


def _scripts(name: str) -> list[Path]:
    return sorted(SOLUTIONS.glob(f"sol1_enhancer*/**/{name}")) + sorted(
        SOLUTIONS.glob(f"sol1_enhancer*/{name}")
    )


def test_every_sol1_port_has_a_check_stop():
    ports = {p.name for p in _ports()}
    found = {_port_of(p) for p in _scripts("check_stop.py")}
    assert ports <= found, f"ports missing check_stop.py: {ports - found}"


def test_every_sol1_port_has_a_check_fields():
    ports = {p.name for p in _ports()}
    found = {_port_of(p) for p in _scripts("check_fields.py")}
    assert ports <= found, f"ports missing check_fields.py: {ports - found}"


def test_the_stop_rule_does_not_drift_inside_its_group():
    for path in _scripts("check_stop.py"):
        text = path.read_text(encoding="utf-8")
        has_signature = "previous_signature" in text
        port = _port_of(path)
        expect = port not in DELIBERATE["no_signature_exit"]
        assert has_signature is expect, (
            f"{port} signature exit is {has_signature}, expected {expect} (#275)"
        )


def test_the_cost_check_does_not_drift_inside_its_group():
    for path in _scripts("check_stop.py"):
        text = path.read_text(encoding="utf-8")
        has_cost = "max_usd" in text or "spent_usd" in text
        port = _port_of(path)
        expect = port not in DELIBERATE["no_cost_check"]
        assert has_cost is expect, (
            f"{port} cost check is {has_cost}, expected {expect} (#276)"
        )


def test_the_bug_rubric_does_not_drift_inside_its_group():
    for path in _scripts("check_fields.py"):
        text = path.read_text(encoding="utf-8")
        has = "source_evidence" in text
        port = _port_of(path)
        expect = port not in DELIBERATE["no_source_evidence"]
        assert has is expect, (
            f"{port} source_evidence is {has}, expected {expect} (#277)"
        )
