"""Helper: print the current TOTP code from the persisted secret.

Used by the operator (and automated checks) to obtain a login code without
scanning a QR code.
"""
from __future__ import annotations

import pyotp

from .setup import ensure_secrets

if __name__ == "__main__":
    secret, _uri, _generated = ensure_secrets()
    print(pyotp.TOTP(secret).now())
