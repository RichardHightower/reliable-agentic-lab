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


class RefNotFound(RuntimeError):
    """The reference answer is not in this repo."""


class ReferenceBackend(Backend):
    """Copies files from a known-good git ref into the working tree.

    This is how the loop runs in a classroom with no key and no network. It is
    a stand-in for a model, never a substitute for one.
    """

    name = "reference"

    def __init__(self, ref: str = "known-good"):
        self.ref = ref

    def _resolve(self, repo: Path) -> str:
        """The ref, or its remote-tracking twin.

        A fresh `git clone` creates one local branch. `known-good` exists only
        as `origin/known-good`, and `git ls-tree known-good` fails there. Trying
        both is what lets an attendee run this on the clone they made this
        morning.
        """
        for candidate in (self.ref, f"origin/{self.ref}"):
            found = subprocess.run(
                ["git", "rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}"],
                cwd=repo,
                text=True,
                capture_output=True,
                check=False,
            )
            if found.returncode == 0:
                return candidate
        raise RefNotFound(
            f"no ref named {self.ref!r} or 'origin/{self.ref}' in {repo}. "
            f"The reference doer has nothing to copy from. "
            f"Run `git -C {repo} fetch origin` and try again."
        )

    def _files_in_ref(self, repo: Path, ref: str) -> list[str]:
        listing = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", ref],
            cwd=repo,
            text=True,
            capture_output=True,
            check=False,
        )
        # Returning an empty list here would make the doer report success while
        # writing nothing, which is the exact failure this workshop is about.
        if listing.returncode != 0:
            raise RefNotFound(f"cannot read {ref} in {repo}: {listing.stderr.strip()}")
        return listing.stdout.splitlines()

    def run(self, *, repo: Path, prompt: str, allow: list[str]) -> DoerResult:
        ref = self._resolve(repo)
        scope = WriteScope(allow=allow)
        wrote: list[str] = []
        for relative in self._files_in_ref(repo, ref):
            # The reference answer is still bound by the role's write scope.
            # A backend that ignores scope would make the whole split cosmetic.
            if not scope.permits(relative):
                continue
            blob = subprocess.run(
                ["git", "show", f"{ref}:{relative}"],
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
        return DoerResult(wrote=wrote, output=f"copied {len(wrote)} files from {ref}")


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
