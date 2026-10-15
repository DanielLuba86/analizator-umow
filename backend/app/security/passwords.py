from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()


def hash_password(p: str) -> str:
    return _hasher.hash(p)


def verify_password(h: str, p: str) -> bool:
    try:
        return _hasher.verify(h, p)
    except (VerificationError, InvalidHashError):
        return False
