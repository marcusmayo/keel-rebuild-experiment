#!/usr/bin/env python3
"""Generate TOTP secret and print setup instructions."""
import os
import pyotp

SECRET_FILE = ".totp_secret"


def setup_totp():
    if os.path.exists(SECRET_FILE):
        with open(SECRET_FILE) as f:
            secret = f.read().strip()
        print(f"TOTP already set up. Secret in {SECRET_FILE}")
    else:
        secret = pyotp.random_base32()
        with open(SECRET_FILE, "w") as f:
            f.write(secret)
        print(f"TOTP secret generated and saved to {SECRET_FILE}")

    otpauth_url = pyotp.totp.TOTP(secret).provisioning_uri(
        name="operator", issuer_name="MeridianPPM"
    )
    print(f"\nOTPAuth URL (scan with authenticator app):")
    print(f"  {otpauth_url}")
    print(f"\nCurrent TOTP code: {pyotp.TOTP(secret).now()}")
    print(f"Secret (base32): {secret}")


if __name__ == "__main__":
    setup_totp()