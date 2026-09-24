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
from app.services.booking.errors import (
    BookingError,
    BookingNotFoundError,
    BookingOverlapError,
    BookingValidationError,
    SlotNotAvailableError,
)


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

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_error(_request: Request, _exc: SQLAlchemyError) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=ErrorBody(
                detail="internal server error",
                code="internal_error",
            ).model_dump(),
        )
