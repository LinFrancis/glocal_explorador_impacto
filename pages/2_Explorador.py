# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from utils.components import render_news_card
from utils.data import load_noticias
from utils.export import experiences_to_excel, experiences_to_word
from utils.filters import apply_search_filters, render_search_filters
from utils.style import inject, page_header, section_label

st.set_page_config(page_title="Explorador Avanzado", layout="wide")
inject()
page_header(
    "Búsqueda multicriterio",
    "Explorador Avanzado",
    "Combina cualquier número de filtros. Dentro de un mismo filtro se combina con 'o'; entre "
    "filtros distintos, con 'y'. Estos mismos criterios se aplican también en Mapa, Evolución "
    "Temporal, Cruces y Correlaciones y Cuencas — para ver todo, quita los filtros.",
)

df = load_noticias()
ITEM_ACTIVO_KEY = "explorador_item_activo"
PAGINA_KEY = "explorador_pagina_catalogo"
POR_PAGINA = 20


@st.cache_data(show_spinner=False)
def _excel_bytes(item_ids: tuple[int, ...]) -> bytes:
    return experiences_to_excel(df[df["item"].isin(item_ids)])


@st.cache_data(show_spinner=False)
def _word_bytes(item_ids: tuple[int, ...], contexto: str) -> bytes:
    return experiences_to_word(df[df["item"].isin(item_ids)], contexto)


with st.sidebar:
    criterios = render_search_filters(df)

result = apply_search_filters(df, criterios)

# ------------------------------------------------------------ resultados
st.metric("Experiencias encontradas", f"{len(result)} de {len(df)}")

# Orden de columnas pedido: Título · Año · País · Resumen · Texto completo · Link · (todo lo demás).
ACTORES_COL = "actores_normalizados" if "actores_normalizados" in df.columns else "actores"
COLUMN_ORDER = [
    ("titulo", "Título", "text"),
    ("anio", "Año", "year"),
    ("pais", "País", "text"),
    ("fuente", "Fuente", "text"),
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
cols_present = [(c, label, kind) for c, label, kind in COLUMN_ORDER if c in result.columns]
display_df = result[[c for c, _, _ in cols_present]].reset_index(drop=True)

col_cfg = {}
for c, label, kind in cols_present:
    if kind == "num":
        col_cfg[c] = st.column_config.NumberColumn(label, width="small")
    elif kind == "year":
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
        display_df,
        width="stretch",
        hide_index=True,
        height=560,
        on_select="rerun",
        selection_mode="multi-row",
        column_config=col_cfg,
    )
    selected_rows = event.selection.rows if event and event.selection else []
    sel_df = result.iloc[selected_rows] if selected_rows else result.iloc[[]]
    sel_ids = tuple(int(i) for i in sel_df["item"].tolist())

    st.divider()
    section_label(f"Selección para exportar — {len(sel_ids)} experiencia(s)")

    if not sel_ids:
        st.info("Marca experiencias en la tabla para descargarlas.")
    else:
        contexto = st.text_input(
            "¿Para qué es esta selección? (opcional, se incluye en el encabezado del Word)",
            placeholder="Ej.: Postulación a fondo de apoyo a comunidades educativas — antecedentes de experiencias previas",
        )
        d1, d2, d3 = st.columns(3)
        d1.download_button(
            "⬇️ Word (.docx)",
            data=_word_bytes(sel_ids, contexto),
            file_name="experiencias_seleccionadas.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            width="stretch",
        )
        d2.download_button(
            "⬇️ Excel (.xlsx)",
            data=_excel_bytes(sel_ids),
            file_name="experiencias_seleccionadas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
        d3.download_button(
            "⬇️ CSV",
            data=sel_df.drop(columns=["item"], errors="ignore").to_csv(index=False).encode("utf-8-sig"),
            file_name="experiencias_seleccionadas.csv",
            mime="text/csv",
            width="stretch",
        )

    st.divider()
    st.download_button(
        "⬇️ CSV con los " + str(len(result)) + " resultados filtrados",
        data=result.drop(columns=["item"], errors="ignore").to_csv(index=False).encode("utf-8-sig"),
        file_name="experiencias_filtradas.csv",
        mime="text/csv",
    )
    if len(result) and st.checkbox("Preparar Word y Excel con todos los resultados filtrados"):
        all_ids = tuple(int(i) for i in result["item"].tolist())
        cc1, cc2 = st.columns(2)
        cc1.download_button(
            "⬇️ Word (" + str(len(result)) + ")",
            data=_word_bytes(all_ids, ""),
            file_name="experiencias_filtradas.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            width="stretch",
        )
        cc2.download_button(
            "⬇️ Excel (" + str(len(result)) + ")",
            data=_excel_bytes(all_ids),
            file_name="experiencias_filtradas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )

# ------------------------------------------------------------ catálogo de lectura (baja fricción)
section_label("Catálogo de resultados — elige una para leerla completa")

catalogo = result.sort_values("fecha_parsed", ascending=False, na_position="last").reset_index(drop=True)
n_total = len(catalogo)
n_paginas = max(1, -(-n_total // POR_PAGINA))

if PAGINA_KEY not in st.session_state:
    st.session_state[PAGINA_KEY] = 0
st.session_state[PAGINA_KEY] = min(st.session_state[PAGINA_KEY], n_paginas - 1)

if n_total == 0:
    st.info("Ningún resultado con los filtros actuales.")
else:
    if n_paginas > 1:
        pc1, pc2, pc3 = st.columns([1, 2, 1])
        with pc1:
            if st.button("← Anteriores", disabled=st.session_state[PAGINA_KEY] <= 0):
                st.session_state[PAGINA_KEY] -= 1
                st.rerun()
        with pc2:
            st.markdown(
                f"<div style='text-align:center'>Página {st.session_state[PAGINA_KEY] + 1} de {n_paginas}</div>",
                unsafe_allow_html=True,
            )
        with pc3:
            if st.button("Siguientes →", disabled=st.session_state[PAGINA_KEY] >= n_paginas - 1):
                st.session_state[PAGINA_KEY] += 1
                st.rerun()

    inicio = st.session_state[PAGINA_KEY] * POR_PAGINA
    pagina_df = catalogo.iloc[inicio: inicio + POR_PAGINA]

    for _, row in pagina_df.iterrows():
        macro = str(row.get("categoria_macro_primary") or row.get("categoria_macro") or "").split(";")[0].strip() or "Sin categoría"
        fecha_txt = row["fecha_parsed"].strftime("%Y") if row.get("tiene_fecha") else "Sin fecha"
        lugar_txt = str(row.get("lugar") or "").split(";")[0].strip() or "Sin lugar"
        resumen = str(row.get("descripcion_catalogo") or row.get("preview_contenido") or "").strip()
        resumen_corto = (resumen[:160] + "…") if len(resumen) > 160 else resumen

        c1, c2 = st.columns([5, 1])
        with c1:
            st.markdown(f"**{row['titulo']}**")
            st.caption(f"{fecha_txt} · {lugar_txt} · {macro}")
            if resumen_corto:
                st.caption(resumen_corto)
        with c2:
            if st.button("📄 Leer", key=f"leer_{row['item']}", width="stretch"):
                st.session_state[ITEM_ACTIVO_KEY] = int(row["item"])
                st.rerun()
        st.divider()

# ------------------------------------------------------------ ficha del ítem activo
item_activo = st.session_state.get(ITEM_ACTIVO_KEY)
if item_activo is not None and item_activo in set(catalogo["item"]):
    st.markdown("### Ficha completa")
    ids_orden = catalogo["item"].tolist()
    pos = ids_orden.index(item_activo)

    n1, n2, n3 = st.columns([1, 2, 1])
    with n1:
        if st.button("← Anterior", disabled=pos <= 0, key="ficha_anterior"):
            st.session_state[ITEM_ACTIVO_KEY] = ids_orden[pos - 1]
            st.rerun()
    with n3:
        if st.button("Siguiente →", disabled=pos >= len(ids_orden) - 1, key="ficha_siguiente"):
            st.session_state[ITEM_ACTIVO_KEY] = ids_orden[pos + 1]
            st.rerun()
    with n2:
        if st.button("✕ Cerrar ficha", key="ficha_cerrar", width="stretch"):
            st.session_state.pop(ITEM_ACTIVO_KEY, None)
            st.rerun()

    with st.container(border=True):
        render_news_card(catalogo[catalogo["item"] == item_activo].iloc[0])
elif item_activo is not None:
    st.session_state.pop(ITEM_ACTIVO_KEY, None)
