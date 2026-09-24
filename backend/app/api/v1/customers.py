from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import ClockDep, CustomerServiceDep
from app.api.schemas.customer import (
    CustomerCreateRequest,
    CustomerResponse,
    CustomerUpdateRequest,
)
from app.auth.deps import require_roles
from app.auth.principals import SalonContext
from app.services.customer.service import CustomerCreateData, CustomerUpdateData

router = APIRouter(prefix="/salons/{salon_id}/customers", tags=["customers"])

ReadSalonContext = Annotated[
    SalonContext,
    Depends(require_roles("owner", "admin", "staff", "receptionist")),
]
WriteSalonContext = Annotated[SalonContext, Depends(require_roles("owner", "admin"))]


def _to_response(customer: object) -> CustomerResponse:
    return CustomerResponse.model_validate(customer)


@router.get("", response_model=list[CustomerResponse])
def list_customers(
    salon_id: uuid.UUID,
    context: ReadSalonContext,
    customer_service: CustomerServiceDep,
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="full_name"),
) -> list[CustomerResponse]:
    _assert_path_salon(context, salon_id)
    rows = customer_service.list_customers(
        salon_id=context.salon_id,
        q=q,
        limit=limit,
        offset=offset,
        sort=sort,
    )
    return [_to_response(row) for row in rows]


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    salon_id: uuid.UUID,
    customer_id: uuid.UUID,
    context: ReadSalonContext,
    customer_service: CustomerServiceDep,
) -> CustomerResponse:
    _assert_path_salon(context, salon_id)
    row = customer_service.get_customer(
        salon_id=context.salon_id,
        customer_id=customer_id,
    )
    return _to_response(row)


@router.post("", response_model=CustomerResponse, status_code=201)
def create_customer(
    salon_id: uuid.UUID,
    body: CustomerCreateRequest,
    context: WriteSalonContext,
    customer_service: CustomerServiceDep,
    clock: ClockDep,
) -> CustomerResponse:
    _assert_path_salon(context, salon_id)
    row = customer_service.create_customer(
        salon_id=context.salon_id,
        data=CustomerCreateData(
            full_name=body.full_name,
            phone=body.phone,
            email=body.email,
            notes=body.notes,
            marketing_opt_in=body.marketing_opt_in,
            whatsapp_opt_in=body.whatsapp_opt_in,
        ),
        clock=clock,
    )
    return _to_response(row)


@router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    salon_id: uuid.UUID,
    customer_id: uuid.UUID,
    body: CustomerUpdateRequest,
    context: WriteSalonContext,
    customer_service: CustomerServiceDep,
    clock: ClockDep,
) -> CustomerResponse:
    _assert_path_salon(context, salon_id)
    row = customer_service.update_customer(
        salon_id=context.salon_id,
        customer_id=customer_id,
        data=CustomerUpdateData(
            full_name=body.full_name,
            phone=body.phone,
            email=body.email,
            notes=body.notes,
            marketing_opt_in=body.marketing_opt_in,
            whatsapp_opt_in=body.whatsapp_opt_in,
        ),
        clock=clock,
    )
    return _to_response(row)


def _assert_path_salon(context: SalonContext, salon_id: uuid.UUID) -> None:
    if context.salon_id != salon_id:
        raise RuntimeError("salon_id path mismatch with SalonContext")
