"""Setup -- generate (once) and persist the TOTP secret and Flask session key.

The TOTP secret is printed as an otpauth URL the operator scans into an
authenticator app. Secrets persist in secrets/ so re-running setup keeps the
same code (only generated when absent).
"""
from __future__ import annotations

import secrets as pysecrets

import pyotp

from . import config


def ensure_secrets() -> tuple[str, str, bool]:
    """Return (totp_secret, otpauth_uri, newly_generated)."""
    config.SECRETS_DIR.mkdir(parents=True, exist_ok=True)

    if config.TOTP_SECRET_FILE.exists():
        totp_secret = config.TOTP_SECRET_FILE.read_text().strip()
        generated = False
    else:
        totp_secret = pyotp.random_base32()
        config.TOTP_SECRET_FILE.write_text(totp_secret)
        generated = True

    if not config.FLASK_SECRET_FILE.exists():
        config.FLASK_SECRET_FILE.write_text(pysecrets.token_hex(32))

    totp = pyotp.TOTP(totp_secret)
    uri = totp.provisioning_uri(name="operator", issuer_name="Meridian PPM")
    return totp_secret, uri, generated


if __name__ == "__main__":
    secret, uri, generated = ensure_secrets()
    if generated:
        print("New TOTP secret generated.")
    else:
        print("Existing TOTP secret reused.")
    print()
    print("Scan this otpauth URL into your authenticator app:")
    print(uri)
    print()
    print(f"TOTP secret (base32): {secret}")
    print("Current code: " + pyotp.TOTP(secret).now())
