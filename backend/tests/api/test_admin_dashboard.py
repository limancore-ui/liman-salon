from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_dashboard_service
from app.auth.deps import get_auth_repository
from app.core.security import create_access_token
from app.main import create_app
from app.services.dashboard.service import DashboardService
from app.services.dashboard.types import (
    AdminDashboardSnapshot,
    DashboardStatusCounts,
    DashboardUpcomingBooking,
    DashboardWarning,
)

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SALON_B = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
BOOKING_ID = uuid.UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
NOW = datetime.now(timezone.utc)


def _snapshot(*, upcoming: list[DashboardUpcomingBooking] | None = None) -> AdminDashboardSnapshot:
    return AdminDashboardSnapshot(
        salon_date=date(2026, 9, 25),
        today_booking_count=3,
        status_counts=DashboardStatusCounts(
            pending=1,
            confirmed=2,
        ),
        upcoming_bookings=upcoming or [],
        active_staff_count=2,
        warnings=[],
    )


def _upcoming_row(
    *,
    starts_at: datetime = datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc),
) -> DashboardUpcomingBooking:
    return DashboardUpcomingBooking(
        id=BOOKING_ID,
        starts_at=starts_at,
        ends_at=datetime(2026, 9, 25, 11, 0, tzinfo=timezone.utc),
        customer_name="Jane Doe",
        customer_phone="+77001234567",
        service_name="Cut",
        staff_name="Alex",
        status="confirmed",
        price_cents=5000,
    )


def _auth_app(
    *,
    role: str = "owner",
    salon_id: uuid.UUID = SALON_A,
) -> tuple[TestClient, MagicMock, dict[str, str]]:
    app = create_app()
    mock_auth = MagicMock()
    mock_auth.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID,
        email="owner@example.com",
        full_name="Owner",
        is_active=True,
    )
    mock_auth.get_active_salon.return_value = SimpleNamespace(
        id=salon_id,
        name="Salon",
        slug="salon",
        is_active=True,
    )
    mock_auth.get_active_membership.return_value = SimpleNamespace(
        salon_id=salon_id,
        user_id=USER_ID,
        role=role,
        is_active=True,
    )
    mock_dashboard = MagicMock(spec=DashboardService)
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    app.dependency_overrides[get_dashboard_service] = lambda: mock_dashboard
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    return client, mock_dashboard, headers


@pytest.mark.parametrize("role", ["owner", "admin", "staff", "receptionist"])
def test_dashboard_read_roles(role: str) -> None:
    client, mock_dashboard, headers = _auth_app(role=role)
    mock_dashboard.get_admin_snapshot.return_value = _snapshot()
    try:
        response = client.get(
            f"/api/v1/salons/{SALON_A}/dashboard",
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["today_booking_count"] == 3
        assert body["status_counts"]["pending"] == 1
        assert body["status_counts"]["confirmed"] == 2
        assert body["status_counts"]["completed"] == 0
        assert body["active_staff_count"] == 2
        assert body["salon_date"] == "2026-09-25"
        mock_dashboard.get_admin_snapshot.assert_called_once()
        assert mock_dashboard.get_admin_snapshot.call_args.kwargs["salon_id"] == SALON_A
    finally:
        client.close()


def test_dashboard_empty_upcoming() -> None:
    client, mock_dashboard, headers = _auth_app()
    mock_dashboard.get_admin_snapshot.return_value = _snapshot(upcoming=[])
    response = client.get(
        f"/api/v1/salons/{SALON_A}/dashboard",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["upcoming_bookings"] == []
    client.close()


def test_dashboard_upcoming_order_preserved() -> None:
    client, mock_dashboard, headers = _auth_app()
    early = _upcoming_row(
        starts_at=datetime(2026, 9, 25, 9, 0, tzinfo=timezone.utc),
    )
    late = _upcoming_row(
        starts_at=datetime(2026, 9, 25, 14, 0, tzinfo=timezone.utc),
    )
    late_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    late = DashboardUpcomingBooking(
        id=late_id,
        starts_at=late.starts_at,
        ends_at=late.ends_at,
        customer_name=late.customer_name,
        customer_phone=late.customer_phone,
        service_name=late.service_name,
        staff_name=late.staff_name,
        status=late.status,
        price_cents=late.price_cents,
    )
    mock_dashboard.get_admin_snapshot.return_value = _snapshot(upcoming=[early, late])
    response = client.get(
        f"/api/v1/salons/{SALON_A}/dashboard",
        headers=headers,
    )
    body = response.json()["upcoming_bookings"]
    assert body[0]["starts_at"] < body[1]["starts_at"]
    client.close()


def test_dashboard_warnings_optional() -> None:
    client, mock_dashboard, headers = _auth_app()
    snap = AdminDashboardSnapshot(
        salon_date=date(2026, 9, 25),
        today_booking_count=0,
        status_counts=DashboardStatusCounts(),
        upcoming_bookings=[],
        active_staff_count=0,
        warnings=[DashboardWarning(code="no_active_staff")],
    )
    mock_dashboard.get_admin_snapshot.return_value = snap
    response = client.get(
        f"/api/v1/salons/{SALON_A}/dashboard",
        headers=headers,
    )
    assert response.status_code == 200
    warnings = response.json()["warnings"]
    assert len(warnings) == 1
    assert warnings[0]["code"] == "no_active_staff"
    client.close()


def test_dashboard_unauthenticated() -> None:
    app = create_app()
    with TestClient(app) as client:
        assert client.get(f"/api/v1/salons/{SALON_A}/dashboard").status_code == 401


def test_dashboard_cross_tenant_403() -> None:
    app = create_app()
    mock_auth = MagicMock()
    mock_auth.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID,
        email="owner@example.com",
        full_name="Owner",
        is_active=True,
    )
    mock_auth.get_active_salon.return_value = SimpleNamespace(
        id=SALON_B,
        name="Other Salon",
        slug="other",
        is_active=True,
    )
    mock_auth.get_active_membership.return_value = None
    mock_dashboard = MagicMock(spec=DashboardService)
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    app.dependency_overrides[get_dashboard_service] = lambda: mock_dashboard
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/salons/{SALON_B}/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 403
    mock_dashboard.get_admin_snapshot.assert_not_called()
