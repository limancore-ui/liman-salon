from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.db.models.service import Service
from app.services.availability.types import TimeInterval
from app.services.smart_gap.service import SmartGapService

UTC = timezone.utc
SALON_A = uuid.uuid4()
SALON_B = uuid.uuid4()
STAFF_ID = uuid.uuid4()
SERVICE_SHORT = uuid.uuid4()
SERVICE_LONG = uuid.uuid4()
AS_OF = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
START = date(2025, 6, 2)
END = date(2025, 6, 2)


def _service_with_mocks() -> tuple[SmartGapService, MagicMock, MagicMock, MagicMock]:
    session = MagicMock()
    svc = SmartGapService(session)
    availability = MagicMock()
    catalog = MagicMock()
    availability_repo = MagicMock()
    availability_repo.get_salon_timezone.return_value = "UTC"
    svc._availability = availability
    svc._catalog = catalog
    svc._availability_repo = availability_repo
    return svc, availability, catalog, availability_repo


def _orm_service(
    *,
    service_id: uuid.UUID,
    salon_id: uuid.UUID,
    duration: int,
    buf_before: int = 0,
    buf_after: int = 0,
    name: str = "Test",
    price_cents: int = 1000,
) -> Service:
    row = Service(
        salon_id=salon_id,
        name=name,
        duration_minutes=duration,
        buffer_before_minutes=buf_before,
        buffer_after_minutes=buf_after,
        price_cents=price_cents,
        is_active=True,
        sort_order=0,
    )
    row.id = service_id
    return row


def test_service_fits_gap_in_result() -> None:
    svc, availability, catalog, availability_repo = _service_with_mocks()
    gap = TimeInterval(
        start=datetime(2025, 6, 2, 9, 0, tzinfo=UTC),
        end=datetime(2025, 6, 2, 11, 0, tzinfo=UTC),
    )
    availability.get_free_gaps.return_value = [gap]
    catalog.list_services.return_value = [
        _orm_service(
            service_id=SERVICE_SHORT,
            salon_id=SALON_A,
            duration=60,
            name="Haircut",
            price_cents=2500,
        ),
    ]
    availability_repo.staff_eligible_for_service.return_value = True

    result = svc.get_gaps_with_suitable_services(
        salon_id=SALON_A,
        staff_id=STAFF_ID,
        start_date=START,
        end_date=END,
        as_of=AS_OF,
    )

    assert result.salon_id == SALON_A
    assert result.staff_id == STAFF_ID
    assert len(result.entries) == 1
    assert result.entries[0].gap == gap
    assert len(result.entries[0].suitable_services) == 1
    suitable = result.entries[0].suitable_services[0]
    assert suitable.service_id == SERVICE_SHORT
    assert suitable.name == "Haircut"
    assert suitable.duration_minutes == 60
    assert suitable.price_cents == 2500
    assert suitable.bookable_start == gap.start
    availability.get_free_gaps.assert_called_once_with(
        salon_id=SALON_A,
        staff_id=STAFF_ID,
        start_date=START,
        end_date=END,
        service_duration_minutes=1,
        as_of=AS_OF,
    )
    catalog.list_services.assert_called_once_with(salon_id=SALON_A, active_only=True)


def test_service_does_not_fit_gap() -> None:
    svc, availability, catalog, availability_repo = _service_with_mocks()
    gap = TimeInterval(
        start=datetime(2025, 6, 2, 9, 0, tzinfo=UTC),
        end=datetime(2025, 6, 2, 9, 30, tzinfo=UTC),
    )
    availability.get_free_gaps.return_value = [gap]
    catalog.list_services.return_value = [
        _orm_service(service_id=SERVICE_LONG, salon_id=SALON_A, duration=60),
    ]
    availability_repo.staff_eligible_for_service.return_value = True

    result = svc.get_gaps_with_suitable_services(
        salon_id=SALON_A,
        staff_id=STAFF_ID,
        start_date=START,
        end_date=END,
        as_of=AS_OF,
    )

    assert result.entries == ()


def test_buffers_required_for_fit() -> None:
    svc, availability, catalog, availability_repo = _service_with_mocks()
    gap_fits = TimeInterval(
        start=datetime(2025, 6, 2, 9, 0, tzinfo=UTC),
        end=datetime(2025, 6, 2, 11, 0, tzinfo=UTC),
    )
    gap_too_short = TimeInterval(
        start=datetime(2025, 6, 2, 11, 0, tzinfo=UTC),
        end=datetime(2025, 6, 2, 12, 29, tzinfo=UTC),
    )
    availability.get_free_gaps.return_value = [gap_fits, gap_too_short]
    catalog.list_services.return_value = [
        _orm_service(
            service_id=SERVICE_LONG,
            salon_id=SALON_A,
            duration=60,
            buf_before=15,
            buf_after=15,
        ),
    ]
    availability_repo.staff_eligible_for_service.return_value = True

    result = svc.get_gaps_with_suitable_services(
        salon_id=SALON_A,
        staff_id=STAFF_ID,
        start_date=START,
        end_date=END,
        as_of=AS_OF,
    )

    assert len(result.entries) == 1
    assert len(result.entries[0].suitable_services) == 1


def test_tenant_isolation_empty_gaps_and_catalog_scoped() -> None:
    svc, availability, catalog, availability_repo = _service_with_mocks()
    availability.get_free_gaps.return_value = []
    catalog.list_services.return_value = []

    result = svc.get_gaps_with_suitable_services(
        salon_id=SALON_B,
        staff_id=STAFF_ID,
        start_date=START,
        end_date=END,
        as_of=AS_OF,
    )

    assert result.salon_id == SALON_B
    assert result.entries == ()
    availability.get_free_gaps.assert_called_once()
    assert availability.get_free_gaps.call_args.kwargs["salon_id"] == SALON_B
    catalog.list_services.assert_called_once_with(salon_id=SALON_B, active_only=True)
    availability_repo.staff_eligible_for_service.assert_not_called()


def test_staff_not_eligible_excludes_service() -> None:
    svc, availability, catalog, availability_repo = _service_with_mocks()
    gap = TimeInterval(
        start=datetime(2025, 6, 2, 9, 0, tzinfo=UTC),
        end=datetime(2025, 6, 2, 12, 0, tzinfo=UTC),
    )
    availability.get_free_gaps.return_value = [gap]
    catalog.list_services.return_value = [
        _orm_service(service_id=SERVICE_SHORT, salon_id=SALON_A, duration=30),
    ]
    availability_repo.staff_eligible_for_service.return_value = False

    result = svc.get_gaps_with_suitable_services(
        salon_id=SALON_A,
        staff_id=STAFF_ID,
        start_date=START,
        end_date=END,
        as_of=AS_OF,
    )

    assert result.entries == ()
    availability_repo.staff_eligible_for_service.assert_called_once_with(
        SALON_A, SERVICE_SHORT, STAFF_ID
    )


def test_gap_with_past_raw_start_uses_future_bookable_start() -> None:
    svc, availability, catalog, availability_repo = _service_with_mocks()
    as_of = datetime(2025, 6, 2, 16, 55, tzinfo=UTC)
    gap = TimeInterval(
        start=datetime(2025, 6, 2, 9, 0, tzinfo=UTC),
        end=datetime(2025, 6, 2, 18, 0, tzinfo=UTC),
    )
    availability.get_free_gaps.return_value = [gap]
    catalog.list_services.return_value = [
        _orm_service(
            service_id=SERVICE_SHORT,
            salon_id=SALON_A,
            duration=60,
            name="Haircut",
            price_cents=2500,
        ),
    ]
    availability_repo.staff_eligible_for_service.return_value = True

    result = svc.get_gaps_with_suitable_services(
        salon_id=SALON_A,
        staff_id=STAFF_ID,
        start_date=START,
        end_date=END,
        as_of=as_of,
    )

    assert len(result.entries) == 1
    assert result.entries[0].gap.start == gap.start
    bookable = result.entries[0].suitable_services[0].bookable_start
    assert bookable >= as_of
    assert bookable == datetime(2025, 6, 2, 17, 0, tzinfo=UTC)


def test_gap_with_no_future_bookable_start_omitted() -> None:
    svc, availability, catalog, availability_repo = _service_with_mocks()
    as_of = datetime(2025, 6, 2, 16, 55, tzinfo=UTC)
    gap = TimeInterval(
        start=datetime(2025, 6, 2, 9, 0, tzinfo=UTC),
        end=datetime(2025, 6, 2, 17, 0, tzinfo=UTC),
    )
    availability.get_free_gaps.return_value = [gap]
    catalog.list_services.return_value = [
        _orm_service(service_id=SERVICE_SHORT, salon_id=SALON_A, duration=60),
    ]
    availability_repo.staff_eligible_for_service.return_value = True

    result = svc.get_gaps_with_suitable_services(
        salon_id=SALON_A,
        staff_id=STAFF_ID,
        start_date=START,
        end_date=END,
        as_of=as_of,
    )

    assert result.entries == ()


def test_naive_as_of_rejected() -> None:
    svc, _, _, _ = _service_with_mocks()
    with pytest.raises(ValueError, match="as_of must be timezone-aware"):
        svc.get_gaps_with_suitable_services(
            salon_id=SALON_A,
            staff_id=STAFF_ID,
            start_date=START,
            end_date=END,
            as_of=datetime(2025, 6, 1, 12, 0),
        )
