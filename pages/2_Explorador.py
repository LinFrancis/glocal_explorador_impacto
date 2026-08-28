# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from utils.data import filter_by_multilabel, get_options, load_noticias
from utils.style import inject, page_header, section_label

st.set_page_config(page_title="Explorador Avanzado", layout="wide")
inject()
page_header(
    "Búsqueda multicriterio",
    "Explorador Avanzado",
    "Combina cualquier número de filtros. Dentro de un mismo filtro se combina con 'o'; entre "
    "filtros distintos, con 'y'.",
)

df = load_noticias()
ACTORES_COL = "actores_normalizados" if "actores_normalizados" in df.columns else "actores"

with st.sidebar:
    st.markdown("**Filtros**")

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
section_label("Resultados")
st.metric("Experiencias encontradas", f"{len(result)} de {len(df)}")

cols_mostrar = [
    "item", "titulo", "categoria_macro", "categorias", "metodologia",
    "eje_gcaa", "atributos_resiliencia", "beneficiarios_directos",
    "enfoque_genero", "lugar", "anio", "url_noticia",
]
cols_mostrar = [c for c in cols_mostrar if c in result.columns]

st.dataframe(
    result[cols_mostrar],
    use_container_width=True,
    hide_index=True,
    column_config={
        "item": st.column_config.NumberColumn("N.", width="small"),
        "titulo": st.column_config.TextColumn("Título", width="medium"),
        "url_noticia": st.column_config.LinkColumn("Ver en el catálogo", display_text="Abrir"),
        "anio": st.column_config.NumberColumn("Año", format="%d"),
    },
)

st.download_button(
    "Descargar resultados filtrados (CSV)",
    data=result[cols_mostrar].to_csv(index=False).encode("utf-8-sig"),
    file_name="experiencias_filtradas.csv",
    mime="text/csv",
)

with st.expander("Ver detalle completo de una experiencia"):
    if len(result):
        item_sel = st.selectbox(
            "Elegir experiencia", result["item"].tolist(),
            format_func=lambda i: f"#{i} — " + result.loc[result['item'] == i, 'titulo'].values[0],
        )
        row = result[result["item"] == item_sel].iloc[0]
        st.markdown(f"### {row['titulo']}")
        st.write(row.get("contenido_completo", ""))
        st.json({
            "categoria_macro": row["categoria_macro"],
            "categorias": row["categorias"],
            "metodologia": row["metodologia"],
            "actores": row.get(ACTORES_COL, row.get("actores")),
            "eje_gcaa": row["eje_gcaa"],
            "objetivo_gcaa": row["objetivo_gcaa"],
            "atributos_resiliencia": row["atributos_resiliencia"],
            "beneficiarios_directos": row["beneficiarios_directos"],
            "beneficiarios_indirectos": row["beneficiarios_indirectos"],
            "enfoque_genero": row["enfoque_genero"],
            "lugar": row["lugar"],
        })
