from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DashboardUpcomingBooking:
    id: UUID
    starts_at: datetime
    ends_at: datetime
    customer_name: str
    customer_phone: str | None
    service_name: str
    staff_name: str
    status: str
    price_cents: int


@dataclass(frozen=True, slots=True)
class DashboardStatusCounts:
    pending: int = 0
    confirmed: int = 0
    in_progress: int = 0
    completed: int = 0
    cancelled: int = 0
    no_show: int = 0
    expired: int = 0

    @classmethod
    def from_raw(cls, counts: dict[str, int]) -> DashboardStatusCounts:
        return cls(
            pending=counts.get("pending", 0),
            confirmed=counts.get("confirmed", 0),
            in_progress=counts.get("in_progress", 0),
            completed=counts.get("completed", 0),
            cancelled=counts.get("cancelled", 0),
            no_show=counts.get("no_show", 0),
            expired=counts.get("expired", 0),
        )

    @property
    def total(self) -> int:
        return (
            self.pending
            + self.confirmed
            + self.in_progress
            + self.completed
            + self.cancelled
            + self.no_show
            + self.expired
        )


@dataclass(frozen=True, slots=True)
class DashboardWarning:
    code: str
    count: int | None = None


@dataclass(frozen=True, slots=True)
class AdminDashboardSnapshot:
    salon_date: date
    today_booking_count: int
    status_counts: DashboardStatusCounts
    upcoming_bookings: list[DashboardUpcomingBooking]
    active_staff_count: int
    warnings: list[DashboardWarning]
