#!/usr/bin/env python3
"""
Generate the two secrets Panjur needs and write them to ~/.panjur.env

    python3 gen_secrets.py

Run this once on the Pi. Run it again any time you want to change the
password. The file it writes is chmod 600 and lives OUTSIDE the git repo,
so the password hash is never committed.
"""

import getpass
import os
import secrets
import stat
import sys

from werkzeug.security import generate_password_hash

ENV_PATH = os.path.expanduser("~/.panjur.env")

MIN_LEN = 10


def main():
    print("Panjur secrets setup")
    print("--------------------")

    if os.path.exists(ENV_PATH):
        ans = input(f"{ENV_PATH} already exists. Overwrite? [y/N] ").strip().lower()
        if ans != "y":
            print("Cancelled.")
            return 1

    pw = getpass.getpass("New panjur password: ")
    if len(pw) < MIN_LEN:
        print(f"\nToo short - use at least {MIN_LEN} characters.")
        print("This password is the only thing between the internet and your")
        print("shutters once the tunnel is up. Use a password manager.")
        return 1
    if pw != getpass.getpass("Repeat password: "):
        print("\nPasswords did not match.")
        return 1

    secret_key = secrets.token_hex(32)
    pw_hash = generate_password_hash(pw)

    # Values are single-quoted: the scrypt hash contains '$' characters,
    # which a shell would try to expand if the value were left bare.
    # systemd's EnvironmentFile strips the quotes the same way a shell does.
    with open(ENV_PATH, "w") as f:
        f.write("# Panjur secrets - do NOT commit this file\n")
        f.write(f"PANJUR_SECRET_KEY='{secret_key}'\n")
        f.write(f"PANJUR_PASSWORD_HASH='{pw_hash}'\n")
        # Flip to 1 once the app is only reachable over HTTPS (tunnel).
        f.write("PANJUR_HTTPS='0'\n")

    os.chmod(ENV_PATH, stat.S_IRUSR | stat.S_IWUSR)  # 600, owner only

    print(f"\nWrote {ENV_PATH} (mode 600)")
    print("\nNext:")
    print("  sudo systemctl restart panjur")
    print("  then open the site - it should ask for this password.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
