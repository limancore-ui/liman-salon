"""Fixtures for notification PostgreSQL integration tests."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session


@pytest.fixture
def db_session(postgres_test_engine) -> Session:
    connection = postgres_test_engine.connect()
    try:
        transaction = connection.begin()
        try:
            with Session(
                bind=connection,
                join_transaction_mode="create_savepoint",
            ) as session:
                yield session
        finally:
            transaction.rollback()
    finally:
        connection.close()
