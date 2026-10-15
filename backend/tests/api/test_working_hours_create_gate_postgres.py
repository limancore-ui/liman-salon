"""PostgreSQL: working_hours.create fingerprint, acknowledgement, and exclusive lock."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, time, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.api.deps import get_clock
from app.auth.deps import get_auth_repository
from app.core.security import create_access_token
from app.db.models.booking import Booking
from app.db.models.customer import Customer
from app.db.models.salon import Salon
from app.db.models.service import Service
from app.db.models.staff import Staff
from app.db.models.staff_service import StaffService
from app.db.models.working_hour import WorkingHour
from app.db.session import SessionLocal, engine
from app.main import create_app
from app.services.booking.service import BookingService
from app.services.customer.service import CustomerService, PublicCustomerResolveData
from app.services.schedule.impact import ScheduleImpactService
from app.services.schedule.overlay import WorkingHoursCreateChange

UTC = timezone.utc
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
AS_OF = datetime(2026, 8, 1, 8, 0, tzinfo=UTC)
# Same instant as AS_OF, expressed with a non-UTC offset.
ECHOED_AS_OF = "2026-08-01T13:00:00+05:00"


def _postgres_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_available(),
    reason="PostgreSQL test database not reachable",
)


def _cleanup_salon(salon_id: uuid.UUID) -> None:
    session = SessionLocal()
    try:
        session.execute(delete(Booking).where(Booking.salon_id == salon_id))
        session.execute(delete(Customer).where(Customer.salon_id == salon_id))
        session.execute(delete(StaffService).where(StaffService.salon_id == salon_id))
        session.execute(delete(Service).where(Service.salon_id == salon_id))
        session.execute(delete(Staff).where(Staff.salon_id == salon_id))
        session.execute(delete(WorkingHour).where(WorkingHour.salon_id == salon_id))
        session.execute(delete(Salon).where(Salon.id == salon_id))
        session.commit()
    finally:
        session.close()


def _seed_open_salon(session: Session) -> tuple[Salon, Staff, Service]:
    suffix = uuid.uuid4().hex[:8]
    salon = Salon(
        name=f"Create Gate {suffix}",
        slug=f"create-gate-{suffix}",
        timezone="UTC",
        currency_code="KZT",
        is_active=True,
    )
    session.add(salon)
    session.flush()
    for day in range(7):
        session.add(
            WorkingHour(
                salon_id=salon.id,
                staff_id=None,
                day_of_week=day,
                start_time=time(0, 0),
                end_time=time(23, 59),
            )
        )
    staff = Staff(
        salon_id=salon.id,
        display_name="Stylist",
        is_active=True,
        is_bookable=True,
        sort_order=1,
    )
    service = Service(
        salon_id=salon.id,
        name="Cut",
        duration_minutes=60,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
        price_cents=1000,
        is_active=True,
        sort_order=1,
    )
    session.add_all([staff, service])
    session.flush()
    session.add(
        StaffService(
            salon_id=salon.id,
            staff_id=staff.id,
            service_id=service.id,
        )
    )
    session.flush()
    return salon, staff, service


def _seed_thursday_salon(session: Session) -> tuple[Salon, Staff, Service]:
    suffix = uuid.uuid4().hex[:8]
    salon = Salon(
        name=f"Create Gate Thu {suffix}",
        slug=f"create-gate-thu-{suffix}",
        timezone="UTC",
        currency_code="KZT",
        is_active=True,
    )
    session.add(salon)
    session.flush()
    session.add(
        WorkingHour(
            salon_id=salon.id,
            staff_id=None,
            day_of_week=3,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
    )
    staff = Staff(
        salon_id=salon.id,
        display_name="Stylist",
        is_active=True,
        is_bookable=True,
        sort_order=1,
    )
    service = Service(
        salon_id=salon.id,
        name="Cut",
        duration_minutes=60,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
        price_cents=1000,
        is_active=True,
        sort_order=1,
    )
    session.add_all([staff, service])
    session.flush()
    session.add(
        StaffService(
            salon_id=salon.id,
            staff_id=staff.id,
            service_id=service.id,
        )
    )
    session.flush()
    return salon, staff, service


def _count_hours(salon_id: uuid.UUID, *, day_of_week: int | None = None) -> int:
    session = SessionLocal()
    try:
        stmt = select(func.count()).select_from(WorkingHour).where(WorkingHour.salon_id == salon_id)
        if day_of_week is not None:
            stmt = stmt.where(WorkingHour.day_of_week == day_of_week)
        value = session.scalar(stmt)
        return int(value or 0)
    finally:
        session.close()


def _preview(session: Session, salon_id: uuid.UUID):
    return ScheduleImpactService(session).preview_impact(
        salon_id=salon_id,
        change=WorkingHoursCreateChange(
            staff_id=None,
            day_of_week=5,
            start_time=time(9, 0),
            end_time=time(12, 0),
        ),
        as_of=AS_OF,
        horizon_days=90,
    )


def _client(salon: Salon) -> tuple[TestClient, dict[str, str]]:
    app = create_app()
    mock_auth = MagicMock()
    mock_auth.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID,
        email="owner@example.com",
        full_name="Owner",
        is_active=True,
    )
    mock_auth.get_active_salon.return_value = SimpleNamespace(
        id=salon.id,
        name=salon.name,
        slug=salon.slug,
        is_active=True,
        timezone="UTC",
        currency_code="KZT",
    )
    mock_auth.get_active_membership.return_value = SimpleNamespace(
        salon_id=salon.id,
        user_id=USER_ID,
        role="owner",
        is_active=True,
    )
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    app.dependency_overrides[get_clock] = lambda: (lambda: AS_OF)
    token, _ = create_access_token(user_id=USER_ID, now=datetime.now(UTC))
    return TestClient(app), {"Authorization": f"Bearer {token}"}


def _create_body(fingerprint: str, *, acknowledge: bool, day_of_week: int = 5) -> dict[str, object]:
    return {
        "day_of_week": day_of_week,
        "start_time": "09:00:00",
        "end_time": "12:00:00",
        "impact_fingerprint": fingerprint,
        "as_of": ECHOED_AS_OF,
        "horizon_days": 90,
        "acknowledge_impacts": acknowledge,
    }


def test_booking_move_invalidates_fingerprint_and_ack_blocks_insert() -> None:
    session = SessionLocal()
    salon_id: uuid.UUID | None = None
    try:
        salon, staff, service = _seed_thursday_salon(session)
        salon_id = salon.id
        staff_id = staff.id
        service_id = service.id
        customer_id = CustomerService(session).resolve_public_customer(
            salon_id=salon_id,
            data=PublicCustomerResolveData(
                full_name="Gate Patron",
                phone=f"+774{uuid.uuid4().int % 10_000_000:07d}",
            ),
        ).customer_id
        created = BookingService(session).create_booking(
            salon_id=salon_id,
            customer_id=customer_id,
            staff_id=staff_id,
            service_id=service_id,
            requested_service_start=datetime(2026, 8, 6, 10, 0, tzinfo=UTC),
            source="admin",
            status="confirmed",
            as_of=AS_OF,
        )
        session.commit()
        original = _preview(session, salon_id)
        assert original.all_impacts == ()
        session.commit()

        booking = session.get(Booking, created.booking_id)
        assert booking is not None
        booking.starts_at = datetime(2026, 8, 7, 10, 0, tzinfo=UTC)
        booking.ends_at = datetime(2026, 8, 7, 11, 0, tzinfo=UTC)
        session.commit()
        moved = _preview(session, salon_id)
        assert len(moved.all_impacts) == 1
        assert moved.impact_fingerprint != original.impact_fingerprint
        session.commit()

        client, headers = _client(salon)
        url = f"/api/v1/salons/{salon_id}/schedule/working-hours"
        try:
            stale = client.post(
                url,
                headers=headers,
                json=_create_body(original.impact_fingerprint, acknowledge=False),
            )
            assert stale.status_code == 409
            assert stale.json()["code"] == "impact_stale"
            assert _count_hours(salon_id, day_of_week=5) == 0

            unacked = client.post(
                url,
                headers=headers,
                json=_create_body(moved.impact_fingerprint, acknowledge=False),
            )
            assert unacked.status_code == 409
            assert unacked.json()["code"] == "impact_ack_required"
            assert _count_hours(salon_id, day_of_week=5) == 0

            created_response = client.post(
                url,
                headers=headers,
                json=_create_body(moved.impact_fingerprint, acknowledge=True),
            )
            assert created_response.status_code == 201
            assert _count_hours(salon_id, day_of_week=5) == 1
        finally:
            client.close()
    finally:
        session.close()
        if salon_id is not None:
            _cleanup_salon(salon_id)


def test_exclusive_create_conflicts_with_booking_shared_lock_then_succeeds() -> None:
    session = SessionLocal()
    salon_id: uuid.UUID | None = None
    try:
        salon, staff, service = _seed_open_salon(session)
        salon_id = salon.id
        staff_id = staff.id
        service_id = service.id
        session.commit()
        preview = ScheduleImpactService(session).preview_impact(
            salon_id=salon_id,
            change=WorkingHoursCreateChange(
                staff_id=None,
                day_of_week=0,
                start_time=time(9, 0),
                end_time=time(12, 0),
            ),
            as_of=AS_OF,
            horizon_days=1,
        )
        assert preview.all_impacts == ()
        session.commit()
        before = _count_hours(salon_id)
        fingerprint = preview.impact_fingerprint

        held = threading.Event()
        release = threading.Event()
        errors: list[BaseException] = []

        def hold_booking_shared_lock() -> None:
            holder = SessionLocal()
            try:
                customer_id = CustomerService(holder).resolve_public_customer(
                    salon_id=salon_id,
                    data=PublicCustomerResolveData(
                        full_name="Lock Holder",
                        phone=f"+773{uuid.uuid4().int % 10_000_000:07d}",
                    ),
                ).customer_id
                BookingService(holder).create_booking(
                    salon_id=salon_id,
                    customer_id=customer_id,
                    staff_id=staff_id,
                    service_id=service_id,
                    requested_service_start=datetime(2026, 8, 6, 14, 0, tzinfo=UTC),
                    source="admin",
                    status="confirmed",
                    as_of=AS_OF,
                )
                held.set()
                assert release.wait(timeout=20)
            except BaseException as exc:
                errors.append(exc)
                held.set()
            finally:
                holder.rollback()
                holder.close()

        worker = threading.Thread(target=hold_booking_shared_lock)
        worker.start()
        assert held.wait(timeout=15), errors
        client, headers = _client(salon)
        url = f"/api/v1/salons/{salon_id}/schedule/working-hours"
        body = _create_body(fingerprint, acknowledge=False, day_of_week=0)
        body["horizon_days"] = 1
        try:
            busy = client.post(url, headers=headers, json=body)
            assert errors == []
            assert busy.status_code == 503
            assert busy.headers.get("retry-after") == "2"
            assert busy.json()["code"] == "schedule_busy"
            assert _count_hours(salon_id) == before
        finally:
            release.set()
            worker.join(timeout=20)
            client.close()

        assert not worker.is_alive()
        assert errors == []
        # The holder's booking transaction was rolled back with the shared lock.
        check = SessionLocal()
        try:
            leftover = check.scalar(
                select(func.count()).select_from(Booking).where(Booking.salon_id == salon_id)
            )
            assert int(leftover or 0) == 0
        finally:
            check.close()

        client, headers = _client(salon)
        try:
            created_response = client.post(url, headers=headers, json=body)
            assert created_response.status_code == 201
            assert _count_hours(salon_id) == before + 1
        finally:
            client.close()
    finally:
        session.close()
        if salon_id is not None:
            _cleanup_salon(salon_id)
