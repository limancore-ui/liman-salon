"""Map application errors to HTTP responses."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.auth.errors import (
    AuthError,
    ForbiddenRoleError,
    InvalidCredentialsError,
    SalonAccessDeniedError,
    SalonNotFoundError,
    UnauthorizedError,
)
from app.services.schedule.errors import (
    ScheduleError,
    ScheduleNotFoundError,
    ScheduleValidationError,
)
from app.services.service_catalog.errors import (
    ServiceCatalogError,
    ServiceCatalogNotFoundError,
    ServiceCatalogValidationError,
)
from app.services.customer.errors import (
    CustomerConflictError,
    CustomerError,
    CustomerNotFoundError,
    CustomerValidationError,
)
from app.services.salon_public.errors import PublicSalonNotFoundError
from app.services.staff.errors import (
    StaffError,
    StaffNotFoundError,
    StaffValidationError,
)
from app.services.availability.errors import (
    AvailabilityError,
    ServiceNotFoundError,
)
from app.services.booking.errors import (
    BookingError,
    BookingNotFoundError,
    BookingOverlapError,
    BookingValidationError,
    SlotNotAvailableError,
)
from app.services.media.errors import (
    MediaConflictError,
    MediaError,
    MediaNotFoundError,
    MediaStorageError,
    MediaValidationError,
)
from app.services.salon_settings.errors import SalonSettingsError, SalonSettingsNotFoundError


class ErrorBody(BaseModel):
    detail: str
    code: str


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(InvalidCredentialsError)
    async def invalid_credentials(
        _request: Request, _exc: InvalidCredentialsError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content=ErrorBody(
                detail="invalid credentials",
                code="invalid_credentials",
            ).model_dump(),
        )

    @app.exception_handler(UnauthorizedError)
    async def unauthorized(_request: Request, _exc: UnauthorizedError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content=ErrorBody(detail="unauthorized", code="unauthorized").model_dump(),
        )

    @app.exception_handler(SalonAccessDeniedError)
    async def salon_access_denied(
        _request: Request, _exc: SalonAccessDeniedError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content=ErrorBody(
                detail="salon access denied",
                code="salon_access_denied",
            ).model_dump(),
        )

    @app.exception_handler(ForbiddenRoleError)
    async def forbidden_role(_request: Request, _exc: ForbiddenRoleError) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content=ErrorBody(detail="forbidden", code="forbidden").model_dump(),
        )

    @app.exception_handler(SalonNotFoundError)
    async def salon_not_found(_request: Request, _exc: SalonNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=ErrorBody(detail="salon not found", code="not_found").model_dump(),
        )

    @app.exception_handler(AuthError)
    async def auth_error(_request: Request, exc: AuthError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content=ErrorBody(detail=str(exc), code="auth_error").model_dump(),
        )

    @app.exception_handler(ScheduleNotFoundError)
    async def schedule_not_found(
        _request: Request, exc: ScheduleNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=ErrorBody(detail=str(exc), code="not_found").model_dump(),
        )

    @app.exception_handler(ScheduleValidationError)
    async def schedule_validation(
        _request: Request, exc: ScheduleValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorBody(detail=str(exc), code="validation_error").model_dump(),
        )

    @app.exception_handler(ScheduleError)
    async def schedule_error(_request: Request, exc: ScheduleError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorBody(detail=str(exc), code="schedule_error").model_dump(),
        )

    @app.exception_handler(ServiceCatalogNotFoundError)
    async def service_catalog_not_found(
        _request: Request, exc: ServiceCatalogNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=ErrorBody(detail=str(exc), code="not_found").model_dump(),
        )

    @app.exception_handler(ServiceCatalogValidationError)
    async def service_catalog_validation(
        _request: Request, exc: ServiceCatalogValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorBody(detail=str(exc), code="validation_error").model_dump(),
        )

    @app.exception_handler(ServiceCatalogError)
    async def service_catalog_error(
        _request: Request, exc: ServiceCatalogError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorBody(detail=str(exc), code="service_catalog_error").model_dump(),
        )

    @app.exception_handler(CustomerNotFoundError)
    async def customer_not_found(
        _request: Request, exc: CustomerNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=ErrorBody(detail=str(exc), code="not_found").model_dump(),
        )

    @app.exception_handler(PublicSalonNotFoundError)
    async def public_salon_not_found(
        _request: Request, exc: PublicSalonNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=ErrorBody(detail=str(exc), code="not_found").model_dump(),
        )

    @app.exception_handler(CustomerConflictError)
    async def customer_conflict(
        _request: Request, exc: CustomerConflictError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content=ErrorBody(detail=str(exc), code="conflict").model_dump(),
        )

    @app.exception_handler(CustomerValidationError)
    async def customer_validation(
        _request: Request, exc: CustomerValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorBody(detail=str(exc), code="validation_error").model_dump(),
        )

    @app.exception_handler(CustomerError)
    async def customer_error(_request: Request, exc: CustomerError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorBody(detail=str(exc), code="customer_error").model_dump(),
        )

    @app.exception_handler(StaffNotFoundError)
    async def staff_not_found(_request: Request, exc: StaffNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=ErrorBody(detail=str(exc), code="not_found").model_dump(),
        )

    @app.exception_handler(StaffValidationError)
    async def staff_validation(_request: Request, exc: StaffValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorBody(detail=str(exc), code="validation_error").model_dump(),
        )

    @app.exception_handler(StaffError)
    async def staff_error(_request: Request, exc: StaffError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorBody(detail=str(exc), code="staff_error").model_dump(),
        )

    @app.exception_handler(ServiceNotFoundError)
    async def availability_service_not_found(
        _request: Request, exc: ServiceNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=ErrorBody(detail=str(exc), code="not_found").model_dump(),
        )

    @app.exception_handler(AvailabilityError)
    async def availability_error(_request: Request, exc: AvailabilityError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorBody(detail=str(exc), code="availability_error").model_dump(),
        )

    @app.exception_handler(BookingNotFoundError)
    async def booking_not_found(_request: Request, exc: BookingNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=ErrorBody(detail=str(exc), code="not_found").model_dump(),
        )

    @app.exception_handler(BookingValidationError)
    async def booking_validation(_request: Request, exc: BookingValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorBody(detail=str(exc), code="validation_error").model_dump(),
        )

    @app.exception_handler(SlotNotAvailableError)
    async def slot_not_available(_request: Request, exc: SlotNotAvailableError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content=ErrorBody(detail=str(exc), code="slot_not_available").model_dump(),
        )

    @app.exception_handler(BookingOverlapError)
    async def booking_overlap(_request: Request, exc: BookingOverlapError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content=ErrorBody(detail=str(exc), code="booking_overlap").model_dump(),
        )

    @app.exception_handler(BookingError)
    async def booking_error(_request: Request, exc: BookingError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorBody(detail=str(exc), code="booking_error").model_dump(),
        )

    @app.exception_handler(SalonSettingsNotFoundError)
    async def salon_settings_not_found(
        _request: Request, exc: SalonSettingsNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=ErrorBody(detail=str(exc), code="not_found").model_dump(),
        )

    @app.exception_handler(SalonSettingsError)
    async def salon_settings_error(
        _request: Request, exc: SalonSettingsError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorBody(detail=str(exc), code="validation_error").model_dump(),
        )

    @app.exception_handler(MediaNotFoundError)
    async def media_not_found(_request: Request, exc: MediaNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=ErrorBody(detail=str(exc), code="not_found").model_dump(),
        )

    @app.exception_handler(MediaValidationError)
    async def media_validation(_request: Request, exc: MediaValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorBody(detail=str(exc), code="validation_error").model_dump(),
        )

    @app.exception_handler(MediaConflictError)
    async def media_conflict(_request: Request, exc: MediaConflictError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content=ErrorBody(detail=str(exc), code="conflict").model_dump(),
        )

    @app.exception_handler(MediaStorageError)
    async def media_storage(_request: Request, exc: MediaStorageError) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=ErrorBody(detail=str(exc), code="media_storage_error").model_dump(),
        )

    @app.exception_handler(MediaError)
    async def media_error(_request: Request, exc: MediaError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorBody(detail=str(exc), code="media_error").model_dump(),
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_error(_request: Request, _exc: SQLAlchemyError) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=ErrorBody(
                detail="internal server error",
                code="internal_error",
            ).model_dump(),
        )
