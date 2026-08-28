# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from utils.components import render_news_card
from utils.data import filter_by_multilabel, get_options, load_noticias
from utils.style import inject, page_header, section_label

st.set_page_config(page_title="Explorador Avanzado", layout="wide")
inject()
page_header(
    "Búsqueda multicriterio",
    "Explorador Avanzado",
    "Combina cualquier número de filtros. Dentro de un mismo filtro se combina con 'o'; entre "
    "filtros distintos, con 'y'. Haz clic en una fila de la tabla para ver la ficha completa.",
)

df = load_noticias()
ACTORES_COL = "actores_normalizados" if "actores_normalizados" in df.columns else "actores"


@st.dialog("Ficha de la experiencia", width="large")
def _show_dialog(item_id: int):
    row = df[df["item"] == item_id].iloc[0]
    render_news_card(row)


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
c1, c2 = st.columns([3, 1])
c1.metric("Experiencias encontradas", f"{len(result)} de {len(df)}")
with c2:
    st.write("")
    st.download_button(
        "Descargar CSV",
        data=result.drop(columns=["item"], errors="ignore").to_csv(index=False).encode("utf-8-sig"),
        file_name="experiencias_filtradas.csv",
        mime="text/csv",
        width="stretch",
    )

cols_mostrar = [
    "item", "titulo", "categoria_macro_primary", "metodologia",
    "eje_gcaa_primary", "atributos_resiliencia_primary",
    "enfoque_genero", "lugar", "anio",
]
cols_mostrar = [c for c in cols_mostrar if c in result.columns]
display_df = result[cols_mostrar].rename(columns={
    "categoria_macro_primary": "categoria_macro",
    "eje_gcaa_primary": "eje_gcaa",
    "atributos_resiliencia_primary": "atributos_resiliencia",
})

event = st.dataframe(
    display_df,
    width="stretch",
    hide_index=True,
    height=460,
    on_select="rerun",
    selection_mode="single-row",
    column_config={
        "item": st.column_config.NumberColumn("N.", width="small"),
        "titulo": st.column_config.TextColumn("Título", width="medium"),
        "categoria_macro": st.column_config.TextColumn("Categoría macro", width="medium"),
        "metodologia": st.column_config.TextColumn("Metodología", width="medium"),
        "eje_gcaa": st.column_config.TextColumn("Eje GCAA", width="medium"),
        "atributos_resiliencia": st.column_config.TextColumn("Atributo resiliencia", width="medium"),
        "enfoque_genero": st.column_config.TextColumn("Género", width="small"),
        "lugar": st.column_config.TextColumn("Lugar", width="medium"),
        "anio": st.column_config.NumberColumn("Año", format="%d", width="small"),
    },
)
st.caption("Categoría, eje GCAA y atributo de resiliencia muestran la etiqueta principal cuando una experiencia tiene más de una.")

selected_rows = event.selection.rows if event and event.selection else []
if selected_rows:
    item_id = int(display_df.iloc[selected_rows[0]]["item"])
    _show_dialog(item_id)
