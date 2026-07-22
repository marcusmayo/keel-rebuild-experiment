"""TOTP authentication helpers.

A single TOTP secret is generated at setup and persisted to a dotfile. The
setup step prints it once as an otpauth:// URL. Login verifies a 6-digit code.
"""
from __future__ import annotations

from pathlib import Path

import pyotp

from .config import TOTP_SECRET_FILE

ISSUER = "Meridian PPM"
ACCOUNT = "operator"


def load_secret() -> str:
    """Return the persisted TOTP secret, or empty string if none exists."""
    if TOTP_SECRET_FILE.exists():
        return TOTP_SECRET_FILE.read_text(encoding="utf-8").strip()
    return ""


def ensure_secret() -> str:
    """Return the existing secret, generating and persisting one if needed."""
    secret = load_secret()
    if secret:
        return secret
    secret = pyotp.random_base32()
    TOTP_SECRET_FILE.write_text(secret + "\n", encoding="utf-8")
    return secret


def provisioning_uri(secret: str) -> str:
    """otpauth:// URI for provisioning an authenticator app."""
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=ACCOUNT, issuer_name=ISSUER
    )


def verify_code(secret: str, code: str) -> bool:
    """Verify a 6-digit TOTP code with a small window for clock drift."""
    if not secret or not code:
        return False
    code = code.strip().replace(" ", "")
    if not code.isdigit():
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)
