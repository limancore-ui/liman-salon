from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.bonus_transaction import BonusTransaction
from app.db.models.customer import Customer


class BonusLedgerRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_customer(
        self, *, salon_id: uuid.UUID, customer_id: uuid.UUID
    ) -> Customer | None:
        return self._session.scalar(
            select(Customer).where(
                Customer.salon_id == salon_id,
                Customer.id == customer_id,
            )
        )

    def get_customer_for_update(
        self, *, salon_id: uuid.UUID, customer_id: uuid.UUID
    ) -> Customer | None:
        return self._session.scalar(
            select(Customer)
            .where(
                Customer.salon_id == salon_id,
                Customer.id == customer_id,
            )
            .with_for_update()
        )

    def get_transaction_by_idempotency_key(
        self, *, salon_id: uuid.UUID, idempotency_key: str
    ) -> BonusTransaction | None:
        return self._session.scalar(
            select(BonusTransaction).where(
                BonusTransaction.salon_id == salon_id,
                BonusTransaction.idempotency_key == idempotency_key,
            )
        )

    def list_transactions_for_customer(
        self,
        *,
        salon_id: uuid.UUID,
        customer_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> list[BonusTransaction]:
        stmt = (
            select(BonusTransaction)
            .where(
                BonusTransaction.salon_id == salon_id,
                BonusTransaction.customer_id == customer_id,
            )
            .order_by(
                BonusTransaction.created_at.desc(),
                BonusTransaction.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(self._session.scalars(stmt))

    def add_transaction(self, transaction: BonusTransaction) -> BonusTransaction:
        self._session.add(transaction)
        return transaction

    def flush(self) -> None:
        self._session.flush()
