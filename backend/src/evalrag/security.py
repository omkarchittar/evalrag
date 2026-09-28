"""Sensitive data utilities. Do not serialize decrypted values into logs or audit events."""

import hashlib
import hmac
import os


def hash_password(password: str) -> str:
    if not 12 <= len(password) <= 1024:
        raise ValueError("Password must contain 12–1024 characters")
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return "scrypt$" + salt.hex() + "$" + digest.hex()


def verify_password(password: str, encoded: str) -> bool:
    if len(password) > 1024:
        return False
    try:
        algorithm, salt, expected = encoded.split("$")
        if algorithm != "scrypt" or len(salt) != 32 or len(expected) != 64:
            return False
        actual = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1, dklen=32
        )
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def session_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
