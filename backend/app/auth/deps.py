from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.deps import SessionDep
from app.auth.errors import (
    SalonAccessDeniedError,
    SalonNotFoundError,
    UnauthorizedError,
)
from app.auth.principals import AuthenticatedUser, SalonContext
from app.auth.repository import AuthRepository
from app.auth.rbac import ensure_role_allowed
from app.core.security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


def get_auth_repository(session: SessionDep) -> AuthRepository:
    return AuthRepository(session)


AuthRepositoryDep = Annotated[AuthRepository, Depends(get_auth_repository)]


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    repo: AuthRepositoryDep,
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError("missing bearer token")
    try:
        user_id = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise UnauthorizedError("invalid or expired token") from exc
    user = repo.get_active_user_by_id(user_id)
    if user is None:
        raise UnauthorizedError("user not found or inactive")
    return AuthenticatedUser(id=user.id, email=user.email, full_name=user.full_name)


CurrentUserDep = Annotated[AuthenticatedUser, Depends(get_current_user)]


def get_salon_context(
    salon_id: uuid.UUID,
    current_user: CurrentUserDep,
    repo: AuthRepositoryDep,
) -> SalonContext:
    salon = repo.get_active_salon(salon_id)
    if salon is None:
        raise SalonNotFoundError("salon not found or inactive")
    membership = repo.get_active_membership(salon_id, current_user.id)
    if membership is None:
        raise SalonAccessDeniedError("no active salon membership")
    return SalonContext(
        user_id=current_user.id,
        salon_id=salon.id,
        role=membership.role,
        salon_name=salon.name,
        salon_slug=salon.slug,
        timezone=salon.timezone,
        currency_code=salon.currency_code,
    )


SalonContextDep = Annotated[SalonContext, Depends(get_salon_context)]


def require_roles(*allowed_roles: str):
    def _guard(context: SalonContextDep) -> SalonContext:
        ensure_role_allowed(context, *allowed_roles)
        return context

    return _guard
