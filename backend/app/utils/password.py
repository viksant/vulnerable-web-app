"""Dual-format password hashing and verification.

Supports bcrypt (new registrations) and MD5 hex (legacy seed users).
Uses passlib CryptContext for bcrypt operations and raw hashlib for
MD5 fallback on pre-existing weak hashes.
"""

import hashlib

from passlib.context import CryptContext

# Bcrypt context for all new password hashing
_crypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bcrypt only processes the first 72 bytes of input
_BCRYPT_MAX_BYTES = 72


def _truncate_for_bcrypt(password: str) -> str:
    """Truncate a password to 72 bytes (bcrypt hard limit).

    Handles multi-byte UTF-8 characters safely by encoding first,
    slicing at the byte boundary, then decoding back.
    """
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES].decode("utf-8", errors="ignore")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored hash.

    Detects the hash format automatically:
    - ``$2a$`` / ``$2b$`` prefix -> bcrypt verification via passlib
    - Otherwise -> MD5 hex digest comparison (legacy seed users)

    Args:
        plain_password: The user-supplied plaintext password.
        hashed_password: The stored hash from the database.

    Returns:
        True if the password matches the stored hash.
    """
    # Bcrypt hashes always start with $2a$ or $2b$
    if hashed_password.startswith(("$2a$", "$2b$")):
        return _crypt_context.verify(_truncate_for_bcrypt(plain_password), hashed_password)

    # Fallback: legacy MD5 raw hex comparison (seed users 4-5)
    md5_hex = hashlib.md5(plain_password.encode()).hexdigest()
    return md5_hex == hashed_password


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using bcrypt.

    Always produces a bcrypt hash regardless of input. Used for
    new registrations and password resets.

    Args:
        plain_password: The plaintext password to hash.

    Returns:
        Bcrypt hash string (e.g., ``$2b$12$...``).
    """
    return _crypt_context.hash(_truncate_for_bcrypt(plain_password))
