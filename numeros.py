"""Conversión de cifras a letras en español (para el 'valor en letras' del avalúo). Sin dependencias externas."""
from __future__ import annotations

_UNITS = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve",
          "diez", "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete",
          "dieciocho", "diecinueve", "veinte"]
_VEINTI_ACCENT = {"dos": "dós", "tres": "trés", "seis": "séis"}
_TENS = {30: "treinta", 40: "cuarenta", 50: "cincuenta", 60: "sesenta",
         70: "setenta", 80: "ochenta", 90: "noventa"}
_HUNDREDS = {100: "ciento", 200: "doscientos", 300: "trescientos", 400: "cuatrocientos",
             500: "quinientos", 600: "seiscientos", 700: "setecientos",
             800: "ochocientos", 900: "novecientos"}


def _below_100(n: int) -> str:
    if n <= 20:
        return _UNITS[n]
    if n < 30:
        unit = n - 20
        return "veinti" + ("uno" if unit == 1 else _VEINTI_ACCENT.get(_UNITS[unit], _UNITS[unit]))
    tens, unit = divmod(n, 10)
    word = _TENS[tens * 10]
    return f"{word} y {_UNITS[unit]}" if unit else word


def _below_1000(n: int) -> str:
    if n == 0:
        return ""
    if n == 100:
        return "cien"
    hundreds, rest = divmod(n, 100)
    parts = []
    if hundreds:
        parts.append(_HUNDREDS[hundreds * 100])
    if rest:
        parts.append(_below_100(rest))
    return " ".join(parts)


def _apocope(words: str) -> str:
    """'veintiuno' -> 'veintiún' antes de sustantivos (apócope de 'uno')."""
    if words.endswith("uno"):
        return words[:-3] + "ún" if words.endswith("iuno") else words[:-3] + "un"
    return words


def to_words(n: int) -> str:
    if n < 0:
        raise ValueError("Solo se admiten cifras no negativas.")
    if n == 0:
        return "cero"
    parts = []
    millones, resto = divmod(n, 1_000_000)
    if millones:
        if millones == 1:
            parts.append("un millón")
        else:
            parts.append(f"{_apocope(to_words(millones))} millones")
    miles, resto = divmod(resto, 1000)
    if miles:
        parts.append("mil" if miles == 1 else f"{_apocope(to_words(miles))} mil")
    if resto:
        parts.append(_below_1000(resto))
    return " ".join(parts)


def pesos_en_letras(valor: int) -> str:
    return f"{to_words(int(valor)).upper()} PESOS M/CTE"
