from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import AsOfDep, DashboardServiceDep
from app.api.schemas.dashboard import (
    AdminDashboardSnapshotResponse,
    DashboardStatusCountsResponse,
    DashboardUpcomingBookingResponse,
    DashboardWarningResponse,
)
from app.auth.deps import require_roles
from app.auth.principals import SalonContext
from app.services.dashboard.types import AdminDashboardSnapshot

router = APIRouter(tags=["dashboard"])

ReadSalonContext = Annotated[
    SalonContext,
    Depends(require_roles("owner", "admin", "staff", "receptionist")),
]


def _to_response(snapshot: AdminDashboardSnapshot) -> AdminDashboardSnapshotResponse:
    sc = snapshot.status_counts
    return AdminDashboardSnapshotResponse(
        salon_date=snapshot.salon_date,
        today_booking_count=snapshot.today_booking_count,
        status_counts=DashboardStatusCountsResponse(
            pending=sc.pending,
            confirmed=sc.confirmed,
            in_progress=sc.in_progress,
            completed=sc.completed,
            cancelled=sc.cancelled,
            no_show=sc.no_show,
            expired=sc.expired,
        ),
        upcoming_bookings=[
            DashboardUpcomingBookingResponse(
                id=row.id,
                starts_at=row.starts_at,
                ends_at=row.ends_at,
                customer_name=row.customer_name,
                customer_phone=row.customer_phone,
                service_name=row.service_name,
                staff_name=row.staff_name,
                status=row.status,
                price_cents=row.price_cents,
            )
            for row in snapshot.upcoming_bookings
        ],
        attention_bookings=[
            DashboardUpcomingBookingResponse(
                id=row.id,
                starts_at=row.starts_at,
                ends_at=row.ends_at,
                customer_name=row.customer_name,
                customer_phone=row.customer_phone,
                service_name=row.service_name,
                staff_name=row.staff_name,
                status=row.status,
                price_cents=row.price_cents,
            )
            for row in snapshot.attention_bookings
        ],
        active_staff_count=snapshot.active_staff_count,
        warnings=[
            DashboardWarningResponse(code=w.code, count=w.count)
            for w in snapshot.warnings
        ],
    )


@router.get(
    "/salons/{salon_id}/dashboard",
    response_model=AdminDashboardSnapshotResponse,
)
def get_admin_dashboard(
    salon_id: uuid.UUID,
    context: ReadSalonContext,
    as_of: AsOfDep,
    dashboard_service: DashboardServiceDep,
) -> AdminDashboardSnapshotResponse:
    snapshot = dashboard_service.get_admin_snapshot(
        salon_id=context.salon_id,
        as_of=as_of,
    )
    return _to_response(snapshot)
