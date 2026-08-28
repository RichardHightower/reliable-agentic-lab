"""steps.jsonl. The planner's only output.

One step per line. Every step carries a validation statement, because a step
you cannot check is a wish.

    {"id": "S1", "ticket": "T001", "role": "test_implementer",
     "action": "Add a test that a Task has a nullable due_date column",
     "validation": "tests/test_due_date.py::test_model_has_optional_due_date fails",
     "criterion": "AC-2", "status": "todo", "evidence": null}

The file is disposable. It belongs to one run against one ticket. Project work
tracking is a different thing with a different lifetime, and mixing them makes
both worse.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

TODO, DOING, DONE, BLOCKED = "todo", "doing", "done", "blocked"
STATUSES = (TODO, DOING, DONE, BLOCKED)
ROLES = ("test_implementer", "code_implementer")

STEPS_FILE = "steps.jsonl"


class PlanRejected(ValueError):
    """The plan does not meet the contract. The orchestrator refuses to run it."""


@dataclass
class Step:
    id: str
    ticket: str
    role: str
    action: str
    validation: str
    criterion: str = ""
    status: str = TODO
    evidence: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)

    @property
    def done(self) -> bool:
        return self.status == DONE


@dataclass
class Plan:
    """An ordered list of steps for one ticket."""

    steps: list[Step] = field(default_factory=list)
    path: Path | None = None

    # -- persistence --------------------------------------------------------

    @classmethod
    def load(cls, repo: Path, name: str = STEPS_FILE) -> Plan:
        path = Path(repo) / name
        if not path.exists():
            raise PlanRejected(f"no {name} in {repo}. The planner did not run.")
        steps = []
        for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except ValueError as exc:
                raise PlanRejected(f"{name} line {number} is not valid JSON: {exc}") from exc
            known = {f: raw.get(f) for f in Step.__dataclass_fields__}
            missing = [
                f for f in ("id", "ticket", "role", "action", "validation") if not known.get(f)
            ]
            if missing:
                raise PlanRejected(f"{name} line {number} is missing: {', '.join(missing)}")
            steps.append(Step(**known))
        return cls(steps=steps, path=path)

    def save(self, repo: Path, name: str = STEPS_FILE) -> Path:
        path = Path(repo) / name
        path.write_text("\n".join(s.to_json() for s in self.steps) + "\n", encoding="utf-8")
        self.path = path
        return path

    # -- the contract -------------------------------------------------------

    def validate(self, criteria: list[str] | None = None) -> None:
        """Raise unless this plan is runnable. The orchestrator calls this first."""
        if not self.steps:
            raise PlanRejected("the plan has no steps")

        seen: set[str] = set()
        for step in self.steps:
            if step.id in seen:
                raise PlanRejected(f"duplicate step id: {step.id}")
            seen.add(step.id)
            if not step.validation.strip():
                raise PlanRejected(
                    f"step {step.id} has no validation statement. "
                    "A step you cannot check is a wish, not a step."
                )
            if step.role not in ROLES:
                raise PlanRejected(f"step {step.id} has an unknown role: {step.role!r}")
            if step.status not in STATUSES:
                raise PlanRejected(f"step {step.id} has an unknown status: {step.status!r}")

        if not any(s.role == "test_implementer" for s in self.steps):
            raise PlanRejected("no step writes a test. Tests come first.")

        if criteria:
            covered = {s.criterion for s in self.steps if s.criterion}
            uncovered = [c for c in criteria if c not in covered]
            if uncovered:
                raise PlanRejected(
                    "these acceptance criteria map to no step: " + ", ".join(uncovered)
                )

    # -- progress -----------------------------------------------------------

    def for_role(self, role: str) -> list[Step]:
        return [s for s in self.steps if s.role == role and s.status != DONE]

    def get(self, step_id: str) -> Step:
        for step in self.steps:
            if step.id == step_id:
                return step
        raise KeyError(step_id)

    def mark(self, step_id: str, status: str, evidence: str | None = None) -> Step:
        """Move a step. Marking one done without evidence is refused."""
        if status not in STATUSES:
            raise PlanRejected(f"unknown status: {status!r}")
        step = self.get(step_id)
        if status == DONE and not evidence:
            raise PlanRejected(
                f"step {step.id} cannot be done without evidence. "
                "Name the test id, or the loop is grading itself on a claim."
            )
        step.status = status
        step.evidence = evidence
        if self.path:
            self.save(self.path.parent, self.path.name)
        return step

    @property
    def complete(self) -> bool:
        return bool(self.steps) and all(s.done for s in self.steps)

    def unfinished(self) -> list[Step]:
        return [s for s in self.steps if not s.done]

    def summary(self) -> str:
        """What the orchestrator sees. Never the whole plan."""
        counts = dict.fromkeys(STATUSES, 0)
        for step in self.steps:
            counts[step.status] += 1
        parts = [f"{name} {counts[name]}" for name in STATUSES if counts[name]]
        return f"{len(self.steps)} steps: " + ", ".join(parts)
