"""Motor valuatorio: método comparativo de mercado y método de reposición (Resolución 620 de 2008)."""
from __future__ import annotations

import statistics
from datetime import date, timedelta

from config.settings import settings
from core.models import ResultadoAvaluo, Testigo
from core.numeros import pesos_en_letras

FACTOR_ESTADO = {"Excelente": 0.8, "Bueno": 1.0, "Regular": 1.2, "Malo": 1.4}
CRITERIOS = ("comparativo", "mayor_valor")


def valor_unitario_ajustado(t: Testigo) -> float:
    """Precio por m² de lote homogenizado (forma de pago, época, tamaño, conservación y comercialización)."""
    factor = (
        t.factor_forma_pago
        * t.factor_tiempo
        * t.factor_tamano
        * t.factor_conservacion
        * (1 - t.descuento_comercializacion)
    )
    return (t.precio / t.area_lote) * factor


def coeficiente_variacion(valores: list[float]) -> float:
    if len(valores) < 2:
        return 0.0
    media = statistics.mean(valores)
    return statistics.stdev(valores) / media * 100 if media else 0.0


def depreciacion(edad_anios: float, estado: str) -> float:
    if edad_anios < 0:
        raise ValueError("La antigüedad no puede ser negativa.")
    factor = FACTOR_ESTADO.get(estado, 1.0)
    return min(edad_anios / settings.vida_util_anios * factor, settings.max_depreciacion)


def valor_en_letras(valor: int) -> str:
    return pesos_en_letras(valor)


def calcular_avaluo(
    *,
    area_lote: float,
    area_construida: float,
    edad_anios: float,
    estado: str,
    testigos: list[Testigo],
    costo_m2_construccion: float,
    criterio: str = "comparativo",
    fecha: date | None = None,
) -> ResultadoAvaluo:
    """Calcula el valor comercial.

    criterio 'comparativo': terreno por mercado + construcción neta de depreciación.
    criterio 'mayor_valor': el mayor entre el comparativo y el costo de reposición a nuevo
    (regla de 'mayor valor' mencionada en el formato original).
    """
    if criterio not in CRITERIOS:
        raise ValueError("Criterio de valoración no reconocido.")
    if area_lote <= 0:
        raise ValueError("El área del lote debe ser mayor que cero.")
    if area_construida < 0 or costo_m2_construccion < 0:
        raise ValueError("Áreas y costos no pueden ser negativos.")
    if not testigos:
        raise ValueError("Se requiere al menos un testigo de mercado.")

    fecha = fecha or date.today()
    unitarios = [valor_unitario_ajustado(t) for t in testigos]
    vm2 = statistics.mean(unitarios)
    cv = coeficiente_variacion(unitarios)

    dep = depreciacion(edad_anios, estado)
    valor_terreno = vm2 * area_lote
    vrn = area_construida * costo_m2_construccion
    vnr = vrn * (1 - dep)
    comparativo = valor_terreno + vnr
    costo = valor_terreno + vrn

    bruto = comparativo if criterio == "comparativo" else max(comparativo, costo)
    final = int(round(bruto / settings.redondeo) * settings.redondeo)

    cumple_min = len(testigos) >= settings.min_testigos
    cumple_cv = cv <= settings.cv_max_percent
    mensajes: list[str] = []
    if not cumple_min:
        mensajes.append(f"Se requieren al menos {settings.min_testigos} testigos; tiene {len(testigos)}.")
    if not cumple_cv:
        mensajes.append(
            f"El coeficiente de variación ({cv:.2f} %) supera el máximo de {settings.cv_max_percent} % "
            "(Resolución 620 de 2008). Revise o depure los testigos."
        )

    return ResultadoAvaluo(
        valor_m2_terreno=round(vm2, 2),
        area_lote=area_lote,
        valor_terreno=round(valor_terreno, 2),
        area_construida=area_construida,
        costo_m2_construccion=costo_m2_construccion,
        valor_reposicion_nuevo=round(vrn, 2),
        depreciacion=round(dep, 4),
        valor_construccion=round(vnr, 2),
        valor_comparativo=round(comparativo, 2),
        valor_costo=round(costo, 2),
        valor_final=final,
        coef_variacion=round(cv, 2),
        n_testigos=len(testigos),
        cumple_cv=cumple_cv,
        cumple_minimo=cumple_min,
        criterio=criterio,
        fecha=fecha.isoformat(),
        vigencia_hasta=(fecha + timedelta(days=365)).isoformat(),
        valor_en_letras=valor_en_letras(final),
        detalle_testigos=[
            {"fuente": t.fuente, "direccion": t.direccion, "valor_m2_ajustado": round(u, 0)}
            for t, u in zip(testigos, unitarios)
        ],
        mensajes=mensajes,
    )
