"""Búsqueda de mercado: Claude + web_search (fuentes citables) y geocodificación OpenStreetMap."""
from __future__ import annotations

import json

import requests

from config.settings import settings

FIELDS = (
    "fuente", "url", "direccion", "barrio", "precio_cop",
    "area_lote_m2", "area_construida_m2", "habitaciones", "fecha_publicacion",
)
PORTALS = "Metrocuadrado, Finca Raíz, Ciencuadras y Properati"


def buscar_oferta(client, model: str, *, tipo: str, municipio: str, barrio: str,
                  direccion: str, area_m2: float, max_results: int = 8) -> list[dict]:
    prompt = (
        f"Busca en {PORTALS} inmuebles en venta similares: tipo '{tipo}', municipio {municipio}, "
        f"barrio o sector '{barrio}', cerca de '{direccion}', área aproximada {area_m2:.0f} m². "
        f"Responde ÚNICAMENTE con un arreglo JSON (máximo {max_results} objetos) con las claves: "
        f"{', '.join(FIELDS)}. precio_cop en pesos sin separadores. Usa null si un dato no aparece. "
        "No incluyas texto fuera del JSON."
    )
    resp = client.messages.create(
        model=model,
        max_tokens=2500,
        tools=[{"type": "web_search_20250305", "name": "web_search",
                "max_uses": settings.web_search_max_uses}],
        messages=[{"role": "user", "content": prompt}],
    )
    text = "\n".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    return parse_json_array(text)[:max_results]


def parse_json_array(text: str) -> list[dict]:
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [{k: item.get(k) for k in FIELDS} for item in data if isinstance(item, dict)]


def geocodificar(direccion: str, municipio: str) -> tuple[float, float] | None:
    resp = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": f"{direccion}, {municipio}, Antioquia, Colombia", "format": "json", "limit": 1},
        headers={"User-Agent": settings.nominatim_user_agent},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data:
        return None
    return float(data[0]["lat"]), float(data[0]["lon"])
