from fastapi.testclient import TestClient

from app.db import Base, get_engine, reset_engine
from app.main import app


def test_health():
    reset_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=get_engine())
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["ok"] is True


def test_create_customer_and_task():
    reset_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=get_engine())
    with TestClient(app) as client:
        customer = client.post(
            "/api/customers",
            json={"name": "Test Buyer", "email": "buyer@example.com", "company": "Example Co"},
        )
        assert customer.status_code == 200
        customer_id = customer.json()["id"]
        task = client.post(
            "/api/tasks",
            json={"customer_id": customer_id, "title": "Call back", "notes": ""},
        )
        assert task.status_code == 200
        assert task.json()["title"] == "Call back"
        listed = client.get("/api/tasks")
        assert any(item["id"] == task.json()["id"] for item in listed.json())
