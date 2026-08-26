"""Tiny GitHub REST helper. Extra credit only. Polling remains the class default."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

API = "https://api.github.com"
IN_PROGRESS = "agent-in-progress"
ATTEMPTS_PREFIX = "agent-attempts-"


class GitHubError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"GitHub {status}: {message}")
        self.status = status


class GitHub:
    def __init__(
        self,
        token: str,
        repo: str,
        *,
        opener: Callable[..., object] | None = None,
    ) -> None:
        self.token = token
        self.repo = repo
        self.opener = opener or urllib.request.urlopen

    def request(self, method: str, path: str, body: dict | None = None) -> Any:
        url = path if path.startswith("http") else f"{API}{path}"
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "reliable-agentic-lab-extra-credit",
                "Content-Type": "application/json",
            },
        )
        try:
            with self.opener(request, timeout=30) as response:  # type: ignore[arg-type]
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise GitHubError(exc.code, detail[:300]) from exc

    def get_issue(self, number: int) -> dict:
        return self.request("GET", f"/repos/{self.repo}/issues/{number}")

    def comment(self, number: int, body: str) -> dict:
        return self.request(
            "POST",
            f"/repos/{self.repo}/issues/{number}/comments",
            {"body": body},
        )

    def add_label(self, number: int, label: str) -> dict:
        return self.request(
            "POST",
            f"/repos/{self.repo}/issues/{number}/labels",
            {"labels": [label]},
        )

    def remove_label(self, number: int, label: str) -> dict:
        return self.request(
            "DELETE",
            f"/repos/{self.repo}/issues/{number}/labels/{quote(label, safe='')}",
        )


def repo_from_env() -> str:
    return (
        os.environ.get("GITHUB_REPO")
        or os.environ.get("GITHUB_REPOSITORY")
        or "RichardHightower/reliable-agentic-lab"
    )


def token_from_env() -> str:
    return (os.environ.get("GITHUB_TOKEN") or "").strip()


def attempt_count(labels: list[str]) -> int:
    counts = []
    for name in labels:
        if name.startswith(ATTEMPTS_PREFIX):
            try:
                counts.append(int(name.split("-")[-1]))
            except ValueError:
                continue
    return max(counts) if counts else 0


def next_attempt_label(current: int) -> str:
    return f"{ATTEMPTS_PREFIX}{current + 1}"


def label_names(issue: dict) -> list[str]:
    names = []
    for item in issue.get("labels") or []:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
    return names
