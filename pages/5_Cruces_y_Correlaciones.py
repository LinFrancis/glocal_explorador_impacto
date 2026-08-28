# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.components import render_news_card
from utils.data import COLUMN_LABELS, RESILIENCE_TAXONOMY, explode_multilabel, load_noticias, resilience_counts
from utils.style import DIMENSION_COLOR_MAPS, inject, page_header, section_label, style_fig

st.set_page_config(page_title="Cruces y Correlaciones", layout="wide")
inject()
page_header(
    "Análisis relacional",
    "Cruces y Correlaciones",
    "Explora cómo se relacionan las distintas dimensiones del catálogo entre sí.",
)

df = load_noticias()


@st.dialog("Ficha de la experiencia", width="large")
def _show_dialog(item_id: int):
    row = df[df["item"] == item_id].iloc[0]
    render_news_card(row)


DIMS = [
    "categoria_macro", "categorias", "metodologia", "actores_normalizados",
    "eje_gcaa", "objetivo_gcaa", "atributos_resiliencia", "subatributos_resiliencia",
    "beneficiarios_directos", "beneficiarios_indirectos",
]
DIMS = [d for d in DIMS if d in df.columns]

# ============================================================== 1. Heatmap cruzado
st.markdown("## Heatmap cruzado")
c1, c2, c3 = st.columns([1, 1, 1])
dim_a = c1.selectbox("Dimensión A (filas)", DIMS, index=0, format_func=lambda c: COLUMN_LABELS.get(c, c))
dim_b = c2.selectbox("Dimensión B (columnas)", DIMS, index=4, format_func=lambda c: COLUMN_LABELS.get(c, c))
excluir = c3.checkbox("Excluir 'No aplica' / 'No especificado'", value=True)

a = explode_multilabel(df, dim_a).rename(columns={"label": "label_a"})
b = explode_multilabel(df, dim_b).rename(columns={"label": "label_b"})
merged = a.merge(b, on="item")

if excluir:
    bad = {"no aplica", "no especificado"}
    merged = merged[~merged["label_a"].str.lower().isin(bad) & ~merged["label_b"].str.lower().isin(bad)]

label_a_name = COLUMN_LABELS.get(dim_a, dim_a)
label_b_name = COLUMN_LABELS.get(dim_b, dim_b)

if dim_a == dim_b:
    st.info("Elige dos dimensiones distintas para cruzarlas.")
elif len(merged) == 0:
    st.info("No hay co-ocurrencias para mostrar con estos filtros.")
else:
    fig = px.density_heatmap(
        merged, x="label_b", y="label_a", color_continuous_scale="Teal",
        labels={"label_a": label_a_name, "label_b": label_b_name, "color": "N° experiencias"},
    )
    fig.update_coloraxes(colorbar_title="N° exp.")
    n_a = merged["label_a"].nunique()
    height = max(380, min(700, 60 + 26 * n_a))
    style_fig(fig, height=height, title=f"{label_a_name} cruzado con {label_b_name}")
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "Cada celda cuenta experiencias que tienen ambas etiquetas presentes "
        "(una experiencia con múltiples etiquetas se cuenta en todas sus combinaciones)."
    )

st.divider()

# ============================================================== 2. Sankey
st.markdown("## Flujo: tema, clima, resiliencia")
st.caption(
    "Flujo desde la categoría macro (de qué habla), pasando por el eje GCAA (si conecta con "
    "acción climática), hasta el atributo de resiliencia que fortalece. Solo incluye experiencias "
    "donde ambos ejes climático y de resiliencia aplican (no 'No aplica')."
)
sub = df[
    (df["eje_gcaa_primary"].str.lower() != "no aplica")
    & (df["atributos_resiliencia_primary"].str.lower() != "no aplica")
].copy()

if len(sub) == 0:
    st.info("No hay experiencias que cumplan ambas condiciones.")
else:
    macros = sorted(sub["categoria_macro_primary"].unique())
    gcaas = sorted(sub["eje_gcaa_primary"].unique())
    resils = sorted(sub["atributos_resiliencia_primary"].unique())

    nodes = macros + gcaas + resils
    idx = {n: i for i, n in enumerate(nodes)}

    link1 = sub.groupby(["categoria_macro_primary", "eje_gcaa_primary"]).size().reset_index(name="n")
    link2 = sub.groupby(["eje_gcaa_primary", "atributos_resiliencia_primary"]).size().reset_index(name="n")

    sources = [idx[m] for m in link1["categoria_macro_primary"]] + [idx[g] for g in link2["eje_gcaa_primary"]]
    targets = [idx[g] for g in link1["eje_gcaa_primary"]] + [idx[r] for r in link2["atributos_resiliencia_primary"]]
    values = link1["n"].tolist() + link2["n"].tolist()

    colors = ["#0B6E4F"] * len(macros) + ["#1F6FB2"] * len(gcaas) + ["#B2531F"] * len(resils)

    fig = go.Figure(go.Sankey(
        node=dict(label=nodes, color=colors, pad=14, thickness=14),
        link=dict(source=sources, target=targets, value=values),
    ))
    style_fig(fig, height=520, title="Flujo: categoría macro → eje GCAA → atributo de resiliencia")
    st.plotly_chart(fig, width="stretch")
    st.caption(
        f"Basado en {len(sub)} experiencias con eje GCAA y atributo de resiliencia aplicables. "
        "Verde = categoría macro, azul = eje GCAA, naranjo = atributo de resiliencia."
    )

st.divider()

# ============================================================== 3. Vacíos de cobertura
st.markdown("## Vacíos de cobertura")
st.caption("Objetivos y sub-atributos con menor cobertura en el catálogo — señales de dónde falta trabajo documentado.")

obj = explode_multilabel(df, "objetivo_gcaa")
obj = obj[obj["label"].str.lower() != "no aplica"]
counts = obj["label"].value_counts().reset_index()
counts.columns = ["Objetivo GCAA", "N"]
counts = counts.sort_values("N")
fig = px.bar(
    counts, x="N", y="Objetivo GCAA", orientation="h",
    color="N", color_continuous_scale="OrRd", labels={"N": "N° experiencias"},
)
fig.update_layout(coloraxis_showscale=False)
style_fig(fig, height=520, title="Objetivos GCAA presentes en el catálogo, de menor a mayor frecuencia", showlegend=False)
st.plotly_chart(fig, width="stretch")

_, df_sub_full = resilience_counts(df)
df_sub_full = df_sub_full.sort_values("n")
fig2 = px.bar(
    df_sub_full, x="n", y="subatributo", orientation="h",
    color="n", color_continuous_scale="OrRd", labels={"n": "N° experiencias", "subatributo": "Sub-atributo"},
)
fig2.update_layout(coloraxis_showscale=False)
style_fig(
    fig2, height=520,
    title="Los 19 sub-atributos de resiliencia (CR2), de menor a mayor frecuencia",
    showlegend=False,
)
st.plotly_chart(fig2, width="stretch")
n_cero = (df_sub_full["n"] == 0).sum()
if n_cero:
    faltantes = ", ".join(df_sub_full.loc[df_sub_full["n"] == 0, "subatributo"])
    st.caption(f"{n_cero} sub-atributo(s) sin ninguna experiencia registrada: {faltantes}.")

st.divider()

# ============================================================== 4. Lente de género
st.markdown("## Lente de género")
genero_df = df[df["enfoque_genero_binario"] == "Sí"].reset_index(drop=True)
st.markdown(f"**{len(genero_df)} experiencias** tienen un enfoque de género explícito (de {len(df)} totales, {len(genero_df)/len(df):.1%}).")
if len(genero_df):
    display_genero = genero_df[["item", "titulo", "categoria_macro_primary", "beneficiarios_directos", "enfoque_genero", "anio"]].rename(
        columns={"categoria_macro_primary": "categoria_macro"}
    )
    st.caption("Haz clic en una fila para ver la ficha completa.")
    event_genero = st.dataframe(
        display_genero, hide_index=True, width="stretch", height=280,
        on_select="rerun", selection_mode="single-row",
    )
    sel_genero = event_genero.selection.rows if event_genero and event_genero.selection else []
    if sel_genero:
        _show_dialog(int(display_genero.iloc[sel_genero[0]]["item"]))
else:
    st.info("No hay experiencias marcadas con enfoque de género explícito.")

st.divider()

# ============================================================== 5. Radial de resiliencia
st.markdown("## Radial de resiliencia")
st.caption(
    "Cuántas experiencias tocan cada atributo y cada sub-atributo de resiliencia, según la taxonomía "
    "oficial del CR2 (Race to Resilience Technical Secretariat, 2023). Ordenados de menor a mayor "
    "frecuencia. Se muestran los 7 atributos y los 19 sub-atributos completos, incluso los que no "
    "tienen ninguna experiencia asociada (en 0)."
)

df_attr, df_sub = resilience_counts(df)
attr_order_asc = df_attr.sort_values("n")["atributo"].tolist()
sub_order_asc = df_sub.sort_values("n")["subatributo"].tolist()
color_map_resil = DIMENSION_COLOR_MAPS.get("atributos_resiliencia_primary")

fig_attr = px.bar_polar(
    df_attr, r="n", theta="atributo", color="atributo",
    category_orders={"atributo": attr_order_asc},
    color_discrete_map=color_map_resil,
    labels={"n": "N° experiencias", "atributo": "Atributo"},
)
fig_attr.update_traces(hovertemplate="%{theta}<br>N° experiencias: %{r}<extra></extra>")
style_fig(fig_attr, height=440, title="Apariciones por atributo de resiliencia — 7 atributos, de menor a mayor", legend_title="Atributo")
st.plotly_chart(fig_attr, width="stretch")

fig_sub = px.bar_polar(
    df_sub, r="n", theta="subatributo", color="atributo",
    category_orders={"subatributo": sub_order_asc, "atributo": attr_order_asc},
    color_discrete_map=color_map_resil,
    labels={"n": "N° experiencias", "subatributo": "Sub-atributo", "atributo": "Atributo"},
)
fig_sub.update_traces(hovertemplate="%{theta}<br>N° experiencias: %{r}<extra></extra>")
style_fig(fig_sub, height=560, title="Apariciones por sub-atributo de resiliencia — 19 sub-atributos, de menor a mayor", legend_title="Atributo")
st.plotly_chart(fig_sub, width="stretch")

st.caption(
    "Fuente: Race to Resilience Technical Secretariat (2023), \"Introduction to Resilience Attributes, "
    "Their Subcategories, and Their Role in the Race to Resilience Campaign\", CR2. "
    "Definiciones completas en la página Glosario."
)
