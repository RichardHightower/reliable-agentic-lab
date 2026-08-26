"""Backends that actually write code.

Three, so the loop can be taught and demonstrated without a model key:

    none        writes nothing. Proves the loop reports failure honestly.
    reference   copies a known-good answer. Runs offline, in front of a room.
    cli         shells out to the attendee's coding agent.

The loop does not care which one it holds. That is the point: the harness is
the product, and the thing that writes the code is swappable.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from loops.roles import WriteScope

CLI_COMMANDS = {
    "claude": ["claude", "-p", "{prompt}", "--allowedTools", "Read,Edit,Write,Bash,Glob,Grep"],
    "codex": ["codex", "exec", "{prompt}"],
    "grok": ["grok", "-p", "{prompt}", "--no-auto-update"],
    "opencode": ["opencode", "run", "{prompt}"],
}


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


class NoneBackend(Backend):
    """Writes nothing. The loop must still report the truth about the suite."""

    name = "none"

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> DoerResult:
        return DoerResult(output="none backend: wrote nothing on purpose")


class ReferenceBackend(Backend):
    """Copies files from a known-good git ref into the working tree.

    This is how the loop runs in a classroom with no key and no network. It is
    a stand-in for a model, never a substitute for one.
    """

    name = "reference"

    def __init__(self, ref: str = "known-good"):
        self.ref = ref

    def _files_in_ref(self, repo: Path) -> list[str]:
        listing = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", self.ref],
            cwd=repo,
            text=True,
            capture_output=True,
            check=False,
        )
        if listing.returncode != 0:
            return []
        return listing.stdout.splitlines()

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> DoerResult:
        scope = WriteScope(allow=allow)
        wrote: list[str] = []
        for relative in self._files_in_ref(repo):
            # The reference answer is still bound by the role's write scope.
            # A backend that ignores scope would make the whole split cosmetic.
            if not scope.permits(relative):
                continue
            blob = subprocess.run(
                ["git", "show", f"{self.ref}:{relative}"],
                cwd=repo,
                text=True,
                capture_output=True,
                check=False,
            )
            if blob.returncode != 0:
                continue
            target = repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_text(encoding="utf-8") == blob.stdout:
                continue
            target.write_text(blob.stdout, encoding="utf-8")
            wrote.append(relative)
        return DoerResult(wrote=wrote, output=f"copied {len(wrote)} files from {self.ref}")


class CliBackend(Backend):
    """Shells out to a coding agent. The attendee picks which one."""

    def __init__(self, tool: str, timeout: int = 900):
        if tool not in CLI_COMMANDS:
            raise ValueError(f"unknown tool {tool!r}. Choose from {sorted(CLI_COMMANDS)}")
        self.name = tool
        self.timeout = timeout

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> DoerResult:
        if shutil.which(CLI_COMMANDS[self.name][0]) is None:
            return DoerResult(ok=False, output=f"{self.name} is not on PATH")
        command = [part.replace("{prompt}", prompt) for part in CLI_COMMANDS[self.name]]
        proc = subprocess.run(
            command,
            cwd=repo,
            text=True,
            capture_output=True,
            timeout=self.timeout,
            check=False,
        )
        return DoerResult(
            ok=proc.returncode == 0,
            output=((proc.stdout or "") + (proc.stderr or ""))[-4000:],
        )


def build(spec: str) -> Backend:
    """`none`, `reference`, `reference:<ref>`, or a tool name."""
    if spec == "none":
        return NoneBackend()
    if spec.startswith("reference"):
        _, _, ref = spec.partition(":")
        return ReferenceBackend(ref or "known-good")
    return CliBackend(spec)
