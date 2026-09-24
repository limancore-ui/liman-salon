from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models.service import Service
from app.db.models.staff import Staff
from app.db.models.staff_service import StaffService


class ServiceCatalogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_services(
        self,
        *,
        salon_id: uuid.UUID,
        active_only: bool = True,
    ) -> list[Service]:
        stmt = (
            select(Service)
            .options(joinedload(Service.salon))
            .where(Service.salon_id == salon_id)
        )
        if active_only:
            stmt = stmt.where(Service.is_active.is_(True))
        stmt = stmt.order_by(Service.sort_order, Service.name, Service.id)
        return list(self._session.scalars(stmt).unique().all())

    def get_service_by_id(
        self, *, salon_id: uuid.UUID, service_id: uuid.UUID
    ) -> Service | None:
        return self._session.scalar(
            select(Service)
            .options(joinedload(Service.salon))
            .where(Service.salon_id == salon_id, Service.id == service_id)
        )

    def add_service(self, service: Service) -> Service:
        self._session.add(service)
        self._session.flush()
        return service

    def flush(self) -> None:
        self._session.flush()

    def list_staff_for_service(
        self, *, salon_id: uuid.UUID, service_id: uuid.UUID
    ) -> list[Staff]:
        stmt = (
            select(Staff)
            .join(
                StaffService,
                (StaffService.staff_id == Staff.id)
                & (StaffService.salon_id == Staff.salon_id),
            )
            .where(
                StaffService.salon_id == salon_id,
                StaffService.service_id == service_id,
                Staff.salon_id == salon_id,
            )
            .order_by(Staff.sort_order, Staff.display_name, Staff.id)
        )
        return list(self._session.scalars(stmt).all())

    def get_staff_service_link(
        self,
        *,
        salon_id: uuid.UUID,
        service_id: uuid.UUID,
        staff_id: uuid.UUID,
    ) -> StaffService | None:
        return self._session.scalar(
            select(StaffService).where(
                StaffService.salon_id == salon_id,
                StaffService.service_id == service_id,
                StaffService.staff_id == staff_id,
            )
        )

    def add_staff_service(self, link: StaffService) -> StaffService:
        self._session.add(link)
        self._session.flush()
        return link

    def delete_staff_service(self, link: StaffService) -> None:
        self._session.delete(link)
        self._session.flush()
