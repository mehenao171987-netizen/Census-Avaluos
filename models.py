"""Modelos de dominio del avalúo."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Testigo:
    """Transacción, oferta o avalúo comparable (testigo de mercado)."""

    fuente: str
    direccion: str
    precio: float
    area_lote: float
    area_construida: float = 0.0
    factor_forma_pago: float = 1.0
    factor_tiempo: float = 1.0
    factor_tamano: float = 1.0
    factor_conservacion: float = 1.0
    descuento_comercializacion: float = 0.0  # fracción entre 0.00 y 0.05

    def __post_init__(self) -> None:
        if self.precio <= 0 or self.area_lote <= 0:
            raise ValueError(f"Testigo '{self.fuente}': precio y área deben ser mayores que cero.")
        if not 0.0 <= self.descuento_comercializacion <= 0.05:
            raise ValueError(
                f"Testigo '{self.fuente}': el descuento de comercialización debe estar entre 0 % y 5 %."
            )
        for name in ("factor_forma_pago", "factor_tiempo", "factor_tamano", "factor_conservacion"):
            if not 0.5 <= getattr(self, name) <= 1.5:
                raise ValueError(f"Testigo '{self.fuente}': {name} fuera de rango (0,5 – 1,5).")


@dataclass
class ResultadoAvaluo:
    valor_m2_terreno: float
    area_lote: float
    valor_terreno: float
    area_construida: float
    costo_m2_construccion: float
    valor_reposicion_nuevo: float
    depreciacion: float
    valor_construccion: float
    valor_comparativo: float
    valor_costo: float
    valor_final: int
    coef_variacion: float
    n_testigos: int
    cumple_cv: bool
    cumple_minimo: bool
    criterio: str
    fecha: str
    vigencia_hasta: str
    valor_en_letras: str
    detalle_testigos: list[dict] = field(default_factory=list)
    mensajes: list[str] = field(default_factory=list)
