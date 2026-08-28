# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import plotly.express as px
import streamlit as st

from utils.components import render_news_card
from utils.data import load_noticias
from utils.style import inject, page_header, section_label, style_fig

st.set_page_config(page_title="Línea de Tiempo", layout="wide")
inject()
page_header(
    "Recorrido histórico",
    "Línea de Tiempo",
    "Cada punto es una experiencia, ordenada por su fecha real de publicación en el sitio web (2010–2026).",
)

df = load_noticias()
con_fecha = df[df["tiene_fecha"]].copy()


@st.dialog("Ficha de la experiencia", width="large")
def _show_dialog(item_id: int):
    row = df[df["item"] == item_id].iloc[0]
    render_news_card(row)


DIM_OPTIONS = {
    "Categoría macro": "categoria_macro_primary",
    "Eje GCAA": "eje_gcaa_primary",
    "Atributo de resiliencia": "atributos_resiliencia_primary",
}

c1, c2 = st.columns(2)
with c1:
    dim_label = st.selectbox("Agrupar carriles por", list(DIM_OPTIONS.keys()), index=0)
with c2:
    color_label = st.selectbox("Colorear por", list(DIM_OPTIONS.keys()), index=0)

dim_col = DIM_OPTIONS[dim_label]
color_col = DIM_OPTIONS[color_label]

section_label("Cronología")
fig = px.scatter(
    con_fecha, x="fecha_parsed", y=dim_col, color=color_col,
    hover_name="titulo",
    hover_data={"fecha_parsed": "|%d %b %Y", dim_col: False, color_col: True},
    labels={"fecha_parsed": "Fecha", dim_col: dim_label, color_col: color_label},
)
fig.update_traces(marker=dict(size=9, line=dict(width=1, color="#FFFFFF")))
fig.update_yaxes(categoryorder="total ascending", title=None)
fig.update_xaxes(title="Fecha")
style_fig(fig, height=460, legend_title=color_label, title=f"Cronología de experiencias, agrupadas por {dim_label.lower()}")
st.plotly_chart(fig, width="stretch")

st.divider()

section_label("Explorar por año")
years = sorted(con_fecha["anio"].dropna().unique().astype(int).tolist(), reverse=True)
year_sel = st.select_slider("Año", options=years, value=years[0])
year_items = con_fecha[con_fecha["anio"] == year_sel].sort_values("fecha_parsed")
st.markdown(f"**{len(year_items)} experiencias en {year_sel}**")

for _, row in year_items.iterrows():
    with st.container(border=True):
        cA, cB, cC = st.columns([1, 4, 1])
        with cA:
            st.markdown(f"**{row['fecha_parsed'].strftime('%d %b %Y')}**")
        with cB:
            st.markdown(f"**{row['titulo']}**")
            tags = [row["categoria_macro_primary"]]
            if row["eje_gcaa_primary"].lower() != "no aplica":
                tags.append(row["eje_gcaa_primary"])
            st.caption(" · ".join(tags))
        with cC:
            if st.button("Ver ficha", key=f"ficha_{row['item']}", width="stretch"):
                _show_dialog(int(row["item"]))
