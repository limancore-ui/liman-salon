#!/usr/bin/env python3
"""Idempotent staging-only demo seed for public booking smoke tests.

Creates fictional salon catalog data (salon, staff, services, links, hours).
Does **not** create users, passwords, customers, or bookings.

Owner / admin login is a **separate** step via ``bootstrap_first_salon.py``
(with ``ALLOW_FIRST_SALON_BOOTSTRAP=1``). Prefer running bootstrap first with
the same ``--salon-slug malina-beauty-test`` when admin UI access is needed;
this seed will reuse that salon by slug.

Writes only when **all** of the following hold:

- ``ENVIRONMENT=staging``
- database name is exactly ``liman_salon_staging``
- ``ALLOW_STAGING_DEMO_SEED=1`` (or true/yes)

Refuses before any DB write otherwise. Does not target production or
``liman_salon_test`` (see ``seed_public_booking_test.py`` for local test DB).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import time
from urllib.parse import unquote, urlparse

STAGING_DB_NAME = "liman_salon_staging"
ALLOW_ENV = "ALLOW_STAGING_DEMO_SEED"
REQUIRED_ENVIRONMENT = "staging"

SALON_NAME = "Malina Beauty Test"
SALON_SLUG = "malina-beauty-test"
SALON_TIMEZONE = "Asia/Bishkek"
SALON_CURRENCY = "KGS"

DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    duration_minutes: int
    price_kgs: int
    sort_order: int

    @property
    def price_cents(self) -> int:
        return self.price_kgs * 100


SERVICE_SPECS: tuple[ServiceSpec, ...] = (
    ServiceSpec("Женская стрижка", 60, 800, 1),
    ServiceSpec("Окрашивание", 120, 2500, 2),
    ServiceSpec("Ресницы 2D", 120, 1800, 3),
    ServiceSpec("Маникюр", 60, 1000, 4),
)

STAFF_NAMES: tuple[str, str] = ("Айжан", "Мээрим")

STAFF_SERVICE_MAP: dict[str, tuple[str, ...]] = {
    "Айжан": ("Женская стрижка", "Окрашивание"),
    "Мээрим": ("Ресницы 2D", "Маникюр"),
}

WORK_DAYS = range(0, 6)  # Mon–Sat
OPEN_TIME = time(10, 0)
CLOSE_TIME = time(19, 0)


def database_name_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    if not parsed.scheme.startswith("postgres"):
        return None
    path = unquote(parsed.path or "").lstrip("/")
    return path.split("?")[0] or None


def assert_staging_demo_allowed(
    *,
    environment: str,
    database_url: str,
    allow_seed: bool,
) -> None:
    """Refuse before any write unless staging + liman_salon_staging + allow flag."""
    env = environment.strip().lower()
    if env != REQUIRED_ENVIRONMENT:
        raise SystemExit(
            f"Refusing staging demo seed: ENVIRONMENT must be "
            f"{REQUIRED_ENVIRONMENT!r} (got {environment!r})."
        )

    if not allow_seed:
        raise SystemExit(
            f"Refusing staging demo seed: set {ALLOW_ENV}=1 when "
            f"ENVIRONMENT is {REQUIRED_ENVIRONMENT!r}."
        )

    db_name = database_name_from_url(database_url)
    if db_name != STAGING_DB_NAME:
        raise SystemExit(
            "Refusing staging demo seed: database name must be exactly "
            f"{STAGING_DB_NAME!r} (parsed name: {db_name!r})."
        )


def _get_or_create_salon(session):  # noqa: ANN001
    from sqlalchemy import select

    from app.db.models.salon import Salon

    salon = session.scalar(select(Salon).where(Salon.slug == SALON_SLUG))
    if salon is None:
        salon = Salon(
            name=SALON_NAME,
            slug=SALON_SLUG,
            timezone=SALON_TIMEZONE,
            currency_code=SALON_CURRENCY,
            is_active=True,
        )
        session.add(salon)
        session.flush()
        return salon, "created"

    # Reuse by slug; keep demo identity fields aligned, leave unrelated salons alone.
    salon.name = SALON_NAME
    salon.timezone = SALON_TIMEZONE
    salon.currency_code = SALON_CURRENCY
    salon.is_active = True
    session.flush()
    return salon, "reused"


def _get_or_create_staff(session, salon_id, display_name: str, sort_order: int):  # noqa: ANN001
    from sqlalchemy import select

    from app.db.models.staff import Staff

    staff = session.scalar(
        select(Staff).where(
            Staff.salon_id == salon_id,
            Staff.display_name == display_name,
        )
    )
    if staff is None:
        staff = Staff(
            salon_id=salon_id,
            display_name=display_name,
            is_active=True,
            is_bookable=True,
            sort_order=sort_order,
        )
        session.add(staff)
        session.flush()
        return staff, "created"

    staff.is_active = True
    staff.is_bookable = True
    staff.sort_order = sort_order
    session.flush()
    return staff, "reused"


def _get_or_create_service(session, salon_id, spec: ServiceSpec):  # noqa: ANN001
    from sqlalchemy import select

    from app.db.models.service import Service

    service = session.scalar(
        select(Service).where(
            Service.salon_id == salon_id,
            Service.name == spec.name,
        )
    )
    if service is None:
        service = Service(
            salon_id=salon_id,
            name=spec.name,
            duration_minutes=spec.duration_minutes,
            price_cents=spec.price_cents,
            is_active=True,
            sort_order=spec.sort_order,
        )
        session.add(service)
        session.flush()
        return service, "created"

    service.duration_minutes = spec.duration_minutes
    service.price_cents = spec.price_cents
    service.is_active = True
    service.sort_order = spec.sort_order
    session.flush()
    return service, "reused"


def _ensure_staff_service(session, salon_id, staff_id, service_id) -> str:  # noqa: ANN001
    from sqlalchemy import select

    from app.db.models.staff_service import StaffService

    link = session.scalar(
        select(StaffService).where(
            StaffService.staff_id == staff_id,
            StaffService.service_id == service_id,
        )
    )
    if link is None:
        session.add(
            StaffService(
                salon_id=salon_id,
                staff_id=staff_id,
                service_id=service_id,
            )
        )
        session.flush()
        return "created"
    if link.salon_id != salon_id:
        raise RuntimeError("staff_service row belongs to another salon")
    return "reused"


def _sync_salon_working_hours(session, salon_id) -> list[str]:  # noqa: ANN001
    """Ensure Mon–Sat salon-level hours; close Sunday. Does not touch staff hours."""
    from sqlalchemy import select

    from app.db.models.working_hour import WorkingHour

    existing = list(
        session.scalars(
            select(WorkingHour).where(
                WorkingHour.salon_id == salon_id,
                WorkingHour.staff_id.is_(None),
            )
        ).all()
    )
    by_day: dict[int, list] = {}
    for row in existing:
        by_day.setdefault(row.day_of_week, []).append(row)

    actions: list[str] = []
    for dow in WORK_DAYS:
        rows = by_day.get(dow, [])
        if not rows:
            session.add(
                WorkingHour(
                    salon_id=salon_id,
                    staff_id=None,
                    day_of_week=dow,
                    start_time=OPEN_TIME,
                    end_time=CLOSE_TIME,
                )
            )
            actions.append(f"{DAY_NAMES[dow]}: created")
            continue
        primary = rows[0]
        primary.start_time = OPEN_TIME
        primary.end_time = CLOSE_TIME
        primary.effective_from = None
        primary.effective_to = None
        for extra in rows[1:]:
            session.delete(extra)
            actions.append(f"{DAY_NAMES[dow]}: removed duplicate")
        actions.append(f"{DAY_NAMES[dow]}: updated")

    for row in by_day.get(6, []):
        session.delete(row)
        actions.append("Sun: removed (closed)")

    session.flush()
    return actions


def _verify_seed(session, salon_id) -> None:  # noqa: ANN001
    from sqlalchemy import select

    from app.db.models.salon import Salon
    from app.db.models.service import Service
    from app.db.models.staff import Staff
    from app.db.models.staff_service import StaffService
    from app.db.models.working_hour import WorkingHour

    salon = session.get(Salon, salon_id)
    assert salon is not None and salon.is_active and salon.slug == SALON_SLUG
    assert salon.timezone == SALON_TIMEZONE
    assert salon.currency_code == SALON_CURRENCY

    staff_rows = list(
        session.scalars(select(Staff).where(Staff.salon_id == salon_id)).all()
    )
    active_staff = [s for s in staff_rows if s.display_name in STAFF_NAMES]
    assert len(active_staff) == 2
    assert all(s.is_active and s.is_bookable and s.salon_id == salon_id for s in active_staff)

    services = list(
        session.scalars(select(Service).where(Service.salon_id == salon_id)).all()
    )
    seeded_services = [s for s in services if s.name in {sp.name for sp in SERVICE_SPECS}]
    assert len(seeded_services) == 4
    assert all(s.is_active and s.salon_id == salon_id for s in seeded_services)

    staff_by_name = {s.display_name: s for s in active_staff}
    service_by_name = {s.name: s for s in seeded_services}
    for staff_name, service_names in STAFF_SERVICE_MAP.items():
        st = staff_by_name[staff_name]
        for svc_name in service_names:
            svc = service_by_name[svc_name]
            link = session.scalar(
                select(StaffService).where(
                    StaffService.staff_id == st.id,
                    StaffService.service_id == svc.id,
                )
            )
            assert link is not None and link.salon_id == salon_id

    hours = list(
        session.scalars(
            select(WorkingHour).where(
                WorkingHour.salon_id == salon_id,
                WorkingHour.staff_id.is_(None),
            )
        ).all()
    )
    hour_days = {h.day_of_week for h in hours}
    assert hour_days == set(WORK_DAYS)
    for h in hours:
        assert h.start_time == OPEN_TIME and h.end_time == CLOSE_TIME


def seed_demo_catalog(session) -> tuple[object, str]:  # noqa: ANN001
    """Insert/update demo catalog rows. Caller owns transaction commit."""
    salon, salon_action = _get_or_create_salon(session)

    staff_by_name: dict[str, object] = {}
    for idx, name in enumerate(STAFF_NAMES):
        staff, _action = _get_or_create_staff(session, salon.id, name, idx + 1)
        staff_by_name[name] = staff

    service_by_name: dict[str, object] = {}
    for spec in SERVICE_SPECS:
        service, _action = _get_or_create_service(session, salon.id, spec)
        service_by_name[spec.name] = service

    for staff_name, service_names in STAFF_SERVICE_MAP.items():
        staff = staff_by_name[staff_name]
        for svc_name in service_names:
            svc = service_by_name[svc_name]
            _ensure_staff_service(
                session,
                salon.id,
                staff.id,  # type: ignore[attr-defined]
                svc.id,  # type: ignore[attr-defined]
            )

    _sync_salon_working_hours(session, salon.id)
    _verify_seed(session, salon.id)
    return salon, salon_action


def _configure_app_env() -> tuple[str, str, bool]:
    from app.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    allow = os.environ.get(ALLOW_ENV, "").strip().lower() in {"1", "true", "yes"}
    assert_staging_demo_allowed(
        environment=settings.environment,
        database_url=settings.database_url,
        allow_seed=allow,
    )
    return settings.environment, settings.database_url, allow


def seed() -> int:
    _configure_app_env()

    from app.db.session import SessionLocal
    from sqlalchemy import func, select

    from app.db.models.service import Service
    from app.db.models.staff import Staff
    from app.db.models.staff_service import StaffService
    from app.db.models.user import User
    from app.db.models.working_hour import WorkingHour

    with SessionLocal() as session:
        users_before = session.scalar(select(func.count()).select_from(User)) or 0

        salon, salon_action = seed_demo_catalog(session)

        staff_count = session.scalar(
            select(func.count()).select_from(Staff).where(Staff.salon_id == salon.id)
        )
        service_count = session.scalar(
            select(func.count()).select_from(Service).where(Service.salon_id == salon.id)
        )
        link_count = session.scalar(
            select(func.count())
            .select_from(StaffService)
            .where(StaffService.salon_id == salon.id)
        )
        hour_count = session.scalar(
            select(func.count())
            .select_from(WorkingHour)
            .where(
                WorkingHour.salon_id == salon.id,
                WorkingHour.staff_id.is_(None),
            )
        )

        users_after = session.scalar(select(func.count()).select_from(User)) or 0
        if users_after != users_before:
            raise SystemExit(
                "Refusing commit: staging demo seed must not create or delete users "
                f"(before={users_before}, after={users_after})."
            )

        session.commit()

        print("=== Staging demo seed OK ===")
        print(f"Salon: id={salon.id} slug={salon.slug} ({salon_action})")
        print(
            f"  timezone={salon.timezone} currency={salon.currency_code} "
            f"active={salon.is_active}"
        )
        print(f"Staff rows (salon): {staff_count}")
        print(f"Service rows (salon): {service_count}")
        print(f"Staff↔service links: {link_count}")
        print(f"Salon working-hour rows: {hour_count}")
        print(
            "Note: no owner/user was created. For admin UI, run "
            "scripts/bootstrap_first_salon.py separately with "
            f"--salon-slug {SALON_SLUG!r} and ALLOW_FIRST_SALON_BOOTSTRAP=1."
        )
        print(f"Public page path: /s/{SALON_SLUG}")

    return 0


def main(argv: list[str] | None = None) -> int:
    del argv  # CLI has no args; guards come from environment only
    backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)
    return seed()


if __name__ == "__main__":
    raise SystemExit(main())
