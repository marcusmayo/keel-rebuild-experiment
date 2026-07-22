"""Generate the TOTP secret for the web app.

Creates .totp_secret (if missing) and prints the otpauth:// URL exactly
once so the operator can enroll an authenticator. The file is
git-ignored.
"""
import os

import pyotp

from common import ROOT

SECRET_PATH = os.path.join(ROOT, ".totp_secret")


def ensure_secret():
    if os.path.exists(SECRET_PATH):
        with open(SECRET_PATH) as f:
            return f.read().strip(), False
    secret = pyotp.random_base32()
    with open(SECRET_PATH, "w") as f:
        f.write(secret + "\n")
    os.chmod(SECRET_PATH, 0o600)
    return secret, True


def main():
    secret, created = ensure_secret()
    uri = pyotp.TOTP(secret).provisioning_uri(name="operator",
                                              issuer_name="Meridian PPM")
    if created:
        print("TOTP secret generated. Enroll this URL in your authenticator:")
    else:
        print("TOTP secret already exists; enrollment URL:")
    print(uri)


if __name__ == "__main__":
    main()
