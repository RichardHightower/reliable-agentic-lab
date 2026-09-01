"""Run the Lab 1 enhancer as a subprocess.

The webhook does not import solutions/sol1_enhancer. That folder is standalone.
This file only picks a folder and shells out to `task run`.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable, Protocol

from solutions.extra_credit import ROOT

# AGENT_BACKEND -> folder under solutions/. Default is the Claude Code plugin
# the Droplet is meant to call: solutions/sol1_enhancer.
# Canonical backend keys. The Actions workflow uses the same names via
# ENHANCER_BACKEND (accepted as an alias of AGENT_BACKEND). Keep these
# lists equal: scripts/tests/test_sol1_backend_dispatch.py pins it.
BACKEND_FOLDERS = {
    "claude": "sol1_enhancer",
    "python": "sol1_enhancer",
    "grok": "sol1_enhancer_grok_build",
    "opencode": "sol1_enhancer_opencode",
    "codex": "sol1_enhancer_codex",
    "vscode": "sol1_enhancer_vscode",
    "copilot-cli": "sol1_enhancer_copilot_cli",
    "antigravity": "sol1_enhancer_antigravity",
    "agent-sdk": "sol1_enhancer_agent_sdk",
    "deep-agents": "sol1_enhancer_deep_agents",
    "langgraph": "sol1_enhancer_deep_agents",
}


class Runner(Protocol):
    def __call__(self, *, ticket_id: str, backend: str, cwd: Path) -> dict: ...


def backend_name() -> str:
    raw = os.environ.get("AGENT_BACKEND") or os.environ.get("ENHANCER_BACKEND") or "claude"
    return raw.strip().lower()


def folder_for(backend: str) -> str:
    name = BACKEND_FOLDERS.get(backend)
    if name is None:
        known = ", ".join(sorted(BACKEND_FOLDERS))
        raise SystemExit(f"unknown backend {backend!r}. Known: {known}")
    return name


def sol1_dir(root: Path | None = None, backend: str | None = None) -> Path:
    root = root or ROOT
    return root / "solutions" / folder_for(backend or backend_name())


def command_for(ticket_id: str) -> list[str]:
    return ["task", "run", "--", "--ticket", ticket_id]


def run_sol1(
    ticket_id: str,
    *,
    backend: str | None = None,
    root: Path | None = None,
    runner: Callable[..., dict] | None = None,
    timeout: int | None = None,
) -> dict:
    """One poll of sol1_enhancer. Returns a JSON-serializable record."""
    chosen = backend or backend_name()
    cwd = sol1_dir(root, chosen)
    cmd = command_for(ticket_id)
    if runner is not None:
        result = runner(ticket_id=ticket_id, backend=chosen, cwd=cwd)
        result.setdefault("cmd", cmd)
        result.setdefault("cwd", str(cwd))
        result.setdefault("backend", chosen)
        result.setdefault("ticket_id", ticket_id)
        return result
    if not cwd.is_dir():
        return {
            "ticket_id": ticket_id,
            "backend": chosen,
            "cwd": str(cwd),
            "cmd": cmd,
            "returncode": 127,
            "stdout": "",
            "stderr": f"missing solution folder: {cwd}",
        }
    seconds = timeout if timeout is not None else int(os.environ.get("AGENT_TIMEOUT", "900"))
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        return {
            "ticket_id": ticket_id,
            "backend": chosen,
            "cwd": str(cwd),
            "cmd": cmd,
            "returncode": 127,
            "stdout": "",
            "stderr": f"task not on PATH: {exc}",
        }
    except subprocess.TimeoutExpired:
        return {
            "ticket_id": ticket_id,
            "backend": chosen,
            "cwd": str(cwd),
            "cmd": cmd,
            "returncode": 124,
            "stdout": "",
            "stderr": f"timed out after {seconds}s",
        }
    return {
        "ticket_id": ticket_id,
        "backend": chosen,
        "cwd": str(cwd),
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "")[-4000:],
        "stderr": (proc.stderr or "")[-4000:],
    }
