import uuid
from dataclasses import dataclass
from enum import StrEnum


class ShowcaseCategory(StrEnum):
    WORK = "work"
    COSMETICS = "cosmetics"
    DYES = "dyes"
    VARNISHES = "varnishes"


@dataclass(frozen=True, slots=True)
class PublicShowcaseItem:
    id: uuid.UUID
    category: ShowcaseCategory
    title: str
    description: str | None
    price_cents: int | None
    media_asset_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class PublicShowcaseItemsResult:
    salon_id: uuid.UUID
    salon_slug: str
    items: tuple[PublicShowcaseItem, ...]


@dataclass(frozen=True, slots=True)
class PublicShowcaseImageReference:
    salon_id: uuid.UUID
    media_asset_id: uuid.UUID
