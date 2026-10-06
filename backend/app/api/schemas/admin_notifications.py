from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AdminNotificationItemResponse(BaseModel):
    id: uuid.UUID
    event_type: str
    booking_id: uuid.UUID
    created_at: datetime
    read_at: datetime | None
    booking_starts_at: datetime
    customer_name: str
    service_name: str
    staff_name: str


class AdminNotificationListResponse(BaseModel):
    items: list[AdminNotificationItemResponse]
    unread_count: int


class AdminNotificationMarkAllReadResponse(BaseModel):
    marked_count: int


class AdminNotificationStreamEventResponse(BaseModel):
    type: str = Field(default="notification")
    notification: AdminNotificationItemResponse
