"""A `loops/doers.Backend` implementation that wraps a Deep Agents agent.

`loops/doers.py`'s `build(spec)` now passes an already-built `Backend` object
through unchanged, which is what lets a runtime port plug in its own doer
without `loops/doers.py` ever importing it. This is that doer, for research.

    agent = roles.build_agent(contract, loop=LOOP)
    backend = DeepAgentsBackend(agent)
    result = backend.run(repo=repo, prompt=prompt, allow=role.allow)

ponytail: research produces a brief, not a code diff, so `wrote` is usually
empty here (the writer subagent lands `brief.md` under `work/research/**`,
which this reports if the agent actually touches it). A no-op stub would
satisfy the interface too; this version still tracks real file changes
because the shape costs nothing extra to fill in honestly.
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
        ["git", "diff", "--name-only"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    return set(out.stdout.split())


class DeepAgentsBackend(Backend):
    """Invokes a built Deep Agent (`roles.build_agent(...)`) and reports what changed.

    The `deepagents`/`langchain` import happens inside `roles.build_agent`, not
    here, so constructing this backend needs no SDK either, same as `roles.py`.
    """

    name = "deep_agents"

    def __init__(self, agent):
        self.agent = agent

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> DoerResult:
        try:
            before = _changed_files(repo)
            result = self.agent.invoke({"messages": [{"role": "user", "content": prompt}]})
            after = _changed_files(repo)
            scope = WriteScope(allow=allow)
            wrote = [path for path in sorted(after - before) if scope.permits(path)]
            return DoerResult(wrote=wrote, output=str(result)[-4000:])
        except Exception as exc:  # noqa: BLE001  (mirrors CliBackend.run's own catch-all)
            return DoerResult(ok=False, output=f"deep agents backend failed: {exc}")


if __name__ == "__main__":
    # No SDK, no live call: only the shape and the diff-snapshot helper.
    backend = DeepAgentsBackend(agent=None)
    assert backend.name == "deep_agents"
    assert isinstance(_changed_files(Path(__file__).parent), set)
    result = DoerResult()
    assert result.wrote == [] and result.ok is True
    print("ok")
