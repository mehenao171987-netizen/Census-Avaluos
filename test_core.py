import sqlite3
from dataclasses import asdict
from datetime import date
from io import BytesIO

import pytest
from cryptography.fernet import Fernet
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from core import security
from core import validators as V
from core.models import Testigo
from core.repository import Repository
from core.valuation import calcular_avaluo, depreciacion, valor_en_letras
from services import image_service as IMG
from services.market_search import parse_json_array
from services.report import build_docx


@pytest.fixture(autouse=True)
def secrets_env(monkeypatch):
    monkeypatch.setenv("CENSUS_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("CENSUS_INDEX_KEY", "k" * 64)


def _t(precio=100_000_000, area=100, **kw):
    return Testigo(fuente="Testigo", direccion="Calle 1", precio=precio, area_lote=area, **kw)


# ---------- Validación ----------
def test_cedula_valida_y_normaliza():
    assert V.validate_cedula("71.683.719") == ("71683719", None)
    assert V.validate_cedula("12ab")[1] is not None


def test_matricula_formato_orip():
    assert V.validate_matricula("001400729") == ("001-400729", None)
    assert V.validate_matricula("001-400729") == ("001-400729", None)
    assert V.validate_matricula("1-2")[1] is not None


def test_nombre_requiere_nombre_y_apellido():
    assert V.validate_nombre("carlos mario arango tobón") == ("CARLOS MARIO ARANGO TOBÓN", None)
    assert V.validate_nombre("Carlos")[1] is not None


def test_direccion_rechaza_html():
    assert V.validate_direccion("Carrera 3C # 1 - 65")[1] is None
    assert V.validate_direccion("<script>alert(1)</script>")[1] is not None


# ---------- Seguridad ----------
def test_password_hash_roundtrip():
    h = security.hash_password("Clave-Segura-123")
    assert security.verify_password("Clave-Segura-123", h)
    assert not security.verify_password("otra", h)
    assert not security.verify_password("x", "basura")


def test_bloqueo_tras_intentos_fallidos():
    state = {}
    for _ in range(3):
        security.register_failure(state, now=1000.0, max_attempts=3, lockout_minutes=15)
    assert security.is_locked(state, now=1001.0)
    assert not security.is_locked(state, now=1000.0 + 16 * 60)


def test_cifrado_roundtrip_y_mascara():
    token = security.encrypt("71683719")
    assert "71683719" not in token
    assert security.decrypt(token) == "71683719"
    assert security.mask("71683719") == "•••••719"


def test_roles():
    assert security.has_permission("revisor", "export")
    assert not security.has_permission("revisor", "create")


# ---------- Motor valuatorio ----------
def test_cv_cero_con_testigos_iguales():
    ts = [_t() for _ in range(5)]
    r = calcular_avaluo(area_lote=50, area_construida=0, edad_anios=0, estado="Bueno",
                        testigos=ts, costo_m2_construccion=0, fecha=date(2026, 1, 1))
    assert r.coef_variacion == 0
    assert r.cumple_minimo and r.cumple_cv
    assert r.valor_final == 50_000_000
    assert r.vigencia_hasta == "2027-01-01"


def test_minimo_de_testigos():
    r = calcular_avaluo(area_lote=50, area_construida=0, edad_anios=0, estado="Bueno",
                        testigos=[_t(), _t()], costo_m2_construccion=0)
    assert not r.cumple_minimo
    assert any("testigos" in m for m in r.mensajes)


def test_factores_de_homologacion():
    t = _t(precio=100_000_000, area=100, descuento_comercializacion=0.05)
    r = calcular_avaluo(area_lote=100, area_construida=0, edad_anios=0, estado="Bueno",
                        testigos=[t] * 5, costo_m2_construccion=0)
    assert r.valor_m2_terreno == pytest.approx(950_000, rel=1e-6)


def test_depreciacion_con_tope():
    assert depreciacion(500, "Malo") == pytest.approx(0.6)
    assert depreciacion(0, "Bueno") == 0


def test_valor_en_letras_como_en_el_formato_original():
    assert valor_en_letras(251092962).startswith("DOSCIENTOS CINCUENTA Y UN MILLONES NOVENTA Y DOS MIL")


def test_descuento_fuera_de_rango():
    with pytest.raises(ValueError):
        _t(descuento_comercializacion=0.10)


def test_criterio_mayor_valor():
    ts = [_t() for _ in range(5)]
    comp = calcular_avaluo(area_lote=50, area_construida=100, edad_anios=0, estado="Bueno",
                           testigos=ts, costo_m2_construccion=1_000_000, criterio="comparativo")
    mayor = calcular_avaluo(area_lote=50, area_construida=100, edad_anios=0, estado="Bueno",
                            testigos=ts, costo_m2_construccion=1_000_000, criterio="mayor_valor")
    assert mayor.valor_final >= comp.valor_final


# ---------- IA y búsqueda ----------
def test_parse_json_array_tolerante():
    txt = 'Resultados:\n[{"fuente":"Finca Raíz","precio_cop":250000000,"extra":1}]\nFin.'
    data = parse_json_array(txt)
    assert data[0]["fuente"] == "Finca Raíz"
    assert "extra" not in data[0]
    assert parse_json_array("sin json") == []


# ---------- Imágenes ----------
def _png_bytes(with_meta=False) -> bytes:
    img = Image.new("RGB", (120, 80), (200, 30, 30))
    buf = BytesIO()
    meta = PngInfo()
    if with_meta:
        meta.add_text("Software", "secreto-gps-12.3")
    img.save(buf, "PNG", pnginfo=meta)
    return buf.getvalue()


def test_validacion_de_imagen():
    assert IMG.validate_upload(_png_bytes(), 10) == "PNG"
    with pytest.raises(IMG.ImageError):
        IMG.validate_upload(b"<html>no soy imagen</html>", 10)


def test_metadatos_eliminados():
    clean = IMG.load_clean(_png_bytes(with_meta=True))
    assert "Software" not in clean.info


def test_edicion_de_imagen():
    out = IMG.apply_edits(IMG.open_bytes(_png_bytes()), rotate=90, crop=(0, 0, 0.5, 1), grayscale=True)
    assert out.size == (40, 120)


# ---------- Persistencia e informe ----------
def test_repositorio_guarda_cifrado(tmp_path):
    repo = Repository(tmp_path / "t.db")
    aid = repo.save("admin", {"nombre": "ANA PÉREZ GÓMEZ", "cedula": "12345678", "matricula": "001-1"})
    assert repo.get(aid)["nombre"] == "ANA PÉREZ GÓMEZ"
    assert len(repo.find_by_cedula("12345678")) == 1
    with sqlite3.connect(tmp_path / "t.db") as c:
        blob = c.execute("SELECT payload_enc FROM avaluos").fetchone()[0]
    assert "ANA PÉREZ" not in blob


def test_informe_docx_se_genera():
    ts = [_t() for _ in range(5)]
    res = asdict(calcular_avaluo(area_lote=48.94, area_construida=82.02, edad_anios=30,
                                 estado="Bueno", testigos=ts, costo_m2_construccion=1_500_000,
                                 fecha=date(2026, 1, 1)))
    data = build_docx({"nombre": "X", "cedula": "1", "matricula": "001-1", "avaluador": "Y", "rna": "3939",
                       "fecha": "2026-01-01", "tipo": "Casa"}, res, [_png_bytes()])
    assert data[:2] == b"PK"
