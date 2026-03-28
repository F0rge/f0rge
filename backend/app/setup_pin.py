from __future__ import annotations

import getpass

import bcrypt


def main() -> None:
    pin = getpass.getpass("Enter your PIN: ")
    if not pin:
        print("Error: PIN cannot be empty.")
        return

    confirm = getpass.getpass("Confirm your PIN: ")
    if pin != confirm:
        print("Error: PINs do not match.")
        return

    hashed = bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt())
    print()
    print("Your PIN hash (copy this to your .env file as PIN_HASH):")
    print()
    print(hashed.decode("utf-8"))


if __name__ == "__main__":
    main()
