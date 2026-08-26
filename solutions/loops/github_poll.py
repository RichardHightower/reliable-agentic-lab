"""Optional GitHub poller.

Class default is the local board in store.py.
Set GITHUB_TOKEN, GITHUB_REPO (owner/name) to poll real issues.
Webhooks need a deploy (Vercel, Grok Build, Claude Managed Agents).
Pin that path for later. Do not build it in the first hour.
"""
from __future__ import annotations

import json
import os
import urllib.request


def poll_github_issues(*, state: str = "open") -> list[dict] | None:
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPO")
    if not token or not repo:
        return None
    url = f"https://api.github.com/repos/{repo}/issues?state={state}&per_page=20"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "reliable-agentic-lab",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return [item for item in payload if "pull_request" not in item]
