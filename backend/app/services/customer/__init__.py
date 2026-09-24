"""Customer administration and public resolve application service."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.customer.service import CustomerService

__all__ = ["CustomerService"]


def __getattr__(name: str) -> object:
    if name == "CustomerService":
        from app.services.customer.service import CustomerService

        return CustomerService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
