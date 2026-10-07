"""PostgreSQL HTTP E2E for public booking reschedule (token-gated)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.deps import get_as_of, get_db
from app.db.models.booking import Booking
from app.db.models.salon import Salon
from app.db.models.service import Service
from app.db.models.staff import Staff
from app.db.models.staff_service import StaffService
from app.db.models.working_hour import WorkingHour
from app.db.session import engine
from app.main import create_app

UTC = timezone.utc
FIXED_AS_OF = datetime(2026, 8, 1, 8, 0, tzinfo=UTC)


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


@pytest.fixture
def db_session() -> Session:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def _seed_bookable_salon(session: Session) -> tuple[Salon, Staff, Service]:
    suffix = uuid.uuid4().hex[:8]
    salon = Salon(
        name=f"Reschedule E2E {suffix}",
        slug=f"reschedule-e2e-{suffix}",
        timezone="UTC",
        currency_code="KZT",
        is_active=True,
    )
    session.add(salon)
    session.flush()

    for day in range(0, 7):
        session.add(
            WorkingHour(
                salon_id=salon.id,
                staff_id=None,
                day_of_week=day,
                start_time=time(9, 0),
                end_time=time(12, 0),
            )
        )
        session.add(
            WorkingHour(
                salon_id=salon.id,
                staff_id=None,
                day_of_week=day,
                start_time=time(14, 0),
                end_time=time(17, 0),
            )
        )

    staff = Staff(
        salon_id=salon.id,
        display_name="Bookable",
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


@pytest.fixture
def public_client(db_session: Session) -> TestClient:
    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()
        app.dependency_overrides.clear()


def _availability_params(
    *,
    service_id: uuid.UUID,
    staff_id: uuid.UUID,
    day: date,
) -> dict[str, str]:
    day_str = day.isoformat()
    return {
        "service_id": str(service_id),
        "start_date": day_str,
        "end_date": day_str,
        "staff_id": str(staff_id),
    }


def _first_slot(body: dict[str, Any], staff_id: uuid.UUID) -> dict[str, str]:
    staff_key = str(staff_id)
    for row in body["staff"]:
        if row["staff_id"] == staff_key and row["slots"]:
            return row["slots"][0]
    raise AssertionError(f"no slots for staff {staff_key}")


def _create_public_booking(
    client: TestClient,
    *,
    base: str,
    service_id: uuid.UUID,
    staff_id: uuid.UUID,
    service_start: str,
) -> tuple[uuid.UUID, str]:
    phone = f"+7780{uuid.uuid4().int % 10_000_000:07d}"
    resp = client.post(
        f"{base}/bookings",
        json={
            "full_name": "Reschedule Guest",
            "phone": phone,
            "service_id": str(service_id),
            "staff_id": str(staff_id),
            "service_start": service_start,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    return uuid.UUID(body["booking_id"]), body["manage_token"]


def test_reschedule_pending_updates_stored_times(
    db_session: Session,
    public_client: TestClient,
) -> None:
    salon, staff, service = _seed_bookable_salon(db_session)
    base = f"/api/v1/public/salons/{salon.slug}"
    probe_day = date(2026, 8, 3)

    avail = public_client.get(
        f"{base}/availability/service",
        params=_availability_params(
            service_id=service.id,
            staff_id=staff.id,
            day=probe_day,
        ),
    )
    assert avail.status_code == 200
    slots = avail.json()
    first = _first_slot(slots, staff.id)
    second = None
    for row in slots["staff"]:
        if row["staff_id"] == str(staff.id) and len(row["slots"]) > 1:
            second = row["slots"][1]
            break
    assert second is not None

    booking_id, token = _create_public_booking(
        public_client,
        base=base,
        service_id=service.id,
        staff_id=staff.id,
        service_start=first["service_start"],
    )

    reschedule_resp = public_client.post(
        f"{base}/bookings/{booking_id}/reschedule",
        json={
            "token": token,
            "staff_id": str(staff.id),
            "service_start": second["service_start"],
        },
    )
    assert reschedule_resp.status_code == 200
    body = reschedule_resp.json()
    assert set(body.keys()) == {
        "booking_id",
        "status",
        "staff_id",
        "service_start",
        "service_end",
    }
    assert body["booking_id"] == str(booking_id)
    assert body["status"] == "pending"
    assert body["staff_id"] == str(staff.id)

    row = db_session.scalar(
        select(Booking).where(
            Booking.salon_id == salon.id,
            Booking.id == booking_id,
        )
    )
    assert row is not None
    assert row.starts_at == datetime.fromisoformat(
        body["service_start"].replace("Z", "+00:00")
    )
    assert row.staff_id == staff.id


def test_reschedule_wrong_token_404(
    db_session: Session,
    public_client: TestClient,
) -> None:
    salon, staff, service = _seed_bookable_salon(db_session)
    base = f"/api/v1/public/salons/{salon.slug}"
    probe_day = date(2026, 8, 4)

    avail = public_client.get(
        f"{base}/availability/service",
        params=_availability_params(
            service_id=service.id,
            staff_id=staff.id,
            day=probe_day,
        ),
    )
    slot = _first_slot(avail.json(), staff.id)
    booking_id, _token = _create_public_booking(
        public_client,
        base=base,
        service_id=service.id,
        staff_id=staff.id,
        service_start=slot["service_start"],
    )

    resp = public_client.post(
        f"{base}/bookings/{booking_id}/reschedule",
        json={
            "token": "wrong-token",
            "staff_id": str(staff.id),
            "service_start": slot["service_start"],
        },
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "not_found"
