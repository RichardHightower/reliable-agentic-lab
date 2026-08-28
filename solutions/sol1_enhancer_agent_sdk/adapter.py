"""A `doers.Backend` for this folder's `ClaudeAgentOptions`.

Issue #2: this folder's `doers.py` `build(spec)` now accepts an already-built
`Backend` and passes it through unchanged, so a runtime port can plug in its
own doer. `Backend` and `DoerResult` are copied here rather than imported —
one more standalone folder, not a ninth shared file.

The SDK is optional and not installed in this environment, so the import
stays lazy (same style `roles.py` already uses for `AgentDefinition` et al.).
Nothing here is exercised without it: `python loop.py --table-only` never
touches this module's `run()`.
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
    proc = subprocess.run(
        ["git", "diff", "--name-only"], cwd=repo, text=True, capture_output=True, check=False
    )
    return set(proc.stdout.splitlines())


class AgentSdkBackend(Backend):
    """Runs the doer role through `claude_agent_sdk.query`.

    `options` is what this folder's `build(contract)` already returns.
    """

    name = "agent_sdk"

    def __init__(self, options):
        self.options = options

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> DoerResult:
        try:
            from claude_agent_sdk import query  # noqa: PLC0415  (optional dependency)

            scope = WriteScope(allow=list(allow))
            before = _changed_files(repo)

            async def collect() -> str:
                chunks = []
                async for message in query(prompt=prompt, options=self.options):
                    chunks.append(str(message))
                return "\n".join(chunks)

            output = asyncio.run(collect())
            wrote = [path for path in sorted(_changed_files(repo) - before) if scope.permits(path)]
            return DoerResult(wrote=wrote, output=output)
        except Exception as exc:  # graceful failure, the way CliBackend.run fails
            return DoerResult(ok=False, output=f"agent sdk backend failed: {exc}")
