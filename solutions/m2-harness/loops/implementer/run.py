#!/usr/bin/env python3
"""One-shot Ticket Implementer stub.

Sunday object. Module 1 will shrink this. Module 2 will wrap it.

Behavior:
1. Load a ready ticket.
2. If ANTHROPIC_API_KEY is set, send one Claude request with the ticket and a
   short file map. Print the model text. Do not auto-apply it yet.
3. Run the hidden grader.
4. Write harness/traces/last-implementer.json.

Attendees may skip Claude and use Claude Code against the same ticket and grader.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TICKET = ROOT / "harness" / "tickets" / "T001-due-dates.ready.md"
TRACE_DIR = ROOT / "harness" / "traces"
GRADER = ROOT / "harness" / "graders" / "test_due_date_contract.py"


def load_ticket(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def file_map() -> list[str]:
    crm = ROOT / "crm"
    paths = []
    for path in sorted(crm.rglob("*")):
        if path.is_file() and "data" not in path.parts and "__pycache__" not in path.parts:
            paths.append(str(path.relative_to(ROOT)))
    return paths


def maybe_call_claude(ticket: str) -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        import urllib.request

        body = json.dumps(
            {
                "model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
                "max_tokens": 800,
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "You are the Ticket Implementer. Propose the smallest CRM change "
                            "that satisfies this ready ticket. Do not write a new app.\n\n"
                            f"{ticket}\n\nFiles:\n" + "\n".join(file_map())
                        ),
                    }
                ],
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "content-type": "application/json",
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
        parts = payload.get("content") or []
        return "\n".join(part.get("text", "") for part in parts if part.get("type") == "text")
    except Exception as exc:  # noqa: BLE001
        return f"claude_call_failed: {exc}"


def run_grader() -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "crm") + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "pytest", str(GRADER), "-q"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )


def main() -> int:
    ticket_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TICKET
    ticket = load_ticket(ticket_path)
    model_text = maybe_call_claude(ticket)
    result = run_grader()
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    trace = {
        "trace_id": f"local-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "ticket_id": "T001",
        "iteration": 1,
        "maker_summary": (model_text or "no_api_key_skip_model")[:2000],
        "checker_summary": "pytest only on sunday stub",
        "tool_calls": ["pytest"],
        "pytest_output": (result.stdout + result.stderr)[-4000:],
        "score": {
            "passed": result.returncode == 0,
            "pytest_exit_code": result.returncode,
            "gate": "pass" if result.returncode == 0 else "retry",
        },
    }
    out = TRACE_DIR / "last-implementer.json"
    out.write_text(json.dumps(trace, indent=2), encoding="utf-8")
    print(out.read_text(encoding="utf-8"))
    print(result.stdout)
    print(result.stderr, file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
