import hashlib
import secrets
from datetime import UTC, datetime

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

_hasher = PasswordHasher()
_dummy = _hasher.hash(secrets.token_urlsafe(32))


def now() -> datetime:
    return datetime.now(UTC)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def hash_password(value: str) -> str:
    return _hasher.hash(value)


def password_matches(encoded: str | None, value: str) -> bool:
    try:
        valid = _hasher.verify(encoded or _dummy, value)
        return valid and encoded is not None
    except VerificationError:
        return False
