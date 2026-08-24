from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dates import parse_due_date, serialize_due_date, utc_today
from app.db import Base, get_engine, get_session
from app.models import Customer, SalesTask

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

app = FastAPI(title="Northwind Field CRM", version="0.2.0")


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=get_engine())


@app.get("/", response_class=HTMLResponse)
def home(request: Request, session: Session = Depends(get_session)):
    customers = session.scalars(select(Customer).order_by(Customer.name)).all()
    tasks = session.scalars(select(SalesTask).order_by(SalesTask.id.desc())).all()
    return TEMPLATES.TemplateResponse(
        request,
        "home.html",
        {"customers": customers, "tasks": tasks},
    )


@app.get("/customers", response_class=HTMLResponse)
def customers_page(
    request: Request,
    q: str = "",
    session: Session = Depends(get_session),
):
    stmt = select(Customer).order_by(Customer.name)
    rows = session.scalars(stmt).all()
    if q:
        rows = [row for row in rows if row.name == q]
    return TEMPLATES.TemplateResponse(
        request,
        "customers.html",
        {"customers": rows, "q": q},
    )


@app.get("/tasks", response_class=HTMLResponse)
def tasks_page(
    request: Request,
    status: str | None = None,
    customer_id: int | None = None,
    due_before: str | None = None,
    overdue: str | None = None,
    session: Session = Depends(get_session),
):
    tasks = _query_tasks(session, status, customer_id, due_before, overdue)
    customers = session.scalars(select(Customer).order_by(Customer.name)).all()
    return TEMPLATES.TemplateResponse(
        request,
        "tasks.html",
        {
            "tasks": tasks,
            "customers": customers,
            "status": status or "",
            "customer_id": customer_id or "",
            "due_before": due_before or "",
            "overdue": overdue or "",
        },
    )


@app.get("/tasks/new", response_class=HTMLResponse)
def new_task_form(request: Request, session: Session = Depends(get_session)):
    customers = session.scalars(select(Customer).order_by(Customer.name)).all()
    return TEMPLATES.TemplateResponse(
        request,
        "task_form.html",
        {"customers": customers, "task": None},
    )


@app.post("/tasks/new")
def create_task_form(
    customer_id: int = Form(...),
    title: str = Form(...),
    notes: str = Form(""),
    status: str = Form("open"),
    due_date: str = Form(""),
    session: Session = Depends(get_session),
):
    task = SalesTask(
        customer_id=customer_id,
        title=title.strip(),
        notes=notes.strip(),
        status=status,
        due_date=parse_due_date(due_date),
    )
    session.add(task)
    session.commit()
    return RedirectResponse("/tasks", status_code=303)


@app.get("/api/health")
def health():
    return {"ok": True, "app": "northwind-field-crm"}


@app.get("/api/customers")
def api_customers(
    q: str = "",
    session: Session = Depends(get_session),
):
    rows = session.scalars(select(Customer).order_by(Customer.name)).all()
    if q:
        rows = [row for row in rows if row.name == q]
    return [_customer_payload(row) for row in rows]


@app.get("/api/tasks")
def api_tasks(
    status: str | None = Query(default=None),
    customer_id: int | None = Query(default=None),
    due_before: str | None = Query(default=None),
    overdue: str | None = Query(default=None),
    session: Session = Depends(get_session),
):
    tasks = _query_tasks(session, status, customer_id, due_before, overdue)
    return [_task_payload(row) for row in tasks]


@app.post("/api/customers")
def api_create_customer(payload: dict, session: Session = Depends(get_session)):
    row = Customer(
        name=payload["name"],
        email=payload["email"],
        company=payload.get("company", ""),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _customer_payload(row)


@app.post("/api/tasks")
def api_create_task(payload: dict, session: Session = Depends(get_session)):
    row = SalesTask(
        customer_id=int(payload["customer_id"]),
        title=payload["title"],
        notes=payload.get("notes", ""),
        status=payload.get("status", "open"),
        due_date=parse_due_date(payload.get("due_date")),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _task_payload(row)


@app.patch("/api/tasks/{task_id}")
def api_patch_task(task_id: int, payload: dict, session: Session = Depends(get_session)):
    row = session.get(SalesTask, task_id)
    if row is None:
        return {"error": "not_found"}
    for key in ("title", "notes", "status"):
        if key in payload:
            setattr(row, key, payload[key])
    if "due_date" in payload:
        row.due_date = parse_due_date(payload.get("due_date"))
    session.commit()
    session.refresh(row)
    return _task_payload(row)


def _query_tasks(session: Session, status, customer_id, due_before, overdue):
    stmt = select(SalesTask).order_by(SalesTask.id)
    if status:
        stmt = stmt.where(SalesTask.status == status)
    if customer_id:
        stmt = stmt.where(SalesTask.customer_id == customer_id)
    rows = list(session.scalars(stmt).all())
    if due_before:
        cutoff = parse_due_date(due_before)
        if cutoff is not None:
            rows = [
                row
                for row in rows
                if row.due_date is not None and row.due_date.date() < cutoff.date()
            ]
    if overdue and overdue.lower() in {"1", "true", "yes", "on"}:
        today = utc_today()
        rows = [
            row
            for row in rows
            if row.status == "open" and row.due_date is not None and row.due_date.date() < today
        ]
    return rows


def _customer_payload(row: Customer) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "email": row.email,
        "company": row.company,
    }


def _task_payload(row: SalesTask) -> dict:
    return {
        "id": row.id,
        "customer_id": row.customer_id,
        "title": row.title,
        "status": row.status,
        "notes": row.notes,
        "due_date": serialize_due_date(row.due_date),
    }
