# -*- coding: utf-8 -*-
"""Tabla editable (tipo planilla): preparación de datos, configuración de columnas por tipo y
traducción de las ediciones de la grilla a cambios con «antes» y «después».

La grilla trabaja sobre la hoja CRUDA en texto canónico (utils/storage.py), nunca sobre la vista
transformada de lectura: así guardar una celda no escribe texto retocado. Los cambios se calculan
SOLO a partir de las celdas que Streamlit marca como editadas (`edited_rows`), no comparando
columnas completas, para que la conversión de tipos (casillas, listas) no genere diferencias falsas.
"""
from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from utils import completitud
from utils import schema as S
from utils.repo import Cambio

COL_COMPLETITUD = "completitud"          # columna calculada, solo lectura (no se guarda)


def _lista(valor) -> list[str]:
    return S.dividir_etiquetas(valor)


def opciones_para_tabla(opciones: dict[str, list[str]], base: pd.DataFrame, libro: pd.DataFrame | None = None) -> dict[str, list[str]]:
    """Opciones que ofrece la tabla en cada columna de categorías: las del campo + los códigos especiales
    («No aplica», «No especificado») que el libro de códigos admite o que ya usa esa columna.

    Es la lista de referencia tanto de los desplegables como de la validación al guardar.
    """
    texto_libro = {}
    if libro is not None and len(libro):
        texto_libro = dict(zip(libro["columna"], libro["opciones_respuesta"]))
    final: dict[str, list[str]] = {}
    for c in S.CAMPOS:
        ops = opciones.get(c.key)
        if c.tipo not in (S.OPCION, S.ETIQUETAS) or not ops:
            continue
        ops = list(ops)
        if not c.variable:
            if c.key in base.columns:
                presentes = {p.casefold() for v in base[c.key] for p in (_lista(v) if c.tipo == S.ETIQUETAS else [v])}
            else:
                presentes = set()
            for cod in S.CODIGOS_ESPECIALES:
                if cod not in ops and (cod.casefold() in presentes or f"'{cod}'" in texto_libro.get(c.key, "")):
                    ops.append(cod)
        final[c.key] = ops
    return final


def preparar_df(base: pd.DataFrame, opciones: dict[str, list[str]]) -> pd.DataFrame:
    """DataFrame para `st.data_editor`: índice = id_evento, mismo orden que `base`.

    - BOOLEANO -> bool (casilla).  - OPCION con lista -> None si está vacío (lista desplegable).
    - ETIQUETAS con lista -> lista de etiquetas (selección múltiple).  - + columna de completitud calculada.
    """
    df = base.copy()
    df.index = df["id_evento"]
    df.index.name = "ID"
    for c in S.CAMPOS:
        if c.key not in df.columns:
            continue
        if c.tipo == S.BOOLEANO:
            df[c.key] = df[c.key].str.strip().str.lower().isin(["true", "1", "sí", "si"])
        elif c.tipo == S.OPCION and opciones.get(c.key):
            df[c.key] = df[c.key].where(df[c.key] != "", None)
        elif c.tipo == S.ETIQUETAS and opciones.get(c.key):
            df[c.key] = df[c.key].map(_lista)
    df[COL_COMPLETITUD] = [completitud.calcular(r).pct for r in base.to_dict("records")]
    return df


def _ayuda(c: S.Campo, libro: pd.DataFrame | None) -> str | None:
    """Texto del tooltip de la columna: su descripción y las opciones, tal como están en el libro de códigos."""
    partes = []
    if c.ayuda:
        partes.append(c.ayuda)
    if libro is not None and len(libro):
        fila = libro[libro["columna"] == c.key]
        if len(fila):
            r = fila.iloc[0]
            if r["descripcion"] and r["descripcion"] != c.label and r["descripcion"] not in partes:
                partes.append(r["descripcion"])
            if r["opciones_respuesta"]:
                partes.append(f"**Libro de códigos:** {r['opciones_respuesta'][:300]}")
    return "\n\n".join(partes) or None


def column_config(opciones: dict[str, list[str]], libro: pd.DataFrame | None = None) -> dict:
    """Configuración de columnas según el tipo de cada campo del registro.

    Las columnas con categorías (opción única o varias) se eligen de una lista: no se escriben a mano.
    Solo los vocabularios abiertos (metodologías, instituciones…) admiten escribir una opción nueva, igual
    que en la ficha; las listas cerradas (categorías, ejes, atributos, variables propias) no.
    """
    from utils.formularios import es_cerrado   # import perezoso: formularios depende de Streamlit

    cfg: dict = {COL_COMPLETITUD: st.column_config.ProgressColumn(
        "Completitud", min_value=0, max_value=100, format="%d %%", width="small",
        help="% de los campos clave con información (solo lectura).")}
    for c in S.CAMPOS:
        ayuda = _ayuda(c, libro)
        ops = opciones.get(c.key)
        if c.tipo == S.BOOLEANO:
            cfg[c.key] = st.column_config.CheckboxColumn(c.label, help=ayuda)
        elif c.tipo == S.OPCION and ops:
            cfg[c.key] = st.column_config.SelectboxColumn(c.label, options=ops, help=ayuda, width="medium")
        elif c.tipo == S.ETIQUETAS and ops:
            cfg[c.key] = st.column_config.MultiselectColumn(c.label, options=ops, help=ayuda, width="large",
                                                            accept_new_options=not es_cerrado(c))
        elif c.tipo in (S.URL, S.IMAGEN_URL):
            cfg[c.key] = st.column_config.LinkColumn(c.label, help=ayuda, width="medium")
        elif c.tipo == S.TEXTO_LARGO:
            cfg[c.key] = st.column_config.TextColumn(c.label, help=ayuda, width="large")
        elif c.key == "titulo":
            cfg[c.key] = st.column_config.TextColumn(c.label, help=ayuda, width="large", pinned=True)
        elif c.key in S.PATRONES_CODIGO:
            patron, explicacion = S.PATRONES_CODIGO[c.key]
            cfg[c.key] = st.column_config.TextColumn(c.label, help=((ayuda or "") + f"\n\n**Formato:** {explicacion}").strip(),
                                                     width="large", validate=patron)
        else:
            cfg[c.key] = st.column_config.TextColumn(c.label, help=(ayuda or (
                "AAAA-MM-DD o «11 de julio de 2026»" if c.tipo == S.FECHA else
                "Varias etiquetas separadas por «;»" if c.tipo == S.ETIQUETAS else None)), width="medium")
    return cfg


def columnas_bloqueadas() -> list[str]:
    """Columnas que el usuario no edita (las completa el sistema) + la de completitud."""
    return [c.key for c in S.CAMPOS if not c.editable] + [COL_COMPLETITUD]


def _es_lista(valor) -> bool:
    return isinstance(valor, (list, tuple)) or (hasattr(valor, "tolist") and not isinstance(valor, (str, bytes)))


def texto_de_celda(valor) -> str:
    """Valor devuelto por la grilla -> texto canónico ('' si está vacío)."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    if _es_lista(valor):
        return S.unir_etiquetas(valor.tolist() if hasattr(valor, "tolist") else valor)
    if isinstance(valor, bool):
        return "True" if valor else "False"
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def cambios_desde_edicion(base: pd.DataFrame, edited_rows: dict) -> list[Cambio]:
    """Cambios (antes -> después) de las celdas editadas.

    `edited_rows`: {posición de la fila: {columna: valor nuevo}} tal como lo guarda st.data_editor.
    `base`: la hoja cruda con el MISMO orden que se le pasó a la grilla. Las celdas cuyo valor nuevo
    equivale al original (tras normalizar a texto) se descartan; las listas de etiquetas se comparan
    como listas (el separador con o sin espacio no cuenta como cambio).
    """
    ids = base["id_evento"].tolist()
    cambios: list[Cambio] = []
    for pos, celdas in edited_rows.items():
        pos = int(pos)
        if pos >= len(ids):
            continue
        ide = ids[pos]
        for col, nuevo in celdas.items():
            if col == COL_COMPLETITUD or col not in base.columns:
                continue
            antes = str(base.iloc[pos][col])
            despues = texto_de_celda(nuevo)
            igual = _lista(antes) == _lista(despues) if _es_lista(nuevo) else despues == antes
            if not igual:
                cambios.append(Cambio(ide, col, antes, despues))
    return cambios


def errores_de_codigos(cambios: list[Cambio], opciones: dict[str, list[str]]) -> dict[tuple[str, str], str]:
    """Cambios que no respetan el libro de códigos: {(id_evento, campo): explicación}.

    Una opción única debe ser una de las opciones; en una lista cerrada (categorías, ejes, atributos, variables
    propias) cada etiqueta nueva debe estar entre sus opciones; los campos con formato (p. ej. el enfoque de
    género) deben cumplirlo. Los valores que ya tenía la celda no se cuestionan.
    """
    from utils.formularios import es_cerrado   # import perezoso: formularios depende de Streamlit

    errores: dict[tuple[str, str], str] = {}
    for c in cambios:
        campo = S.CAMPO[c.campo]
        ops = opciones.get(c.campo)
        if c.campo in S.PATRONES_CODIGO and c.despues:
            patron, explicacion = S.PATRONES_CODIGO[c.campo]
            if not re.match(patron, c.despues):
                errores[(c.id_evento, c.campo)] = f"«{campo.label}»: {explicacion}"
        elif ops and campo.tipo == S.OPCION and c.despues and c.despues not in ops and c.despues != c.antes:
            vista = ", ".join(ops[:8]) + ("…" if len(ops) > 8 else "")
            errores[(c.id_evento, c.campo)] = f"«{campo.label}»: «{c.despues}» no es una de sus opciones ({vista})."
        elif ops and campo.tipo == S.ETIQUETAS and es_cerrado(campo):
            nuevas = [t for t in _lista(c.despues) if t not in _lista(c.antes) and t not in ops]
            if nuevas:
                errores[(c.id_evento, c.campo)] = f"«{campo.label}»: {', '.join('«' + t + '»' for t in nuevas)} no está(n) entre sus opciones."
    return errores
