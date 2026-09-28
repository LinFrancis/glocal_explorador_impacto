# -*- coding: utf-8 -*-
"""Sección 'Resultados' dentro de Explorador Glocal: planilla + catálogo de lectura + ficha +
exportación. Al presionar "Leer", la ficha reemplaza la lista al instante (no se agrega debajo:
así el usuario no tiene que hacer scroll para encontrarla)."""
import streamlit as st

from utils.components import render_news_card
from utils.export import experiences_to_excel, experiences_to_word
from utils.style import section_label

ITEM_ACTIVO_KEY = "explorador_item_activo"
PAGINA_KEY = "explorador_pagina_catalogo"
POR_PAGINA = 20


@st.cache_data(show_spinner=False)
def _excel_bytes(df, item_ids: tuple[int, ...]) -> bytes:
    return experiences_to_excel(df[df["item"].isin(item_ids)])


@st.cache_data(show_spinner=False)
def _word_bytes(df, item_ids: tuple[int, ...], contexto: str) -> bytes:
    return experiences_to_word(df[df["item"].isin(item_ids)], contexto)


def render(df):
    catalogo = df.sort_values("fecha_parsed", ascending=False, na_position="last").reset_index(drop=True)

    item_activo = st.session_state.get(ITEM_ACTIVO_KEY)
    if item_activo is not None and item_activo not in set(catalogo["item"]):
        item_activo = None
        st.session_state.pop(ITEM_ACTIVO_KEY, None)

    # -------------------------------------------------------- ficha (reemplaza la lista)
    if item_activo is not None:
        if st.button("← Volver a resultados", key="resultados_volver"):
            st.session_state.pop(ITEM_ACTIVO_KEY, None)
            st.rerun()
        with st.container(border=True):
            render_news_card(catalogo[catalogo["item"] == item_activo].iloc[0])
        return

    # -------------------------------------------------------- planilla (colapsada)
    ACTORES_COL = "actores_normalizados" if "actores_normalizados" in df.columns else "actores"
    COLUMN_ORDER = [
        ("titulo", "Título", "text"),
        ("anio", "Año", "year"),
        ("pais", "País", "text"),
        ("fuente", "Fuente", "text"),
        ("tipo_informacion", "Tipo de información", "text"),
        ("Fundación Glocal?", "Fundación Glocal", "text"),
        ("Consultora", "Consultora", "text"),
        ("descripcion_catalogo", "Resumen", "text"),
        ("contenido_completo", "Texto completo", "text"),
        ("url_noticia", "Link", "link"),
        ("categorias", "Categoría temática", "text"),
        ("categoria_macro", "Categoría macro", "text"),
        ("metodologia", "Metodología", "text"),
        (ACTORES_COL, "Actores institucionales", "text"),
        ("eje_gcaa", "Eje GCAA", "text"),
        ("objetivo_gcaa", "Objetivo GCAA", "text"),
        ("atributos_resiliencia", "Atributo de resiliencia", "text"),
        ("subatributos_resiliencia", "Sub-atributo de resiliencia", "text"),
        ("beneficiarios_directos", "Beneficiarios directos", "text"),
        ("beneficiarios_indirectos", "Beneficiarios indirectos", "text"),
        ("enfoque_genero", "Enfoque de género", "text"),
        ("lugar", "Lugar", "text"),
    ]
    cols_present = [(c, label, kind) for c, label, kind in COLUMN_ORDER if c in df.columns]
    display_df = df[[c for c, _, _ in cols_present]].reset_index(drop=True)

    col_cfg = {}
    for c, label, kind in cols_present:
        if kind == "year":
            col_cfg[c] = st.column_config.NumberColumn(label, format="%d", width="small")
        elif kind == "link":
            col_cfg[c] = st.column_config.LinkColumn(label, display_text="Abrir ↗", width="small")
        elif c in ("descripcion_catalogo", "contenido_completo"):
            col_cfg[c] = st.column_config.TextColumn(label, width="large")
        else:
            col_cfg[c] = st.column_config.TextColumn(label, width="medium")

    with st.expander("Ver como planilla", expanded=False):
        st.caption(
            "Marca una o varias filas con las casillas de la izquierda para exportarlas en Word y "
            "Excel para una postulación."
        )
        event = st.dataframe(
            display_df, width="stretch", hide_index=True, height=560,
            on_select="rerun", selection_mode="multi-row", column_config=col_cfg,
            key="resultados_tabla_planilla",
        )
        selected_rows = event.selection.rows if event and event.selection else []
        sel_df = df.iloc[selected_rows] if selected_rows else df.iloc[[]]
        sel_ids = tuple(int(i) for i in sel_df["item"].tolist())

        st.divider()
        section_label(f"Selección para exportar — {len(sel_ids)} experiencia(s)")

        if not sel_ids:
            st.info("Marca experiencias en la tabla para descargarlas.")
        else:
            contexto = st.text_input(
                "¿Para qué es esta selección? (opcional, se incluye en el encabezado del Word)",
                placeholder="Ej.: Postulación a fondo de apoyo a comunidades educativas — antecedentes de experiencias previas",
                key="resultados_export_contexto",
            )
            d1, d2, d3 = st.columns(3)
            d1.download_button(
                "Word (.docx)", data=_word_bytes(df, sel_ids, contexto),
                file_name="experiencias_seleccionadas.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                width="stretch", key="resultados_dl_word_sel",
            )
            d2.download_button(
                "Excel (.xlsx)", data=_excel_bytes(df, sel_ids),
                file_name="experiencias_seleccionadas.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch", key="resultados_dl_excel_sel",
            )
            d3.download_button(
                "CSV", data=sel_df.drop(columns=["item"], errors="ignore").to_csv(index=False).encode("utf-8-sig"),
                file_name="experiencias_seleccionadas.csv", mime="text/csv",
                width="stretch", key="resultados_dl_csv_sel",
            )

        st.divider()
        st.download_button(
            "CSV con los " + str(len(df)) + " resultados filtrados",
            data=df.drop(columns=["item"], errors="ignore").to_csv(index=False).encode("utf-8-sig"),
            file_name="experiencias_filtradas.csv", mime="text/csv", key="resultados_dl_csv_todos",
        )
        if len(df) and st.checkbox("Preparar Word y Excel con todos los resultados filtrados", key="resultados_check_todos"):
            all_ids = tuple(int(i) for i in df["item"].tolist())
            cc1, cc2 = st.columns(2)
            cc1.download_button(
                "Word (" + str(len(df)) + ")", data=_word_bytes(df, all_ids, ""),
                file_name="experiencias_filtradas.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                width="stretch", key="resultados_dl_word_todos",
            )
            cc2.download_button(
                "Excel (" + str(len(df)) + ")", data=_excel_bytes(df, all_ids),
                file_name="experiencias_filtradas.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch", key="resultados_dl_excel_todos",
            )

    # -------------------------------------------------------- catálogo de lectura
    section_label("Catálogo de resultados — elige una para leerla completa")

    n_total = len(catalogo)
    n_paginas = max(1, -(-n_total // POR_PAGINA))

    if PAGINA_KEY not in st.session_state:
        st.session_state[PAGINA_KEY] = 0
    st.session_state[PAGINA_KEY] = min(st.session_state[PAGINA_KEY], n_paginas - 1)

    if n_total == 0:
        st.info("Ningún resultado con los filtros actuales.")
        return

    if n_paginas > 1:
        pc1, pc2, pc3 = st.columns([1, 2, 1])
        with pc1:
            if st.button("← Anteriores", disabled=st.session_state[PAGINA_KEY] <= 0, key="resultados_pag_ant"):
                st.session_state[PAGINA_KEY] -= 1
                st.rerun()
        with pc2:
            st.markdown(
                f"<div style='text-align:center'>Página {st.session_state[PAGINA_KEY] + 1} de {n_paginas}</div>",
                unsafe_allow_html=True,
            )
        with pc3:
            if st.button("Siguientes →", disabled=st.session_state[PAGINA_KEY] >= n_paginas - 1, key="resultados_pag_sig"):
                st.session_state[PAGINA_KEY] += 1
                st.rerun()

    inicio = st.session_state[PAGINA_KEY] * POR_PAGINA
    pagina_df = catalogo.iloc[inicio: inicio + POR_PAGINA]

    for _, row in pagina_df.iterrows():
        macro = str(row.get("categoria_macro_primary") or row.get("categoria_macro") or "").split(";")[0].strip() or "Sin categoría"
        fecha_txt = row["fecha_parsed"].strftime("%Y") if row.get("tiene_fecha") else "Sin fecha"
        lugar_txt = str(row.get("lugar") or "").split(";")[0].strip() or "Sin lugar"
        tipo_info = str(row.get("tipo_informacion") or "").strip()
        resumen = str(row.get("descripcion_catalogo") or row.get("preview_contenido") or "").strip()
        resumen_corto = (resumen[:160] + "…") if len(resumen) > 160 else resumen

        c1, c2 = st.columns([5, 1])
        with c1:
            st.markdown(f"**{row['titulo']}**")
            meta_bits = [fecha_txt, lugar_txt, macro] + ([tipo_info] if tipo_info else [])
            st.caption(" · ".join(meta_bits))
            if resumen_corto:
                st.caption(resumen_corto)
        with c2:
            if st.button("Leer", key=f"resultados_leer_{row['item']}", width="stretch"):
                st.session_state[ITEM_ACTIVO_KEY] = int(row["item"])
                st.rerun()
        st.divider()
