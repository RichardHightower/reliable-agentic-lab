"""A GitHub client that records instead of calling.

More than one assignment needs it, so it lives beside `github_api.py` rather
than in one assignment's tests.
"""

from __future__ import annotations

from solutions.extra_credit import github_api as gh


class FakeGitHub:
    def __init__(self, issue: dict) -> None:
        self.issue = issue
        self.comments: list[str] = []
        self.added: list[str] = []
        self.removed: list[str] = []

    def get_issue(self, number: int) -> dict:
        self.issue["number"] = number
        return self.issue

    def comment(self, number: int, body: str) -> dict:
        self.comments.append(body)
        return {"body": body}

    def add_label(self, number: int, label: str) -> dict:
        names = gh.label_names(self.issue)
        if label not in names:
            raw = self.issue.setdefault("labels", [])
            raw.append({"name": label})
            self.added.append(label)
        return {}

    def remove_label(self, number: int, label: str) -> dict:
        self.issue["labels"] = [
            item
            for item in self.issue.get("labels") or []
            if (item if isinstance(item, str) else item.get("name")) != label
        ]
        self.removed.append(label)
        return {}
