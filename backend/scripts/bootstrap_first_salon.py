#!/usr/bin/env python3
"""Idempotent first-salon bootstrap: owner user, salon, owner membership.

Safe to re-run when the same email and salon slug are supplied; does not
create duplicate users or salons. Does not modify an existing user's password.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

from sqlalchemy import func, select

TEST_DB_NAME = "liman_salon_test"
BOOTSTRAP_ALLOW_ENV = "ALLOW_FIRST_SALON_BOOTSTRAP"
PRODUCTION_LIKE_ENVIRONMENTS = frozenset({"production", "staging"})


@dataclass(frozen=True)
class BootstrapResult:
    user_id: str
    user_action: str
    salon_id: str
    salon_slug: str
    salon_action: str
    membership_action: str


def database_name_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    if not parsed.scheme.startswith("postgres"):
        return None
    path = unquote(parsed.path or "").lstrip("/")
    return path.split("?")[0] or None


def assert_bootstrap_allowed(
    *,
    environment: str,
    database_url: str,
    allow_bootstrap: bool,
) -> None:
    env = environment.strip().lower()
    if env not in PRODUCTION_LIKE_ENVIRONMENTS:
        return

    if not allow_bootstrap:
        raise SystemExit(
            f"Refusing bootstrap: set {BOOTSTRAP_ALLOW_ENV}=1 when "
            f"ENVIRONMENT is {environment!r}."
        )

    db_name = database_name_from_url(database_url)
    if db_name == TEST_DB_NAME or TEST_DB_NAME in database_url:
        raise SystemExit(
            "Refusing bootstrap: production-like ENVIRONMENT must not target "
            f"database '{TEST_DB_NAME}' (parsed name: {db_name!r})."
        )


def _get_or_create_user(session, *, email: str, full_name: str, password: str):  # noqa: ANN001
    from app.core.security import hash_password, normalize_email
    from app.db.models.user import User

    normalized = normalize_email(email)
    user = session.scalar(select(User).where(func.lower(User.email) == normalized))
    if user is None:
        user = User(
            email=normalized,
            password_hash=hash_password(password),
            full_name=full_name.strip(),
            is_active=True,
            is_platform_admin=False,
        )
        session.add(user)
        session.flush()
        return user, "created"

    if not user.is_active:
        user.is_active = True
        session.flush()
    return user, "reused"


def _find_owned_salon(session, user_id):  # noqa: ANN001
    from app.db.models.salon import Salon
    from app.db.models.salon_user import SalonUser

    membership = session.scalar(
        select(SalonUser).where(
            SalonUser.user_id == user_id,
            SalonUser.role == "owner",
            SalonUser.is_active.is_(True),
        )
    )
    if membership is None:
        return None
    return session.get(Salon, membership.salon_id)


def _resolve_new_salon_slug(session, raw_slug: str | None, salon_name: str) -> str:  # noqa: ANN001
    from app.db.models.salon import Salon
    from app.services.salon_public.slug import dedupe_salon_slug, normalize_salon_slug

    if raw_slug and raw_slug.strip():
        slug = normalize_salon_slug(raw_slug)
        taken = session.scalar(select(Salon.id).where(Salon.slug == slug))
        if taken is not None:
            raise SystemExit(f"Refusing bootstrap: salon slug {slug!r} is already taken.")
        return slug

    base = normalize_salon_slug(salon_name)

    def exists(candidate: str) -> bool:
        return (
            session.scalar(select(Salon.id).where(Salon.slug == candidate)) is not None
        )

    return dedupe_salon_slug(base, exists)


def _get_or_create_salon(
    session,  # noqa: ANN001
    *,
    name: str,
    slug: str,
    timezone: str,
    currency_code: str,
):
    from app.db.models.salon import Salon

    salon = session.scalar(select(Salon).where(Salon.slug == slug))
    if salon is None:
        salon = Salon(
            name=name.strip(),
            slug=slug,
            timezone=timezone.strip(),
            currency_code=currency_code.strip().upper(),
            is_active=True,
        )
        session.add(salon)
        session.flush()
        return salon, "created"

    if salon.name != name.strip():
        salon.name = name.strip()
    salon.timezone = timezone.strip()
    salon.currency_code = currency_code.strip().upper()
    salon.is_active = True
    session.flush()
    return salon, "reused"


def _ensure_owner_membership(session, *, salon_id, user_id) -> str:  # noqa: ANN001
    from app.db.models.salon_user import SalonUser

    membership = session.scalar(
        select(SalonUser).where(
            SalonUser.salon_id == salon_id,
            SalonUser.user_id == user_id,
        )
    )
    if membership is None:
        session.add(
            SalonUser(
                salon_id=salon_id,
                user_id=user_id,
                role="owner",
                is_active=True,
            )
        )
        session.flush()
        return "created"

    if membership.salon_id != salon_id:
        raise RuntimeError("membership salon mismatch")
    if membership.role != "owner":
        raise SystemExit(
            "Refusing bootstrap: user already has a non-owner role for this salon."
        )
    if not membership.is_active:
        membership.is_active = True
        session.flush()
        return "reactivated"
    return "reused"


def run_bootstrap(
    *,
    email: str,
    password: str,
    full_name: str,
    salon_name: str,
    salon_slug: str | None,
    timezone: str,
    currency_code: str,
) -> BootstrapResult:
    from app.db.session import SessionLocal
    from app.services.salon_public.slug import normalize_salon_slug

    with SessionLocal() as session:
        user, user_action = _get_or_create_user(
            session,
            email=email,
            full_name=full_name,
            password=password,
        )

        owned = _find_owned_salon(session, user.id)
        if owned is not None:
            salon = owned
            salon_action = "reused"
            if salon_slug and normalize_salon_slug(salon_slug) != salon.slug:
                raise SystemExit(
                    "Refusing bootstrap: user already owns a salon; omit --salon-slug "
                    "or use the existing slug."
                )
            salon.name = salon_name.strip()
            salon.timezone = timezone.strip()
            salon.currency_code = currency_code.strip().upper()
            salon.is_active = True
            session.flush()
        else:
            slug = _resolve_new_salon_slug(session, salon_slug, salon_name)
            salon, salon_action = _get_or_create_salon(
                session,
                name=salon_name,
                slug=slug,
                timezone=timezone,
                currency_code=currency_code,
            )
            if salon_action == "reused":
                existing_owners = session.scalars(
                    select(SalonUser).where(
                        SalonUser.salon_id == salon.id,
                        SalonUser.role == "owner",
                        SalonUser.user_id != user.id,
                        SalonUser.is_active.is_(True),
                    )
                ).all()
                if existing_owners:
                    raise SystemExit(
                        "Refusing bootstrap: salon already has another active owner."
                    )

        membership_action = _ensure_owner_membership(
            session,
            salon_id=salon.id,
            user_id=user.id,
        )

        session.commit()

        return BootstrapResult(
            user_id=str(user.id),
            user_action=user_action,
            salon_id=str(salon.id),
            salon_slug=salon.slug,
            salon_action=salon_action,
            membership_action=membership_action,
        )


def _load_env_from_backend_dotenv() -> None:
    from pathlib import Path

    env_file = Path(__file__).resolve().parents[1] / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


def _configure_app_env() -> tuple[str, str, bool]:
    _load_env_from_backend_dotenv()
    from app.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    allow = os.environ.get(BOOTSTRAP_ALLOW_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    assert_bootstrap_allowed(
        environment=settings.environment,
        database_url=settings.database_url,
        allow_bootstrap=allow,
    )
    return settings.environment, settings.database_url, allow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bootstrap the first salon owner, salon tenant, and owner membership.",
    )
    parser.add_argument("--email", required=True, help="Owner login email")
    parser.add_argument("--password", required=True, help="Owner password (new users only)")
    parser.add_argument("--full-name", required=True, dest="full_name", help="Owner display name")
    parser.add_argument("--salon-name", required=True, dest="salon_name", help="Salon name")
    parser.add_argument(
        "--salon-slug",
        dest="salon_slug",
        default=None,
        help="Public URL slug (derived from salon name when omitted)",
    )
    parser.add_argument(
        "--timezone",
        default="Asia/Bishkek",
        help="IANA timezone (default: Asia/Bishkek)",
    )
    parser.add_argument(
        "--currency",
        default="KGS",
        dest="currency_code",
        help="ISO 4217 currency code (default: KGS)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)

    args = build_parser().parse_args(argv)
    _configure_app_env()

    result = run_bootstrap(
        email=args.email,
        password=args.password,
        full_name=args.full_name,
        salon_name=args.salon_name,
        salon_slug=args.salon_slug,
        timezone=args.timezone,
        currency_code=args.currency_code,
    )

    print("=== First salon bootstrap OK ===")
    print(f"User: id={result.user_id} ({result.user_action})")
    print(
        f"Salon: id={result.salon_id} slug={result.salon_slug} ({result.salon_action})"
    )
    print(f"Owner membership: {result.membership_action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
