from __future__ import annotations

from app.services.booking.manage_token import (
    generate_manage_token,
    hash_manage_token,
    verify_manage_token,
)

TEST_PEPPER = "unit-test-booking-manage-token-pepper"


def test_generate_manage_token_unique_and_non_empty() -> None:
    a = generate_manage_token()
    b = generate_manage_token()
    assert a
    assert b
    assert a != b
    assert len(a) >= 32


def test_hash_is_not_raw_token() -> None:
    raw = generate_manage_token()
    stored = hash_manage_token(raw, pepper=TEST_PEPPER)
    assert stored != raw
    assert len(stored) == 64


def test_verify_manage_token_accepts_valid() -> None:
    raw = generate_manage_token()
    stored = hash_manage_token(raw, pepper=TEST_PEPPER)
    assert verify_manage_token(raw, stored, pepper=TEST_PEPPER)


def test_verify_manage_token_rejects_wrong_token() -> None:
    raw = generate_manage_token()
    stored = hash_manage_token(raw, pepper=TEST_PEPPER)
    assert not verify_manage_token("wrong-token", stored, pepper=TEST_PEPPER)


def test_verify_manage_token_rejects_missing_hash() -> None:
    assert not verify_manage_token("any", None, pepper=TEST_PEPPER)


def test_verify_manage_token_rejects_wrong_pepper() -> None:
    raw = generate_manage_token()
    stored = hash_manage_token(raw, pepper=TEST_PEPPER)
    assert not verify_manage_token(raw, stored, pepper="other-pepper")
