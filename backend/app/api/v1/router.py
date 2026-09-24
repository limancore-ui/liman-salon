from fastapi import APIRouter

from app.api.v1 import availability, bookings

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(availability.router)
v1_router.include_router(bookings.router)
