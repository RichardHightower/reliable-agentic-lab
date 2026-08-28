#!/usr/bin/env python3
"""Confirm clone, GitHub token, and model key. Prints a ready checklist."""

from __future__ import annotations

import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# Tickets live in the target repo, not in this one. `task setup` clones it.
TARGET = REPO_ROOT / "work" / "northwind-field-crm"


def load_dotenv() -> None:
    path = REPO_ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def check_python() -> tuple[bool, str]:
    ok = sys.version_info >= (3, 10)
    return ok, f"Python {sys.version.split()[0]}"


def check_git() -> tuple[bool, str]:
    path = shutil.which("git")
    return bool(path), path or "git not on PATH"


def check_target() -> tuple[bool, str]:
    """The target repo, and the tickets the labs work on.

    A clone that is present but has no tickets is a different problem from one
    that was never cloned. Saying which is the difference between a fix and a
    guess at 09:55 on Saturday.
    """
    if not TARGET.exists():
        return False, f"not cloned yet. Run `task clone` (expected at {TARGET.name})"
    if not (TARGET / "Taskfile.yml").exists():
        return False, f"{TARGET.name} has no Taskfile.yml, so no lab can run against it"
    files = sorted(p.name for p in (TARGET / "tickets").glob("T0*.md"))
    if not files:
        return False, f"{TARGET.name} is cloned but holds no tickets"
    return True, f"{TARGET.name}: {', '.join(files)}"


def github_get(url: str, token: str) -> tuple[int, object]:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "reliable-agentic-lab-verify",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, {"message": str(exc)}
    except Exception as exc:
        return 0, {"message": str(exc)}


def check_github() -> tuple[str, str]:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repo = os.environ.get("GITHUB_REPO", "RichardHightower/reliable-agentic-lab").strip()
    if not token:
        return "skip", "GITHUB_TOKEN not set. Local labs still run."
    status, payload = github_get("https://api.github.com/user", token)
    if status != 200:
        return "fail", f"token rejected ({status}). Check scopes."
    login = payload.get("login", "?") if isinstance(payload, dict) else "?"
    issues_status, issues = github_get(
        f"https://api.github.com/repos/{repo}/issues?state=all&per_page=5",
        token,
    )
    if issues_status == 404:
        return (
            "warn",
            f"token works as {login}, but cannot see {repo} yet. Ask Rick for collaborator access.",
        )
    if issues_status != 200:
        return (
            "fail",
            f"cannot list issues on {repo} ({issues_status}). Need contents, issues, pull requests.",
        )
    count = len(issues) if isinstance(issues, list) else 0
    return "pass", f"{login} can list issues on {repo} ({count} returned)"


def check_anthropic() -> tuple[str, str]:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return "skip", "ANTHROPIC_API_KEY not set"
    body = json.dumps(
        {
            "model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            "max_tokens": 16,
            "messages": [{"role": "user", "content": "Reply with the single word ready."}],
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
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
        text = " ".join(
            part.get("text", "")
            for part in payload.get("content") or []
            if part.get("type") == "text"
        ).strip()
        return "pass", f"Anthropic call ok ({text[:40] or 'empty'})"
    except urllib.error.HTTPError as exc:
        return "fail", f"Anthropic call failed ({exc.code})"
    except Exception as exc:
        return "fail", f"Anthropic call failed ({exc})"


def check_openai() -> tuple[str, str]:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        return "skip", "OPENAI_API_KEY not set"
    body = json.dumps(
        {
            "model": os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
            "max_tokens": 16,
            "messages": [{"role": "user", "content": "Reply with the single word ready."}],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "content-type": "application/json",
            "authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
        text = payload.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        return "pass", f"OpenAI call ok ({text[:40] or 'empty'})"
    except urllib.error.HTTPError as exc:
        return "fail", f"OpenAI call failed ({exc.code})"
    except Exception as exc:
        return "fail", f"OpenAI call failed ({exc})"


def main() -> int:
    load_dotenv()
    rows: list[tuple[str, str, str]] = []

    ok, detail = check_python()
    rows.append(("pass" if ok else "fail", "python", detail))
    ok, detail = check_git()
    rows.append(("pass" if ok else "fail", "git", detail))
    ok, detail = check_target()
    rows.append(("pass" if ok else "fail", "target repo", detail))
    rows.append(
        (
            "pass" if (REPO_ROOT / ".venv").exists() else "warn",
            "venv",
            ".venv found"
            if (REPO_ROOT / ".venv").exists()
            else "no .venv yet. Run python -m venv .venv",
        )
    )
    rows.append(
        (
            "pass" if (REPO_ROOT / ".env").exists() else "warn",
            ".env",
            ".env found" if (REPO_ROOT / ".env").exists() else "copy .env.example to .env",
        )
    )
    gh_status, gh_detail = check_github()
    rows.append((gh_status, "github", gh_detail))
    an_status, an_detail = check_anthropic()
    rows.append((an_status, "anthropic", an_detail))
    oa_status, oa_detail = check_openai()
    rows.append((oa_status, "openai", oa_detail))

    print("reliable-agentic-lab setup check")
    print(f"repo: {REPO_ROOT}")
    failed = 0
    for status, name, detail in rows:
        mark = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP", "warn": "WARN"}[status]
        print(f"  [{mark}] {name}: {detail}")
        if status == "fail":
            failed += 1

    if failed:
        print("\nNot ready. Fix FAIL lines, then rerun: python scripts/verify_setup.py")
        return 1

    model_ok = an_status == "pass" or oa_status == "pass"
    if not model_ok:
        print("\nLabs 2-4 still run with no model key from their solution folders.")
        print("Add ANTHROPIC_API_KEY or OPENAI_API_KEY when you fill a live-model lab.")
        return 0

    print("\nReady. Open labs/ and paste one prompt from prompts/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
