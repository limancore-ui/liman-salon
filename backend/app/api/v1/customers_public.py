from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.api.deps import CustomerServiceDep
from app.api.schemas.customer import (
    PublicCustomerResolveRequest,
    PublicCustomerResolveResponse,
)
from app.services.customer.service import PublicCustomerResolveData

router = APIRouter(tags=["customers-public"])


@router.post(
    "/salons/{salon_id}/public/customers/resolve",
    response_model=PublicCustomerResolveResponse,
    status_code=200,
)
def resolve_public_customer(
    salon_id: uuid.UUID,
    body: PublicCustomerResolveRequest,
    customer_service: CustomerServiceDep,
) -> PublicCustomerResolveResponse:
    result = customer_service.resolve_public_customer(
        salon_id=salon_id,
        data=PublicCustomerResolveData(
            full_name=body.full_name,
            phone=body.phone,
            email=body.email,
        ),
    )
    return PublicCustomerResolveResponse(
        customer_id=result.customer_id,
        created=result.created,
    )
