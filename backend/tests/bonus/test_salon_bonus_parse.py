from __future__ import annotations

import pytest

from app.services.salon_settings.parse import (
    BonusEarnPolicy,
    compute_earn_amount_cents,
    resolve_bonus_earn_policy,
)


def test_resolve_bonus_defaults_when_missing() -> None:
    assert resolve_bonus_earn_policy(None) == BonusEarnPolicy()
    assert resolve_bonus_earn_policy({}) == BonusEarnPolicy()


def test_resolve_bonus_from_settings() -> None:
    policy = resolve_bonus_earn_policy(
        {"v": 1, "bonuses": {"enabled": True, "earn_percentage": 7.5}}
    )
    assert policy.enabled is True
    assert policy.earn_percentage == 7.5


@pytest.mark.parametrize(
    ("price", "pct", "expected"),
    [
        (10_000, 10, 1_000),
        (10_001, 10, 1_000),
        (100, 0, 0),
    ],
)
def test_compute_earn_amount(price: int, pct: float, expected: int) -> None:
    policy = BonusEarnPolicy(enabled=True, earn_percentage=pct)
    assert compute_earn_amount_cents(price_cents=price, policy=policy) == expected


def test_compute_earn_disabled() -> None:
    policy = BonusEarnPolicy(enabled=False, earn_percentage=50)
    assert compute_earn_amount_cents(price_cents=1000, policy=policy) == 0
