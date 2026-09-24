from __future__ import annotations

from app.auth.errors import ForbiddenRoleError
from app.auth.principals import SalonContext


def ensure_role_allowed(context: SalonContext, *allowed_roles: str) -> None:
    if context.role not in allowed_roles:
        raise ForbiddenRoleError("insufficient salon role")
