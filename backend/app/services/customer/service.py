from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.customer import Customer
from app.services.customer.errors import (
    CustomerConflictError,
    CustomerNotFoundError,
    CustomerValidationError,
)
from app.services.customer.repository import CustomerRepository
from app.services.customer.types import CustomerResolveResult


@dataclass(frozen=True, slots=True)
class CustomerCreateData:
    full_name: str
    phone: str | None = None
    email: str | None = None
    notes: str | None = None
    marketing_opt_in: bool = False
    whatsapp_opt_in: bool = False


@dataclass(frozen=True, slots=True)
class CustomerUpdateData:
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    notes: str | None = None
    marketing_opt_in: bool | None = None
    whatsapp_opt_in: bool | None = None


@dataclass(frozen=True, slots=True)
class PublicCustomerResolveData:
    full_name: str
    phone: str
    email: str | None = None


class CustomerService:
    def __init__(self, session: Session) -> None:
        self._repo = CustomerRepository(session)

    def list_customers(
        self,
        *,
        salon_id: uuid.UUID,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
        sort: str = "full_name",
    ) -> list[Customer]:
        if limit < 1 or limit > 200:
            raise CustomerValidationError("limit must be between 1 and 200")
        if offset < 0:
            raise CustomerValidationError("offset must be >= 0")
        return self._repo.list_customers(
            salon_id=salon_id,
            q=q,
            limit=limit,
            offset=offset,
            sort=sort,
        )

    def get_customer(self, *, salon_id: uuid.UUID, customer_id: uuid.UUID) -> Customer:
        row = self._repo.get_customer_by_id(salon_id=salon_id, customer_id=customer_id)
        if row is None:
            raise CustomerNotFoundError("customer not found")
        return row

    def create_customer(
        self,
        *,
        salon_id: uuid.UUID,
        data: CustomerCreateData,
        clock: Callable[[], datetime],
    ) -> Customer:
        full_name = self._validate_full_name(data.full_name)
        customer = Customer(
            salon_id=salon_id,
            full_name=full_name,
            phone=data.phone,
            email=data.email,
            notes=data.notes,
            marketing_opt_in=data.marketing_opt_in,
            whatsapp_opt_in=data.whatsapp_opt_in,
        )
        self._apply_whatsapp_opt_in_on_write(
            customer,
            whatsapp_opt_in=data.whatsapp_opt_in,
            previous=False,
            clock=clock,
        )
        try:
            return self._repo.add_customer(customer)
        except IntegrityError as exc:
            raise CustomerConflictError("customer conflicts with an existing record") from exc

    def update_customer(
        self,
        *,
        salon_id: uuid.UUID,
        customer_id: uuid.UUID,
        data: CustomerUpdateData,
        clock: Callable[[], datetime],
    ) -> Customer:
        customer = self.get_customer(salon_id=salon_id, customer_id=customer_id)
        previous_whatsapp = customer.whatsapp_opt_in
        if data.full_name is not None:
            customer.full_name = self._validate_full_name(data.full_name)
        if data.phone is not None:
            customer.phone = data.phone
        if data.email is not None:
            customer.email = data.email
        if data.notes is not None:
            customer.notes = data.notes
        if data.marketing_opt_in is not None:
            customer.marketing_opt_in = data.marketing_opt_in
        if data.whatsapp_opt_in is not None:
            customer.whatsapp_opt_in = data.whatsapp_opt_in
            self._apply_whatsapp_opt_in_on_write(
                customer,
                whatsapp_opt_in=data.whatsapp_opt_in,
                previous=previous_whatsapp,
                clock=clock,
            )
        try:
            self._repo.flush()
        except IntegrityError as exc:
            raise CustomerConflictError("customer conflicts with an existing record") from exc
        return customer

    def resolve_public_customer(
        self,
        *,
        salon_id: uuid.UUID,
        data: PublicCustomerResolveData,
    ) -> CustomerResolveResult:
        full_name = self._validate_full_name(data.full_name)
        phone = data.phone.strip()
        if not phone:
            raise CustomerValidationError("phone must not be blank")
        existing = self._repo.get_customer_by_phone(salon_id=salon_id, phone=phone)
        if existing is not None:
            return CustomerResolveResult(customer_id=existing.id, created=False)
        customer = Customer(
            salon_id=salon_id,
            full_name=full_name,
            phone=phone,
            email=data.email,
            notes=None,
            marketing_opt_in=False,
            whatsapp_opt_in=False,
            user_id=None,
        )
        try:
            self._repo.add_customer(customer)
        except IntegrityError as exc:
            raise CustomerConflictError("customer conflicts with an existing record") from exc
        return CustomerResolveResult(customer_id=customer.id, created=True)

    @staticmethod
    def _validate_full_name(value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise CustomerValidationError("full_name must not be blank")
        return stripped

    @staticmethod
    def _apply_whatsapp_opt_in_on_write(
        customer: Customer,
        *,
        whatsapp_opt_in: bool,
        previous: bool,
        clock: Callable[[], datetime],
    ) -> None:
        if whatsapp_opt_in and not previous:
            customer.whatsapp_opt_in_at = clock()
        elif not whatsapp_opt_in and previous:
            customer.whatsapp_opt_in_at = None
