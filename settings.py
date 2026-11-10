"""Configuración central. Los secretos se leen SOLO desde variables de entorno."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str = "Census Avalúos"
    company: str = "Adaptiva.com.co"
    version: str = "1.0.0"

    db_path: Path = BASE_DIR / "data" / "census.db"
    log_dir: Path = BASE_DIR / "logs"

    # Seguridad
    session_timeout_min: int = _env_int("CENSUS_SESSION_TIMEOUT_MIN", 30)
    max_login_attempts: int = _env_int("CENSUS_MAX_LOGIN_ATTEMPTS", 5)
    lockout_minutes: int = _env_int("CENSUS_LOCKOUT_MIN", 15)
    max_upload_mb: int = 10

    # IA y búsqueda web
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY") or None
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
    web_search_max_uses: int = 5
    nominatim_user_agent: str = os.getenv(
        "NOMINATIM_USER_AGENT", "CensusAvaluos/1.0 (contacto@adaptiva.com.co)"
    )

    # Parámetros valuatorios (Resolución 620 de 2008)
    min_testigos: int = 5
    cv_max_percent: float = 7.4
    vida_util_anios: int = 80
    max_depreciacion: float = 0.6
    redondeo: int = 1000


settings = Settings()
