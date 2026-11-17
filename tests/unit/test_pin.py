from datetime import datetime, timedelta, timezone

import pytest

from itm_arena.domain.errors import AccountLockedError, InvalidPinError
from itm_arena.domain.pin import (
    LoginState,
    ensure_not_locked,
    generate_salt,
    hash_pin,
    register_failure,
    register_success,
    validate_pin,
    verify_pin,
)

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


def test_valid_pin_has_no_errors():
    assert validate_pin("0123") == []


@pytest.mark.parametrize("pin", ["", "123", "12345", "12a4", " 123", "١٢٣٤"])
def test_invalid_pin_format_is_rejected(pin):
    errors = validate_pin(pin)
    assert len(errors) == 1
    assert errors[0].code == "INVALID_PIN_FORMAT"


def test_same_pin_with_different_salts_gives_different_hashes():
    assert hash_pin("1234", generate_salt()) != hash_pin("1234", generate_salt())


def test_same_pin_and_salt_gives_same_hash():
    salt = generate_salt()
    assert hash_pin("1234", salt) == hash_pin("1234", salt)


def test_correct_pin_passes():
    salt = generate_salt()
    verify_pin("1234", salt, hash_pin("1234", salt))


def test_wrong_pin_raises_invalid_pin_error():
    salt = generate_salt()
    with pytest.raises(InvalidPinError):
        verify_pin("9999", salt, hash_pin("1234", salt))


def fail_times(count: int) -> LoginState:
    state = LoginState(failed_attempts=0, locked_until=None)
    for _ in range(count):
        state = register_failure(state, NOW)
    return state


def test_four_failures_do_not_lock():
    ensure_not_locked(fail_times(4), NOW)


def test_five_failures_lock_the_account():
    with pytest.raises(AccountLockedError):
        ensure_not_locked(fail_times(5), NOW + timedelta(minutes=1))


def test_lock_is_released_after_ten_minutes():
    ensure_not_locked(fail_times(5), NOW + timedelta(minutes=10))


def test_success_resets_failed_attempts():
    state = register_failure(LoginState(failed_attempts=3, locked_until=None), NOW)
    assert register_success() == LoginState(failed_attempts=0, locked_until=None)
    assert state.failed_attempts == 4