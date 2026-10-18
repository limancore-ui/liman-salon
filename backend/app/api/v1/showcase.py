from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse

from app.api.deps import MediaServiceDep, ShowcaseServiceDep
from app.api.schemas.showcase import (
    PublicShowcaseItemResponse,
    PublicShowcaseResponse,
    ShowcaseItemCreateRequest,
    ShowcaseItemPatchRequest,
    ShowcaseItemResponse,
)
from app.auth.deps import require_roles
from app.auth.principals import SalonContext
from app.services.showcase.types import ShowcaseCategory

router = APIRouter(tags=["showcase"])

ReadSalonContext = Annotated[
    SalonContext,
    Depends(require_roles("owner", "admin", "staff", "receptionist")),
]
WriteSalonContext = Annotated[SalonContext, Depends(require_roles("owner", "admin"))]


def _assert_path_salon(context: SalonContext, salon_id: uuid.UUID) -> None:
    if context.salon_id != salon_id:
        raise RuntimeError("salon_id path mismatch with SalonContext")


@router.get(
    "/salons/{salon_id}/showcase/items",
    response_model=list[ShowcaseItemResponse],
)
def list_showcase_items(
    salon_id: uuid.UUID,
    context: ReadSalonContext,
    showcase_service: ShowcaseServiceDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ShowcaseItemResponse]:
    _assert_path_salon(context, salon_id)
    rows = showcase_service.list_items(
        salon_id=context.salon_id,
        limit=limit,
        offset=offset,
    )
    return [ShowcaseItemResponse.model_validate(row) for row in rows]


@router.post(
    "/salons/{salon_id}/showcase/items",
    response_model=ShowcaseItemResponse,
    status_code=201,
)
def create_showcase_item(
    salon_id: uuid.UUID,
    body: ShowcaseItemCreateRequest,
    context: WriteSalonContext,
    showcase_service: ShowcaseServiceDep,
) -> ShowcaseItemResponse:
    _assert_path_salon(context, salon_id)
    item = showcase_service.create_item(
        salon_id=context.salon_id,
        media_asset_id=body.media_asset_id,
        category=body.category,
        title=body.title,
        description=body.description,
        price_cents=body.price_cents,
        sort_order=body.sort_order,
    )
    return ShowcaseItemResponse.model_validate(item)


@router.patch(
    "/salons/{salon_id}/showcase/items/{item_id}",
    response_model=ShowcaseItemResponse,
)
def update_showcase_item(
    salon_id: uuid.UUID,
    item_id: uuid.UUID,
    body: ShowcaseItemPatchRequest,
    context: WriteSalonContext,
    showcase_service: ShowcaseServiceDep,
) -> ShowcaseItemResponse:
    _assert_path_salon(context, salon_id)
    item = showcase_service.update_item(
        salon_id=context.salon_id,
        item_id=item_id,
        changes=body.model_dump(exclude_unset=True),
    )
    return ShowcaseItemResponse.model_validate(item)


@router.patch(
    "/salons/{salon_id}/showcase/items/{item_id}/publish",
    response_model=ShowcaseItemResponse,
)
def publish_showcase_item(
    salon_id: uuid.UUID,
    item_id: uuid.UUID,
    context: WriteSalonContext,
    showcase_service: ShowcaseServiceDep,
) -> ShowcaseItemResponse:
    _assert_path_salon(context, salon_id)
    item = showcase_service.publish_item(
        salon_id=context.salon_id,
        item_id=item_id,
    )
    return ShowcaseItemResponse.model_validate(item)


@router.patch(
    "/salons/{salon_id}/showcase/items/{item_id}/unpublish",
    response_model=ShowcaseItemResponse,
)
def unpublish_showcase_item(
    salon_id: uuid.UUID,
    item_id: uuid.UUID,
    context: WriteSalonContext,
    showcase_service: ShowcaseServiceDep,
) -> ShowcaseItemResponse:
    _assert_path_salon(context, salon_id)
    item = showcase_service.unpublish_item(
        salon_id=context.salon_id,
        item_id=item_id,
    )
    return ShowcaseItemResponse.model_validate(item)


@router.delete(
    "/salons/{salon_id}/showcase/items/{item_id}",
    status_code=204,
)
def delete_showcase_item(
    salon_id: uuid.UUID,
    item_id: uuid.UUID,
    context: WriteSalonContext,
    showcase_service: ShowcaseServiceDep,
) -> Response:
    _assert_path_salon(context, salon_id)
    showcase_service.delete_item(salon_id=context.salon_id, item_id=item_id)
    return Response(status_code=204)


@router.get(
    "/public/salons/{slug}/showcase",
    response_model=PublicShowcaseResponse,
)
def list_public_showcase_items(
    slug: str,
    showcase_service: ShowcaseServiceDep,
    category: ShowcaseCategory | None = Query(default=None),
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PublicShowcaseResponse:
    result = showcase_service.list_public_items_by_slug(
        slug=slug,
        category=category,
        limit=limit,
        offset=offset,
    )
    return PublicShowcaseResponse(
        salon_id=result.salon_id,
        items=[
            PublicShowcaseItemResponse(
                id=item.id,
                category=item.category,
                title=item.title,
                description=item.description,
                price_cents=item.price_cents,
                image_url=(
                    f"/api/v1/public/salons/{result.salon_slug}/showcase/items/"
                    f"{item.id}/image"
                ),
            )
            for item in result.items
        ],
    )


@router.get(
    "/public/salons/{slug}/showcase/items/{item_id}/image",
    response_class=StreamingResponse,
)
def get_public_showcase_item_image(
    slug: str,
    item_id: uuid.UUID,
    showcase_service: ShowcaseServiceDep,
    media_service: MediaServiceDep,
) -> StreamingResponse:
    reference = showcase_service.get_public_image_reference_by_slug(
        slug=slug,
        item_id=item_id,
    )
    asset = media_service.get_asset(
        salon_id=reference.salon_id,
        media_id=reference.media_asset_id,
    )
    stream = media_service.open_asset_content(
        salon_id=reference.salon_id,
        media_id=reference.media_asset_id,
    )
    headers = {"Cache-Control": "no-store"}
    if asset.checksum_sha256:
        headers["ETag"] = f'"{asset.checksum_sha256}"'
    return StreamingResponse(stream, media_type=asset.content_type, headers=headers)
