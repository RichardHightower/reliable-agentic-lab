"""The five roles.

Write scope is the point. It is structural, not a rule in a prompt.

    Orchestrator      writes nothing. Owns the budget and the order.
    Planner           writes steps.jsonl. Runs in its own context.
    Doer              writes files inside a declared scope.
    Judge             writes nothing. Reads reports and the diff.

A `Judge` has no write method to call. That is why a judge cannot grade its own
homework: not because it was told not to, but because there is no path.

The code implementer and the test implementer are both `Doer`s with disjoint
scopes. The code implementer cannot weaken a test because `tests/**` is not in
its allow list.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath


class ScopeViolation(PermissionError):
    """A role tried to write outside its declared scope."""


def _matches(relative: str, patterns: list[str]) -> bool:
    """Glob match with `**` meaning "any depth", the way .loop.yml reads."""
    path = PurePosixPath(relative)
    for pattern in patterns:
        if fnmatch.fnmatch(relative, pattern):
            return True
        # `tests/**` should also match `tests/a.py`, not only `tests/a/b.py`.
        if pattern.endswith("/**") and (
            relative == pattern[:-3] or relative.startswith(pattern[:-2])
        ):
            return True
        if pattern == "**":
            return True
        try:
            if path.match(pattern):
                return True
        except ValueError:
            pass
    return False


@dataclass(frozen=True)
class WriteScope:
    """What one role may write. Deny always beats allow."""

    allow: list[str] = field(default_factory=list)
    deny: list[str] = field(default_factory=list)

    def permits(self, relative: str) -> bool:
        relative = str(PurePosixPath(relative))
        if _matches(relative, self.deny):
            return False
        return _matches(relative, self.allow)

    def check(self, relative: str) -> None:
        if not self.permits(relative):
            raise ScopeViolation(
                f"write to {relative} is outside this role's scope "
                f"(allow={self.allow or 'nothing'}, deny={self.deny or 'nothing'})"
            )


@dataclass
class Role:
    """A named participant in a loop."""

    name: str
    repo: Path

    def summary(self) -> str:
        return f"{self.__class__.__name__.lower()}:{self.name}"


@dataclass
class Judge(Role):
    """Scores work. Holds no write path.

    There is deliberately no `write` method on this class. Adding one is not a
    convenience, it is the end of the separation the harness depends on.
    """

    def read(self, relative: str) -> str:
        return (self.repo / relative).read_text(encoding="utf-8")


@dataclass
class Doer(Role):
    """Writes files, inside a scope it cannot widen."""

    scope: WriteScope = field(default_factory=WriteScope)

    def write(self, relative: str, text: str) -> Path:
        self.scope.check(relative)
        target = self.repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def read(self, relative: str) -> str:
        return (self.repo / relative).read_text(encoding="utf-8")

    def violations(self, changed: list[str]) -> list[str]:
        """Which of these paths this role was not allowed to write."""
        return [path for path in changed if not self.scope.permits(path)]


@dataclass
class Planner(Doer):
    """Writes the plan and nothing else. Runs as a subagent to save context."""


@dataclass
class Orchestrator(Role):
    """Owns the budget and the order. Writes nothing.

    It sees summaries, not whole diffs. That is what keeps the plan and the
    patch out of its context window.
    """

    budget_iterations: int = 3
    budget_usd: float = 2.0
    spent_usd: float = 0.0
    iteration: int = 0
    # #539, follow-up 7. `spent_usd` alone cannot tell "every turn answered
    # and cost nothing" from "we never heard a real number", the same silent
    # zero the ticket exists to kill, one level up. This count is the
    # difference: a trace with a nonzero count here has a `spent_usd` that
    # is a floor, not a total.
    unknown_spend_turns: int = 0
    # #562. One `spend` call is one turn, known-cost or not. `implementer.py`'s
    # `_checkpoint_spend` reads this to number each `turns.jsonl` row -- pure
    # bookkeeping, still no write, the same as `spent_usd` above.
    turns: int = 0

    def start_iteration(self) -> int:
        self.iteration += 1
        return self.iteration

    @property
    def iterations_left(self) -> int:
        return max(0, self.budget_iterations - self.iteration)

    @property
    def usd_left(self) -> float:
        return max(0.0, self.budget_usd - self.spent_usd)

    def spend(self, usd: float | None) -> None:
        # #539. `None` means the backend never answered (a timed-out query,
        # a raised exception), not that the turn was free. The budget still
        # has to keep moving, so an unknown turn spends 0.0 against it; the
        # trace reports the `None` itself, never a silent 0.0, so a reader
        # can tell "cost nothing" from "we do not know".
        self.turns += 1
        if usd is None:
            self.unknown_spend_turns += 1
            return
        # #546. The SDK has never reported a negative cost, but nothing
        # stops a malformed one from arriving; a bare `+=` would let it walk
        # `spent_usd` backwards and loosen `usd_left` below. `max(usd, 0.0)`
        # is the same clamp `AgentSdkE2EBackend._bookkeep` already carries in
        # e2e_t001.py, one level up from this backend-agnostic role.
        self.spent_usd += max(usd, 0.0)

    @property
    def exhausted(self) -> bool:
        return self.iterations_left <= 0 or self.usd_left <= 0


def build(contract, repo: Path | None = None) -> dict[str, Role]:
    """Make every role for one target repo, scoped from its .loop.yml."""
    root = Path(repo or contract.repo)

    def scope(name: str) -> WriteScope:
        config = contract.role(name)
        return WriteScope(
            allow=list(config.get("write_allow") or []),
            deny=list(config.get("write_deny") or []),
        )

    budget = contract.budget
    return {
        "orchestrator": Orchestrator(
            name="orchestrator",
            repo=root,
            budget_iterations=int(budget.get("iterations", 3)),
            budget_usd=float(budget.get("usd", 2.0)),
        ),
        "planner": Planner(name="planner", repo=root, scope=scope("planner")),
        "test_implementer": Doer(
            name="test_implementer", repo=root, scope=scope("test_implementer")
        ),
        "code_implementer": Doer(
            name="code_implementer", repo=root, scope=scope("code_implementer")
        ),
        "judge": Judge(name="judge", repo=root),
    }
