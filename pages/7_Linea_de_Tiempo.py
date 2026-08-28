# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import plotly.express as px
import streamlit as st

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

DIM_OPTIONS = {
    "Categoría macro": "categoria_macro",
    "Eje GCAA": "eje_gcaa",
    "Atributo de resiliencia": "atributos_resiliencia",
}

c1, c2 = st.columns(2)
with c1:
    dim_label = st.selectbox("Agrupar carriles por", list(DIM_OPTIONS.keys()), index=0)
with c2:
    color_label = st.selectbox("Colorear por", list(DIM_OPTIONS.keys()), index=0)

dim_col = DIM_OPTIONS[dim_label]
color_col = DIM_OPTIONS[color_label]


def _primary(v):
    if not isinstance(v, str) or not v.strip():
        return "Sin dato"
    return v.split(";")[0].strip()


plot_df = con_fecha.copy()
plot_df["carril"] = plot_df[dim_col].apply(_primary)
plot_df["color_dim"] = plot_df[color_col].apply(_primary)

section_label("Cronología")
fig = px.scatter(
    plot_df, x="fecha_parsed", y="carril", color="color_dim",
    hover_name="titulo",
    hover_data={"fecha_parsed": "|%d %b %Y", "carril": False, "color_dim": True},
    labels={"fecha_parsed": "Fecha", "carril": dim_label, "color_dim": color_label},
)
fig.update_traces(marker=dict(size=10, line=dict(width=1, color="#FFFFFF")))
fig.update_yaxes(categoryorder="total ascending", title=None)
fig.update_xaxes(title="Fecha")
style_fig(fig, height=560, legend_title=color_label, title=f"Cronología de experiencias, agrupadas por {dim_label.lower()}")
st.plotly_chart(fig, use_container_width=True)

st.divider()

section_label("Explorar por año")
years = sorted(con_fecha["anio"].dropna().unique().astype(int).tolist(), reverse=True)
year_sel = st.select_slider("Año", options=years, value=years[0])
year_items = con_fecha[con_fecha["anio"] == year_sel].sort_values("fecha_parsed")
st.markdown(f"**{len(year_items)} experiencias en {year_sel}**")

for _, row in year_items.iterrows():
    with st.container(border=True):
        cA, cB = st.columns([1, 5])
        with cA:
            st.markdown(f"**{row['fecha_parsed'].strftime('%d %b %Y')}**")
        with cB:
            st.markdown(f"**{row['titulo']}**")
            eje = row["eje_gcaa"] if row["eje_gcaa"].strip().lower() != "no aplica" else None
            tags = [row["categoria_macro"].split(";")[0].strip()]
            if eje:
                tags.append(eje.split(";")[0].strip())
            st.caption(" · ".join(tags))
