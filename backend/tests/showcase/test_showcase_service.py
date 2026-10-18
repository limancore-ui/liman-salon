from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.db.models.showcase_item import ShowcaseItem
from app.services.showcase.errors import (
    ShowcaseItemNotFoundError,
    ShowcaseItemValidationError,
    ShowcaseMediaNotFoundError,
)
from app.services.showcase.repository import ShowcaseRepository
from app.services.showcase.service import ShowcaseService
from app.services.showcase.types import ShowcaseCategory

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SALON_B = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
MEDIA_ID = uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")


@pytest.mark.parametrize("category", list(ShowcaseCategory))
@pytest.mark.parametrize("price_cents", [None, 1250])
def test_create_item_accepts_categories_and_optional_price(
    category: ShowcaseCategory,
    price_cents: int | None,
) -> None:
    session = MagicMock(spec=Session)
    service = ShowcaseService(session)
    service._repo = MagicMock(spec=ShowcaseRepository)
    service._repo.get_active_media_asset.return_value = SimpleNamespace(id=MEDIA_ID)
    service._repo.add_item.side_effect = lambda item: item

    item = service.create_item(
        salon_id=SALON_A,
        media_asset_id=MEDIA_ID,
        category=category,
        title="  Example item  ",
        description="",
        price_cents=price_cents,
    )

    assert item.category == category.value
    assert item.title == "Example item"
    assert item.description == ""
    assert item.price_cents == price_cents
    assert item.is_published is False
    assert item.sort_order == 0
    service._repo.get_active_media_asset.assert_called_once_with(
        salon_id=SALON_A,
        media_asset_id=MEDIA_ID,
    )


def test_create_item_rejects_unknown_category() -> None:
    service = ShowcaseService(MagicMock(spec=Session))

    with pytest.raises(ShowcaseItemValidationError, match="category"):
        service.create_item(
            salon_id=SALON_A,
            media_asset_id=MEDIA_ID,
            category="other",
            title="Example",
        )


def test_create_item_rejects_negative_price() -> None:
    service = ShowcaseService(MagicMock(spec=Session))
    service._repo = MagicMock(spec=ShowcaseRepository)

    with pytest.raises(ShowcaseItemValidationError, match="price_cents"):
        service.create_item(
            salon_id=SALON_A,
            media_asset_id=MEDIA_ID,
            category=ShowcaseCategory.WORK,
            title="Example",
            price_cents=-1,
        )

    service._repo.get_active_media_asset.assert_not_called()


def test_create_item_does_not_accept_media_from_another_salon() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None
    service = ShowcaseService(session)

    with pytest.raises(ShowcaseMediaNotFoundError, match="media asset"):
        service.create_item(
            salon_id=SALON_B,
            media_asset_id=MEDIA_ID,
            category=ShowcaseCategory.WORK,
            title="Example",
        )

    statement = session.scalar.call_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "media_assets.salon_id =" in sql
    assert "media_assets.id =" in sql
    assert "media_assets.deleted_at IS NULL" in sql
    assert SALON_B in compiled.params.values()
    assert MEDIA_ID in compiled.params.values()


def test_model_has_composite_tenant_media_foreign_key() -> None:
    constraint = next(
        constraint
        for constraint in ShowcaseItem.__table__.foreign_key_constraints
        if len(constraint.elements) == 2
    )

    assert [element.parent.name for element in constraint.elements] == [
        "salon_id",
        "media_asset_id",
    ]
    assert [element.target_fullname for element in constraint.elements] == [
        "media_assets.salon_id",
        "media_assets.id",
    ]
    assert constraint.ondelete == "RESTRICT"


def test_migration_follows_current_head() -> None:
    migration_path = (
        Path(__file__).parents[2]
        / "alembic"
        / "versions"
        / "20261018_0021_showcase_items.py"
    )
    source = migration_path.read_text(encoding="utf-8")

    assert 'revision: str = "20261018_0021"' in source
    assert 'down_revision: str | None = "20250924_0020"' in source


def test_update_item_is_scoped_and_validates_replacement_media() -> None:
    service = ShowcaseService(MagicMock(spec=Session))
    service._repo = MagicMock(spec=ShowcaseRepository)
    row = SimpleNamespace(
        id=uuid.uuid4(),
        salon_id=SALON_A,
        title="Old",
        category="work",
        description=None,
        price_cents=None,
        media_asset_id=MEDIA_ID,
        sort_order=0,
        is_published=False,
    )
    service._repo.get_item_by_id.return_value = row
    service._repo.get_active_media_asset.return_value = SimpleNamespace(id=MEDIA_ID)
    service._repo.save_item.side_effect = lambda item: item

    updated = service.update_item(
        salon_id=SALON_A,
        item_id=row.id,
        changes={"title": " New ", "media_asset_id": MEDIA_ID},
    )

    assert updated.title == "New"
    assert updated.media_asset_id == MEDIA_ID
    service._repo.get_item_by_id.assert_called_once_with(
        salon_id=SALON_A,
        item_id=row.id,
    )
    service._repo.get_active_media_asset.assert_called_once_with(
        salon_id=SALON_A,
        media_asset_id=MEDIA_ID,
    )


def test_update_item_rejects_unknown_item_for_salon() -> None:
    service = ShowcaseService(MagicMock(spec=Session))
    service._repo = MagicMock(spec=ShowcaseRepository)
    service._repo.get_item_by_id.return_value = None

    with pytest.raises(ShowcaseItemNotFoundError):
        service.update_item(
            salon_id=SALON_B,
            item_id=uuid.uuid4(),
            changes={"title": "Attempt"},
        )

    assert service._repo.get_item_by_id.call_args.kwargs["salon_id"] == SALON_B
    service._repo.save_item.assert_not_called()


@pytest.mark.parametrize(
    ("operation", "initial_published"),
    [
        ("patch", False),
        ("publish", False),
        ("unpublish", True),
        ("delete", True),
    ],
)
def test_mutations_reject_another_salons_item_without_changing_it(
    operation: str,
    initial_published: bool,
) -> None:
    foreign_item = SimpleNamespace(
        id=uuid.uuid4(),
        salon_id=SALON_B,
        title="Foreign item",
        category="work",
        description=None,
        price_cents=None,
        media_asset_id=MEDIA_ID,
        sort_order=0,
        is_published=initial_published,
    )
    original_title = foreign_item.title
    original_published = foreign_item.is_published
    repository = MagicMock(spec=ShowcaseRepository)

    def scoped_lookup(*, salon_id: uuid.UUID, item_id: uuid.UUID):
        if salon_id == foreign_item.salon_id and item_id == foreign_item.id:
            return foreign_item
        return None

    repository.get_item_by_id.side_effect = scoped_lookup
    service = ShowcaseService(MagicMock(spec=Session))
    service._repo = repository

    with pytest.raises(ShowcaseItemNotFoundError, match="showcase item not found"):
        if operation == "patch":
            service.update_item(
                salon_id=SALON_A,
                item_id=foreign_item.id,
                changes={"title": "Attempted update"},
            )
        elif operation == "publish":
            service.publish_item(salon_id=SALON_A, item_id=foreign_item.id)
        elif operation == "unpublish":
            service.unpublish_item(salon_id=SALON_A, item_id=foreign_item.id)
        else:
            service.delete_item(salon_id=SALON_A, item_id=foreign_item.id)

    repository.get_item_by_id.assert_called_once_with(
        salon_id=SALON_A,
        item_id=foreign_item.id,
    )
    assert foreign_item.title == original_title
    assert foreign_item.is_published is original_published
    repository.save_item.assert_not_called()
    repository.delete_item.assert_not_called()


def test_update_item_rejects_media_from_another_salon() -> None:
    service = ShowcaseService(MagicMock(spec=Session))
    service._repo = MagicMock(spec=ShowcaseRepository)
    row = SimpleNamespace(id=uuid.uuid4())
    service._repo.get_item_by_id.return_value = row
    service._repo.get_active_media_asset.return_value = None

    with pytest.raises(ShowcaseMediaNotFoundError):
        service.update_item(
            salon_id=SALON_A,
            item_id=row.id,
            changes={"media_asset_id": MEDIA_ID},
        )

    service._repo.get_active_media_asset.assert_called_once_with(
        salon_id=SALON_A,
        media_asset_id=MEDIA_ID,
    )
    service._repo.save_item.assert_not_called()


def test_publish_requires_active_tenant_media() -> None:
    service = ShowcaseService(MagicMock(spec=Session))
    service._repo = MagicMock(spec=ShowcaseRepository)
    row = SimpleNamespace(id=uuid.uuid4(), media_asset_id=MEDIA_ID, is_published=False)
    service._repo.get_item_by_id.return_value = row
    service._repo.get_active_media_asset.return_value = None

    with pytest.raises(ShowcaseMediaNotFoundError):
        service.publish_item(salon_id=SALON_A, item_id=row.id)

    service._repo.get_active_media_asset.assert_called_once_with(
        salon_id=SALON_A,
        media_asset_id=MEDIA_ID,
    )
    service._repo.save_item.assert_not_called()


def test_publish_unpublish_and_delete_mutate_only_tenant_scoped_item() -> None:
    service = ShowcaseService(MagicMock(spec=Session))
    service._repo = MagicMock(spec=ShowcaseRepository)
    row = SimpleNamespace(
        id=uuid.uuid4(),
        salon_id=SALON_A,
        media_asset_id=MEDIA_ID,
        is_published=False,
    )
    service._repo.get_item_by_id.return_value = row
    service._repo.get_active_media_asset.return_value = SimpleNamespace(id=MEDIA_ID)
    service._repo.save_item.side_effect = lambda item: item

    published = service.publish_item(salon_id=SALON_A, item_id=row.id)
    assert published.is_published is True
    hidden = service.unpublish_item(salon_id=SALON_A, item_id=row.id)
    assert hidden.is_published is False
    service.delete_item(salon_id=SALON_A, item_id=row.id)

    assert service._repo.get_item_by_id.call_count == 3
    assert all(
        call.kwargs["salon_id"] == SALON_A
        for call in service._repo.get_item_by_id.call_args_list
    )
    service._repo.delete_item.assert_called_once_with(row)


def test_public_items_are_resolved_from_slug_and_return_public_fields() -> None:
    service = ShowcaseService(MagicMock(spec=Session))
    service._salon_public = MagicMock()
    service._salon_public.resolve_public_salon_by_slug.return_value = SimpleNamespace(
        salon_id=SALON_A,
        slug="salon-a",
    )
    service._repo = MagicMock(spec=ShowcaseRepository)
    service._repo.list_published_items.return_value = [
        SimpleNamespace(
            id=uuid.uuid4(),
            category="cosmetics",
            title="Published",
            description=None,
            price_cents=100,
            media_asset_id=MEDIA_ID,
            is_published=True,
        )
    ]

    result = service.list_public_items_by_slug(
        slug="salon-a",
        category=ShowcaseCategory.COSMETICS,
    )

    assert result.salon_id == SALON_A
    assert result.salon_slug == "salon-a"
    assert result.items[0].title == "Published"
    assert result.items[0].media_asset_id == MEDIA_ID
    service._salon_public.resolve_public_salon_by_slug.assert_called_once_with(
        "salon-a"
    )
    service._repo.list_published_items.assert_called_once_with(
        salon_id=SALON_A,
        category=ShowcaseCategory.COSMETICS,
        limit=50,
        offset=0,
    )


def test_public_image_requires_published_item_in_resolved_salon() -> None:
    service = ShowcaseService(MagicMock(spec=Session))
    service._salon_public = MagicMock()
    service._salon_public.resolve_public_salon_by_slug.return_value = SimpleNamespace(
        salon_id=SALON_A,
    )
    service._repo = MagicMock(spec=ShowcaseRepository)
    service._repo.get_published_item_by_id.return_value = None

    with pytest.raises(ShowcaseItemNotFoundError):
        service.get_public_image_reference_by_slug(slug="salon-a", item_id=ITEM_ID)

    service._repo.get_published_item_by_id.assert_called_once_with(
        salon_id=SALON_A,
        item_id=ITEM_ID,
    )


def test_public_items_reject_inactive_or_unknown_slug_before_querying_items() -> None:
    from app.services.salon_public.errors import PublicSalonNotFoundError

    service = ShowcaseService(MagicMock(spec=Session))
    service._salon_public = MagicMock()
    service._salon_public.resolve_public_salon_by_slug.side_effect = (
        PublicSalonNotFoundError("salon not found")
    )
    service._repo = MagicMock(spec=ShowcaseRepository)

    with pytest.raises(PublicSalonNotFoundError):
        service.list_public_items_by_slug(slug="inactive-salon")

    service._repo.list_published_items.assert_not_called()


ITEM_ID = uuid.UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
