"""Validación y saneamiento de entradas (defensa contra inyección y datos mal formados)."""
from __future__ import annotations

import re

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_TAGS = re.compile(r"<[^>]*>")
_SPACES = re.compile(r"\s+")
_NAME = re.compile(r"^[A-ZÁÉÍÓÚÑÜ][A-ZÁÉÍÓÚÑÜ .'\-]{4,119}$")
_ADDRESS = re.compile(r"^[A-Z0-9ÁÉÍÓÚÑÜ#°ºª.,/\- ]{5,150}$")
_CEDULA = re.compile(r"\d{6,10}")
_MATRICULA = re.compile(r"(\d{3})\s?-?\s?(\d{3,7})")


def clean_text(value) -> str:
    """Elimina caracteres de control, etiquetas HTML y espacios sobrantes."""
    text = "" if value is None else str(value)
    text = _CONTROL.sub("", text)
    text = _TAGS.sub("", text)
    return _SPACES.sub(" ", text).strip()


def validate_nombre(value) -> tuple[str, str | None]:
    text = clean_text(value).upper()
    if not _NAME.match(text):
        return text, "Ingrese el nombre (solo letras, mínimo 5 caracteres)."
    if len(text.split()) < 2:
        return text, "Ingrese al menos un nombre y un apellido."
    return text, None


def validate_cedula(value) -> tuple[str, str | None]:
    text = re.sub(r"[.\s,]", "", clean_text(value))
    if not _CEDULA.fullmatch(text):
        return text, "La cédula debe tener entre 6 y 10 dígitos numéricos."
    return text, None


def validate_matricula(value) -> tuple[str, str | None]:
    """Formato Colombia: código ORIP de 3 dígitos + consecutivo, p. ej. 001-400729."""
    text = clean_text(value)
    match = _MATRICULA.fullmatch(text)
    if not match:
        return text, "Use el formato ORIP-consecutivo, por ejemplo 001-400729."
    return f"{match.group(1)}-{match.group(2)}", None


def validate_direccion(value) -> tuple[str, str | None]:
    text = clean_text(value).upper()
    if not _ADDRESS.match(text):
        return text, "Dirección inválida. Use letras, números y símbolos # - . , /."
    return text, None


def validate_positive(value, label: str) -> str | None:
    try:
        if float(value) <= 0:
            return f"{label} debe ser mayor que cero."
    except (TypeError, ValueError):
        return f"{label} debe ser un número válido."
    return None
