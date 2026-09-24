from __future__ import annotations



import uuid

from datetime import date, datetime, time, timezone

from unittest.mock import MagicMock



import pytest



from app.services.availability.errors import ServiceNotFoundError

from app.services.availability.intervals import net_service_slots_from_free_gaps

from app.services.availability.service import AvailabilityService

from app.services.availability.types import (

    BookingOccupancy,

    BusyInterval,

    ServiceForAvailability,

    TimeInterval,

    WorkingHourSpec,

)



UTC = timezone.utc

SALON_ID = uuid.uuid4()

STAFF_A = uuid.uuid4()

STAFF_B = uuid.uuid4()

SERVICE_ID = uuid.uuid4()

AS_OF = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)





def _service_with_repo(repo: MagicMock) -> AvailabilityService:

    session = MagicMock()

    svc = AvailabilityService(session)

    svc._repo = repo

    return svc





def _base_repo() -> MagicMock:

    repo = MagicMock()

    repo.get_salon_timezone.return_value = "UTC"

    repo.load_working_hours.return_value = (

        [

            WorkingHourSpec(

                day_of_week=0,

                start_time=time(9, 0),

                end_time=time(17, 0),

                staff_id=None,

                effective_from=None,

                effective_to=None,

            )

        ],

        [],

    )

    repo.load_blocked_periods.return_value = []

    repo.load_bookings_for_availability.return_value = []

    repo.staff_belongs_to_salon.return_value = True

    return repo





def _active_service(**kwargs: object) -> ServiceForAvailability:

    defaults = {

        "id": SERVICE_ID,

        "is_active": True,

        "duration_minutes": 60,

        "buffer_before_minutes": 0,

        "buffer_after_minutes": 0,

    }

    defaults.update(kwargs)

    return ServiceForAvailability(**defaults)  # type: ignore[arg-type]





def test_net_slots_trim_buffers_from_free_gap() -> None:

    gaps = [

        TimeInterval(

            start=datetime(2025, 6, 2, 9, 0, tzinfo=UTC),

            end=datetime(2025, 6, 2, 17, 0, tzinfo=UTC),

        )

    ]

    slots = net_service_slots_from_free_gaps(

        gaps,

        duration_minutes=60,

        buffer_before_minutes=15,

        buffer_after_minutes=15,

    )

    assert len(slots) == 1

    assert slots[0].service_start == datetime(2025, 6, 2, 9, 15, tzinfo=UTC)

    assert slots[0].service_end == datetime(2025, 6, 2, 16, 45, tzinfo=UTC)





def test_missing_service_raises_not_found() -> None:

    repo = _base_repo()

    repo.get_service_for_availability.return_value = None

    svc = _service_with_repo(repo)

    with pytest.raises(ServiceNotFoundError):

        svc.get_service_availability(

            salon_id=SALON_ID,

            service_id=SERVICE_ID,

            start_date=date(2025, 6, 2),

            end_date=date(2025, 6, 2),

            as_of=AS_OF,

        )

    repo.list_bookable_staff_for_service.assert_not_called()





def test_inactive_service_returns_empty_staff() -> None:

    repo = _base_repo()

    repo.get_service_for_availability.return_value = _active_service(is_active=False)

    svc = _service_with_repo(repo)

    result = svc.get_service_availability(

        salon_id=SALON_ID,

        service_id=SERVICE_ID,

        start_date=date(2025, 6, 2),

        end_date=date(2025, 6, 2),

        as_of=AS_OF,

    )

    assert result.service_id == SERVICE_ID

    assert result.staff == ()

    repo.list_bookable_staff_for_service.assert_not_called()





def test_fixed_staff_requires_link() -> None:

    repo = _base_repo()

    repo.get_service_for_availability.return_value = _active_service(duration_minutes=60)

    repo.staff_eligible_for_service.return_value = False

    svc = _service_with_repo(repo)

    result = svc.get_service_availability(

        salon_id=SALON_ID,

        service_id=SERVICE_ID,

        start_date=date(2025, 6, 2),

        end_date=date(2025, 6, 2),

        staff_id=STAFF_A,

        as_of=AS_OF,

    )

    assert result.staff == ()

    repo.staff_eligible_for_service.assert_called_once_with(SALON_ID, SERVICE_ID, STAFF_A)





def test_any_staff_sorted_and_scoped() -> None:

    repo = _base_repo()

    repo.get_service_for_availability.return_value = _active_service(

        duration_minutes=30,

    )

    repo.list_bookable_staff_for_service.return_value = [STAFF_A, STAFF_B]

    svc = _service_with_repo(repo)

    result = svc.get_service_availability(

        salon_id=SALON_ID,

        service_id=SERVICE_ID,

        start_date=date(2025, 6, 2),

        end_date=date(2025, 6, 2),

        as_of=AS_OF,

    )

    assert [s.staff_id for s in result.staff] == [STAFF_A, STAFF_B]

    assert len(result.staff[0].slots) == 1

    assert repo.load_working_hours.call_count == 2





def test_salon_wide_blocked_period_clears_slots() -> None:

    repo = _base_repo()

    repo.get_service_for_availability.return_value = _active_service(duration_minutes=30)

    repo.list_bookable_staff_for_service.return_value = [STAFF_A]

    repo.load_blocked_periods.return_value = [

        BusyInterval(

            start=datetime(2025, 6, 2, 9, 0, tzinfo=UTC),

            end=datetime(2025, 6, 2, 17, 0, tzinfo=UTC),

        )

    ]

    svc = _service_with_repo(repo)

    result = svc.get_service_availability(

        salon_id=SALON_ID,

        service_id=SERVICE_ID,

        start_date=date(2025, 6, 2),

        end_date=date(2025, 6, 2),

        as_of=AS_OF,

    )

    assert result.staff[0].slots == ()





def test_staff_specific_blocked_period_clears_slots() -> None:

    repo = _base_repo()

    repo.get_service_for_availability.return_value = _active_service(duration_minutes=30)

    repo.staff_eligible_for_service.return_value = True

    repo.load_blocked_periods.return_value = [

        BusyInterval(

            start=datetime(2025, 6, 2, 10, 0, tzinfo=UTC),

            end=datetime(2025, 6, 2, 11, 0, tzinfo=UTC),

        )

    ]

    svc = _service_with_repo(repo)

    result = svc.get_service_availability(

        salon_id=SALON_ID,

        service_id=SERVICE_ID,

        start_date=date(2025, 6, 2),

        end_date=date(2025, 6, 2),

        staff_id=STAFF_A,

        as_of=AS_OF,

    )

    assert len(result.staff[0].slots) == 2





def test_confirmed_booking_reduces_service_slots() -> None:

    repo = _base_repo()

    repo.get_service_for_availability.return_value = _active_service(duration_minutes=30)

    repo.staff_eligible_for_service.return_value = True

    repo.load_bookings_for_availability.return_value = [

        BookingOccupancy(

            starts_at=datetime(2025, 6, 2, 12, 0, tzinfo=UTC),

            ends_at=datetime(2025, 6, 2, 13, 0, tzinfo=UTC),

            status="confirmed",

            expires_at=None,

        )

    ]

    svc = _service_with_repo(repo)

    result = svc.get_service_availability(

        salon_id=SALON_ID,

        service_id=SERVICE_ID,

        start_date=date(2025, 6, 2),

        end_date=date(2025, 6, 2),

        staff_id=STAFF_A,

        as_of=AS_OF,

    )

    assert len(result.staff[0].slots) == 2





def test_live_pending_booking_reduces_service_slots() -> None:

    repo = _base_repo()

    repo.get_service_for_availability.return_value = _active_service(duration_minutes=30)

    repo.staff_eligible_for_service.return_value = True

    repo.load_bookings_for_availability.return_value = [

        BookingOccupancy(

            starts_at=datetime(2025, 6, 2, 12, 0, tzinfo=UTC),

            ends_at=datetime(2025, 6, 2, 13, 0, tzinfo=UTC),

            status="pending",

            expires_at=datetime(2025, 6, 2, 14, 0, tzinfo=UTC),

        )

    ]

    svc = _service_with_repo(repo)

    result = svc.get_service_availability(

        salon_id=SALON_ID,

        service_id=SERVICE_ID,

        start_date=date(2025, 6, 2),

        end_date=date(2025, 6, 2),

        staff_id=STAFF_A,

        as_of=AS_OF,

    )

    assert len(result.staff[0].slots) == 2





def test_stale_pending_does_not_reduce_service_slots() -> None:

    repo = _base_repo()

    repo.get_service_for_availability.return_value = _active_service(duration_minutes=30)

    repo.staff_eligible_for_service.return_value = True

    repo.load_bookings_for_availability.return_value = [

        BookingOccupancy(

            starts_at=datetime(2025, 6, 2, 12, 0, tzinfo=UTC),

            ends_at=datetime(2025, 6, 2, 13, 0, tzinfo=UTC),

            status="pending",

            expires_at=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),

        )

    ]

    svc = _service_with_repo(repo)

    result = svc.get_service_availability(

        salon_id=SALON_ID,

        service_id=SERVICE_ID,

        start_date=date(2025, 6, 2),

        end_date=date(2025, 6, 2),

        staff_id=STAFF_A,

        as_of=AS_OF,

    )

    assert len(result.staff[0].slots) == 1





def test_buffers_require_occupied_span_in_gap() -> None:

    repo = _base_repo()

    repo.get_service_for_availability.return_value = _active_service(

        duration_minutes=60,

        buffer_before_minutes=15,

        buffer_after_minutes=15,

    )

    repo.staff_eligible_for_service.return_value = True

    svc = _service_with_repo(repo)

    result = svc.get_service_availability(

        salon_id=SALON_ID,

        service_id=SERVICE_ID,

        start_date=date(2025, 6, 2),

        end_date=date(2025, 6, 2),

        staff_id=STAFF_A,

        as_of=AS_OF,

    )

    assert len(result.staff[0].slots) == 1

    slot = result.staff[0].slots[0]

    assert slot.service_start == datetime(2025, 6, 2, 9, 15, tzinfo=UTC)

    assert slot.service_end == datetime(2025, 6, 2, 16, 45, tzinfo=UTC)





def test_gap_exact_fit_for_occupied_span_yields_slot() -> None:

    repo = _base_repo()

    repo.get_service_for_availability.return_value = _active_service(

        duration_minutes=60,

        buffer_before_minutes=15,

        buffer_after_minutes=15,

    )

    repo.staff_eligible_for_service.return_value = True

    repo.load_working_hours.return_value = (

        [

            WorkingHourSpec(

                day_of_week=0,

                start_time=time(9, 0),

                end_time=time(10, 30),

                staff_id=None,

                effective_from=None,

                effective_to=None,

            )

        ],

        [],

    )

    svc = _service_with_repo(repo)

    result = svc.get_service_availability(

        salon_id=SALON_ID,

        service_id=SERVICE_ID,

        start_date=date(2025, 6, 2),

        end_date=date(2025, 6, 2),

        staff_id=STAFF_A,

        as_of=AS_OF,

    )

    assert len(result.staff[0].slots) == 1





def test_gap_too_short_for_occupied_span_yields_no_slots() -> None:

    repo = _base_repo()

    repo.get_service_for_availability.return_value = _active_service(

        duration_minutes=60,

        buffer_before_minutes=15,

        buffer_after_minutes=15,

    )

    repo.staff_eligible_for_service.return_value = True

    repo.load_working_hours.return_value = (

        [

            WorkingHourSpec(

                day_of_week=0,

                start_time=time(9, 0),

                end_time=time(10, 0),

                staff_id=None,

                effective_from=None,

                effective_to=None,

            )

        ],

        [],

    )

    svc = _service_with_repo(repo)

    result = svc.get_service_availability(

        salon_id=SALON_ID,

        service_id=SERVICE_ID,

        start_date=date(2025, 6, 2),

        end_date=date(2025, 6, 2),

        staff_id=STAFF_A,

        as_of=AS_OF,

    )

    assert result.staff[0].slots == ()





def test_service_availability_uses_salon_timezone_for_working_day() -> None:

    """Positive UTC offset: local Monday can differ from UTC Sunday."""

    repo = _base_repo()

    repo.get_salon_timezone.return_value = "Asia/Almaty"

    repo.get_service_for_availability.return_value = _active_service(duration_minutes=30)

    repo.staff_eligible_for_service.return_value = True

    repo.load_working_hours.return_value = (

        [

            WorkingHourSpec(

                day_of_week=0,

                start_time=time(9, 0),

                end_time=time(17, 0),

                staff_id=None,

                effective_from=None,

                effective_to=None,

            )

        ],

        [],

    )

    svc = _service_with_repo(repo)

    result = svc.get_service_availability(

        salon_id=SALON_ID,

        service_id=SERVICE_ID,

        start_date=date(2025, 6, 2),

        end_date=date(2025, 6, 2),

        staff_id=STAFF_A,

        as_of=AS_OF,

    )

    assert len(result.staff[0].slots) == 1

    repo.load_working_hours.assert_called()


