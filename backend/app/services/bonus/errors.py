from __future__ import annotations


class BonusLedgerError(Exception):
    """Base class for bonus ledger application errors."""


class BonusLedgerNotFoundError(BonusLedgerError):
    """Tenant-scoped customer, booking, or related row was not found."""


class BonusLedgerValidationError(BonusLedgerError):
    """Input or business rule violation (e.g. negative balance)."""


class BonusLedgerConflictError(BonusLedgerError):
    """Unexpected ledger conflict (non-idempotent integrity failure)."""
