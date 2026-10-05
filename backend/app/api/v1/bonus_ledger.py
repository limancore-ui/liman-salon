from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import BonusLedgerServiceDep
from app.api.schemas.bonus_ledger import (
    BonusAdjustmentRequest,
    BonusTransactionResponse,
)
from app.auth.deps import require_roles
from app.auth.principals import SalonContext
from app.services.bonus.types import LedgerTransactionResult

router = APIRouter(
    prefix="/salons/{salon_id}/customers/{customer_id}/bonus-transactions",
    tags=["bonus-ledger"],
)

ReadSalonContext = Annotated[
    SalonContext,
    Depends(require_roles("owner", "admin", "staff", "receptionist")),
]
WriteSalonContext = Annotated[SalonContext, Depends(require_roles("owner", "admin"))]


def _assert_path_salon(context: SalonContext, salon_id: uuid.UUID) -> None:
    if context.salon_id != salon_id:
        raise RuntimeError("salon_id path mismatch with SalonContext")


def _to_response(row: LedgerTransactionResult) -> BonusTransactionResponse:
    return BonusTransactionResponse(
        id=row.transaction_id,
        salon_id=row.salon_id,
        customer_id=row.customer_id,
        booking_id=row.booking_id,
        transaction_type=row.transaction_type,
        amount_cents=row.amount_cents,
        balance_after_cents=row.balance_after_cents,
        description=row.description,
        idempotency_key=row.idempotency_key,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at,
    )


@router.get("", response_model=list[BonusTransactionResponse])
def list_bonus_transactions(
    salon_id: uuid.UUID,
    customer_id: uuid.UUID,
    context: ReadSalonContext,
    bonus_ledger_service: BonusLedgerServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[BonusTransactionResponse]:
    _assert_path_salon(context, salon_id)
    rows = bonus_ledger_service.list_transactions(
        salon_id=context.salon_id,
        customer_id=customer_id,
        limit=limit,
        offset=offset,
    )
    return [_to_response(row) for row in rows]


@router.post(
    "/adjustment",
    response_model=BonusTransactionResponse,
    status_code=201,
)
def create_bonus_adjustment(
    salon_id: uuid.UUID,
    customer_id: uuid.UUID,
    body: BonusAdjustmentRequest,
    context: WriteSalonContext,
    bonus_ledger_service: BonusLedgerServiceDep,
) -> BonusTransactionResponse:
    _assert_path_salon(context, salon_id)
    result = bonus_ledger_service.create_adjustment(
        salon_id=context.salon_id,
        customer_id=customer_id,
        amount_cents=body.amount_cents,
        description=body.reason,
        created_by_user_id=context.user_id,
    )
    return _to_response(result)
