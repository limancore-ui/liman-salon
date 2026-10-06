from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.api.deps import AdminNotificationServiceDep, AsOfDep
from app.api.schemas.admin_notifications import (
    AdminNotificationItemResponse,
    AdminNotificationListResponse,
    AdminNotificationMarkAllReadResponse,
    AdminNotificationStreamEventResponse,
)
from app.auth.deps import require_roles
from app.auth.principals import SalonContext
from app.db.session import SessionLocal
from app.services.admin_notifications.service import (
    AdminNotificationNotFoundError,
    AdminNotificationService,
)

router = APIRouter(tags=["admin-notifications"])

OwnerAdminSalonContext = Annotated[
    SalonContext,
    Depends(require_roles("owner", "admin")),
]


def _to_item(row) -> AdminNotificationItemResponse:
    return AdminNotificationItemResponse(
        id=row.id,
        event_type=row.event_type,
        booking_id=row.booking_id,
        created_at=row.created_at,
        read_at=row.read_at,
        booking_starts_at=row.booking_starts_at,
        customer_name=row.customer_name,
        service_name=row.service_name,
        staff_name=row.staff_name,
    )


@router.get(
    "/salons/{salon_id}/admin-notifications",
    response_model=AdminNotificationListResponse,
)
def list_admin_notifications(
    salon_id: uuid.UUID,
    context: OwnerAdminSalonContext,
    service: AdminNotificationServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AdminNotificationListResponse:
    items = service.list_notifications(
        salon_id=context.salon_id,
        recipient_user_id=context.user_id,
        limit=limit,
        offset=offset,
    )
    unread = service.unread_count(
        salon_id=context.salon_id,
        recipient_user_id=context.user_id,
    )
    return AdminNotificationListResponse(
        items=[_to_item(row) for row in items],
        unread_count=unread,
    )


@router.patch(
    "/salons/{salon_id}/admin-notifications/{notification_id}/read",
    status_code=204,
)
def mark_admin_notification_read(
    salon_id: uuid.UUID,
    notification_id: uuid.UUID,
    context: OwnerAdminSalonContext,
    as_of: AsOfDep,
    service: AdminNotificationServiceDep,
) -> None:
    try:
        service.mark_read(
            salon_id=context.salon_id,
            recipient_user_id=context.user_id,
            event_id=notification_id,
            read_at=as_of,
        )
    except AdminNotificationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/salons/{salon_id}/admin-notifications/mark-all-read",
    response_model=AdminNotificationMarkAllReadResponse,
)
def mark_all_admin_notifications_read(
    salon_id: uuid.UUID,
    context: OwnerAdminSalonContext,
    as_of: AsOfDep,
    service: AdminNotificationServiceDep,
) -> AdminNotificationMarkAllReadResponse:
    count = service.mark_all_read(
        salon_id=context.salon_id,
        recipient_user_id=context.user_id,
        read_at=as_of,
    )
    return AdminNotificationMarkAllReadResponse(marked_count=count)


async def _sse_notification_stream(
    *,
    request: Request,
    salon_id: uuid.UUID,
    recipient_user_id: uuid.UUID,
    after_id: uuid.UUID | None,
) -> AsyncIterator[str]:
    last_id = after_id
    seen: set[uuid.UUID] = set()
    heartbeat_every = 15
    ticks = 0
    while True:
        if await request.is_disconnected():
            break
        session = SessionLocal()
        try:
            service = AdminNotificationService(session)
            rows = service.list_since(
                salon_id=salon_id,
                recipient_user_id=recipient_user_id,
                after_id=last_id,
                limit=20,
            )
            for row in rows:
                if row.id in seen:
                    continue
                seen.add(row.id)
                last_id = row.id
                payload = AdminNotificationStreamEventResponse(
                    notification=_to_item(row),
                )
                yield f"data: {json.dumps(payload.model_dump(mode='json'))}\n\n"
        finally:
            session.close()

        ticks += 1
        if ticks >= heartbeat_every:
            ticks = 0
            yield ": heartbeat\n\n"
        await asyncio.sleep(2)
        if await request.is_disconnected():
            break


@router.get("/salons/{salon_id}/admin-notifications/stream")
async def stream_admin_notifications(
    salon_id: uuid.UUID,
    request: Request,
    context: OwnerAdminSalonContext,
    after_id: uuid.UUID | None = Query(default=None),
) -> StreamingResponse:
    generator = _sse_notification_stream(
        request=request,
        salon_id=context.salon_id,
        recipient_user_id=context.user_id,
        after_id=after_id,
    )
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
