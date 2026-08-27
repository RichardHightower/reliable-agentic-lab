"""A `doers.Backend` for this runtime port, copied flat from `loops/doers.py`.

`implementer.run()` in the reference loop takes any object shaped like
`Backend`: a `.name` and a `.run(*, repo, prompt, allow) -> DoerResult`. This
folder is standalone, so it does not import `loops.doers` for that shape, it
restates the two small pieces it needs and wraps the Agent SDK behind them.

`claude_agent_sdk` is not installed in this environment. The import stays
inside `run()`, the same way `roles.py` already imports `ClaudeAgentOptions`
lazily, so `harness.py --table-only` keeps working without it.
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
        ["git", "diff", "--name-only"], cwd=repo, text=True, capture_output=True, check=False
    )
    return {line.strip() for line in out.stdout.splitlines() if line.strip()}


class AgentSdkBackend(Backend):
    """Runs one role's prompt through the Claude Agent SDK options this folder builds."""

    name = "agent_sdk"

    def __init__(self, options):
        self.options = options

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> DoerResult:
        try:
            from claude_agent_sdk import query  # noqa: PLC0415  (optional dependency)

            before = _changed_files(repo)

            async def _collect() -> str:
                chunks = []
                async for message in query(prompt=prompt, options=self.options):
                    chunks.append(str(message))
                return "\n".join(chunks)

            output = asyncio.run(_collect())
            after = _changed_files(repo)
            scope = WriteScope(allow=allow)
            wrote = sorted(path for path in (after - before) if scope.permits(path))
            return DoerResult(wrote=wrote, output=output)
        except Exception as exc:  # noqa: BLE001  (mirrors CliBackend.run: never raise, report it)
            return DoerResult(ok=False, output=f"agent_sdk backend failed: {exc}")
