from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.services.availability.types import ServiceForAvailability, TimeInterval
from app.services.smart_gap.matching import service_fits_gap, suitable_services_for_gap

UTC = timezone.utc
SERVICE_ID = uuid.uuid4()


def _svc(*, duration: int, before: int = 0, after: int = 0) -> ServiceForAvailability:
    return ServiceForAvailability(
        id=SERVICE_ID,
        is_active=True,
        duration_minutes=duration,
        buffer_before_minutes=before,
        buffer_after_minutes=after,
    )


def test_matching_unit_fit_and_no_fit() -> None:
    gap_ok = TimeInterval(
        start=datetime(2025, 6, 2, 9, 0, tzinfo=UTC),
        end=datetime(2025, 6, 2, 10, 30, tzinfo=UTC),
    )
    gap_short = TimeInterval(
        start=datetime(2025, 6, 2, 10, 0, tzinfo=UTC),
        end=datetime(2025, 6, 2, 10, 45, tzinfo=UTC),
    )
    service = _svc(duration=60, before=15, after=15)

    assert service_fits_gap(service, gap_ok) is True
    assert service_fits_gap(service, gap_short) is False

    matched = suitable_services_for_gap(gap_ok, (service,))
    assert matched == (service,)
    assert suitable_services_for_gap(gap_short, (service,)) == ()
