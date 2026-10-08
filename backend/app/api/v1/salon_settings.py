from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import SalonSettingsServiceDep
from app.api.schemas.salon_settings import (
    SalonBookingSettingsPatch,
    SalonBookingSettingsResponse,
    SalonBonusesSettingsPatch,
    SalonBonusesSettingsResponse,
    SalonSettingsPatchRequest,
    SalonSettingsResponse,
)
from app.auth.deps import require_roles
from app.auth.principals import SalonContext
from app.services.salon_settings.service import (
    SalonBookingPatchData,
    SalonBonusesPatchData,
    SalonSettingsPatchData,
    SalonSettingsView,
)

router = APIRouter(prefix="/salons/{salon_id}/settings", tags=["salon-settings"])

WriteSalonContext = Annotated[SalonContext, Depends(require_roles("owner", "admin"))]


def _to_response(view: SalonSettingsView) -> SalonSettingsResponse:
    booking = None
    if view.public_hold_seconds is not None:
        booking = SalonBookingSettingsResponse(public_hold_seconds=view.public_hold_seconds)
    bonuses = None
    if view.bonuses_enabled is not None and view.bonuses_earn_percentage is not None:
        bonuses = SalonBonusesSettingsResponse(
            enabled=view.bonuses_enabled,
            earn_percentage=view.bonuses_earn_percentage,
        )
    return SalonSettingsResponse(v=1, booking=booking, bonuses=bonuses)


def _patch_from_request(body: SalonSettingsPatchRequest) -> SalonSettingsPatchData:
    fields_set = body.model_fields_set
    booking_set = "booking" in fields_set
    bonuses_set = "bonuses" in fields_set

    booking_patch: SalonBookingPatchData | None = None
    if booking_set:
        if body.booking is not None:
            booking_body: SalonBookingSettingsPatch = body.booking
            booking_patch = SalonBookingPatchData(
                public_hold_seconds=booking_body.public_hold_seconds,
            )

    bonuses_patch: SalonBonusesPatchData | None = None
    if bonuses_set and body.bonuses is not None:
        bonuses_body: SalonBonusesSettingsPatch = body.bonuses
        bonuses_patch = SalonBonusesPatchData(
            enabled=bonuses_body.enabled,
            earn_percentage=bonuses_body.earn_percentage,
        )

    return SalonSettingsPatchData(
        booking_set=booking_set,
        booking=booking_patch,
        bonuses_set=bonuses_set,
        bonuses=bonuses_patch,
    )


@router.get("", response_model=SalonSettingsResponse, response_model_exclude_none=True)
def get_salon_settings(
    salon_id: uuid.UUID,
    context: WriteSalonContext,
    salon_settings_service: SalonSettingsServiceDep,
) -> SalonSettingsResponse:
    _assert_path_salon(context, salon_id)
    view = salon_settings_service.get_settings(salon_id=context.salon_id)
    return _to_response(view)


@router.patch("", response_model=SalonSettingsResponse, response_model_exclude_none=True)
def patch_salon_settings(
    salon_id: uuid.UUID,
    body: SalonSettingsPatchRequest,
    context: WriteSalonContext,
    salon_settings_service: SalonSettingsServiceDep,
) -> SalonSettingsResponse:
    _assert_path_salon(context, salon_id)
    view = salon_settings_service.patch_settings(
        salon_id=context.salon_id,
        patch=_patch_from_request(body),
    )
    return _to_response(view)


def _assert_path_salon(context: SalonContext, salon_id: uuid.UUID) -> None:
    if context.salon_id != salon_id:
        raise RuntimeError("salon_id path mismatch with SalonContext")
