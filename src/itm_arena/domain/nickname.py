import re
import unicodedata

from itm_arena.domain.types import ValidationError

NICKNAME_MIN_LENGTH = 2
NICKNAME_MAX_LENGTH = 12
# Complete Hangul syllables, ASCII letters, and ASCII digits only
_NICKNAME_PATTERN = re.compile(r"[\uAC00-\uD7A3A-Za-z0-9]+")


def normalize_nickname(nickname: str) -> str:
    # Compose decomposed Hangul (NFD) so each syllable counts as one character
    return unicodedata.normalize("NFC", nickname)


def validate_nickname(nickname: str) -> list[ValidationError]:
    normalized = normalize_nickname(nickname)
    length_ok = NICKNAME_MIN_LENGTH <= len(normalized) <= NICKNAME_MAX_LENGTH
    if length_ok and _NICKNAME_PATTERN.fullmatch(normalized):
        return []
    return [
        ValidationError(
            code="INVALID_NICKNAME_FORMAT",
            position=None,
            message="Nickname must be 2 to 12 Korean letters, English letters, or digits.",
        )
    ]


def make_nickname_key(nickname: str) -> str:
    # Used only for the uniqueness check; the display nickname keeps its case
    return normalize_nickname(nickname).casefold()