from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import ServiceCatalogServiceDep
from app.api.schemas.services import (
    ServiceCreateRequest,
    ServiceResponse,
    ServiceUpdateRequest,
)
from app.api.schemas.staff import StaffResponse
from app.auth.deps import require_roles
from app.auth.principals import SalonContext
from app.db.models.service import Service
from app.services.service_catalog.service import ServiceCreateData, ServiceUpdateData

router = APIRouter(prefix="/salons/{salon_id}/services", tags=["services"])

ReadSalonContext = Annotated[
    SalonContext,
    Depends(require_roles("owner", "admin", "staff", "receptionist")),
]
WriteSalonContext = Annotated[SalonContext, Depends(require_roles("owner", "admin"))]


def _to_service_response(service: Service) -> ServiceResponse:
    currency_code: str | None = None
    salon = service.salon
    if salon is not None:
        currency_code = salon.currency_code
    base = ServiceResponse.model_validate(service)
    if currency_code is None:
        return base
    return base.model_copy(update={"currency_code": currency_code})


@router.get("", response_model=list[ServiceResponse])
def list_services(
    salon_id: uuid.UUID,
    context: ReadSalonContext,
    catalog_service: ServiceCatalogServiceDep,
    active_only: bool = Query(default=True),
) -> list[ServiceResponse]:
    _assert_path_salon(context, salon_id)
    rows = catalog_service.list_services(
        salon_id=context.salon_id,
        active_only=active_only,
    )
    return [_to_service_response(row) for row in rows]


@router.get("/{service_id}", response_model=ServiceResponse)
def get_service(
    salon_id: uuid.UUID,
    service_id: uuid.UUID,
    context: ReadSalonContext,
    catalog_service: ServiceCatalogServiceDep,
) -> ServiceResponse:
    _assert_path_salon(context, salon_id)
    row = catalog_service.get_service(salon_id=context.salon_id, service_id=service_id)
    return _to_service_response(row)


@router.post("", response_model=ServiceResponse, status_code=201)
def create_service(
    salon_id: uuid.UUID,
    body: ServiceCreateRequest,
    context: WriteSalonContext,
    catalog_service: ServiceCatalogServiceDep,
) -> ServiceResponse:
    _assert_path_salon(context, salon_id)
    row = catalog_service.create_service(
        salon_id=context.salon_id,
        data=ServiceCreateData(
            name=body.name,
            description=body.description,
            duration_minutes=body.duration_minutes,
            buffer_before_minutes=body.buffer_before_minutes,
            buffer_after_minutes=body.buffer_after_minutes,
            price_cents=body.price_cents,
            is_active=body.is_active,
            sort_order=body.sort_order,
        ),
    )
    return _to_service_response(row)


@router.patch("/{service_id}", response_model=ServiceResponse)
def update_service(
    salon_id: uuid.UUID,
    service_id: uuid.UUID,
    body: ServiceUpdateRequest,
    context: WriteSalonContext,
    catalog_service: ServiceCatalogServiceDep,
) -> ServiceResponse:
    _assert_path_salon(context, salon_id)
    row = catalog_service.update_service(
        salon_id=context.salon_id,
        service_id=service_id,
        data=ServiceUpdateData(
            name=body.name,
            description=body.description,
            duration_minutes=body.duration_minutes,
            buffer_before_minutes=body.buffer_before_minutes,
            buffer_after_minutes=body.buffer_after_minutes,
            price_cents=body.price_cents,
            is_active=body.is_active,
            sort_order=body.sort_order,
        ),
    )
    return _to_service_response(row)


@router.delete("/{service_id}", status_code=405)
def delete_service_not_allowed(
    salon_id: uuid.UUID,
    service_id: uuid.UUID,
    context: ReadSalonContext,
) -> Response:
    _assert_path_salon(context, salon_id)
    return Response(status_code=405)


@router.get("/{service_id}/staff", response_model=list[StaffResponse])
def list_service_staff(
    salon_id: uuid.UUID,
    service_id: uuid.UUID,
    context: ReadSalonContext,
    catalog_service: ServiceCatalogServiceDep,
) -> list[StaffResponse]:
    _assert_path_salon(context, salon_id)
    rows = catalog_service.list_service_staff(
        salon_id=context.salon_id,
        service_id=service_id,
    )
    return [StaffResponse.model_validate(row) for row in rows]


@router.put("/{service_id}/staff/{staff_id}", response_model=StaffResponse)
def attach_staff_to_service(
    salon_id: uuid.UUID,
    service_id: uuid.UUID,
    staff_id: uuid.UUID,
    context: WriteSalonContext,
    catalog_service: ServiceCatalogServiceDep,
) -> StaffResponse:
    _assert_path_salon(context, salon_id)
    staff = catalog_service.attach_staff_to_service(
        salon_id=context.salon_id,
        service_id=service_id,
        staff_id=staff_id,
    )
    return StaffResponse.model_validate(staff)


@router.delete("/{service_id}/staff/{staff_id}", status_code=204)
def detach_staff_from_service(
    salon_id: uuid.UUID,
    service_id: uuid.UUID,
    staff_id: uuid.UUID,
    context: WriteSalonContext,
    catalog_service: ServiceCatalogServiceDep,
) -> Response:
    _assert_path_salon(context, salon_id)
    catalog_service.detach_staff_from_service(
        salon_id=context.salon_id,
        service_id=service_id,
        staff_id=staff_id,
    )
    return Response(status_code=204)


def _assert_path_salon(context: SalonContext, salon_id: uuid.UUID) -> None:
    if context.salon_id != salon_id:
        raise RuntimeError("salon_id path mismatch with SalonContext")
