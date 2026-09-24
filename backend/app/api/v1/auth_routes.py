from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import ClockDep
from app.api.schemas.auth import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    SalonContextResponse,
)
from app.auth.deps import AuthRepositoryDep, CurrentUserDep, SalonContextDep
from app.auth.errors import InvalidCredentialsError
from app.core.security import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, repo: AuthRepositoryDep, clock: ClockDep) -> LoginResponse:
    user = repo.get_user_by_email(body.email)
    if user is None or not user.is_active:
        raise InvalidCredentialsError("invalid credentials")
    if not verify_password(body.password, user.password_hash):
        raise InvalidCredentialsError("invalid credentials")
    token, expires_in = create_access_token(user_id=user.id, now=clock())
    return LoginResponse(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=MeResponse)
def me(current_user: CurrentUserDep) -> MeResponse:
    return MeResponse(
        user_id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
    )


@router.get("/salons/{salon_id}/context", response_model=SalonContextResponse)
def salon_context(
    context: SalonContextDep,
    current_user: CurrentUserDep,
) -> SalonContextResponse:
    return SalonContextResponse(
        user_id=context.user_id,
        salon_id=context.salon_id,
        role=context.role,
        email=current_user.email,
        salon_name=context.salon_name,
        salon_slug=context.salon_slug,
    )
