from __future__ import annotations

from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.models import Customer, SalesTask


CUSTOMERS = [
    {"name": "Ada Meadows", "email": "ada@meadows.example", "company": "Meadows Horticulture"},
    {"name": "Lin Park", "email": "lin@harbor.example", "company": "Harbor Lights"},
    {"name": "Omar Singh", "email": "omar@northline.example", "company": "Northline Freight"},
]

TASKS = [
    {"customer": "Ada Meadows", "title": "Send catalog for spring bulbs", "status": "open", "notes": "She asked after tulips."},
    {"customer": "Ada Meadows", "title": "Quote bulk soil amendment", "status": "open", "notes": ""},
    {"customer": "Lin Park", "title": "Follow up on event center order", "status": "open", "notes": "Call before Friday."},
    {"customer": "Lin Park", "title": "Collect signed contract", "status": "done", "notes": "Filed in drawer 3."},
    {"customer": "Omar Singh", "title": "Confirm delivery window", "status": "open", "notes": "Dock closes at 16:00."},
]


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        if session.scalar(select(Customer.id).limit(1)):
            return
        by_name: dict[str, Customer] = {}
        for row in CUSTOMERS:
            customer = Customer(**row)
            session.add(customer)
            session.flush()
            by_name[customer.name] = customer
        for row in TASKS:
            session.add(
                SalesTask(
                    customer_id=by_name[row["customer"]].id,
                    title=row["title"],
                    status=row["status"],
                    notes=row["notes"],
                )
            )
        session.commit()
    finally:
        session.close()


if __name__ == "__main__":
    seed()
