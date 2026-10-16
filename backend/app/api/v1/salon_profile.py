from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import SalonProfileServiceDep
from app.api.schemas.salon_profile import (
    SalonProfilePatchRequest,
    SalonProfileResponse,
)
from app.auth.deps import require_roles
from app.auth.principals import SalonContext
from app.services.salon_profile.service import SalonProfileView

router = APIRouter(prefix="/salons/{salon_id}/profile", tags=["salon-profile"])

WriteSalonContext = Annotated[SalonContext, Depends(require_roles("owner", "admin"))]


def _to_response(view: SalonProfileView) -> SalonProfileResponse:
    return SalonProfileResponse(
        salon_id=view.salon_id,
        name=view.name,
        slug=view.slug,
    )


@router.patch("", response_model=SalonProfileResponse)
def patch_salon_profile(
    salon_id: uuid.UUID,
    body: SalonProfilePatchRequest,
    context: WriteSalonContext,
    salon_profile_service: SalonProfileServiceDep,
) -> SalonProfileResponse:
    _assert_path_salon(context, salon_id)
    view = salon_profile_service.update_name(
        salon_id=context.salon_id,
        name=body.name,
    )
    return _to_response(view)


def _assert_path_salon(context: SalonContext, salon_id: uuid.UUID) -> None:
    if context.salon_id != salon_id:
        raise RuntimeError("salon_id path mismatch with SalonContext")
