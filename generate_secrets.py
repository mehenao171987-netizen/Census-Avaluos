"""Genera claves de cifrado y el primer usuario administrador. Imprime variables para el entorno."""
from __future__ import annotations

import getpass
import json
import secrets
import sys
from pathlib import Path

from cryptography.fernet import Fernet

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.security import hash_password  # noqa: E402


def main() -> None:
    print(f"CENSUS_ENCRYPTION_KEY={Fernet.generate_key().decode()}")
    print(f"CENSUS_INDEX_KEY={secrets.token_hex(32)}")
    user = input("Usuario administrador [admin]: ").strip() or "admin"
    password = getpass.getpass("Contraseña (mínimo 12 caracteres): ")
    if len(password) < 12:
        sys.exit("La contraseña debe tener al menos 12 caracteres.")
    users = {user: {"password_hash": hash_password(password), "role": "admin"}}
    print(f"CENSUS_USERS_JSON={json.dumps(users)}")
    print("\nGuarde estas variables en .env o en los secretos de su plataforma. No las versione.")


if __name__ == "__main__":
    main()
