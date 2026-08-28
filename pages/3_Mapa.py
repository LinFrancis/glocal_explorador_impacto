# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import plotly.express as px
import streamlit as st

from utils.data import dimension_order, genero_label, load_mapa_ubicaciones, load_noticias
from utils.style import DIMENSION_COLOR_MAPS, inject, page_header, style_fig

st.set_page_config(page_title="Mapa", layout="wide")
inject()
page_header(
    "Vista geográfica",
    "Mapa de experiencias",
    "Tres niveles de vista: país, ciudad/localidad y coordenadas específicas. Cada categoría usa "
    "siempre el mismo color y el mismo orden, sin importar el nivel de agregación elegido.",
)

mapa_full = load_mapa_ubicaciones()
df = load_noticias()

# `pais`, `categoria_macro_primary` y `eje_gcaa_primary` ya vienen calculados de forma centralizada
# en load_mapa_ubicaciones(); solo se agregan aquí las dimensiones que no viven en esa hoja.
mapa = mapa_full[mapa_full["lat"].notna()].copy()
extra = df[["item", "atributos_resiliencia_primary", "enfoque_genero"]].copy()
extra["enfoque_genero_primary"] = extra["enfoque_genero"].apply(genero_label)
mapa = mapa.merge(extra.drop(columns="enfoque_genero"), on="item", how="left")

DIM_OPTIONS = {
    "Categoría macro": "categoria_macro_primary",
    "Eje GCAA": "eje_gcaa_primary",
    "Atributo de resiliencia": "atributos_resiliencia_primary",
    "Enfoque de género": "enfoque_genero_primary",
}
DIM_HELP = {
    "Categoría macro": "De qué habla la experiencia, a nivel agregado (7 categorías). Ver Glosario para el detalle de cada una.",
    "Eje GCAA": "Conexión con la Global Climate Action Agenda de la UNFCCC (6 ejes + 'No aplica'). Ver Glosario.",
    "Atributo de resiliencia": "Atributo de resiliencia del CR2 que fortalece la experiencia (7 atributos + 'No aplica'). Ver Glosario.",
    "Enfoque de género": "Si la experiencia tiene un foco explícito en mujeres, niñas u otra identidad de género.",
}

c1, c2 = st.columns([2, 1])
with c1:
    vista = st.radio(
        "Nivel de vista", ["Coordenadas específicas", "Ciudad / localidad", "País"], horizontal=True
    )
with c2:
    color_label = st.selectbox("Colorear por", list(DIM_OPTIONS.keys()))
    st.caption(DIM_HELP[color_label])
color_col = DIM_OPTIONS[color_label]
order = dimension_order(mapa, color_col)
color_map = DIMENSION_COLOR_MAPS.get(color_col)

MAP_HEIGHT = 540

if vista == "Coordenadas específicas":
    fig = px.scatter_map(
        mapa, lat="lat", lon="lon", color=color_col,
        category_orders={color_col: order}, color_discrete_map=color_map,
        hover_name="titulo",
        hover_data={"lugar_texto": True, color_col: True, "lat": False, "lon": False},
        labels={color_col: color_label},
        zoom=2.2,
    )
    fig.update_layout(map_style="open-street-map")
    style_fig(fig, height=MAP_HEIGHT, title=f"Ubicación exacta, coloreado por {color_label.lower()}", legend_title=color_label)
    st.plotly_chart(fig, width="stretch")
    st.caption(f"{len(mapa)} puntos geolocalizados, de {mapa['lugar_texto'].nunique()} lugares únicos.")

elif vista == "Ciudad / localidad":
    grp = (
        mapa.groupby("lugar_texto")
        .agg(
            lat=("lat", "mean"), lon=("lon", "mean"), n=("item", "count"),
            dominante=(color_col, lambda s: s.mode().iat[0] if not s.mode().empty else "Sin dato"),
        )
        .reset_index()
    )
    fig = px.scatter_map(
        grp, lat="lat", lon="lon", size="n", color="dominante",
        category_orders={"dominante": order}, color_discrete_map=color_map,
        hover_name="lugar_texto", hover_data={"n": True, "lat": False, "lon": False},
        labels={"dominante": color_label, "n": "N° experiencias"},
        zoom=2.2, size_max=32,
    )
    fig.update_layout(map_style="open-street-map")
    style_fig(fig, height=MAP_HEIGHT, title="Experiencias agrupadas por ciudad / localidad", legend_title=color_label)
    st.plotly_chart(fig, width="stretch")
    st.caption(
        f"{len(grp)} lugares agregados. Color = {color_label.lower()} más frecuente en ese lugar "
        "(mismo color que en la vista de coordenadas); tamaño = N° de experiencias."
    )

else:  # País
    grp = (
        mapa.groupby("pais")
        .agg(
            lat=("lat", "mean"), lon=("lon", "mean"), n=("item", "count"),
            dominante=(color_col, lambda s: s.mode().iat[0] if not s.mode().empty else "Sin dato"),
        )
        .reset_index()
    )
    fig = px.scatter_map(
        grp, lat="lat", lon="lon", size="n", color="dominante",
        category_orders={"dominante": order}, color_discrete_map=color_map,
        hover_name="pais", hover_data={"n": True, "lat": False, "lon": False},
        labels={"dominante": color_label, "n": "N° experiencias"},
        zoom=1.1, size_max=45,
    )
    fig.update_layout(map_style="open-street-map")
    style_fig(fig, height=MAP_HEIGHT, title="Experiencias agrupadas por país", legend_title=color_label)
    st.plotly_chart(fig, width="stretch")
    st.dataframe(
        grp[["pais", "n"]].sort_values("n", ascending=False).rename(columns={"pais": "País", "n": "N° experiencias"}),
        hide_index=True, width="stretch", height=280,
    )

with st.expander("Por qué el color 'dominante' de una ciudad o país puede no coincidir con todos sus puntos"):
    st.markdown(
        "Cada ciudad o país agrupa varias experiencias, que pueden tener distintas categorías. "
        "El color que se muestra es la categoría **más frecuente dentro de ese grupo**, usando "
        "siempre la misma paleta que la vista de coordenadas — por eso el color de una misma "
        "categoría nunca cambia, aunque la cantidad de categorías visibles pueda variar según "
        "cuántas lleguen a ser 'la más frecuente' en algún grupo."
    )
    st.markdown(
        f"El catálogo tiene **{len(mapa_full)}** menciones de sitio en total, pero "
        f"**{mapa_full['lat'].isna().sum()}** no tienen coordenadas porque son experiencias 100% online sin "
        "país específico, o describen 'varias regiones' sin un punto único que las represente."
    )
