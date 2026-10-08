from __future__ import annotations

import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.db.models.service import Service
from app.services.availability.intervals import first_bookable_net_start_on_or_after
from app.services.availability.repository import AvailabilityRepository
from app.services.availability.service import AvailabilityService
from app.services.availability.types import ServiceForAvailability, TimeInterval
from app.services.service_catalog.service import ServiceCatalogService
from app.services.smart_gap.matching import suitable_services_for_gap
from app.services.smart_gap.types import SmartGapEntry, SmartGapResult, SuitableService

# Smallest positive duration accepted by Availability Core gap filtering.
_PROBE_GAP_MINUTES = 1


def _service_to_availability(row: Service) -> ServiceForAvailability:
    return ServiceForAvailability(
        id=row.id,
        is_active=row.is_active,
        duration_minutes=row.duration_minutes,
        buffer_before_minutes=row.buffer_before_minutes,
        buffer_after_minutes=row.buffer_after_minutes,
    )


def _service_to_suitable(row: Service, *, bookable_start: datetime) -> SuitableService:
    return SuitableService(
        service_id=row.id,
        name=row.name,
        duration_minutes=row.duration_minutes,
        price_cents=row.price_cents,
        bookable_start=bookable_start,
    )


class SmartGapService:
    """
    Map staff free gaps to salon services that fit duration and buffers.

    Reuses Availability Core for gap discovery; does not duplicate schedule math.
    """

    def __init__(self, session: Session) -> None:
        self._availability = AvailabilityService(session)
        self._catalog = ServiceCatalogService(session)
        self._availability_repo = AvailabilityRepository(session)

    def get_gaps_with_suitable_services(
        self,
        *,
        salon_id: uuid.UUID,
        staff_id: uuid.UUID,
        start_date: date,
        end_date: date,
        as_of: datetime,
    ) -> SmartGapResult:
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware (UTC recommended)")

        free_gaps = self._availability.get_free_gaps(
            salon_id=salon_id,
            staff_id=staff_id,
            start_date=start_date,
            end_date=end_date,
            service_duration_minutes=_PROBE_GAP_MINUTES,
            as_of=as_of,
        )

        tz_name = self._availability_repo.get_salon_timezone(salon_id)
        if not tz_name:
            return SmartGapResult(salon_id=salon_id, staff_id=staff_id, entries=())
        tz = ZoneInfo(tz_name)

        eligible = self._eligible_services_for_staff(
            salon_id=salon_id,
            staff_id=staff_id,
        )
        for_matching = tuple(avail for avail, _ in eligible)
        product_by_id = {avail.id: row for avail, row in eligible}

        entries_list: list[SmartGapEntry] = []
        for gap in free_gaps:
            fitting = suitable_services_for_gap(gap, for_matching)
            suitable: list[SuitableService] = []
            for fit in fitting:
                bookable_start = first_bookable_net_start_on_or_after(
                    gap,
                    duration_minutes=fit.duration_minutes,
                    buffer_before_minutes=fit.buffer_before_minutes,
                    buffer_after_minutes=fit.buffer_after_minutes,
                    not_before=as_of,
                    tz=tz,
                )
                if bookable_start is None:
                    continue
                suitable.append(
                    _service_to_suitable(
                        product_by_id[fit.id],
                        bookable_start=bookable_start,
                    )
                )
            if not suitable:
                continue
            entries_list.append(
                SmartGapEntry(
                    gap=TimeInterval(start=gap.start, end=gap.end),
                    suitable_services=tuple(suitable),
                )
            )
        entries = tuple(entries_list)
        return SmartGapResult(
            salon_id=salon_id,
            staff_id=staff_id,
            entries=entries,
        )

    def _eligible_services_for_staff(
        self,
        *,
        salon_id: uuid.UUID,
        staff_id: uuid.UUID,
    ) -> tuple[tuple[ServiceForAvailability, Service], ...]:
        rows = self._catalog.list_services(salon_id=salon_id, active_only=True)
        out: list[tuple[ServiceForAvailability, Service]] = []
        for row in rows:
            if self._availability_repo.staff_eligible_for_service(
                salon_id, row.id, staff_id
            ):
                out.append((_service_to_availability(row), row))
        return tuple(out)
