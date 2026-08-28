# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.data import load_mapa_ubicaciones, load_noticias
from utils.style import inject, page_header, section_label, style_fig

st.set_page_config(page_title="Evolución Temporal", layout="wide")
inject()
page_header(
    "Serie histórica",
    "Evolución en el tiempo",
    "258 experiencias con fecha real, obtenida directamente del sitio web (2010–2026).",
)

df = load_noticias()
con_fecha = df[df["tiene_fecha"]].copy()
con_fecha["anio"] = con_fecha["anio"].astype(int)
anio_min, anio_max = int(con_fecha["anio"].min()), int(con_fecha["anio"].max())

cobertura = len(con_fecha) / len(df)
if cobertura >= 0.99:
    st.success(
        f"{len(con_fecha)} de {len(df)} experiencias ({cobertura:.0%}) tienen fecha, obtenida directamente "
        "del sitio web (WordPress) — no depende de que el texto la mencione.",
    )
else:
    st.warning(
        f"Solo {len(con_fecha)} de {len(df)} experiencias ({cobertura:.0%}) tienen fecha registrada. "
        "Los gráficos de esta página reflejan solo el subconjunto con fecha.",
    )

DIM_OPTIONS = {
    "Categoría macro": "categoria_macro",
    "Eje GCAA": "eje_gcaa",
    "Atributo de resiliencia": "atributos_resiliencia",
}
dim_label = st.selectbox("Desglosar por", list(DIM_OPTIONS.keys()))
dim_col = DIM_OPTIONS[dim_label]

section_label(f"Experiencias por año ({len(con_fecha)} con fecha)")
por_anio = con_fecha.groupby("anio").size().reset_index(name="n")
fig1 = px.bar(por_anio, x="anio", y="n", labels={"anio": "Año", "n": "N° experiencias"})
fig1.update_traces(marker_color="#0B6E4F", name="Experiencias", showlegend=True)
style_fig(fig1, height=300, title="Cantidad de experiencias publicadas por año", legend_title="Serie")
st.plotly_chart(fig1, width="stretch")

section_label(f"Desglose por {dim_label.lower()} y año")
exploded = con_fecha.assign(**{dim_col: con_fecha[dim_col].str.split(";")}).explode(dim_col)
exploded[dim_col] = exploded[dim_col].str.strip()
exploded = exploded[(exploded[dim_col] != "") & (exploded[dim_col].str.lower() != "no aplica")]

if len(exploded):
    stacked = exploded.groupby(["anio", dim_col]).size().reset_index(name="n")
    fig2 = px.bar(
        stacked, x="anio", y="n", color=dim_col,
        labels={"anio": "Año", "n": "N° experiencias", dim_col: dim_label},
    )
    style_fig(fig2, height=380, title=f"Experiencias por año, desglosadas por {dim_label.lower()}", legend_title=dim_label)
    st.plotly_chart(fig2, width="stretch")
else:
    st.info(f"No hay experiencias con fecha y con un valor de '{dim_label}' distinto de 'No aplica'.")

section_label("Crecimiento acumulado")
acumulado = por_anio.sort_values("anio").copy()
acumulado["acumulado"] = acumulado["n"].cumsum()
fig3 = px.line(acumulado, x="anio", y="acumulado", markers=True, labels={"anio": "Año", "acumulado": "Total acumulado"})
fig3.update_traces(line_color="#0B6E4F", name="Total acumulado", showlegend=True)
style_fig(fig3, height=280, title="Crecimiento acumulado del catálogo", legend_title="Serie")
st.plotly_chart(fig3, width="stretch")

st.divider()

# =================================================================== ANIMACIONES
st.markdown("## Avance dinámico en el tiempo")
st.caption("Presiona Play para ver cómo se construyó el catálogo, año a año.")

anim_tab1, anim_tab2 = st.tabs(["Por categoría", "Por zona geográfica"])

# ---------------------------------------------------------- Animación por categoría (bar chart race)
with anim_tab1:
    exploded_macro = con_fecha.assign(
        categoria_macro=con_fecha["categoria_macro"].str.split(";")
    ).explode("categoria_macro")
    exploded_macro["categoria_macro"] = exploded_macro["categoria_macro"].str.strip()
    exploded_macro = exploded_macro[exploded_macro["categoria_macro"] != ""]

    counts_year_cat = exploded_macro.groupby(["anio", "categoria_macro"]).size().reset_index(name="n")
    pivot = counts_year_cat.pivot(index="anio", columns="categoria_macro", values="n").fillna(0)
    full_years = range(anio_min, anio_max + 1)
    pivot = pivot.reindex(full_years, fill_value=0)
    cum = pivot.cumsum()

    final_order = cum.iloc[-1].sort_values(ascending=False).index.tolist()
    long_df = cum.reset_index().melt(id_vars="anio", var_name="categoria_macro", value_name="acumulado")

    fig_race = px.bar(
        long_df, x="acumulado", y="categoria_macro", color="categoria_macro",
        animation_frame="anio", orientation="h",
        range_x=[0, float(cum.values.max()) * 1.1],
        category_orders={"categoria_macro": final_order},
        labels={"acumulado": "Total acumulado", "categoria_macro": "Categoría macro", "anio": "Año"},
    )
    style_fig(
        fig_race, height=440,
        title="Avance acumulado por categoría macro (2010–2026)",
        legend_title="Categoría macro", showlegend=False,
    )
    if fig_race.layout.updatemenus:
        fig_race.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"] = 700
        fig_race.layout.updatemenus[0].buttons[0].args[1]["transition"]["duration"] = 350
        fig_race.layout.updatemenus[0].buttons[0].args[1]["transition"]["easing"] = "cubic-in-out"
    st.plotly_chart(fig_race, width="stretch")
    st.caption("Cada barra muestra el total acumulado de experiencias de esa categoría hasta el año seleccionado.")

# ---------------------------------------------------------- Animación por zona (mapa acumulado)
with anim_tab2:
    mapa = load_mapa_ubicaciones()
    mapa = mapa[mapa["lat"].notna()].copy()
    mapa = mapa.merge(df[["item", "anio", "tiene_fecha"]], on="item", how="left")
    mapa_fecha = mapa[mapa["tiene_fecha"] == True].copy()
    mapa_fecha["anio"] = mapa_fecha["anio"].astype(int)
    # categoria_macro_primary ya viene calculada de forma centralizada en load_mapa_ubicaciones()

    frames = []
    for y in range(anio_min, anio_max + 1):
        sub = mapa_fecha[mapa_fecha["anio"] <= y].copy()
        sub["frame_anio"] = y
        frames.append(sub)
    cum_map_df = pd.concat(frames, ignore_index=True)

    fig_map = px.scatter_map(
        cum_map_df, lat="lat", lon="lon", color="categoria_macro_primary",
        animation_frame="frame_anio", hover_name="titulo",
        hover_data={"lugar_texto": True, "lat": False, "lon": False},
        labels={"categoria_macro_primary": "Categoría macro", "frame_anio": "Año"},
        zoom=1.4,
    )
    fig_map.update_layout(map_style="open-street-map")
    style_fig(fig_map, height=560, title="Expansión geográfica acumulada, año a año", legend_title="Categoría macro")
    if fig_map.layout.updatemenus:
        fig_map.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"] = 700
        fig_map.layout.updatemenus[0].buttons[0].args[1]["transition"]["duration"] = 350
    st.plotly_chart(fig_map, width="stretch")
    st.caption(
        f"Muestra todas las experiencias geolocalizadas con fecha ({mapa_fecha['item'].nunique()} "
        f"experiencias, {mapa_fecha['lugar_texto'].nunique()} lugares), acumuladas hasta el año seleccionado."
    )
