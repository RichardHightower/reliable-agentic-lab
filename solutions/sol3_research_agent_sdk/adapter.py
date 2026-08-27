"""A `loops/doers.Backend` implementation that wraps the Agent SDK.

`loops/doers.py`'s `build(spec)` now passes an already-built `Backend` object
through unchanged, which is what lets a runtime port plug in its own doer
without `loops/doers.py` ever importing it. This is that doer, for research.

    backend = AgentSDKBackend(build(contract))
    result = backend.run(repo=repo, prompt=prompt, allow=role.allow)

ponytail: research produces a brief, not a code diff, so `wrote` is usually
empty here (the writer role lands `brief.md` under `work/research/**`, which
this reports if the SDK actually touches it). A no-op stub would satisfy the
interface too; this version still tracks real file changes because the shape
costs nothing extra to fill in honestly.
"""

from __future__ import annotations

import asyncio
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


class AgentSDKBackend(Backend):
    """Runs one Agent SDK query under this loop's options.

    `options` is whatever `build(contract)` in `loop.py` returned
    (`ClaudeAgentOptions`). The SDK import is lazy, same as `roles.py`: the
    workshop's own tests run with no SDK installed.
    """

    name = "agent_sdk"

    def __init__(self, options):
        self.options = options

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> DoerResult:
        try:
            from claude_agent_sdk import query  # noqa: PLC0415  (optional dependency)

            before = _changed_files(repo)

            async def _go() -> str:
                chunks = []
                async for message in query(prompt=prompt, options=self.options):
                    chunks.append(str(message))
                return "".join(chunks)

            output = asyncio.run(_go())
            after = _changed_files(repo)
            scope = WriteScope(allow=allow)
            wrote = [path for path in sorted(after - before) if scope.permits(path)]
            return DoerResult(wrote=wrote, output=output[-4000:])
        except Exception as exc:  # noqa: BLE001  (mirrors CliBackend.run's own catch-all)
            return DoerResult(ok=False, output=f"agent sdk backend failed: {exc}")


if __name__ == "__main__":
    # No SDK, no live call: only the shape and the diff-snapshot helper.
    backend = AgentSDKBackend(options=None)
    assert backend.name == "agent_sdk"
    assert isinstance(_changed_files(Path(__file__).parent), set)
    result = DoerResult()
    assert result.wrote == [] and result.ok is True
    print("ok")
