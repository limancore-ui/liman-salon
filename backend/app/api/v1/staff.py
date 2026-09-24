from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import StaffServiceDep
from app.api.schemas.staff import StaffCreateRequest, StaffResponse, StaffUpdateRequest
from app.auth.deps import require_roles
from app.auth.principals import SalonContext
from app.services.staff.service import StaffCreateData, StaffUpdateData

router = APIRouter(prefix="/salons/{salon_id}/staff", tags=["staff"])

ReadSalonContext = Annotated[
    SalonContext,
    Depends(require_roles("owner", "admin", "staff", "receptionist")),
]
WriteSalonContext = Annotated[SalonContext, Depends(require_roles("owner", "admin"))]


def _to_response(staff: object) -> StaffResponse:
    return StaffResponse.model_validate(staff)


@router.get("", response_model=list[StaffResponse])
def list_staff(
    salon_id: uuid.UUID,
    context: ReadSalonContext,
    staff_service: StaffServiceDep,
    active_only: bool = Query(default=True),
    bookable_only: bool = Query(default=False),
) -> list[StaffResponse]:
    _assert_path_salon(context, salon_id)
    rows = staff_service.list_staff(
        salon_id=context.salon_id,
        active_only=active_only,
        bookable_only=bookable_only,
    )
    return [_to_response(row) for row in rows]


@router.get("/{staff_id}", response_model=StaffResponse)
def get_staff(
    salon_id: uuid.UUID,
    staff_id: uuid.UUID,
    context: ReadSalonContext,
    staff_service: StaffServiceDep,
) -> StaffResponse:
    _assert_path_salon(context, salon_id)
    row = staff_service.get_staff(salon_id=context.salon_id, staff_id=staff_id)
    return _to_response(row)


@router.post("", response_model=StaffResponse, status_code=201)
def create_staff(
    salon_id: uuid.UUID,
    body: StaffCreateRequest,
    context: WriteSalonContext,
    staff_service: StaffServiceDep,
) -> StaffResponse:
    _assert_path_salon(context, salon_id)
    row = staff_service.create_staff(
        salon_id=context.salon_id,
        data=StaffCreateData(
            display_name=body.display_name,
            title=body.title,
            bio=body.bio,
            color_hex=body.color_hex,
            is_bookable=body.is_bookable,
            is_active=body.is_active,
            sort_order=body.sort_order,
        ),
    )
    return _to_response(row)


@router.patch("/{staff_id}", response_model=StaffResponse)
def update_staff(
    salon_id: uuid.UUID,
    staff_id: uuid.UUID,
    body: StaffUpdateRequest,
    context: WriteSalonContext,
    staff_service: StaffServiceDep,
) -> StaffResponse:
    _assert_path_salon(context, salon_id)
    row = staff_service.update_staff(
        salon_id=context.salon_id,
        staff_id=staff_id,
        data=StaffUpdateData(
            display_name=body.display_name,
            title=body.title,
            bio=body.bio,
            color_hex=body.color_hex,
            is_bookable=body.is_bookable,
            is_active=body.is_active,
            sort_order=body.sort_order,
        ),
    )
    return _to_response(row)


def _assert_path_salon(context: SalonContext, salon_id: uuid.UUID) -> None:
    if context.salon_id != salon_id:
        raise RuntimeError("salon_id path mismatch with SalonContext")
