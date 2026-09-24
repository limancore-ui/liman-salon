from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models.service import Service
from app.db.models.staff import Staff
from app.db.models.staff_service import StaffService
from app.services.service_catalog.errors import (
    ServiceCatalogNotFoundError,
    ServiceCatalogValidationError,
)
from app.services.service_catalog.repository import ServiceCatalogRepository
from app.services.staff.repository import StaffRepository


@dataclass(frozen=True, slots=True)
class ServiceCreateData:
    name: str
    description: str | None = None
    duration_minutes: int = 30
    buffer_before_minutes: int = 0
    buffer_after_minutes: int = 0
    price_cents: int = 0
    is_active: bool = True
    sort_order: int = 0


@dataclass(frozen=True, slots=True)
class ServiceUpdateData:
    name: str | None = None
    description: str | None = None
    duration_minutes: int | None = None
    buffer_before_minutes: int | None = None
    buffer_after_minutes: int | None = None
    price_cents: int | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class ServiceCatalogService:
    def __init__(self, session: Session) -> None:
        self._repo = ServiceCatalogRepository(session)
        self._staff_repo = StaffRepository(session)

    def list_services(
        self,
        *,
        salon_id: uuid.UUID,
        active_only: bool = True,
    ) -> list[Service]:
        return self._repo.list_services(salon_id=salon_id, active_only=active_only)

    def get_service(self, *, salon_id: uuid.UUID, service_id: uuid.UUID) -> Service:
        row = self._repo.get_service_by_id(salon_id=salon_id, service_id=service_id)
        if row is None:
            raise ServiceCatalogNotFoundError("service not found")
        return row

    def create_service(self, *, salon_id: uuid.UUID, data: ServiceCreateData) -> Service:
        self._validate_create(data)
        service = Service(
            salon_id=salon_id,
            name=data.name.strip(),
            description=data.description,
            duration_minutes=data.duration_minutes,
            buffer_before_minutes=data.buffer_before_minutes,
            buffer_after_minutes=data.buffer_after_minutes,
            price_cents=data.price_cents,
            is_active=data.is_active,
            sort_order=data.sort_order,
        )
        created = self._repo.add_service(service)
        return self.get_service(salon_id=salon_id, service_id=created.id)

    def update_service(
        self,
        *,
        salon_id: uuid.UUID,
        service_id: uuid.UUID,
        data: ServiceUpdateData,
    ) -> Service:
        service = self.get_service(salon_id=salon_id, service_id=service_id)
        if data.name is not None:
            name = data.name.strip()
            if not name:
                raise ServiceCatalogValidationError("name must not be blank")
            service.name = name
        if data.description is not None:
            service.description = data.description
        if data.duration_minutes is not None:
            if data.duration_minutes <= 0:
                raise ServiceCatalogValidationError("duration_minutes must be > 0")
            service.duration_minutes = data.duration_minutes
        if data.buffer_before_minutes is not None:
            if data.buffer_before_minutes < 0:
                raise ServiceCatalogValidationError("buffer_before_minutes must be >= 0")
            service.buffer_before_minutes = data.buffer_before_minutes
        if data.buffer_after_minutes is not None:
            if data.buffer_after_minutes < 0:
                raise ServiceCatalogValidationError("buffer_after_minutes must be >= 0")
            service.buffer_after_minutes = data.buffer_after_minutes
        if data.price_cents is not None:
            if data.price_cents < 0:
                raise ServiceCatalogValidationError("price_cents must be >= 0")
            service.price_cents = data.price_cents
        if data.is_active is not None:
            service.is_active = data.is_active
        if data.sort_order is not None:
            if data.sort_order < 0:
                raise ServiceCatalogValidationError("sort_order must be >= 0")
            service.sort_order = data.sort_order
        self._repo.flush()
        return service

    def list_service_staff(
        self, *, salon_id: uuid.UUID, service_id: uuid.UUID
    ) -> list[Staff]:
        self.get_service(salon_id=salon_id, service_id=service_id)
        return self._repo.list_staff_for_service(salon_id=salon_id, service_id=service_id)

    def attach_staff_to_service(
        self,
        *,
        salon_id: uuid.UUID,
        service_id: uuid.UUID,
        staff_id: uuid.UUID,
    ) -> Staff:
        self.get_service(salon_id=salon_id, service_id=service_id)
        staff = self._staff_repo.get_staff_by_id(salon_id=salon_id, staff_id=staff_id)
        if staff is None:
            raise ServiceCatalogNotFoundError("staff not found")
        existing = self._repo.get_staff_service_link(
            salon_id=salon_id,
            service_id=service_id,
            staff_id=staff_id,
        )
        if existing is None:
            link = StaffService(
                salon_id=salon_id,
                staff_id=staff_id,
                service_id=service_id,
            )
            self._repo.add_staff_service(link)
        return staff

    def detach_staff_from_service(
        self,
        *,
        salon_id: uuid.UUID,
        service_id: uuid.UUID,
        staff_id: uuid.UUID,
    ) -> None:
        self.get_service(salon_id=salon_id, service_id=service_id)
        staff = self._staff_repo.get_staff_by_id(salon_id=salon_id, staff_id=staff_id)
        if staff is None:
            raise ServiceCatalogNotFoundError("staff not found")
        link = self._repo.get_staff_service_link(
            salon_id=salon_id,
            service_id=service_id,
            staff_id=staff_id,
        )
        if link is None:
            raise ServiceCatalogNotFoundError("staff-service relationship not found")
        self._repo.delete_staff_service(link)

    @staticmethod
    def _validate_create(data: ServiceCreateData) -> None:
        if not data.name or not data.name.strip():
            raise ServiceCatalogValidationError("name must not be blank")
        if data.duration_minutes <= 0:
            raise ServiceCatalogValidationError("duration_minutes must be > 0")
        if data.buffer_before_minutes < 0:
            raise ServiceCatalogValidationError("buffer_before_minutes must be >= 0")
        if data.buffer_after_minutes < 0:
            raise ServiceCatalogValidationError("buffer_after_minutes must be >= 0")
        if data.price_cents < 0:
            raise ServiceCatalogValidationError("price_cents must be >= 0")
        if data.sort_order < 0:
            raise ServiceCatalogValidationError("sort_order must be >= 0")
