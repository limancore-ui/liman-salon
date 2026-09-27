#!/usr/bin/env python3
"""Local-only idempotent seed for manual public booking flow tests.

Refuses to run unless DATABASE_URL targets the ``liman_salon_test`` database.
Does not create customers or modify production application code paths.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import time
from urllib.parse import unquote, urlparse

TEST_DB_NAME = "liman_salon_test"

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

WORK_DAYS = range(0, 6)  # Mon–Sat (Python weekday: Mon=0, Sun=6)
OPEN_TIME = time(10, 0)
CLOSE_TIME = time(19, 0)


def _database_name_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    if not parsed.scheme.startswith("postgres"):
        return None
    path = unquote(parsed.path or "").lstrip("/")
    return path.split("?")[0] or None


def _assert_test_database_url(url: str) -> None:
    if not url.strip():
        raise SystemExit(
            "Refusing to seed: DATABASE_URL is not set. "
            f"Point it at {TEST_DB_NAME} and re-run."
        )
    db_name = _database_name_from_url(url)
    if db_name == TEST_DB_NAME or TEST_DB_NAME in url:
        return
    raise SystemExit(
        "Refusing to seed: DATABASE_URL must target database "
        f"'{TEST_DB_NAME}' (parsed name: {db_name!r})."
    )


def _configure_app_env() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        from pathlib import Path

        env_file = Path(__file__).resolve().parents[1] / ".env"
        if env_file.is_file():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("DATABASE_URL=") and not line.startswith("#"):
                    _, _, value = line.partition("=")
                    url = value.strip().strip('"').strip("'")
                    os.environ.setdefault("DATABASE_URL", url)
                    break
    url = os.environ.get("DATABASE_URL", "").strip()
    _assert_test_database_url(url)
    os.environ.setdefault(
        "JWT_SECRET_KEY",
        "01234567890123456789012345678901",
    )
    from app.core.config import get_settings

    get_settings.cache_clear()
    return url


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
    by_day: dict[int, list[WorkingHour]] = {}
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

    sunday_rows = by_day.get(6, [])
    for row in sunday_rows:
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


def seed() -> int:
    _configure_app_env()

    from app.db.session import SessionLocal

    with SessionLocal() as session:
        salon, salon_action = _get_or_create_salon(session)

        staff_log: list[tuple[str, str, str]] = []
        staff_by_name: dict[str, object] = {}
        for idx, name in enumerate(STAFF_NAMES):
            staff, action = _get_or_create_staff(session, salon.id, name, idx + 1)
            staff_by_name[name] = staff
            staff_log.append((name, str(staff.id), action))

        service_log: list[tuple[str, str, str]] = []
        service_by_name: dict[str, object] = {}
        for spec in SERVICE_SPECS:
            service, action = _get_or_create_service(session, salon.id, spec)
            service_by_name[spec.name] = service
            service_log.append((spec.name, str(service.id), action))

        assignment_log: list[str] = []
        for staff_name, service_names in STAFF_SERVICE_MAP.items():
            staff = staff_by_name[staff_name]
            for svc_name in service_names:
                svc = service_by_name[svc_name]
                link_action = _ensure_staff_service(
                    session, salon.id, staff.id, svc.id  # type: ignore[attr-defined]
                )
                assignment_log.append(f"{staff_name} ↔ {svc_name} ({link_action})")

        wh_actions = _sync_salon_working_hours(session, salon.id)

        _verify_seed(session, salon.id)
        session.commit()

        print("=== Public booking test seed OK ===")
        print(f"Salon: id={salon.id} slug={salon.slug} ({salon_action})")
        print(f"  timezone={salon.timezone} currency={salon.currency_code} active={salon.is_active}")
        print("Staff:")
        for name, sid, action in staff_log:
            print(f"  - {name}: id={sid} ({action})")
        print("Services:")
        for name, sid, action in service_log:
            spec = next(s for s in SERVICE_SPECS if s.name == name)
            print(
                f"  - {name}: id={sid} duration={spec.duration_minutes}min "
                f"price_cents={spec.price_cents} ({action})"
            )
        print("Staff ↔ service:")
        for line in assignment_log:
            print(f"  - {line}")
        print("Salon working hours (Mon–Sat 10:00–19:00, Sun closed):")
        for line in wh_actions:
            print(f"  - {line}")

    return 0


def main() -> None:
    backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)
    raise SystemExit(seed())


if __name__ == "__main__":
    main()
