from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.bonus_transaction import BonusTransaction
from app.db.models.customer import Customer
from app.services.booking.errors import BookingNotFoundError, BookingValidationError
from app.services.booking.repository import BookingRepository
from app.services.bonus.errors import (
    BonusLedgerConflictError,
    BonusLedgerNotFoundError,
    BonusLedgerValidationError,
)
from app.services.bonus.repository import BonusLedgerRepository
from app.services.bonus.types import LedgerTransactionResult
from app.services.salon_settings.parse import (
    compute_earn_amount_cents,
    resolve_bonus_earn_policy,
)

_DESCRIPTION_MAX = 255
_EARN_IDEMPOTENCY_PREFIX = "earn:booking:"


class BonusLedgerService:
    """Sole write point for bonus_transactions and customers.bonus_balance_cents."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = BonusLedgerRepository(session)
        self._bookings = BookingRepository(session)

    def earn_for_booking(
        self,
        *,
        salon_id: uuid.UUID,
        booking_id: uuid.UUID,
        customer_id: uuid.UUID,
    ) -> LedgerTransactionResult | None:
        """
        Credit earn for a completed booking.

        Earn amount is derived from the booking's stored price_cents and salon bonus
        settings. Disabled or zero-percent policy yields None (silent no-op).
        """
        booking = self._bookings.get_booking(salon_id, booking_id)
        if booking is None:
            raise BookingNotFoundError("booking not found")
        if booking.status != "completed":
            raise BookingValidationError(
                "bonus cannot be earned for booking in its current status"
            )
        if booking.customer_id != customer_id:
            raise BonusLedgerValidationError(
                "booking customer_id does not match earn request"
            )

        price_cents = booking.price_cents
        if price_cents < 0:
            raise BonusLedgerValidationError("booking price_cents must be >= 0")

        raw_settings = self._bookings.get_salon_settings(salon_id)
        policy = resolve_bonus_earn_policy(raw_settings)
        earn_amount = compute_earn_amount_cents(
            price_cents=price_cents,
            policy=policy,
        )

        if earn_amount <= 0:
            return None

        idempotency_key = f"{_EARN_IDEMPOTENCY_PREFIX}{booking_id}"
        return self._post_ledger_entry(
            salon_id=salon_id,
            customer_id=customer_id,
            amount_cents=earn_amount,
            transaction_type="earn",
            booking_id=booking_id,
            description=None,
            idempotency_key=idempotency_key,
            created_by_user_id=None,
        )

    def list_transactions(
        self,
        *,
        salon_id: uuid.UUID,
        customer_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> list[LedgerTransactionResult]:
        customer = self._repo.get_customer(
            salon_id=salon_id,
            customer_id=customer_id,
        )
        if customer is None:
            raise BonusLedgerNotFoundError("customer not found")

        rows = self._repo.list_transactions_for_customer(
            salon_id=salon_id,
            customer_id=customer_id,
            limit=limit,
            offset=offset,
        )
        return [
            self._to_result(row, idempotent_replay=False) for row in rows
        ]

    def create_adjustment(
        self,
        *,
        salon_id: uuid.UUID,
        customer_id: uuid.UUID,
        amount_cents: int,
        description: str,
        created_by_user_id: uuid.UUID | None = None,
    ) -> LedgerTransactionResult:
        if amount_cents == 0:
            raise BonusLedgerValidationError("adjustment amount_cents must be non-zero")

        normalized = self._normalize_description(description)
        return self._post_ledger_entry(
            salon_id=salon_id,
            customer_id=customer_id,
            amount_cents=amount_cents,
            transaction_type="adjustment",
            booking_id=None,
            description=normalized,
            idempotency_key=None,
            created_by_user_id=created_by_user_id,
        )

    def _post_ledger_entry(
        self,
        *,
        salon_id: uuid.UUID,
        customer_id: uuid.UUID,
        amount_cents: int,
        transaction_type: str,
        booking_id: uuid.UUID | None,
        description: str | None,
        idempotency_key: str | None,
        created_by_user_id: uuid.UUID | None,
    ) -> LedgerTransactionResult:
        customer = self._repo.get_customer_for_update(
            salon_id=salon_id,
            customer_id=customer_id,
        )
        if customer is None:
            raise BonusLedgerNotFoundError("customer not found")

        if idempotency_key is not None:
            existing = self._repo.get_transaction_by_idempotency_key(
                salon_id=salon_id,
                idempotency_key=idempotency_key,
            )
            if existing is not None:
                return self._idempotent_replay(customer, existing)

        new_balance = customer.bonus_balance_cents + amount_cents
        if new_balance < 0:
            raise BonusLedgerValidationError("bonus balance cannot go negative")

        transaction = BonusTransaction(
            salon_id=salon_id,
            customer_id=customer_id,
            booking_id=booking_id,
            transaction_type=transaction_type,
            amount_cents=amount_cents,
            balance_after_cents=new_balance,
            description=description,
            idempotency_key=idempotency_key,
            created_by_user_id=created_by_user_id,
        )

        if idempotency_key is not None:
            try:
                with self._session.begin_nested():
                    self._repo.add_transaction(transaction)
                    self._repo.flush()
            except IntegrityError as exc:
                existing = self._repo.get_transaction_by_idempotency_key(
                    salon_id=salon_id,
                    idempotency_key=idempotency_key,
                )
                if existing is not None:
                    return self._idempotent_replay(customer, existing)
                raise BonusLedgerConflictError("bonus ledger write conflict") from exc
        else:
            self._repo.add_transaction(transaction)
            self._repo.flush()

        customer.bonus_balance_cents = new_balance
        self._repo.flush()
        return self._to_result(transaction, idempotent_replay=False)

    def _idempotent_replay(
        self,
        customer: Customer,
        existing: BonusTransaction,
    ) -> LedgerTransactionResult:
        expected_balance = existing.balance_after_cents
        if customer.bonus_balance_cents != expected_balance:
            customer.bonus_balance_cents = expected_balance
            self._repo.flush()
        return self._to_result(existing, idempotent_replay=True)

    @staticmethod
    def _normalize_description(description: str) -> str:
        trimmed = description.strip()
        if not trimmed:
            raise BonusLedgerValidationError("adjustment description is required")
        if len(trimmed) > _DESCRIPTION_MAX:
            raise BonusLedgerValidationError(
                f"adjustment description must be at most {_DESCRIPTION_MAX} characters"
            )
        return trimmed

    @staticmethod
    def _to_result(
        transaction: BonusTransaction,
        *,
        idempotent_replay: bool,
    ) -> LedgerTransactionResult:
        return LedgerTransactionResult(
            transaction_id=transaction.id,
            salon_id=transaction.salon_id,
            customer_id=transaction.customer_id,
            booking_id=transaction.booking_id,
            transaction_type=transaction.transaction_type,
            amount_cents=transaction.amount_cents,
            balance_after_cents=transaction.balance_after_cents,
            description=transaction.description,
            idempotency_key=transaction.idempotency_key,
            created_by_user_id=transaction.created_by_user_id,
            created_at=transaction.created_at,
            idempotent_replay=idempotent_replay,
        )
