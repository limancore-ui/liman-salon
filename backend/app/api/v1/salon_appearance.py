from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import SalonAppearanceServiceDep
from app.api.schemas.salon_appearance import (
    SalonAppearancePatchRequest,
    SalonAppearanceResponse,
)
from app.auth.deps import require_roles
from app.auth.principals import SalonContext
from app.services.salon_appearance.service import (
    SalonAppearancePatchData,
    SalonAppearanceView,
)

router = APIRouter(prefix="/salons/{salon_id}/appearance", tags=["salon-appearance"])

WriteSalonContext = Annotated[SalonContext, Depends(require_roles("owner", "admin"))]


def _to_response(view: SalonAppearanceView) -> SalonAppearanceResponse:
    return SalonAppearanceResponse(
        salon_id=view.salon_id,
        salon_name=view.salon_name,
        primary_color=view.primary_color,
        accent_soft_color=view.accent_soft_color,
        background_color=view.background_color,
        logo_media_id=view.logo_media_id,
        background_media_id=view.background_media_id,
    )


def _patch_from_request(body: SalonAppearancePatchRequest) -> SalonAppearancePatchData:
    colors_set = "colors" in body.model_fields_set
    return SalonAppearancePatchData(
        colors_set=colors_set,
        colors=body.colors if colors_set else None,
    )


@router.get("", response_model=SalonAppearanceResponse, response_model_exclude_none=True)
def get_salon_appearance(
    salon_id: uuid.UUID,
    context: WriteSalonContext,
    salon_appearance_service: SalonAppearanceServiceDep,
) -> SalonAppearanceResponse:
    _assert_path_salon(context, salon_id)
    view = salon_appearance_service.get_appearance(salon_id=context.salon_id)
    return _to_response(view)


@router.patch(
    "",
    response_model=SalonAppearanceResponse,
    response_model_exclude_none=True,
)
def patch_salon_appearance(
    salon_id: uuid.UUID,
    body: SalonAppearancePatchRequest,
    context: WriteSalonContext,
    salon_appearance_service: SalonAppearanceServiceDep,
) -> SalonAppearanceResponse:
    _assert_path_salon(context, salon_id)
    view = salon_appearance_service.patch_appearance(
        salon_id=context.salon_id,
        patch=_patch_from_request(body),
    )
    return _to_response(view)


def _assert_path_salon(context: SalonContext, salon_id: uuid.UUID) -> None:
    if context.salon_id != salon_id:
        raise RuntimeError("salon_id path mismatch with SalonContext")
