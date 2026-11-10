"""Capa de ciberseguridad: autenticación, roles, cifrado en reposo, bloqueo y auditoría."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timezone

from cryptography.fernet import Fernet

from config.settings import settings

PBKDF2_ITERATIONS = 310_000

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": {"create", "read", "export", "manage_users"},
    "avaluador": {"create", "read", "export"},
    "revisor": {"read", "export"},
}


# ---------- Contraseñas (PBKDF2-SHA256 con sal) ----------
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


def load_users() -> dict:
    try:
        users = json.loads(os.getenv("CENSUS_USERS_JSON", "{}"))
    except json.JSONDecodeError:
        return {}
    return users if isinstance(users, dict) else {}


# ---------- Control de acceso por rol ----------
def has_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())


# ---------- Bloqueo por intentos fallidos ----------
def is_locked(state: dict, now: float) -> bool:
    return now < state.get("locked_until", 0.0)


def register_failure(state: dict, now: float, max_attempts: int, lockout_minutes: int) -> None:
    state["fails"] = state.get("fails", 0) + 1
    if state["fails"] >= max_attempts:
        state["locked_until"] = now + lockout_minutes * 60
        state["fails"] = 0


def reset_failures(state: dict) -> None:
    state["fails"] = 0
    state["locked_until"] = 0.0


# ---------- Cifrado en reposo e índice ciego ----------
def _fernet() -> Fernet:
    key = os.getenv("CENSUS_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("Falta CENSUS_ENCRYPTION_KEY. Ejecute: python scripts/generate_secrets.py")
    return Fernet(key.encode())


def encrypt(text: str) -> str:
    return _fernet().encrypt(text.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode("ascii")).decode("utf-8")


def blind_index(value: str) -> str:
    """HMAC para buscar por cédula sin almacenarla en claro."""
    key = os.getenv("CENSUS_INDEX_KEY")
    if not key:
        raise RuntimeError("Falta CENSUS_INDEX_KEY.")
    return hmac.new(key.encode(), value.encode("utf-8"), hashlib.sha256).hexdigest()


def mask(value: str, visible: int = 3) -> str:
    return "•" * max(len(value) - visible, 0) + value[-visible:]


# ---------- Auditoría (sin datos personales) ----------
def audit(event: str, user: str, **details) -> None:
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    record = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, "user": user, **details}
    with open(settings.log_dir / "audit.log", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
