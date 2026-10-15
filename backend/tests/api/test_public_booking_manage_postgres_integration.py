"""PostgreSQL HTTP E2E for public booking manage (read-only, token header)."""

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
MANAGE_TOKEN_HEADER = "X-Booking-Manage-Token"

FORBIDDEN_RESPONSE_KEYS = frozenset(
    {
        "salon_id",
        "customer_id",
        "customer_name",
        "phone",
        "email",
        "manage_token",
        "manage_token_hash",
        "notes",
        "customer_notes",
        "internal_notes",
    }
)


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
        name=f"Manage E2E {suffix}",
        slug=f"manage-e2e-{suffix}",
        timezone="Asia/Almaty",
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
                start_time=time(0, 0),
                end_time=time(23, 59),
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
        app.dependency_overrides.clear()


def _availability_params(
    *,
    service_id: uuid.UUID,
    staff_id: uuid.UUID,
    day: date,
) -> dict[str, str]:
    return {
        "service_id": str(service_id),
        "staff_id": str(staff_id),
        "start_date": day.isoformat(),
        "end_date": day.isoformat(),
    }


def _first_slot(body: dict[str, Any], staff_id: uuid.UUID) -> dict[str, Any]:
    for entry in body["staff"]:
        if entry["staff_id"] == str(staff_id):
            slots = entry["slots"]
            assert slots, "expected at least one slot"
            return slots[0]
    raise AssertionError("staff not found in availability")


def _create_public_booking(
    client: TestClient,
    *,
    base: str,
    service_id: uuid.UUID,
    staff_id: uuid.UUID,
    service_start: str,
) -> tuple[uuid.UUID, str]:
    phone = f"+7762{uuid.uuid4().int % 10_000_000:07d}"
    resp = client.post(
        f"{base}/bookings",
        json={
            "full_name": "Manage Guest",
            "phone": phone,
            "service_id": str(service_id),
            "staff_id": str(staff_id),
            "service_start": service_start,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    return uuid.UUID(body["booking_id"]), body["manage_token"]


def _manage_url(base: str, booking_id: uuid.UUID) -> str:
    return f"{base}/bookings/{booking_id}/manage"


def test_manage_valid_token_returns_safe_fields(
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
    slot = _first_slot(avail.json(), staff.id)
    service_start = slot["service_start"]

    booking_id, manage_token = _create_public_booking(
        public_client,
        base=base,
        service_id=service.id,
        staff_id=staff.id,
        service_start=service_start,
    )

    resp = public_client.get(
        _manage_url(base, booking_id),
        headers={MANAGE_TOKEN_HEADER: manage_token},
    )
    assert resp.status_code == 200
    assert resp.headers.get("cache-control") == "no-store"
    body = resp.json()
    assert body["booking_id"] == str(booking_id)
    assert body["status"] == "pending"
    assert body["service_id"] == str(service.id)
    assert body["service_name"] == "Cut"
    assert body["staff_id"] == str(staff.id)
    assert body["staff_display_name"] == "Bookable"
    assert body["service_start"] == service_start
    assert body["can_cancel"] is True
    assert body["can_reschedule"] is True
    assert body["timezone"] == "Asia/Almaty"
    assert body.get("hold_expires_at") is not None
    for key in FORBIDDEN_RESPONSE_KEYS:
        assert key not in body
    assert manage_token not in resp.text


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {MANAGE_TOKEN_HEADER: "not-the-real-token"},
    ],
)
def test_manage_inaccessible_returns_uniform_not_found(
    db_session: Session,
    public_client: TestClient,
    headers: dict[str, str],
) -> None:
    salon, staff, service = _seed_bookable_salon(db_session)
    other_salon, _, _ = _seed_bookable_salon(db_session)
    base = f"/api/v1/public/salons/{salon.slug}"
    other_base = f"/api/v1/public/salons/{other_salon.slug}"
    probe_day = date(2026, 8, 5)

    avail = public_client.get(
        f"{base}/availability/service",
        params=_availability_params(
            service_id=service.id,
            staff_id=staff.id,
            day=probe_day,
        ),
    )
    slot = _first_slot(avail.json(), staff.id)
    booking_id, manage_token = _create_public_booking(
        public_client,
        base=base,
        service_id=service.id,
        staff_id=staff.id,
        service_start=slot["service_start"],
    )

    missing_id = uuid.uuid4()
    cases: list[tuple[str, dict[str, str]]] = [
        (_manage_url(base, missing_id), {MANAGE_TOKEN_HEADER: manage_token}),
        (_manage_url(base, booking_id), headers),
        (_manage_url(other_base, booking_id), {MANAGE_TOKEN_HEADER: manage_token}),
    ]

    bodies: list[dict[str, Any]] = []
    for url, hdrs in cases:
        resp = public_client.get(url, headers=hdrs)
        assert resp.status_code == 404
        bodies.append(resp.json())

    assert len({b.get("detail") for b in bodies}) == 1
    assert bodies[0].get("code") == "not_found"


def test_manage_stale_pending_reports_expired_without_db_mutation(
    db_session: Session,
    public_client: TestClient,
) -> None:
    salon, staff, service = _seed_bookable_salon(db_session)
    base = f"/api/v1/public/salons/{salon.slug}"
    probe_day = date(2026, 8, 6)

    avail = public_client.get(
        f"{base}/availability/service",
        params=_availability_params(
            service_id=service.id,
            staff_id=staff.id,
            day=probe_day,
        ),
    )
    slot = _first_slot(avail.json(), staff.id)
    booking_id, manage_token = _create_public_booking(
        public_client,
        base=base,
        service_id=service.id,
        staff_id=staff.id,
        service_start=slot["service_start"],
    )

    row = db_session.scalar(
        select(Booking).where(
            Booking.salon_id == salon.id,
            Booking.id == booking_id,
        )
    )
    assert row is not None
    row.expires_at = datetime(2026, 7, 1, 0, 0, tzinfo=UTC)
    db_session.flush()

    resp = public_client.get(
        _manage_url(base, booking_id),
        headers={MANAGE_TOKEN_HEADER: manage_token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "expired"
    assert body["can_cancel"] is False
    assert body["can_reschedule"] is False

    db_session.refresh(row)
    assert row.status == "pending"
