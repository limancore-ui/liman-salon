from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DashboardStatusCountsResponse(BaseModel):
    pending: int = 0
    confirmed: int = 0
    in_progress: int = 0
    completed: int = 0
    cancelled: int = 0
    no_show: int = 0
    expired: int = 0


class DashboardUpcomingBookingResponse(BaseModel):
    id: UUID
    starts_at: datetime
    ends_at: datetime
    customer_name: str
    customer_phone: str | None
    service_name: str
    staff_name: str
    status: str
    price_cents: int = Field(..., description="Booked price in minor units (cents)")


class DashboardWarningResponse(BaseModel):
    code: str
    count: int | None = None


class AdminDashboardSnapshotResponse(BaseModel):
    salon_date: date
    today_booking_count: int
    status_counts: DashboardStatusCountsResponse
    upcoming_bookings: list[DashboardUpcomingBookingResponse]
    active_staff_count: int
    warnings: list[DashboardWarningResponse]
