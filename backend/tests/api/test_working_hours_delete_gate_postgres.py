"""PostgreSQL: working_hours.delete fingerprint, acknowledgement, and exclusive lock."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, time, timezone
from time import monotonic, sleep
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
from app.services.schedule.lock import salon_schedule_lock_key
from app.services.schedule.overlay import WorkingHoursDeleteChange

UTC = timezone.utc
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
AS_OF = datetime(2026, 8, 1, 8, 0, tzinfo=UTC)
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
        name=f"Delete Gate {suffix}",
        slug=f"delete-gate-{suffix}",
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


def _seed_thursday_salon(session: Session) -> tuple[Salon, Staff, Service, uuid.UUID]:
    suffix = uuid.uuid4().hex[:8]
    salon = Salon(
        name=f"Delete Gate Thu {suffix}",
        slug=f"delete-gate-thu-{suffix}",
        timezone="UTC",
        currency_code="KZT",
        is_active=True,
    )
    session.add(salon)
    session.flush()
    hour = WorkingHour(
        salon_id=salon.id,
        staff_id=None,
        day_of_week=3,
        start_time=time(9, 0),
        end_time=time(17, 0),
    )
    session.add(hour)
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
    return salon, staff, service, hour.id


def _hour_exists(working_hours_id: uuid.UUID) -> bool:
    session = SessionLocal()
    try:
        value = session.scalar(
            select(func.count())
            .select_from(WorkingHour)
            .where(WorkingHour.id == working_hours_id)
        )
        return int(value or 0) == 1
    finally:
        session.close()


def _count_hours(salon_id: uuid.UUID) -> int:
    session = SessionLocal()
    try:
        value = session.scalar(
            select(func.count()).select_from(WorkingHour).where(WorkingHour.salon_id == salon_id)
        )
        return int(value or 0)
    finally:
        session.close()


def _preview_delete(session: Session, salon_id: uuid.UUID, working_hours_id: uuid.UUID):
    return ScheduleImpactService(session).preview_impact(
        salon_id=salon_id,
        change=WorkingHoursDeleteChange(working_hours_id=working_hours_id),
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


def _delete_body(fingerprint: str, *, acknowledge: bool) -> dict[str, object]:
    return {
        "impact_fingerprint": fingerprint,
        "as_of": ECHOED_AS_OF,
        "horizon_days": 90,
        "acknowledge_impacts": acknowledge,
    }


def test_booking_move_invalidates_delete_fingerprint_and_ack_blocks_delete() -> None:
    session = SessionLocal()
    salon_id: uuid.UUID | None = None
    try:
        salon, staff, service, hour_id = _seed_thursday_salon(session)
        salon_id = salon.id
        session.commit()
        original = _preview_delete(session, salon_id, hour_id)
        assert original.all_impacts == ()
        session.commit()

        customer_id = CustomerService(session).resolve_public_customer(
            salon_id=salon_id,
            data=PublicCustomerResolveData(
                full_name="Gate Patron",
                phone=f"+775{uuid.uuid4().int % 10_000_000:07d}",
            ),
        ).customer_id
        BookingService(session).create_booking(
            salon_id=salon_id,
            customer_id=customer_id,
            staff_id=staff.id,
            service_id=service.id,
            requested_service_start=datetime(2026, 8, 6, 10, 0, tzinfo=UTC),
            source="admin",
            status="confirmed",
            as_of=AS_OF,
        )
        session.commit()
        moved = _preview_delete(session, salon_id, hour_id)
        assert len(moved.all_impacts) == 1
        assert moved.impact_fingerprint != original.impact_fingerprint
        session.commit()

        client, headers = _client(salon)
        url = f"/api/v1/salons/{salon_id}/schedule/working-hours/{hour_id}"
        try:
            stale = client.request(
                "DELETE",
                url,
                headers=headers,
                json=_delete_body(original.impact_fingerprint, acknowledge=False),
            )
            assert stale.status_code == 409
            assert stale.json()["code"] == "impact_stale"
            assert _hour_exists(hour_id)

            unacked = client.request(
                "DELETE",
                url,
                headers=headers,
                json=_delete_body(moved.impact_fingerprint, acknowledge=False),
            )
            assert unacked.status_code == 409
            assert unacked.json()["code"] == "impact_ack_required"
            assert _hour_exists(hour_id)

            deleted = client.request(
                "DELETE",
                url,
                headers=headers,
                json=_delete_body(moved.impact_fingerprint, acknowledge=True),
            )
            assert deleted.status_code == 204
            assert deleted.content == b""
            assert not _hour_exists(hour_id)
        finally:
            client.close()
    finally:
        session.close()
        if salon_id is not None:
            _cleanup_salon(salon_id)


def test_exclusive_delete_conflicts_with_booking_shared_lock_then_succeeds() -> None:
    session = SessionLocal()
    salon_id: uuid.UUID | None = None
    try:
        salon, staff, service = _seed_open_salon(session)
        salon_id = salon.id
        hour_id = session.scalar(
            select(WorkingHour.id).where(
                WorkingHour.salon_id == salon_id,
                WorkingHour.day_of_week == 0,
            )
        )
        assert hour_id is not None
        session.commit()
        preview = _preview_delete(session, salon_id, hour_id)
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
                        phone=f"+772{uuid.uuid4().int % 10_000_000:07d}",
                    ),
                ).customer_id
                BookingService(holder).create_booking(
                    salon_id=salon_id,
                    customer_id=customer_id,
                    staff_id=staff.id,
                    service_id=service.id,
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
        url = f"/api/v1/salons/{salon_id}/schedule/working-hours/{hour_id}"
        body = _delete_body(fingerprint, acknowledge=True)
        try:
            busy = client.request(
                "DELETE",
                url, headers=headers, json=body)
            assert errors == []
            assert busy.status_code == 503
            assert busy.headers.get("retry-after") == "2"
            assert busy.json()["code"] == "schedule_busy"
            assert _count_hours(salon_id) == before
            assert _hour_exists(hour_id)
        finally:
            release.set()
            worker.join(timeout=20)
            client.close()

        assert not worker.is_alive()
        assert errors == []
        client, headers = _client(salon)
        try:
            deleted = client.request(
                "DELETE",
                url, headers=headers, json=body)
            assert deleted.status_code == 204
            assert deleted.content == b""
            assert _count_hours(salon_id) == before - 1
            assert not _hour_exists(hour_id)
        finally:
            client.close()
    finally:
        session.close()
        if salon_id is not None:
            _cleanup_salon(salon_id)


def _advisory_waiters(lock_key: int) -> int:
    """Sessions blocked on this salon's exclusive schedule advisory lock."""
    classid = (lock_key >> 32) & 0xFFFFFFFF
    objid = lock_key & 0xFFFFFFFF
    session = SessionLocal()
    try:
        value = session.scalar(
            text(
                """
                SELECT count(*)
                FROM pg_locks
                WHERE locktype = 'advisory'
                  AND objsubid = 1
                  AND granted = false
                  AND mode = 'ExclusiveLock'
                  AND classid = CAST(:classid AS oid)
                  AND objid = CAST(:objid AS oid)
                """
            ),
            {"classid": str(classid), "objid": str(objid)},
        )
        return int(value or 0)
    finally:
        session.rollback()
        session.close()


def _wait_for_advisory_waiters(lock_key: int, expected: int, *, timeout: float) -> int:
    deadline = monotonic() + timeout
    latest = 0
    while monotonic() < deadline:
        latest = _advisory_waiters(lock_key)
        if latest >= expected:
            return latest
        sleep(0.01)
    return latest


def test_second_delete_waits_behind_exclusive_lock_then_returns_404() -> None:
    """Two deletes queue on one advisory lock; the later waiter gets 404.

    A holder takes the exclusive lock first. Each DELETE is started only after
    pg_locks shows the previous one waiting, and the holder is released only
    after both are waiting. PostgreSQL grants that exclusive queue in order,
    so the first waiter deletes the row and the second wakes to a missing row.
    """
    session = SessionLocal()
    salon_id: uuid.UUID | None = None
    holder: threading.Thread | None = None
    release = threading.Event()
    workers: list[threading.Thread] = []
    try:
        salon, _staff, _service, hour_id = _seed_thursday_salon(session)
        salon_id = salon.id
        session.commit()
        preview = _preview_delete(session, salon_id, hour_id)
        assert preview.all_impacts == ()
        session.commit()
        lock_key = salon_schedule_lock_key(salon_id)
        url = f"/api/v1/salons/{salon_id}/schedule/working-hours/{hour_id}"
        body = _delete_body(preview.impact_fingerprint, acknowledge=False)
        first_client, first_headers = _client(salon)
        second_client, second_headers = _client(salon)
        first: dict[str, object] = {}
        second: dict[str, object] = {}

        def hold_exclusive_lock() -> None:
            owned = SessionLocal()
            try:
                owned.execute(
                    text("SELECT pg_advisory_xact_lock(CAST(:key AS bigint))"),
                    {"key": lock_key},
                )
                held.set()
                assert release.wait(timeout=20)
            finally:
                owned.rollback()
                owned.close()

        def send_delete(
            client: TestClient,
            headers: dict[str, str],
            slot: dict[str, object],
        ) -> None:
            try:
                response = client.request("DELETE", url, headers=headers, json=body)
                slot["status"] = response.status_code
                slot["content"] = response.content
                slot["payload"] = response.json() if response.content else None
            except BaseException as exc:
                slot["error"] = exc
            finally:
                client.close()

        held = threading.Event()
        holder = threading.Thread(target=hold_exclusive_lock)
        holder.start()
        assert held.wait(timeout=15)

        workers.append(
            threading.Thread(
                target=send_delete,
                args=(first_client, first_headers, first),
            )
        )
        workers[-1].start()
        assert _wait_for_advisory_waiters(lock_key, 1, timeout=5) == 1, first

        workers.append(
            threading.Thread(
                target=send_delete,
                args=(second_client, second_headers, second),
            )
        )
        workers[-1].start()
        assert _wait_for_advisory_waiters(lock_key, 2, timeout=5) == 2, (first, second)

        release.set()
        for worker in workers:
            worker.join(timeout=20)
        holder.join(timeout=20)

        assert first.get("error") is None
        assert second.get("error") is None
        assert first.get("status") == 204, first
        assert first.get("content") == b""
        assert second.get("status") == 404, second
        assert isinstance(second.get("payload"), dict)
        assert second["payload"]["code"] == "not_found"  # type: ignore[index]
        assert not _hour_exists(hour_id)
        assert not holder.is_alive()
        assert all(not worker.is_alive() for worker in workers)
    finally:
        release.set()
        for worker in workers:
            worker.join(timeout=5)
        if holder is not None:
            holder.join(timeout=5)
        session.close()
        if salon_id is not None:
            _cleanup_salon(salon_id)
