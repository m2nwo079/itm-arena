import unicodedata

import pytest

from itm_arena.domain.nickname import (
    make_nickname_key,
    normalize_nickname,
    validate_nickname,
)


@pytest.mark.parametrize(
    "nickname",
    ["민우", "Minwoo", "user01", "이민우Lee2", "a" * 12, "가나"],
)
def test_valid_nicknames_have_no_errors(nickname):
    assert validate_nickname(nickname) == []


@pytest.mark.parametrize(
    "nickname",
    [
        "",
        "a",
        "a" * 13,
        "min woo",
        " minwoo",
        "minwoo!",
        "min_woo",
        "ㅋㅋ",
        "ㅁ",
        "café",
        "１２３",
    ],
)
def test_invalid_nicknames_return_format_error(nickname):
    errors = validate_nickname(nickname)

    assert len(errors) == 1
    assert errors[0].code == "INVALID_NICKNAME_FORMAT"
    assert errors[0].position is None


def test_decomposed_korean_is_checked_by_composed_length():
    # "민우" in NFD is 5 code points but 2 characters after NFC
    decomposed = unicodedata.normalize("NFD", "민우")
    assert len(decomposed) == 5

    assert validate_nickname(decomposed) == []


def test_decomposed_twelve_syllables_are_accepted():
    decomposed = unicodedata.normalize("NFD", "가" * 12)
    assert len(decomposed) > 12

    assert validate_nickname(decomposed) == []


def test_normalize_returns_composed_form():
    decomposed = unicodedata.normalize("NFD", "민우")

    assert normalize_nickname(decomposed) == "민우"


def test_key_ignores_letter_case():
    assert make_nickname_key("MinWoo") == make_nickname_key("minwoo")


def test_key_matches_for_decomposed_and_composed_korean():
    decomposed = unicodedata.normalize("NFD", "민우")

    assert make_nickname_key(decomposed) == make_nickname_key("민우")


def test_key_keeps_korean_and_digits():
    assert make_nickname_key("이민우2") == "이민우2"