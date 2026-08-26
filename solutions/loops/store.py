"""Local issue and pull request board.

Polling reads this file. That is the class default.
GitHub Issues are an optional later swap. Webhooks stay pinned.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .paths import DEFAULT_WORK, TICKETS_ROOT


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _front_matter(text: str) -> tuple[dict, str]:
    meta: dict = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for raw in parts[1].splitlines():
                if ":" in raw:
                    key, value = raw.split(":", 1)
                    meta[key.strip()] = value.strip()
            body = parts[2].lstrip("\n")
    return meta, body


class LocalBoard:
    def __init__(self, work_dir: Path | None = None) -> None:
        self.work = Path(work_dir or DEFAULT_WORK)
        self.work.mkdir(parents=True, exist_ok=True)
        self.path = self.work / "board.json"
        if not self.path.exists():
            self._write({"issues": {}, "pulls": {}})

    def _read(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def seed_from_tickets(self) -> None:
        data = self._read()
        for ticket in sorted(TICKETS_ROOT.glob("T*.md")):
            if ticket.name.endswith(".ready.md"):
                continue
            text = ticket.read_text(encoding="utf-8")
            meta, body = _front_matter(text)
            issue_id = meta.get("id") or ticket.stem
            if issue_id in data["issues"]:
                continue
            data["issues"][issue_id] = {
                "id": issue_id,
                "title": meta.get("title") or ticket.stem,
                "body": body,
                "state": meta.get("state") or "draft",
                "labels": [meta.get("state") or "draft"],
                "comments": [],
                "updated_at": _now(),
                "source": str(ticket),
            }
        self._write(data)

    def poll_issues(self, *, without_label: str | None = None, with_label: str | None = None) -> list[dict]:
        issues = list(self._read()["issues"].values())
        if without_label:
            issues = [i for i in issues if without_label not in i.get("labels", [])]
        if with_label:
            issues = [i for i in issues if with_label in i.get("labels", [])]
        return sorted(issues, key=lambda i: i["id"])

    def get_issue(self, issue_id: str) -> dict:
        return self._read()["issues"][issue_id]

    def comment(self, issue_id: str, body: str) -> dict:
        data = self._read()
        issue = data["issues"][issue_id]
        comment = {"at": _now(), "body": body}
        issue["comments"].append(comment)
        issue["updated_at"] = _now()
        self._write(data)
        return comment

    def set_body(self, issue_id: str, body: str) -> None:
        data = self._read()
        data["issues"][issue_id]["body"] = body
        data["issues"][issue_id]["updated_at"] = _now()
        self._write(data)

    def add_label(self, issue_id: str, label: str) -> None:
        data = self._read()
        labels = data["issues"][issue_id].setdefault("labels", [])
        if label not in labels:
            labels.append(label)
        data["issues"][issue_id]["state"] = label if label in {"draft", "ready", "needs-info"} else data["issues"][issue_id]["state"]
        data["issues"][issue_id]["updated_at"] = _now()
        self._write(data)

    def open_pr(self, *, issue_id: str, title: str, body: str, files: list[str], passing: bool) -> dict:
        data = self._read()
        pr_id = f"PR-{issue_id}"
        pr = {
            "id": pr_id,
            "issue_id": issue_id,
            "title": title,
            "body": body,
            "files": files,
            "passing": passing,
            "comments": [],
            "updated_at": _now(),
        }
        data["pulls"][pr_id] = pr
        self._write(data)
        return pr

    def poll_broken_prs(self) -> list[dict]:
        return [p for p in self._read()["pulls"].values() if not p.get("passing")]

    def get_pr(self, pr_id: str) -> dict:
        return self._read()["pulls"][pr_id]

    def comment_pr(self, pr_id: str, body: str) -> None:
        data = self._read()
        data["pulls"][pr_id]["comments"].append({"at": _now(), "body": body})
        data["pulls"][pr_id]["updated_at"] = _now()
        self._write(data)

    def mark_pr(self, pr_id: str, passing: bool) -> None:
        data = self._read()
        data["pulls"][pr_id]["passing"] = passing
        data["pulls"][pr_id]["updated_at"] = _now()
        self._write(data)


def slug_from_body(body: str) -> str | None:
    match = re.search(r"^id:\s*(\w+)", body, re.M)
    return match.group(1) if match else None
