from __future__ import annotations

import uuid

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.db.models.customer import Customer


class CustomerRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_customers(
        self,
        *,
        salon_id: uuid.UUID,
        q: str | None,
        limit: int,
        offset: int,
        sort: str,
    ) -> list[Customer]:
        stmt = select(Customer).where(Customer.salon_id == salon_id)
        if q:
            pattern = f"%{q.strip()}%"
            stmt = stmt.where(
                or_(
                    Customer.full_name.ilike(pattern),
                    Customer.phone.ilike(pattern),
                    Customer.email.ilike(pattern),
                )
            )
        stmt = self._apply_sort(stmt, sort)
        stmt = stmt.limit(limit).offset(offset)
        return list(self._session.scalars(stmt).all())

    def get_customer_by_id(
        self, *, salon_id: uuid.UUID, customer_id: uuid.UUID
    ) -> Customer | None:
        return self._session.scalar(
            select(Customer).where(
                Customer.salon_id == salon_id,
                Customer.id == customer_id,
            )
        )

    def get_customer_by_phone(
        self, *, salon_id: uuid.UUID, phone: str
    ) -> Customer | None:
        return self._session.scalar(
            select(Customer).where(
                Customer.salon_id == salon_id,
                Customer.phone == phone,
            )
        )

    def add_customer(self, customer: Customer) -> Customer:
        self._session.add(customer)
        self._session.flush()
        return customer

    def flush(self) -> None:
        self._session.flush()

    @staticmethod
    def _apply_sort(stmt: Select[tuple[Customer]], sort: str) -> Select[tuple[Customer]]:
        descending = sort.startswith("-")
        field = sort[1:] if descending else sort
        if field not in ("full_name", "id"):
            field = "full_name"
            descending = False
        column = Customer.full_name if field == "full_name" else Customer.id
        order = column.desc() if descending else column.asc()
        if field == "full_name":
            return stmt.order_by(order, Customer.id.asc())
        return stmt.order_by(order)
