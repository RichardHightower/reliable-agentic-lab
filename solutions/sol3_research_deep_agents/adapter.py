"""A `doers.Backend` for this runtime port, copied flat into this folder.

`implementer.run()` in the reference loop takes any object shaped like
`Backend`: a `.name` and a `.run(*, repo, prompt, allow) -> DoerResult`. This
folder is standalone, so it does not import a shared engine for that shape, it
restates the two small pieces it needs and wraps the Deep Agents graph
behind them.

`deepagents` is not installed in this environment. The import stays inside
`build_agent()` (already true in `roles.py`), so `harness.py --table-only`
keeps working without it.
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
    out = subprocess.run(
        ["git", "diff", "--name-only"], cwd=repo, text=True, capture_output=True, check=False
    )
    return {line.strip() for line in out.stdout.splitlines() if line.strip()}


class DeepAgentsBackend(Backend):
    """Runs one role's prompt through the Deep Agents graph this folder builds."""

    name = "deep_agents"

    def __init__(self, agent):
        self.agent = agent

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> DoerResult:
        try:
            before = _changed_files(repo)
            result = self.agent.invoke({"messages": [{"role": "user", "content": prompt}]})
            after = _changed_files(repo)
            scope = WriteScope(allow=allow)
            wrote = sorted(path for path in (after - before) if scope.permits(path))
            return DoerResult(wrote=wrote, output=str(result))
        except Exception as exc:  # noqa: BLE001  (mirrors CliBackend.run: never raise, report it)
            return DoerResult(ok=False, output=f"deep_agents backend failed: {exc}")
