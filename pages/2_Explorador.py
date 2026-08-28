# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from utils.components import render_news_card
from utils.data import filter_by_multilabel, get_options, load_noticias
from utils.export import experiences_to_excel, experiences_to_word
from utils.style import inject, page_header, section_label

st.set_page_config(page_title="Explorador Avanzado", layout="wide")
inject()
page_header(
    "Búsqueda multicriterio",
    "Explorador Avanzado",
    "Combina cualquier número de filtros. Dentro de un mismo filtro se combina con 'o'; entre "
    "filtros distintos, con 'y'. Marca experiencias con las casillas para abrir su ficha o "
    "descargarlas en Word y Excel para una postulación.",
)

df = load_noticias()
ACTORES_COL = "actores_normalizados" if "actores_normalizados" in df.columns else "actores"


@st.dialog("Ficha de la experiencia", width="large")
def _show_dialog(item_id: int):
    row = df[df["item"] == item_id].iloc[0]
    render_news_card(row)


@st.cache_data(show_spinner=False)
def _excel_bytes(item_ids: tuple[int, ...]) -> bytes:
    return experiences_to_excel(df[df["item"].isin(item_ids)])


@st.cache_data(show_spinner=False)
def _word_bytes(item_ids: tuple[int, ...], contexto: str) -> bytes:
    return experiences_to_word(df[df["item"].isin(item_ids)], contexto)


with st.sidebar:
    st.markdown("**Filtros**")
    st.page_link("pages/8_Glosario.py", label="¿Qué significa cada categoría? → Glosario")

    texto = st.text_input("Buscar texto en título o contenido")

    f_macro = st.multiselect("Categoría macro", get_options(df, "categoria_macro"))
    f_cat = st.multiselect("Categoría temática", get_options(df, "categorias"))
    f_meto = st.multiselect("Metodología", get_options(df, "metodologia"))
    f_actor = st.multiselect("Actores institucionales", get_options(df, ACTORES_COL))

    st.divider()
    f_gcaa_eje = st.multiselect("Eje GCAA", get_options(df, "eje_gcaa"))
    f_gcaa_obj = st.multiselect("Objetivo GCAA", get_options(df, "objetivo_gcaa"))
    f_resil = st.multiselect("Atributo de resiliencia", get_options(df, "atributos_resiliencia"))
    f_subresil = st.multiselect("Sub-atributo de resiliencia", get_options(df, "subatributos_resiliencia"))

    st.divider()
    f_benef_dir = st.multiselect("Beneficiarios directos", get_options(df, "beneficiarios_directos"))
    f_benef_ind = st.multiselect("Beneficiarios indirectos", get_options(df, "beneficiarios_indirectos"))
    f_genero = st.radio("Enfoque de género", ["Todos", "Solo con enfoque explícito", "Sin enfoque"], index=0)

    st.divider()
    if df["tiene_fecha"].any():
        anio_min, anio_max = int(df["anio"].min()), int(df["anio"].max())
        f_anios = st.slider("Año", anio_min, anio_max, (anio_min, anio_max))
        f_incluir_sin_fecha = st.checkbox("Incluir experiencias sin fecha registrada", value=True)
    else:
        f_anios = None
        f_incluir_sin_fecha = True

    if st.button("Limpiar filtros"):
        st.rerun()

# ------------------------------------------------------------ aplicar filtros
result = df.copy()

if texto:
    t = texto.lower()
    result = result[
        result["titulo"].astype(str).str.lower().str.contains(t, na=False)
        | result["contenido_completo"].astype(str).str.lower().str.contains(t, na=False)
    ]

result = filter_by_multilabel(result, "categoria_macro", f_macro)
result = filter_by_multilabel(result, "categorias", f_cat)
result = filter_by_multilabel(result, "metodologia", f_meto)
result = filter_by_multilabel(result, ACTORES_COL, f_actor)
result = filter_by_multilabel(result, "eje_gcaa", f_gcaa_eje)
result = filter_by_multilabel(result, "objetivo_gcaa", f_gcaa_obj)
result = filter_by_multilabel(result, "atributos_resiliencia", f_resil)
result = filter_by_multilabel(result, "subatributos_resiliencia", f_subresil)
result = filter_by_multilabel(result, "beneficiarios_directos", f_benef_dir)
result = filter_by_multilabel(result, "beneficiarios_indirectos", f_benef_ind)

if f_genero == "Solo con enfoque explícito":
    result = result[result["enfoque_genero"].astype(str).str.startswith("Sí")]
elif f_genero == "Sin enfoque":
    result = result[~result["enfoque_genero"].astype(str).str.startswith("Sí")]

if f_anios is not None:
    mask_rango = result["anio"].between(f_anios[0], f_anios[1])
    if f_incluir_sin_fecha:
        mask_rango = mask_rango | (~result["tiene_fecha"])
    result = result[mask_rango]

# ------------------------------------------------------------ resultados
st.metric("Experiencias encontradas", f"{len(result)} de {len(df)}")

# Orden de columnas pedido: Título · Año · País · Resumen · Texto completo · Link · (todo lo demás).
COLUMN_ORDER = [
    ("titulo", "Título", "text"),
    ("anio", "Año", "year"),
    ("pais", "País", "text"),
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

st.caption(
    "Marca una o varias experiencias con las casillas de la izquierda. Con **una** marcada puedes "
    "abrir su **ficha completa** (con todas las categorizaciones, más de lo que muestra la web "
    "original). Con **una o más**, puedes descargarlas en **Word** y **Excel** para una postulación."
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
    st.info("Marca experiencias en la tabla para abrir su ficha o descargarlas.")
else:
    if len(sel_ids) == 1:
        if st.button("📄 Ver ficha completa de la experiencia marcada", type="primary"):
            _show_dialog(sel_ids[0])
    else:
        st.caption("Para ver una ficha, deja solo una experiencia marcada.")

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

with st.expander("Descargar TODOS los resultados filtrados (sin marcar uno por uno)"):
    st.download_button(
        "⬇️ CSV con los " + str(len(result)) + " resultados",
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
