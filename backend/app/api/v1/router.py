from fastapi import APIRouter

from app.api.v1 import (
    admin_notifications,
    auth_routes,
    availability,
    bonus_ledger,
    bookings,
    customers,
    customers_public,
    dashboard,
    media,
    salons_public,
    salon_settings,
    reviews,
    schedule,
    services,
    smart_gaps,
    staff,
)

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth_routes.router)
v1_router.include_router(admin_notifications.router)
v1_router.include_router(availability.router)
v1_router.include_router(bookings.router)
v1_router.include_router(dashboard.router)
v1_router.include_router(customers.router)
v1_router.include_router(bonus_ledger.router)
v1_router.include_router(customers_public.router)
v1_router.include_router(salons_public.router)
v1_router.include_router(staff.router)
v1_router.include_router(media.router)
v1_router.include_router(services.router)
v1_router.include_router(schedule.router)
v1_router.include_router(smart_gaps.router)
v1_router.include_router(reviews.router)
v1_router.include_router(salon_settings.router)
