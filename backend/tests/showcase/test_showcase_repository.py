from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.services.showcase.repository import ShowcaseRepository
from app.services.showcase.types import ShowcaseCategory

SALON_ID = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
ITEM_ID = uuid.UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")


def _sql_and_params(statement: object) -> tuple[str, dict[str, object]]:
    compiled = statement.compile(dialect=postgresql.dialect())  # type: ignore[attr-defined]
    return str(compiled).lower(), compiled.params


def test_admin_listing_scopes_and_orders_by_sort_then_id() -> None:
    session = MagicMock(spec=Session)
    session.scalars.return_value.all.return_value = []
    repository = ShowcaseRepository(session)

    repository.list_items(salon_id=SALON_ID, limit=50, offset=0)

    sql, params = _sql_and_params(session.scalars.call_args.args[0])
    assert "showcase_items.salon_id =" in sql
    assert "order by showcase_items.sort_order asc, showcase_items.id asc" in sql
    assert SALON_ID in params.values()


def test_item_lookup_scopes_by_salon_and_item_id() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None
    repository = ShowcaseRepository(session)

    repository.get_item_by_id(salon_id=SALON_ID, item_id=ITEM_ID)

    # SQL compilation inspects predicates only; it does not execute against PostgreSQL.
    sql, params = _sql_and_params(session.scalar.call_args.args[0])
    assert "showcase_items.salon_id =" in sql
    assert "showcase_items.id =" in sql
    assert SALON_ID in params.values()
    assert ITEM_ID in params.values()


def test_public_listing_filters_active_tenant_published_items_and_category() -> None:
    session = MagicMock(spec=Session)
    session.scalars.return_value.all.return_value = []
    repository = ShowcaseRepository(session)

    repository.list_published_items(
        salon_id=SALON_ID,
        category=ShowcaseCategory.COSMETICS,
        limit=50,
        offset=0,
    )

    sql, params = _sql_and_params(session.scalars.call_args.args[0])
    assert "showcase_items.salon_id =" in sql
    assert "showcase_items.is_published is true" in sql
    assert "media_assets.deleted_at is null" in sql
    assert "media_assets.salon_id = showcase_items.salon_id" in sql
    assert "showcase_items.category =" in sql
    assert "order by showcase_items.sort_order asc, showcase_items.id asc" in sql
    assert SALON_ID in params.values()
    assert ShowcaseCategory.COSMETICS.value in params.values()


def test_public_listing_without_category_keeps_tenant_and_publication_filters() -> None:
    session = MagicMock(spec=Session)
    session.scalars.return_value.all.return_value = []
    repository = ShowcaseRepository(session)

    repository.list_published_items(
        salon_id=SALON_ID,
        category=None,
        limit=10,
        offset=5,
    )

    sql, params = _sql_and_params(session.scalars.call_args.args[0])
    assert "showcase_items.is_published is true" in sql
    assert "showcase_items.category =" not in sql
    assert SALON_ID in params.values()
    assert 10 in params.values()
    assert 5 in params.values()


def test_public_image_lookup_requires_published_item_and_active_same_tenant_media() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None
    repository = ShowcaseRepository(session)

    repository.get_published_item_by_id(salon_id=SALON_ID, item_id=ITEM_ID)

    sql, params = _sql_and_params(session.scalar.call_args.args[0])
    assert "showcase_items.salon_id =" in sql
    assert "showcase_items.id =" in sql
    assert "showcase_items.is_published is true" in sql
    assert "media_assets.deleted_at is null" in sql
    assert "media_assets.salon_id = showcase_items.salon_id" in sql
    assert SALON_ID in params.values()
    assert ITEM_ID in params.values()
