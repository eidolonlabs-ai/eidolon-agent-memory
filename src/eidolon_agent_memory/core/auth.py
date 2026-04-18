from __future__ import annotations

import secrets
import uuid

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_ph = PasswordHasher()


def generate_api_key() -> tuple[str, str]:
    """Return (raw_key, hashed_key). Store the hash; give raw_key to user."""
    raw = f"mnemo-{secrets.token_urlsafe(32)}"
    hashed = _ph.hash(raw)
    return raw, hashed


def verify_api_key(raw_key: str, hashed_key: str) -> bool:
    try:
        return _ph.verify(hashed_key, raw_key)
    except VerifyMismatchError:
        return False
