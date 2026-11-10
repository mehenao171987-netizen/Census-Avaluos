"""Asistente de avalúo paso a paso. Cada campo se sincroniza con st.session_state.draft."""
from __future__ import annotations

import json
import math
import statistics
from dataclasses import asdict
from datetime import date

import pandas as pd
import streamlit as st

from config.settings import settings
from core import security
from core import validators as V
from core.models import Testigo
from core.repository import Repository
from core.valuation import calcular_avaluo, coeficiente_variacion, valor_unitario_ajustado
from services import image_service as IMG
from services import market_search as MS
from services.ai_assistant import AIUnavailable, ClaudeAssistant, datos_tecnicos, get_client
from services.report import build_docx
from ui import components as C

TIPOS = ["Casa independiente", "Casa en conjunto cerrado", "Apartamento", "Lote",
         "Local comercial", "Bodega", "Finca"]
ESTADOS = ["Excelente", "Bueno", "Regular", "Malo"]
SERVICIOS = ["Agua", "Energía", "Teléfono", "Gas domiciliario", "Acueducto",
             "Alcantarillado", "Alumbrado público", "Internet"]
CRITERIOS = {"comparativo": "Método comparativo de mercado",
             "mayor_valor": "Mayor valor entre métodos"}
TESTIGO_COLS = ["fuente", "direccion", "precio", "area_lote", "area_construida",
                "factor_forma_pago", "factor_tiempo", "factor_tamano",
                "factor_conservacion", "descuento"]
TESTIGO_CFG = {
    "fuente": st.column_config.TextColumn("Fuente", required=True),
    "direccion": st.column_config.TextColumn("Dirección"),
    "precio": st.column_config.NumberColumn("Precio (COP)", min_value=0, format="%d"),
    "area_lote": st.column_config.NumberColumn("Área lote m²", min_value=0.0, format="%.2f"),
    "area_construida": st.column_config.NumberColumn("Área const. m²", min_value=0.0, format="%.2f"),
    "factor_forma_pago": st.column_config.NumberColumn("Forma pago", min_value=0.5, max_value=1.5, format="%.3f", help="1,000 = contado"),
    "factor_tiempo": st.column_config.NumberColumn("Época", min_value=0.5, max_value=1.5, format="%.3f"),
    "factor_tamano": st.column_config.NumberColumn("Tamaño", min_value=0.5, max_value=1.5, format="%.3f"),
    "factor_conservacion": st.column_config.NumberColumn("Conservación", min_value=0.5, max_value=1.5, format="%.3f"),
    "descuento": st.column_config.NumberColumn("Comercialización %", min_value=0.0, max_value=5.0, format="%.1f"),
}


# ---------- utilidades ----------
def _user() -> str:
    return st.session_state.auth["user"]


def _role() -> str:
    return st.session_state.auth["role"]


def _d() -> dict:
    return st.session_state.draft


def _f(value, default=None):
    try:
        if value is None or pd.isna(value) or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _idx(options, value) -> int:
    return options.index(value) if value in options else 0


_WIDGETS = {
    "text": st.text_input, "area": st.text_area, "num": st.number_input,
    "select": st.selectbox, "multi": st.multiselect, "date": st.date_input, "toggle": st.toggle,
}


def field(kind: str, label: str, name: str, default, **kw):
    """Widget con clave persistente; sincroniza el valor con el borrador."""
    key = f"f_{name}"
    if key not in st.session_state:
        st.session_state[key] = default
    _WIDGETS[kind](label, key=key, **kw)
    st.session_state.draft[name] = st.session_state[key]
    return st.session_state[key]


def _clean_identifiers(d: dict) -> None:
    d["nombre"] = V.validate_nombre(d.get("nombre"))[0]
    d["cedula"] = V.validate_cedula(d.get("cedula"))[0]
    d["matricula"] = V.validate_matricula(d.get("matricula"))[0]
    d["direccion"] = V.validate_direccion(d.get("direccion"))[0]


@st.cache_resource
def _repo() -> Repository:
    return Repository()


# ---------- Paso 1: propietario ----------
def s_propietario(d):
    field("text", "Nombre completo del propietario", "nombre", "", max_chars=120,
          placeholder="Ej.: Carlos Mario Arango Tobón",
          help="Tal como figura en el certificado de tradición y libertad.")


def v_propietario(d):
    d["nombre"], err = V.validate_nombre(d.get("nombre"))
    return [err] if err else []


# ---------- Paso 2: cédula ----------
def s_cedula(d):
    field("text", "Número de cédula de ciudadanía", "cedula", "", max_chars=14,
          placeholder="Sin puntos. Ej.: 71683719",
          help="Se almacena cifrada en el registro seguro.")


def v_cedula(d):
    d["cedula"], err = V.validate_cedula(d.get("cedula"))
    return [err] if err else []


# ---------- Paso 3: matrícula ----------
def s_matricula(d):
    field("text", "Matrícula inmobiliaria", "matricula", "", max_chars=14,
          placeholder="001-400729",
          help="Código de la Oficina de Registro (ORIP) seguido del consecutivo.")


def v_matricula(d):
    d["matricula"], err = V.validate_matricula(d.get("matricula"))
    return [err] if err else []


# ---------- Paso 4: ubicación ----------
def s_ubicacion(d):
    c1, c2 = st.columns(2)
    with c1:
        field("text", "Dirección del inmueble", "direccion", "", max_chars=150,
              placeholder="CARRERA 3C # 1 - 65")
        field("text", "Municipio", "municipio", "La Estrella", max_chars=60)
        field("text", "Barrio o sector", "barrio", "", max_chars=80)
    with c2:
        field("select", "Tipo de inmueble", "tipo", TIPOS[0], options=TIPOS)
        field("select", "Estrato", "estrato", 3, options=[1, 2, 3, 4, 5, 6])
        if st.button("Ubicar en el mapa"):
            try:
                loc = MS.geocodificar(d.get("direccion", ""), d.get("municipio", ""))
                if loc:
                    d["lat"], d["lon"] = loc
                else:
                    st.warning("No se encontró la dirección. Puede continuar y registrar el punto manualmente.")
            except Exception:
                st.warning("El servicio de geocodificación no está disponible en este momento.")
    if d.get("lat") and d.get("lon"):
        st.map(pd.DataFrame({"lat": [d["lat"]], "lon": [d["lon"]]}), zoom=15)


def v_ubicacion(d):
    d["direccion"], err = V.validate_direccion(d.get("direccion"))
    errors = [err] if err else []
    if not d.get("municipio"):
        errors.append("Indique el municipio.")
    return errors


# ---------- Paso 5: características ----------
def s_caracteristicas(d):
    c1, c2, c3 = st.columns(3)
    with c1:
        field("num", "Área del lote según ficha catastral (m²)", "area_lote", 0.0,
              min_value=0.0, step=0.5, format="%.2f")
        field("num", "Antigüedad (años)", "antiguedad", 0, min_value=0, max_value=150, step=1)
        field("num", "Habitaciones", "habitaciones", 0, min_value=0, max_value=30, step=1)
    with c2:
        field("num", "Área adicional: antejardín u otra (m²)", "area_antejardin", 0.0,
              min_value=0.0, step=0.5, format="%.2f")
        field("num", "Área construida (m²)", "area_construida", 0.0,
              min_value=0.0, step=0.5, format="%.2f")
        field("num", "Baños", "banos", 0, min_value=0, max_value=30, step=1)
    with c3:
        field("num", "Niveles", "niveles", 1, min_value=1, max_value=12, step=1)
        total = (d.get("area_lote") or 0) + (d.get("area_antejardin") or 0)
        C.kpi("Área total del lote", f"{total:,.2f} m²")


def v_caracteristicas(d):
    errors = []
    for name, label in (("area_lote", "El área del lote"), ("area_construida", "El área construida")):
        if (d.get(name) or 0) <= 0:
            errors.append(f"{label} debe ser mayor que cero.")
    return errors


# ---------- Paso 6: acabados y estado ----------
def s_acabados(d):
    c1, c2 = st.columns(2)
    with c1:
        field("select", "Estado de conservación", "estado", "Bueno", options=ESTADOS)
        field("text", "Estructura", "estructura", "Tradicional aporticada", max_chars=120)
    with c2:
        field("area", "Acabados y descripción por niveles", "acabados", "", height=170,
              placeholder="Pisos, muros, cocina, baños, carpintería, ventanería…")


def v_acabados(d):
    return [] if len((d.get("acabados") or "").strip()) >= 10 else [
        "Describa los acabados (mínimo 10 caracteres)."
    ]


# ---------- Paso 7: servicios, entorno y POT ----------
def s_servicios(d):
    field("multi", "Servicios públicos disponibles", "servicios", ["Agua", "Energía"], options=SERVICIOS)
    field("area", "Transporte y vías de acceso", "transporte", "", height=80)

    if st.button("Redactar entorno con Claude"):
        try:
            st.session_state["f_entorno"] = ClaudeAssistant().redactar_entorno(datos_tecnicos(d))
        except AIUnavailable as exc:
            st.warning(str(exc))
        except Exception:
            st.error("No fue posible contactar al servicio de IA. Intente de nuevo.")
    field("area", "Descripción del entorno y sector", "entorno", "", height=150)

    c1, c2, c3 = st.columns(3)
    with c1:
        field("text", "Tratamiento POT", "pot_tratamiento", "Renovación urbana", max_chars=80)
    with c2:
        field("text", "Densidad", "pot_densidad", "", max_chars=80)
    with c3:
        field("text", "Uso del suelo", "uso", "Residencial", max_chars=80)


def v_servicios(d):
    return [] if len((d.get("entorno") or "").strip()) >= 20 else [
        "Describa el entorno del inmueble (mínimo 20 caracteres)."
    ]


# ---------- Paso 8: testigos de mercado ----------
def s_testigos(d):
    st.caption("Registre transacciones, ofertas o avalúos comparables. Factores: 1,000 = sin ajuste.")
    ver = st.session_state.setdefault("testigos_v", 0)
    base_key = f"base_testigos_{ver}"
    if base_key not in st.session_state:
        st.session_state[base_key] = pd.DataFrame(d.get("testigos") or [], columns=TESTIGO_COLS)
    edited = st.data_editor(
        st.session_state[base_key],
        key=f"f_testigos_{ver}",
        num_rows="dynamic",
        column_config=TESTIGO_CFG,
        hide_index=True,
    )
    d["testigos"] = [
        {k: (None if pd.isna(v) else v) for k, v in row.items()}
        for row in edited.to_dict("records")
    ]
    testigos, errs = to_testigos(d["testigos"])
    if testigos:
        vals = [valor_unitario_ajustado(t) for t in testigos]
        c1, c2, c3 = st.columns(3)
        with c1:
            C.kpi("Testigos válidos", str(len(testigos)))
        with c2:
            C.kpi("Valor m² ajustado (prom.)", C.fmt_cop(statistics.mean(vals)))
        with c3:
            C.kpi("Coef. de variación", f"{coeficiente_variacion(vals):.2f} %")
    for e in errs:
        st.warning(e)


def to_testigos(rows: list[dict]) -> tuple[list[Testigo], list[str]]:
    out, errors = [], []
    for i, r in enumerate(rows, start=1):
        precio, area = _f(r.get("precio")), _f(r.get("area_lote"))
        if precio is None and area is None:
            continue
        try:
            out.append(Testigo(
                fuente=str(r.get("fuente") or "Sin fuente")[:80],
                direccion=str(r.get("direccion") or "")[:150],
                precio=precio or 0.0,
                area_lote=area or 0.0,
                area_construida=_f(r.get("area_construida"), 0.0),
                factor_forma_pago=_f(r.get("factor_forma_pago"), 1.0),
                factor_tiempo=_f(r.get("factor_tiempo"), 1.0),
                factor_tamano=_f(r.get("factor_tamano"), 1.0),
                factor_conservacion=_f(r.get("factor_conservacion"), 1.0),
                descuento_comercializacion=_f(r.get("descuento"), 0.0) / 100,
            ))
        except ValueError as exc:
            errors.append(f"Fila {i}: {exc}")
    return out, errors


def v_testigos(d):
    testigos, errs = to_testigos(d.get("testigos") or [])
    if errs:
        return errs
    if not testigos:
        return ["Registre al menos un testigo de mercado."]
    return []


# ---------- Paso 9: investigación web e IA ----------
def s_mercado(d):
    st.caption("Búsqueda en portales inmobiliarios con Claude. Las fuentes deben verificarse antes de usarse como testigos.")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Buscar oferta comparable en la web", type="primary"):
            with st.spinner("Buscando en portales inmobiliarios…"):
                try:
                    d["web"] = MS.buscar_oferta(
                        get_client(), settings.claude_model,
                        tipo=d.get("tipo", ""), municipio=d.get("municipio", ""),
                        barrio=d.get("barrio", ""), direccion=d.get("direccion", ""),
                        area_m2=(d.get("area_lote") or 0) + (d.get("area_antejardin") or 0),
                    )
                    security.audit("web_search", _user(), municipio=d.get("municipio"), n=len(d["web"]))
                except AIUnavailable as exc:
                    st.warning(str(exc))
                except Exception:
                    st.error("No fue posible completar la búsqueda. Intente de nuevo.")
    with c2:
        if st.button("Agregar resultados con precio y área a testigos"):
            nuevos = []
            for item in d.get("web") or []:
                precio, area = _f(item.get("precio_cop")), _f(item.get("area_lote_m2"))
                if precio and area:
                    nuevos.append({
                        "fuente": f"Web · {item.get('fuente') or 'portal'}"[:80],
                        "direccion": str(item.get("direccion") or "")[:150],
                        "precio": precio, "area_lote": area,
                        "area_construida": _f(item.get("area_construida_m2"), 0.0),
                        "factor_forma_pago": 1.0, "factor_tiempo": 1.0, "factor_tamano": 1.0,
                        "factor_conservacion": 1.0, "descuento": 0.0,
                    })
            if nuevos:
                d["testigos"] = (d.get("testigos") or []) + nuevos
                st.session_state.testigos_v = st.session_state.get("testigos_v", 0) + 1
                st.rerun()
            else:
                st.info("No hay resultados con precio y área para agregar.")

    web = d.get("web") or []
    if web:
        st.dataframe(
            pd.DataFrame(web),
            hide_index=True,
            column_config={"url": st.column_config.LinkColumn("Enlace")},
        )
    else:
        st.info("Sin resultados todavía. Ejecute la búsqueda o ingrese testigos manualmente.")

    if st.button("Analizar mercado con Claude"):
        try:
            with st.spinner("Claude está analizando los testigos…"):
                d["mercado_texto"] = ClaudeAssistant().consultar(
                    "Evalúe la homogeneidad de los testigos, identifique atípicos y sugiera el "
                    "tratamiento de homologación del mercado en esta zona.", datos_tecnicos(d))
        except AIUnavailable as exc:
            st.warning(str(exc))
        except Exception:
            st.error("No fue posible completar el análisis.")
    if d.get("mercado_texto"):
        st.markdown(d["mercado_texto"])


# ---------- Paso 10: cálculo ----------
def _calcular(d) -> tuple[dict | None, list[str]]:
    testigos, errs = to_testigos(d.get("testigos") or [])
    if errs:
        return None, errs
    if not testigos:
        return None, ["Agregue al menos un testigo de mercado."]
    try:
        res = calcular_avaluo(
            area_lote=(d.get("area_lote") or 0) + (d.get("area_antejardin") or 0),
            area_construida=d.get("area_construida") or 0.0,
            edad_anios=d.get("antiguedad") or 0,
            estado=d.get("estado", "Bueno"),
            testigos=testigos,
            costo_m2_construccion=d.get("costo_m2") or 0.0,
            criterio=d.get("criterio", "comparativo"),
            fecha=d.get("fecha") if isinstance(d.get("fecha"), date) else date.today(),
        )
        return asdict(res), []
    except ValueError as exc:
        return None, [str(exc)]


def s_calculo(d):
    c1, c2 = st.columns(2)
    with c1:
        field("num", "Costo de reposición de construcción (COP/m²)", "costo_m2", 1_500_000.0,
              min_value=0.0, step=10_000.0, format="%.0f",
              help="Costo de reposición a nuevo por m², según tabla vigente. Verifique antes de firmar.")
    with c2:
        field("select", "Criterio de valor final", "criterio", "comparativo",
              options=list(CRITERIOS), format_func=lambda k: CRITERIOS[k])

    res, errs = _calcular(d)
    d["resultado"] = res
    for e in errs:
        st.warning(e)
    if not res:
        return

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        C.kpi("Valor comercial", C.fmt_cop(res["valor_final"]))
    with k2:
        C.kpi("Valor m² terreno", C.fmt_cop(res["valor_m2_terreno"]))
    with k3:
        C.kpi("Coef. variación", f"{res['coef_variacion']:.2f} %")
    with k4:
        C.kpi("Vigencia hasta", res["vigencia_hasta"])
    for m in res["mensajes"]:
        st.warning(m)

    st.table(pd.DataFrame([
        ("Valor del terreno", C.fmt_cop(res["valor_terreno"])),
        ("Costo de reposición a nuevo", C.fmt_cop(res["valor_reposicion_nuevo"])),
        ("Depreciación", f"{res['depreciacion'] * 100:.1f} %"),
        ("Construcción neta", C.fmt_cop(res["valor_construccion"])),
        ("Valor por método comparativo", C.fmt_cop(res["valor_comparativo"])),
        ("Valor por costo de reposición", C.fmt_cop(res["valor_costo"])),
    ], columns=["Concepto", "Valor"]).set_index("Concepto"))

    if st.button("Revisión técnica con Claude"):
        try:
            with st.spinner("Revisando el avalúo…"):
                st.markdown(ClaudeAssistant().revisar_avaluo(datos_tecnicos(d)))
        except AIUnavailable as exc:
            st.warning(str(exc))
        except Exception:
            st.error("No fue posible completar la revisión.")


def v_calculo(d):
    res, errs = _calcular(d)
    d["resultado"] = res
    if errs:
        return errs
    return [m for m in res["mensajes"] if "Se requieren" in m]


# ---------- Paso 11: imágenes ----------
def s_imagenes(d):
    user = _user()
    imgs = d.setdefault("imagenes", [])
    files = st.file_uploader(
        "Fotografías del inmueble (JPG, PNG o WEBP · máx. 10 MB c/u)",
        type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True,
    )
    known = {i["name"] for i in imgs}
    for f in files or []:
        if f.name in known:
            continue
        data = f.getvalue()
        try:
            IMG.validate_upload(data, settings.max_upload_mb)
            png = IMG.to_png(IMG.load_clean(data))
        except IMG.ImageError as exc:
            st.error(f"{f.name}: {exc}")
            known.add(f.name)
            continue
        imgs.append({"name": f.name, "original": png, "edited": png})
        known.add(f.name)
        security.audit("image_upload", user, bytes=len(data))

    if not imgs:
        st.info("Suba fotografías para incluirlas como anexo del informe.")
        return

    nombres = [i["name"] for i in imgs]
    sel = st.selectbox("Imagen a editar", nombres, key="img_sel")
    item = imgs[nombres.index(sel)]
    k = lambda s: f"img_{sel}_{s}"  # noqa: E731

    left, right = st.columns([1, 2])
    with left:
        rot = st.selectbox("Rotación", [0, 90, 180, 270], format_func=lambda x: f"{x}°", key=k("rot"))
        flip = st.toggle("Reflejar horizontal", key=k("flip"))
        gris = st.toggle("Escala de grises", key=k("gris"))
        brillo = st.slider("Brillo", 0.5, 1.5, 1.0, 0.05, key=k("br"))
        contraste = st.slider("Contraste", 0.5, 1.5, 1.0, 0.05, key=k("ct"))
        nitidez = st.slider("Nitidez", 0.0, 2.0, 1.0, 0.1, key=k("nt"))
        cl = st.slider("Recorte izquierda %", 0, 40, 0, key=k("cl"))
        ct = st.slider("Recorte superior %", 0, 40, 0, key=k("ct2"))
        cr = st.slider("Recorte derecha %", 0, 40, 0, key=k("cr"))
        cb = st.slider("Recorte inferior %", 0, 40, 0, key=k("cb"))
    with right:
        try:
            prev = IMG.apply_edits(
                IMG.open_bytes(item["original"]), rotate=rot, flip_h=flip,
                crop=(cl / 100, ct / 100, 1 - cr / 100, 1 - cb / 100),
                brightness=brillo, contrast=contraste, sharpness=nitidez, grayscale=gris,
            )
            st.image(prev, caption=sel)
        except IMG.ImageError as exc:
            st.error(str(exc))
            prev = None
        b1, b2, b3 = st.columns(3)
        if prev is not None and b1.button("Guardar edición"):
            item["edited"] = IMG.to_png(prev)
            st.success("Edición guardada en el anexo.")
        if b2.button("Restaurar original"):
            item["edited"] = item["original"]
            st.rerun()
        if b3.button("Eliminar imagen"):
            imgs.remove(item)
            st.rerun()


# ---------- Paso 12: informe y registro ----------
def s_informe(d):
    c1, c2 = st.columns(2)
    with c1:
        field("text", "Nombre del avaluador", "avaluador", "", max_chars=120)
        field("text", "Registro Nacional de Avaluadores (RNA)", "rna", "", max_chars=20)
        field("date", "Fecha del avalúo", "fecha", date.today())
    with c2:
        field("area", "Títulos y documentos consultados", "soportes",
              "Certificado de tradición y libertad; escritura pública; ficha catastral.", height=140)

    res = d.get("resultado")
    if res:
        C.kpi("Valor comercial del avalúo", C.fmt_cop(res["valor_final"]))

    st.divider()
    b1, b2 = st.columns(2)
    _clean_identifiers(d)
    images = [i["edited"] for i in d.get("imagenes", [])]
    if res and security.has_permission(_role(), "export"):
        report_bytes = build_docx(_payload(d), res, images)
        b1.download_button(
            "Descargar informe (.docx)", data=report_bytes,
            file_name=f"avaluo_{d.get('matricula', 'sin-matricula')}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    if res and security.has_permission(_role(), "create"):
        if b2.button("Guardar en registro seguro", type="primary"):
            avaluo_id = _repo().save(_user(), _payload(d))
            security.audit("avaluo_saved", _user(), id=avaluo_id, matricula=d.get("matricula"))
            st.success(f"Avalúo guardado. Identificador: {avaluo_id}")


def v_informe(d):
    errors = []
    if not (d.get("avaluador") or "").strip():
        errors.append("Indique el nombre del avaluador.")
    if not (d.get("rna") or "").strip():
        errors.append("Indique el número de registro RNA.")
    if not d.get("resultado"):
        errors.append("Complete el cálculo del avalúo antes de generar el informe.")
    return errors


def _payload(d: dict) -> dict:
    """Copia serializable del borrador, sin imágenes ni resultados de búsqueda."""
    raw = {k: v for k, v in d.items() if k not in ("imagenes", "web")}
    return json.loads(json.dumps(raw, default=str))


# ---------- Navegación ----------
WIZARD = [
    ("Propietario", s_propietario, v_propietario),
    ("Cédula", s_cedula, v_cedula),
    ("Matrícula inmobiliaria", s_matricula, v_matricula),
    ("Ubicación del inmueble", s_ubicacion, v_ubicacion),
    ("Características físicas", s_caracteristicas, v_caracteristicas),
    ("Acabados y estado", s_acabados, v_acabados),
    ("Servicios, entorno y POT", s_servicios, v_servicios),
    ("Testigos de mercado", s_testigos, v_testigos),
    ("Investigación web e IA", s_mercado, lambda d: []),
    ("Cálculo del avalúo", s_calculo, v_calculo),
    ("Imágenes", s_imagenes, lambda d: []),
    ("Informe y registro", s_informe, v_informe),
]


def reset_draft() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(("f_", "base_testigos_", "img_")):
            del st.session_state[key]
    st.session_state.draft = {}
    st.session_state.step = 0
    st.session_state.testigos_v = 0


def render_wizard() -> None:
    d = _d()
    i = st.session_state.step
    total = len(WIZARD)
    title, render, validate = WIZARD[i]
    C.step_header(i + 1, total, title)
    render(d)

    st.divider()
    left, _, right = st.columns([1, 2, 1])
    if left.button("← Anterior", disabled=i == 0):
        st.session_state.step = i - 1
        st.rerun()
    if i < total - 1 and right.button("Siguiente →", type="primary"):
        errors = validate(d)
        if errors:
            for e in errors:
                st.error(e)
        else:
            st.session_state.step = i + 1
            st.rerun()
