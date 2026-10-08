from __future__ import annotations

from datetime import date

from app.services.availability.errors import AvailabilityValidationError

PUBLIC_SERVICE_AVAILABILITY_MAX_CALENDAR_DAYS = 62


def validate_public_service_availability_date_range(
    start_date: date,
    end_date: date,
) -> None:
    """Inclusive salon-local calendar days; rejects oversized public availability scans."""
    if end_date < start_date:
        return
    calendar_days = (end_date - start_date).days + 1
    if calendar_days > PUBLIC_SERVICE_AVAILABILITY_MAX_CALENDAR_DAYS:
        raise AvailabilityValidationError(
            "date range must not exceed "
            f"{PUBLIC_SERVICE_AVAILABILITY_MAX_CALENDAR_DAYS} calendar days"
        )
