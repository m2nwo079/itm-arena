import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from itm_arena.domain.errors import AccountLockedError, InvalidPinError
from itm_arena.domain.types import ValidationError

PIN_LENGTH = 4
SALT_BYTES = 16
HASH_ALGORITHM = "sha256"
# Iteration count for PBKDF2; higher values slow down brute-force attacks
HASH_ITERATIONS = 200_000
MAX_FAILED_ATTEMPTS = 5
LOCK_DURATION = timedelta(minutes=10)


def validate_pin(pin: str) -> list[ValidationError]:
    # Accept only exactly four ASCII digits; isdigit alone also accepts non-ASCII digits
    if len(pin) == PIN_LENGTH and pin.isascii() and pin.isdigit():
        return []
    return [
        ValidationError(
            code="INVALID_PIN_FORMAT",
            position=None,
            message="PIN must be exactly 4 digits.",
        )
    ]


def generate_salt() -> str:
    # A random salt per user makes identical PINs produce different hashes
    return secrets.token_hex(SALT_BYTES)


def hash_pin(pin: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac(
        HASH_ALGORITHM,
        pin.encode("utf-8"),
        bytes.fromhex(salt),
        HASH_ITERATIONS,
    )
    return digest.hex()


def verify_pin(pin: str, salt: str, expected_hash: str) -> None:
    # Constant-time comparison avoids leaking information through timing
    if not hmac.compare_digest(hash_pin(pin, salt), expected_hash):
        raise InvalidPinError("Incorrect PIN.")


@dataclass(frozen=True)
class LoginState:
    # Mirrors users.failed_attempts and users.locked_until in the DB layer (#1)
    failed_attempts: int
    locked_until: datetime | None


def ensure_not_locked(state: LoginState, now: datetime) -> None:
    if state.locked_until is not None and now < state.locked_until:
        raise AccountLockedError(f"Account is locked until {state.locked_until.isoformat()}.")


def register_failure(state: LoginState, now: datetime) -> LoginState:
    failed = state.failed_attempts + 1
    if failed >= MAX_FAILED_ATTEMPTS:
        # Reset the counter so the user gets a fresh set of attempts after the lock ends
        return LoginState(failed_attempts=0, locked_until=now + LOCK_DURATION)
    return LoginState(failed_attempts=failed, locked_until=state.locked_until)


def register_success() -> LoginState:
    return LoginState(failed_attempts=0, locked_until=None)