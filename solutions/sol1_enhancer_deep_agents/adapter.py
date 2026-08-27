"""A `doers.Backend` for this folder's Deep Agents agent.

Issue #2: `loops/doers.py`'s `build(spec)` now accepts an already-built
`Backend` and passes it through unchanged, so a runtime port can plug in its
own doer. `Backend` and `DoerResult` are copied here rather than imported —
one more standalone folder, not a ninth shared file.

`deepagents` is already imported inside `roles.build_agent`, so there is
nothing extra to import lazily here. Nothing in this module is exercised by
`python loop.py --table-only`, which never calls `run()`.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from write_scope import WriteScope


@dataclass
class DoerResult:
    wrote: list[str] = field(default_factory=list)
    output: str = ""
    usd: float = 0.0
    ok: bool = True


class Backend:
    name = "backend"

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> DoerResult:
        raise NotImplementedError


def _changed_files(repo: Path) -> set[str]:
    proc = subprocess.run(
        ["git", "diff", "--name-only"], cwd=repo, text=True, capture_output=True, check=False
    )
    return set(proc.stdout.splitlines())


class DeepAgentsBackend(Backend):
    """Runs the doer role through a Deep Agents agent's `.invoke`.

    `agent` is what this folder's `build_agent(contract, loop=LOOP)` already
    returns.
    """

    name = "deep_agents"

    def __init__(self, agent):
        self.agent = agent

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> DoerResult:
        try:
            scope = WriteScope(allow=list(allow))
            before = _changed_files(repo)
            result = self.agent.invoke({"messages": [{"role": "user", "content": prompt}]})
            wrote = [path for path in sorted(_changed_files(repo) - before) if scope.permits(path)]
            return DoerResult(wrote=wrote, output=str(result))
        # Graceful failure, mirrors CliBackend.run. A backend that raises
        # takes the loop down with it.
        except Exception as exc:
            return DoerResult(ok=False, output=f"deep agents backend failed: {exc}")
