from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.db.session import get_db


def _finish_successful_request(gen) -> None:
    try:
        next(gen)
    except StopIteration:
        pass


def test_get_db_commits_on_successful_request() -> None:
    gen = get_db()
    db = next(gen)
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.close = MagicMock()

    _finish_successful_request(gen)

    db.commit.assert_called_once()
    db.rollback.assert_not_called()
    db.close.assert_called_once()


def test_get_db_rolls_back_on_exception() -> None:
    gen = get_db()
    db = next(gen)
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.close = MagicMock()

    with pytest.raises(RuntimeError, match="boom"):
        gen.throw(RuntimeError("boom"))

    db.rollback.assert_called_once()
    db.commit.assert_not_called()
    db.close.assert_called_once()
