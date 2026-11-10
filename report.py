"""Generación del informe de avalúo en Word (.docx) siguiendo la estructura del formato original."""
from __future__ import annotations

from io import BytesIO

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

from config.settings import settings


def _cop(valor) -> str:
    try:
        return "$ " + f"{float(valor):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return str(valor or "—")


def _kv_table(doc, rows: list[tuple[str, str]]) -> None:
    table = doc.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    for key, value in rows:
        cells = table.add_row().cells
        cells[0].text = key
        cells[1].text = str(value if value not in (None, "") else "—")
        for run in cells[0].paragraphs[0].runs:
            run.bold = True


def build_docx(d: dict, res: dict, images: list[bytes]) -> bytes:
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10)
    for section in doc.sections:
        section.left_margin = section.right_margin = Inches(0.8)

    title = doc.add_heading("AVALÚO COMERCIAL", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = doc.add_paragraph(f"{d.get('tipo', '')} · {d.get('direccion', '')} · {d.get('municipio', '')}")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_heading("1. Objeto del avalúo", 1)
    doc.add_paragraph(
        "Determinar el valor comercial del inmueble en su estado actual, mediante el método comparativo "
        "de mercado y el método de reposición, con base en sus características físicas, jurídicas, "
        "el entorno y el comportamiento del mercado inmobiliario."
    )

    doc.add_heading("2. Datos generales", 1)
    _kv_table(doc, [
        ("Fecha", d.get("fecha")),
        ("Tipo de inmueble", d.get("tipo")),
        ("Dirección", d.get("direccion")),
        ("Municipio / barrio", f"{d.get('municipio', '')} / {d.get('barrio', '')}"),
        ("Matrícula inmobiliaria", d.get("matricula")),
        ("Solicitante", f"{d.get('nombre', '')} · C.C. {d.get('cedula', '')}"),
        ("Avaluador", f"{d.get('avaluador', '')} · RNA {d.get('rna', '')}"),
    ])

    doc.add_heading("3. Aspecto jurídico", 1)
    doc.add_paragraph(d.get("soportes") or "Documentos consultados: certificado de tradición y libertad.")

    doc.add_heading("4. Entorno y ubicación", 1)
    doc.add_paragraph(d.get("entorno") or "—")
    if d.get("transporte"):
        doc.add_paragraph(f"Transporte: {d['transporte']}")
    if d.get("servicios"):
        doc.add_paragraph("Servicios públicos: " + ", ".join(d["servicios"]) + ".")

    doc.add_heading("5. Descripción, acabados y estado de conservación", 1)
    _kv_table(doc, [
        ("Área del lote", f"{res['area_lote']:.2f} m²"),
        ("Área construida", f"{d.get('area_construida', 0)} m²"),
        ("Antigüedad", f"{d.get('antiguedad', 0)} años"),
        ("Estado de conservación", d.get("estado")),
        ("Estructura", d.get("estructura")),
    ])
    doc.add_paragraph(d.get("acabados") or "")

    doc.add_heading("6. Aspecto económico y normativo", 1)
    doc.add_paragraph(
        f"Plan de ordenamiento: tratamiento {d.get('pot_tratamiento') or '—'}; "
        f"densidad {d.get('pot_densidad') or '—'}; uso {d.get('uso') or '—'}."
    )
    if d.get("mercado_texto"):
        doc.add_paragraph(d["mercado_texto"])

    doc.add_heading("7. Metodología valuatoria", 1)
    doc.add_paragraph(
        "Método comparativo de mercado: homologación de testigos por forma de pago, época, tamaño, "
        "conservación y factor de comercialización (0 % a 5 %), y verificación del coeficiente de "
        f"variación frente al máximo de {settings.cv_max_percent} % (Resolución 620 de 2008). "
        "Método de reposición: costo de reposición a nuevo de la construcción, depreciado por edad y estado."
    )
    if res.get("detalle_testigos"):
        table = doc.add_table(rows=1, cols=3)
        table.style = "Table Grid"
        for cell, text in zip(table.rows[0].cells, ("Fuente", "Dirección", "Valor m² ajustado")):
            cell.text = text
        for t in res["detalle_testigos"]:
            cells = table.add_row().cells
            cells[0].text, cells[1].text, cells[2].text = t["fuente"], t["direccion"], _cop(t["valor_m2_ajustado"])
    doc.add_paragraph(f"Coeficiente de variación: {res['coef_variacion']:.2f} % (límite {settings.cv_max_percent} %).")

    doc.add_heading("8. Valor final", 1)
    _kv_table(doc, [
        ("Valor m² de terreno", _cop(res["valor_m2_terreno"])),
        ("Valor del terreno", _cop(res["valor_terreno"])),
        ("Costo de reposición a nuevo", _cop(res["valor_reposicion_nuevo"])),
        ("Depreciación aplicada", f"{res['depreciacion'] * 100:.1f} %"),
        ("Construcción neta", _cop(res["valor_construccion"])),
        ("Criterio de valoración", res["criterio"]),
    ])
    p = doc.add_paragraph()
    run = p.add_run(f"VALOR COMERCIAL: {_cop(res['valor_final'])}")
    run.bold = True
    run.font.size = Pt(13)
    doc.add_paragraph(res["valor_en_letras"])

    doc.add_heading("9. Vigencia", 1)
    doc.add_paragraph(
        f"El presente avalúo tiene vigencia hasta el {res['vigencia_hasta']}, siempre que las condiciones "
        "intrínsecas y extrínsecas que afectan el valor se conserven."
    )

    doc.add_heading("10. Certificación de imparcialidad", 1)
    doc.add_paragraph(
        "El avaluador certifica que los valores presentados son producto de métodos objetivos, "
        "sin influencia de intereses personales, y que no tiene interés directo ni indirecto en el inmueble."
    )

    doc.add_heading("11. Conclusiones y consideraciones", 1)
    doc.add_paragraph(
        "El valor comercial es el precio estimado de contado entre un comprador y un vendedor dispuestos, "
        "sin presión. El valor de negociación puede diferir del valor objetivo por factores subjetivos "
        "(plazos, tasas, urgencia de las partes). El avalúo no contempla aspectos jurídicos no informados, "
        "características geológicas ni la capacidad portante del terreno."
    )

    if images:
        doc.add_heading("Anexo fotográfico", 1)
        for img in images:
            doc.add_picture(BytesIO(img), width=Inches(5.8))

    doc.add_paragraph("\n\n__________________________")
    doc.add_paragraph(d.get("avaluador", ""))
    doc.add_paragraph(f"PERITO AVALUADOR · RNA {d.get('rna', '')}")

    doc.sections[0].footer.paragraphs[0].text = (
        f"Generado con {settings.app_name} · Desarrollado por {settings.company}"
    )
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()
