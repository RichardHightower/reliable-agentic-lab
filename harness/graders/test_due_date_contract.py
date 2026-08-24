"""Hidden contract tests for the ready due-date ticket.

These tests are the Module 2 grader. They must fail on the starter CRM
and pass after a correct implementer run.

Do not hardcode seed customer names. Create fresh rows in an isolated database.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.db import Base, get_engine, reset_engine
from app.main import app
from app.models import SalesTask


@pytest.fixture()
def client():
    reset_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=get_engine())
    with TestClient(app) as test_client:
        yield test_client


def _make_customer(client: TestClient, suffix: str) -> int:
    response = client.post(
        "/api/customers",
        json={
            "name": f"Buyer {suffix}",
            "email": f"buyer-{suffix}@contract.test",
            "company": f"Co {suffix}",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_model_has_optional_due_date():
    mapper = inspect(SalesTask)
    assert "due_date" in mapper.columns, "sales_tasks.due_date is missing"
    column = mapper.columns["due_date"]
    assert column.nullable is True


def test_existing_tasks_remain_valid_with_null_due_date(client: TestClient):
    customer_id = _make_customer(client, "null-due")
    created = client.post(
        "/api/tasks",
        json={"customer_id": customer_id, "title": "No date yet", "notes": ""},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body.get("due_date") in (None, "")
    listed = client.get("/api/tasks")
    match = next(item for item in listed.json() if item["id"] == body["id"])
    assert match.get("due_date") in (None, "")


def test_create_task_with_iso8601_due_date(client: TestClient):
    customer_id = _make_customer(client, "iso-due")
    created = client.post(
        "/api/tasks",
        json={
            "customer_id": customer_id,
            "title": "Follow up with date",
            "due_date": "2026-09-15",
        },
    )
    assert created.status_code == 200, created.text
    raw = created.json()["due_date"]
    assert raw is not None
    assert str(raw).startswith("2026-09-15")


def test_filter_due_before(client: TestClient):
    customer_id = _make_customer(client, "before")
    early = client.post(
        "/api/tasks",
        json={"customer_id": customer_id, "title": "Early", "due_date": "2026-09-01"},
    )
    late = client.post(
        "/api/tasks",
        json={"customer_id": customer_id, "title": "Late", "due_date": "2026-10-01"},
    )
    none = client.post(
        "/api/tasks",
        json={"customer_id": customer_id, "title": "None"},
    )
    assert early.status_code == late.status_code == none.status_code == 200
    filtered = client.get("/api/tasks", params={"due_before": "2026-09-15"})
    assert filtered.status_code == 200, filtered.text
    titles = {item["title"] for item in filtered.json()}
    assert "Early" in titles
    assert "Late" not in titles
    assert "None" not in titles


def test_filter_overdue(client: TestClient):
    customer_id = _make_customer(client, "overdue")
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    tomorrow = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
    past = client.post(
        "/api/tasks",
        json={
            "customer_id": customer_id,
            "title": "Past due open",
            "status": "open",
            "due_date": yesterday,
        },
    )
    future = client.post(
        "/api/tasks",
        json={
            "customer_id": customer_id,
            "title": "Future open",
            "status": "open",
            "due_date": tomorrow,
        },
    )
    done = client.post(
        "/api/tasks",
        json={
            "customer_id": customer_id,
            "title": "Past due done",
            "status": "done",
            "due_date": yesterday,
        },
    )
    assert past.status_code == future.status_code == done.status_code == 200
    filtered = client.get("/api/tasks", params={"overdue": "true"})
    assert filtered.status_code == 200, filtered.text
    titles = {item["title"] for item in filtered.json()}
    assert "Past due open" in titles
    assert "Future open" not in titles
    assert "Past due done" not in titles


def test_task_form_exposes_due_date_field(client: TestClient):
    page = client.get("/tasks/new")
    assert page.status_code == 200
    html = page.text.lower()
    assert 'name="due_date"' in html or "name='due_date'" in html


def test_list_page_can_filter_due_before_and_overdue(client: TestClient):
    customer_id = _make_customer(client, "html-filter")
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    client.post(
        "/api/tasks",
        json={
            "customer_id": customer_id,
            "title": "Visible overdue",
            "status": "open",
            "due_date": yesterday,
        },
    )
    client.post(
        "/api/tasks",
        json={
            "customer_id": customer_id,
            "title": "Not yet due",
            "status": "open",
            "due_date": tomorrow,
        },
    )
    overdue_page = client.get("/tasks", params={"overdue": "true"})
    assert overdue_page.status_code == 200
    assert "Visible overdue" in overdue_page.text
    assert "Not yet due" not in overdue_page.text
    before_page = client.get("/tasks", params={"due_before": date.today().isoformat()})
    assert before_page.status_code == 200
    assert "Visible overdue" in before_page.text
    assert "Not yet due" not in before_page.text
