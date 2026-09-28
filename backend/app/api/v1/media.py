from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.api.deps import ClockDep, MediaServiceDep
from app.api.schemas.media import (
    MediaAssetDetailResponse,
    MediaAssetResponse,
    MediaAttachRequest,
    MediaAttachmentIndexItemResponse,
    MediaAttachmentResponse,
)
from app.auth.deps import require_roles
from app.auth.principals import SalonContext
from app.db.models.media_asset import MediaAsset
from app.services.media.types import MediaAttachInput, MediaUploadInput

router = APIRouter(prefix="/salons/{salon_id}/media", tags=["media"])

ReadSalonContext = Annotated[
    SalonContext,
    Depends(require_roles("owner", "admin", "staff", "receptionist")),
]
WriteSalonContext = Annotated[SalonContext, Depends(require_roles("owner", "admin"))]


def _assert_path_salon(context: SalonContext, salon_id: uuid.UUID) -> None:
    if context.salon_id != salon_id:
        raise RuntimeError("salon_id path mismatch with SalonContext")


def _to_asset_response(asset: MediaAsset) -> MediaAssetResponse:
    return MediaAssetResponse.model_validate(asset)


def _to_detail_response(asset: MediaAsset) -> MediaAssetDetailResponse:
    attachments = [
        MediaAttachmentResponse.model_validate(row) for row in asset.attachments
    ]
    base = MediaAssetResponse.model_validate(asset)
    return MediaAssetDetailResponse(**base.model_dump(), attachments=attachments)


@router.get("", response_model=list[MediaAssetResponse])
def list_media(
    salon_id: uuid.UUID,
    context: ReadSalonContext,
    media_service: MediaServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[MediaAssetResponse]:
    _assert_path_salon(context, salon_id)
    rows = media_service.list_assets(
        salon_id=context.salon_id,
        limit=limit,
        offset=offset,
    )
    return [_to_asset_response(row) for row in rows]


@router.post("", response_model=MediaAssetResponse, status_code=201)
async def upload_media(
    salon_id: uuid.UUID,
    context: WriteSalonContext,
    media_service: MediaServiceDep,
    file: UploadFile = File(...),
) -> MediaAssetResponse:
    _assert_path_salon(context, salon_id)
    data = await file.read()
    content_type = file.content_type or "application/octet-stream"
    original_filename = file.filename or "upload"
    asset = media_service.upload_asset(
        salon_id=context.salon_id,
        upload=MediaUploadInput(
            original_filename=original_filename,
            content_type=content_type,
            data=data,
        ),
        created_by_user_id=context.user_id,
    )
    return _to_asset_response(asset)


@router.get(
    "/attachments/index",
    response_model=list[MediaAttachmentIndexItemResponse],
)
def list_attachment_index(
    salon_id: uuid.UUID,
    context: ReadSalonContext,
    media_service: MediaServiceDep,
) -> list[MediaAttachmentIndexItemResponse]:
    _assert_path_salon(context, salon_id)
    rows = media_service.list_attachment_index(salon_id=context.salon_id)
    return [
        MediaAttachmentIndexItemResponse(
            media_id=row.media_id,
            attachment_id=row.attachment_id,
            filename=row.filename,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            purpose=row.purpose,
        )
        for row in rows
    ]


@router.get("/{media_id}", response_model=MediaAssetDetailResponse)
def get_media(
    salon_id: uuid.UUID,
    media_id: uuid.UUID,
    context: ReadSalonContext,
    media_service: MediaServiceDep,
) -> MediaAssetDetailResponse:
    _assert_path_salon(context, salon_id)
    asset = media_service.get_asset(salon_id=context.salon_id, media_id=media_id)
    return _to_detail_response(asset)


@router.delete("/{media_id}", status_code=204)
def delete_media(
    salon_id: uuid.UUID,
    media_id: uuid.UUID,
    context: WriteSalonContext,
    media_service: MediaServiceDep,
    clock: ClockDep,
) -> None:
    _assert_path_salon(context, salon_id)
    media_service.soft_delete_asset(
        salon_id=context.salon_id,
        media_id=media_id,
        clock=clock,
    )


@router.get("/{media_id}/content")
def get_media_content(
    salon_id: uuid.UUID,
    media_id: uuid.UUID,
    context: ReadSalonContext,
    media_service: MediaServiceDep,
) -> StreamingResponse:
    _assert_path_salon(context, salon_id)
    asset = media_service.get_asset(salon_id=context.salon_id, media_id=media_id)
    stream = media_service.open_asset_content(
        salon_id=context.salon_id,
        media_id=media_id,
    )
    return StreamingResponse(
        stream,
        media_type=asset.content_type,
        headers={
            "Content-Disposition": f'inline; filename="{asset.original_filename}"',
        },
    )


@router.put(
    "/{media_id}/attachments",
    response_model=MediaAttachmentResponse,
    status_code=200,
)
def attach_media(
    salon_id: uuid.UUID,
    media_id: uuid.UUID,
    body: MediaAttachRequest,
    context: WriteSalonContext,
    media_service: MediaServiceDep,
) -> MediaAttachmentResponse:
    _assert_path_salon(context, salon_id)
    attachment = media_service.attach_asset(
        salon_id=context.salon_id,
        media_id=media_id,
        data=MediaAttachInput(
            entity_type=body.entity_type,
            entity_id=body.entity_id,
            purpose=body.purpose,
            sort_order=body.sort_order,
        ),
    )
    return MediaAttachmentResponse.model_validate(attachment)


@router.delete("/{media_id}/attachments/{attachment_id}", status_code=204)
def detach_media_attachment(
    salon_id: uuid.UUID,
    media_id: uuid.UUID,
    attachment_id: uuid.UUID,
    context: WriteSalonContext,
    media_service: MediaServiceDep,
) -> None:
    _assert_path_salon(context, salon_id)
    media_service.detach_attachment(
        salon_id=context.salon_id,
        media_id=media_id,
        attachment_id=attachment_id,
    )
