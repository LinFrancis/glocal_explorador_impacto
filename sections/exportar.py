# -*- coding: utf-8 -*-
"""Panel de exportación selectiva: qué noticias, qué información y en qué formato.

1. Noticias: solo mi selección / todas las filtradas / toda la base.
2. Información: completa, o solo las columnas que elijo (con plantillas).
3. Formato: Excel, Word (con logos opcionales) o CSV. El archivo se genera al hacer clic y la
   exportación queda registrada (quién, qué, cuándo) para poder repetirla desde el historial.
"""
from datetime import date

import pandas as pd
import streamlit as st

from utils import auth, export, repo, seleccion
from utils import schema as S
from utils.style import section_label

MIME = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "csv": "text/csv",
}
INFO_COMPLETA = "Información completa"
INFO_ELEGIR = "Solo las columnas que elijo"
K_HIST, K_INFO, K_CONTEXTO, K_LOGOS, K_TABLA = "exp_historias", "exp_info", "exp_contexto", "exp_logos", "exp_tabla"


def _k(grupo: str) -> str:
    return f"exp_cols_{grupo}"


def resumen_filtros(criterios: dict | None) -> str:
    """Texto corto de los criterios activos (para el registro de exportaciones)."""
    if not criterios:
        return ""
    partes = []
    if criterios.get("texto"):
        partes.append(f"texto={criterios['texto']}")
    for k, v in criterios.items():
        if k in ("texto", "fuzzy_umbral", "incluir_sin_fecha", "genero", "anios") or not v:
            continue
        partes.append(f"{k}={'|'.join(v)}")
    if criterios.get("genero") not in (None, "Todos"):
        partes.append(f"género={criterios['genero']}")
    if criterios.get("anios"):
        partes.append(f"años={criterios['anios'][0]}-{criterios['anios'][1]}")
    return "; ".join(partes)


def _aplicar_plantilla(claves: tuple[str, ...] | None, catalogo: list[tuple[str, str, str]]) -> None:
    """Callback de los botones de plantilla: marca las columnas de cada grupo."""
    for grupo in S.GRUPOS:
        del_grupo = [k for k, _, g in catalogo if g == grupo]
        st.session_state[_k(grupo)] = del_grupo if claves is None else [k for k in del_grupo if k in claves]


def _seleccion_de_columnas(catalogo: list[tuple[str, str, str]]) -> list[str]:
    """Dibuja los selectores por grupo y devuelve las columnas elegidas en el orden del registro."""
    etiquetas = {k: lab for k, lab, _ in catalogo}
    with st.container(horizontal=True):
        st.caption("Plantillas:")
        for nombre, claves in export.PRESETS.items():
            st.button(nombre, key=f"exp_preset_{nombre}", on_click=_aplicar_plantilla, args=(claves, catalogo),
                      type="secondary", width="content")
        st.button("Todas", key="exp_preset_todas", on_click=_aplicar_plantilla, args=(None, catalogo), width="content")
        st.button("Ninguna", key="exp_preset_ninguna", on_click=_aplicar_plantilla, args=((), catalogo), width="content")

    elegidas: set[str] = set()
    for grupo in S.GRUPOS:
        del_grupo = [k for k, _, g in catalogo if g == grupo]
        if not del_grupo:
            continue
        if _k(grupo) not in st.session_state:
            st.session_state[_k(grupo)] = [k for k in del_grupo if k in export.PRESET_POSTULACION]
        abierto = grupo in (S.G_IDENT, S.G_CLASIF)
        with st.expander(grupo, expanded=abierto):
            sel = st.multiselect(grupo, del_grupo, key=_k(grupo), format_func=lambda k: etiquetas[k],
                                 label_visibility="collapsed", placeholder="Elige las columnas de este grupo")
        elegidas.update(sel)
    return [k for k, _, _ in catalogo if k in elegidas]


def render(df_filtrado: pd.DataFrame, df_total: pd.DataFrame, criterios: dict | None) -> None:
    section_label("Exportar")
    usuario = auth.nombre_actual()
    existentes = list(df_total["id_evento"])
    ids_sel = seleccion.vigentes(existentes)
    ids_fil = list(df_filtrado["id_evento"])
    ids_todos = existentes

    # ---------------------------------------------------------------- 1. noticias
    opciones = {"seleccion": f"Mi selección ({len(ids_sel)})", "filtradas": f"Todas las filtradas ({len(ids_fil)})",
                "base": f"Toda la base ({len(ids_todos)})"}
    modo = st.segmented_control("¿Qué noticias incluir?", list(opciones), format_func=opciones.get,
                                default="seleccion" if ids_sel else "filtradas", key=K_HIST) or "filtradas"
    ids_export = {"seleccion": ids_sel, "filtradas": ids_fil, "base": ids_todos}[modo]
    if modo == "seleccion" and not ids_sel:
        st.info("Aún no seleccionaste noticias: marca «Incluir» en las tarjetas de arriba o usa los botones de selección.",
                icon=":material/checklist:")

    # ---------------------------------------------------------------- 2. información
    info = st.radio("¿Qué información incluir?", [INFO_COMPLETA, INFO_ELEGIR], horizontal=True, key=K_INFO)
    columnas = None
    if info == INFO_ELEGIR:
        catalogo = export.catalogo_exportable(df_total.columns)
        columnas = _seleccion_de_columnas(catalogo)
        st.caption(f"{len(columnas)} columna(s) elegida(s).")
    else:
        st.caption("Excel: hoja «Resumen» con las columnas clave y hoja «Datos completos» con todo. "
                   "Word: ficha completa por noticia, con texto completo.")

    # ---------------------------------------------------------------- 3. formato
    c1, c2 = st.columns([3, 2])
    contexto = c1.text_input("¿Para qué postulación es esta evidencia? (opcional, va en el encabezado del Word)",
                             placeholder="Ej.: Postulación a fondo de apoyo a comunidades educativas", key=K_CONTEXTO)
    with c2:
        con_logos = st.checkbox("Word con logos", value=True, key=K_LOGOS,
                                 help="Portada con los logos de Glocal Minds y Fundación Glocal, y encabezado con logos pequeños.")
        con_tabla = st.checkbox("Word con tabla resumen", value=True, key=K_TABLA,
                                 help="Tabla al inicio con título, año, país y categoría de cada noticia.")

    subset = df_total[df_total["id_evento"].isin(ids_export)]
    orden = {i: n for n, i in enumerate(ids_export)}
    subset = subset.assign(_o=subset["id_evento"].map(orden)).sort_values("_o").drop(columns="_o")
    fecha = date.today().strftime("%Y%m%d")
    sin_datos = subset.empty or (info == INFO_ELEGIR and not columnas)

    def generar(formato: str):
        def f():
            if formato == "xlsx":
                datos = export.experiences_to_excel(subset, columnas)
            elif formato == "docx":
                datos = export.experiences_to_word(subset, contexto, campos=columnas, incluir_tabla=con_tabla,
                                                   con_logos=con_logos)
            else:
                datos = export.experiences_to_csv(subset, columnas)
            if usuario:
                try:
                    repo.registrar_exportacion(usuario, contexto, formato, modo, ids_export,
                                               columnas if columnas is not None else ["*"], resumen_filtros(criterios))
                except Exception:  # noqa: BLE001  (registrar no debe impedir la descarga)
                    pass
            return datos
        return f

    with st.container(horizontal=True):
        for formato, etiqueta, icono in (("xlsx", "Excel (.xlsx)", ":material/table_view:"),
                                         ("docx", "Word (.docx)", ":material/description:"),
                                         ("csv", "CSV", ":material/csv:")):
            st.download_button(etiqueta, data=generar(formato), file_name=f"noticias_{modo}_{fecha}.{formato}",
                               mime=MIME[formato], icon=icono, disabled=sin_datos, key=f"exp_dl_{formato}",
                               on_click="ignore")
    if not usuario:
        st.caption("Elige tu nombre en «Editando como» para que la exportación quede registrada en el historial.")
    if not sin_datos:
        st.caption(f"Se exportarán {len(subset)} noticia(s).")
