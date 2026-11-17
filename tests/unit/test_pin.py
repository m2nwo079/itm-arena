import pytest

from itm_arena.domain.errors import InvalidPinError
from itm_arena.domain.pin import generate_salt, hash_pin, validate_pin, verify_pin


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