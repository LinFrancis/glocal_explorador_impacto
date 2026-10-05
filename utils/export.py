# -*- coding: utf-8 -*-
"""Exportadores de noticias a Excel, Word y CSV, con columnas/campos a elección.

Pensado para el flujo de postulación a fondos/proyectos: se filtra en el Explorador, se marcan las
noticias relevantes y se descarga una ficha en Word (para pegar en una propuesta) y/o una planilla
Excel o CSV (para anexos). Los exportadores reciben el DataFrame de lectura (`load_noticias()`).
"""
from __future__ import annotations

import io
import re
from datetime import date
from pathlib import Path

import pandas as pd

from utils import schema as S
from utils.validation import a_texto

RAIZ = Path(__file__).resolve().parent.parent
LOGO_GLOCALMINDS_PNG = RAIZ / "images" / "logoGnaranja.png"
LOGO_FUNDACION_PNG = RAIZ / "images" / "logo_fundacion_glocal_oscuro.png"

# Campos derivados que no son columnas de Base_Datos pero sí se pueden exportar.
CAMPOS_DERIVADOS = {"anio": "Año", "pais": "País"}

# Plantillas de selección de columnas.
PRESET_POSTULACION = (
    "titulo", "anio", "pais", "lugar", "descripcion_catalogo", "categoria_macro", "categorias", "metodologia",
    "actores_normalizados", "eje_gcaa", "objetivo_gcaa", "atributos_resiliencia", "subatributos_resiliencia",
    "beneficiarios_directos", "beneficiarios_indirectos", "enfoque_genero", "url_noticia",
)
PRESET_MINIMO = ("titulo", "anio", "pais", "lugar", "url_noticia")
PRESET_ANALISIS = ("titulo", "anio", "pais", "categoria_macro", "categorias", "metodologia", "actores_normalizados",
                   "eje_gcaa", "atributos_resiliencia", "beneficiarios_directos", "enfoque_genero")
PRESETS = {"Postulación": PRESET_POSTULACION, "Mínimo": PRESET_MINIMO, "Análisis": PRESET_ANALISIS}

# Campos del Word (ficha) cuando se elige «información completa» (orden pensado para una propuesta).
FICHA_FIELDS = [
    ("Resumen", "descripcion_catalogo"), ("Categoría macro", "categoria_macro"),
    ("Categoría temática", "categorias"), ("Metodología de facilitación", "metodologia"),
    ("Actores institucionales", "actores_normalizados"), ("Eje GCAA (acción climática)", "eje_gcaa"),
    ("Objetivo GCAA", "objetivo_gcaa"), ("Atributo de resiliencia (CR2)", "atributos_resiliencia"),
    ("Sub-atributo de resiliencia", "subatributos_resiliencia"), ("Beneficiarios directos", "beneficiarios_directos"),
    ("Beneficiarios indirectos", "beneficiarios_indirectos"), ("Enfoque de género", "enfoque_genero"),
]
WORD_COMPLETO = ("titulo", "anio", "pais", "lugar") + tuple(k for _, k in FICHA_FIELDS) + ("url_noticia", "contenido_completo")
CAMPOS_PROYECTO = ("carpeta_proyecto", "documentos_proyecto")
# Columnas de la hoja «Resumen» del Excel completo.
EXCEL_RESUMEN = ("titulo", "anio", "pais", "lugar", "descripcion_catalogo", "categoria_macro", "categorias",
                 "metodologia", "actores_normalizados", "eje_gcaa", "objetivo_gcaa", "atributos_resiliencia",
                 "subatributos_resiliencia", "beneficiarios_directos", "beneficiarios_indirectos",
                 "enfoque_genero", "url_noticia", "contenido_completo")

_EMPTY = {"", "no aplica", "no especificado", "sin dato", "nan", "none"}
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")      # caracteres que Word/Excel no admiten


def etiqueta(key: str) -> str:
    return CAMPOS_DERIVADOS.get(key) or S.etiqueta(key)


def _con_extras(base: tuple[str, ...]) -> list[str]:
    """`base` con la carpeta del proyecto y las variables propias antes del enlace/texto (información completa)."""
    extras = list(CAMPOS_PROYECTO) + [c.key for c in S.CAMPOS if c.variable]
    antes = [k for k in base if k not in ("url_noticia", "contenido_completo")]
    return antes + extras + [k for k in base if k in ("url_noticia", "contenido_completo")]


def _txt(value, tipo: str | None = None) -> str:
    return _CONTROL.sub("", a_texto(value, tipo))


def _clean_multi(value) -> str:
    """'a;b ; c' -> 'a; b; c', quitando vacíos y marcadores de 'sin valor'."""
    raw = _txt(value)
    if not raw:
        return ""
    parts = [p.strip() for p in raw.split(";")]
    parts = [p for p in parts if p and p.lower() not in _EMPTY]
    return "; ".join(dict.fromkeys(parts))


def _valor(row, key: str) -> str:
    """Valor de un campo listo para exportar (etiquetas limpias, fechas ISO, año/país derivados)."""
    if key == "anio":
        return _anio(row)
    v = row.get(key)
    if key == "pais" or (key in S.CAMPO and S.CAMPO[key].tipo == S.ETIQUETAS):
        return _clean_multi(v)
    return _txt(v, S.CAMPO[key].tipo if key in S.CAMPO else None)


def _anio(row) -> str:
    for key in ("anio", "fecha_parsed", "fecha_publicacion"):
        v = row.get(key)
        if v is None or (isinstance(v, float) and pd.isna(v)) or type(v).__name__ == "NaTType":
            continue
        if key == "anio":
            try:
                return str(int(v))
            except (TypeError, ValueError):
                continue
        if key == "fecha_parsed":
            return str(pd.Timestamp(v).year)
        return _txt(v)
    return "s/f"


# ----------------------------------------------------------------------------- catálogo de campos
def catalogo_exportable(columnas_disponibles) -> list[tuple[str, str, str]]:
    """[(clave, etiqueta, grupo)] de los campos que se pueden exportar, agrupados y en orden."""
    disp = set(columnas_disponibles)
    salida = []
    for grupo in S.GRUPOS:
        for c in S.CAMPOS:
            if c.grupo == grupo and c.key in disp:
                salida.append((c.key, c.label, grupo))
        if grupo == S.G_IDENT:
            for k, lab in CAMPOS_DERIVADOS.items():
                if k in disp:
                    salida.append((k, lab, grupo))
    return salida


def columnas_validas(claves, columnas_disponibles) -> list[str]:
    disp = set(columnas_disponibles) | ({"anio"} if "anio" in columnas_disponibles else set())
    return [k for k in claves if k in disp]


# ----------------------------------------------------------------------------- Excel / CSV
def _ajustar_hoja(ws) -> None:
    ws.freeze_panes = "A2"
    for column_cells in ws.columns:
        width = min(60, max(12, max((len(str(c.value or "")) for c in column_cells[:40]), default=12) + 2))
        ws.column_dimensions[column_cells[0].column_letter].width = width


def tabla_exportable(rows: pd.DataFrame, columnas) -> pd.DataFrame:
    return pd.DataFrame({etiqueta(k): [_valor(r, k) for r in rows.to_dict("records")] for k in columnas})


def experiences_to_excel(rows: pd.DataFrame, columnas=None) -> bytes:
    """`columnas=None` -> información completa: hoja «Resumen» (columnas clave) + «Datos completos».
    Con `columnas` -> una sola hoja «Noticias» con exactamente esas columnas, en ese orden."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xls:
        if columnas is None:
            resumen = tabla_exportable(rows, columnas_validas(_con_extras(EXCEL_RESUMEN), rows.columns))
            resumen.to_excel(xls, sheet_name="Resumen", index=False)
            todas = [k for k in S.COLUMNAS if k in rows.columns]
            tabla_exportable(rows, todas).to_excel(xls, sheet_name="Datos completos", index=False)
        else:
            tabla_exportable(rows, columnas_validas(columnas, rows.columns)).to_excel(xls, sheet_name="Noticias", index=False)
        for sheet in xls.book.worksheets:
            _ajustar_hoja(sheet)
    return buf.getvalue()


def experiences_to_csv(rows: pd.DataFrame, columnas=None) -> bytes:
    cols = columnas_validas(columnas, rows.columns) if columnas is not None else [k for k in S.COLUMNAS if k in rows.columns]
    return tabla_exportable(rows, cols).to_csv(index=False).encode("utf-8-sig")


# ----------------------------------------------------------------------------- Word
def _agregar_logos(doc, alto_cm: float, centrado: bool, contenedor=None) -> bool:
    """Inserta los logos de ambas organizaciones. False si no hay ningún archivo de logo."""
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm

    logos = [p for p in (LOGO_GLOCALMINDS_PNG, LOGO_FUNDACION_PNG) if p.exists()]
    if not logos:
        return False
    destino = contenedor if contenedor is not None else doc
    par = destino.paragraphs[0] if contenedor is not None and destino.paragraphs else destino.add_paragraph()
    if centrado:
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for i, p in enumerate(logos):
        if i:
            par.add_run("      ")
        par.add_run().add_picture(str(p), height=Cm(alto_cm))
    return True


def experiences_to_word(rows: pd.DataFrame, contexto: str = "", campos=None, incluir_tabla: bool = True,
                        con_logos: bool = False) -> bytes:
    """Documento con una portada + una ficha por noticia.

    `campos=None` -> información completa. Con `campos` solo se incluyen esos campos (el título siempre).
    `con_logos`: portada con los logos de ambas organizaciones y encabezado con logos pequeños.
    """
    from docx import Document
    from docx.shared import Pt

    campos = _con_extras(WORD_COMPLETO) if campos is None else list(campos)
    elegidos = set(campos)
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)

    if con_logos:
        sec = doc.sections[0]
        sec.different_first_page_header_footer = True      # la portada lleva logos grandes; el resto, encabezado
        _agregar_logos(doc, 0.9, centrado=False, contenedor=sec.header)
        _agregar_logos(doc, 1.8, centrado=True)

    doc.add_heading("Experiencias seleccionadas — Catálogo Glocalminds / Fundación Glocal", level=0)
    p = doc.add_paragraph()
    p.add_run(f"{len(rows)} experiencia(s)  ·  Generado el {date.today().strftime('%d-%m-%Y')}").italic = True
    if contexto.strip():
        doc.add_paragraph(f"Contexto de la selección: {_CONTROL.sub('', contexto.strip())}")

    filas = rows.to_dict("records")
    if incluir_tabla:
        doc.add_heading("Resumen", level=1)
        cols_tabla = [("titulo", "Título")] + [(k, etiqueta(k)) for k in ("anio", "pais", "categoria_macro")
                                              if k in elegidos and (k in rows.columns or k == "anio")]
        table = doc.add_table(rows=1, cols=len(cols_tabla))
        table.style = "Light Grid Accent 1"
        for i, (_, lab) in enumerate(cols_tabla):
            table.rows[0].cells[i].text = lab
        for r in filas:
            cells = table.add_row().cells
            for i, (k, _) in enumerate(cols_tabla):
                cells[i].text = _valor(r, k) or "s/d"

    for r in filas:
        doc.add_page_break()
        doc.add_heading(_valor(r, "titulo") or "Sin título", level=1)
        meta = "  ·  ".join(x for x in (
            f"Año: {_valor(r, 'anio')}" if "anio" in elegidos else "",
            f"País: {_valor(r, 'pais')}" if "pais" in elegidos and _valor(r, "pais") else "",
            f"Lugar: {_valor(r, 'lugar')}" if "lugar" in elegidos and _valor(r, "lugar") else "",
        ) if x)
        if meta:
            doc.add_paragraph(meta).runs[0].italic = True

        for k in campos:
            if k in ("titulo", "anio", "pais", "lugar", "url_noticia", "contenido_completo") or k not in rows.columns:
                continue
            val = _valor(r, k)
            if not val:
                continue
            para = doc.add_paragraph()
            para.add_run(f"{etiqueta(k)}: ").bold = True
            para.add_run(val)

        if "url_noticia" in elegidos and _valor(r, "url_noticia"):
            para = doc.add_paragraph()
            para.add_run("Enlace: ").bold = True
            para.add_run(_valor(r, "url_noticia"))

        texto = _valor(r, "contenido_completo")
        if "contenido_completo" in elegidos and texto and texto.lower() != _valor(r, "descripcion_catalogo").lower():
            doc.add_heading("Texto completo", level=2)
            for bloque in texto.split("\n"):
                if bloque.strip():
                    doc.add_paragraph(bloque.strip())

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
