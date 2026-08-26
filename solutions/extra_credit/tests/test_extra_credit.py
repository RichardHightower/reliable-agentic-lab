from __future__ import annotations

from solutions.extra_credit import github_api as gh
from solutions.extra_credit import fix_pr, groom_ticket


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
        self.issue["labels"] = [item for item in self.issue.get("labels") or [] if (item if isinstance(item, str) else item.get("name")) != label]
        self.removed.append(label)
        return {}


def test_attempt_count():
    assert gh.attempt_count(["ready", "agent-attempts-2"]) == 2
    assert gh.attempt_count([]) == 0


def test_local_groom_with_incorporate(tmp_path, monkeypatch):
    monkeypatch.setattr(groom_ticket, "WORK", tmp_path)
    payload = groom_ticket.run_local("T001", incorporate=True, budget=2)
    assert payload["ready"] is True
    assert payload["mode"] == "local"
    assert (tmp_path / "last-groom.json").exists()


def test_github_groom_comments_when_thin():
    fake = FakeGitHub({"title": "Due dates", "body": "please add them", "labels": []})
    payload = groom_ticket.run_github(7, budget=3, client=fake)
    assert payload["exit"] == "commented"
    assert payload["ready"] is False
    assert fake.comments
    assert gh.IN_PROGRESS in fake.added
    assert gh.IN_PROGRESS in fake.removed


def test_github_groom_labels_ready():
    body = "## Success criteria\n\n- a\n- b\n- c\n- d\n"
    fake = FakeGitHub({"title": "Due dates", "body": body, "labels": []})
    payload = groom_ticket.run_github(8, budget=3, client=fake)
    assert payload["exit"] == "ready label"
    assert "ready" in fake.added


def test_github_groom_skips_in_progress():
    fake = FakeGitHub({"title": "x", "body": "y", "labels": [{"name": gh.IN_PROGRESS}]})
    payload = groom_ticket.run_github(9, budget=3, client=fake)
    assert payload["exit"] == "skipped concurrent run"
    assert fake.comments == []


def test_github_groom_stops_at_budget():
    fake = FakeGitHub({"title": "x", "body": "y", "labels": [{"name": "agent-attempts-3"}]})
    payload = groom_ticket.run_github(10, budget=3, client=fake)
    assert payload["exit"] == "budget"
    assert "Max attempts" in fake.comments[0]


def test_local_fixer_reference(tmp_path, monkeypatch):
    monkeypatch.setattr(fix_pr, "WORK", tmp_path)
    payload = fix_pr.run_local("T001", maker="reference", budget=2)
    assert payload["passed"] is True
    assert (tmp_path / "last-fix.json").exists()
