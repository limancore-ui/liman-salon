from fastapi import APIRouter

from app.api.v1 import (
    auth_routes,
    availability,
    bookings,
    customers,
    customers_public,
    salons_public,
    schedule,
    services,
    staff,
)

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth_routes.router)
v1_router.include_router(availability.router)
v1_router.include_router(bookings.router)
v1_router.include_router(customers.router)
v1_router.include_router(customers_public.router)
v1_router.include_router(salons_public.router)
v1_router.include_router(staff.router)
v1_router.include_router(services.router)
v1_router.include_router(schedule.router)
