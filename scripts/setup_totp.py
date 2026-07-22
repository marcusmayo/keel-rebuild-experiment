#!/usr/bin/env python3
"""Generate the TOTP secret (once) and print it as an otpauth:// URL.

If a secret already exists it is reused and its URL is printed again. This is
the only place the secret is surfaced.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from meridian.auth import ensure_secret, provisioning_uri, load_secret  # noqa: E402


def main() -> int:
    existed = bool(load_secret())
    secret = ensure_secret()
    uri = provisioning_uri(secret)
    if existed:
        print("TOTP secret already exists; reusing it.")
    else:
        print("Generated new TOTP secret.")
    print(f"Secret: {secret}")
    print(f"otpauth URL: {uri}")
    print("Add this to an authenticator app (or use pyotp to derive codes).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
