# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import plotly.express as px
import streamlit as st

from utils.data import (
    attach_map_dimensions,
    cap_categories,
    dimension_order,
    load_mapa_ubicaciones,
    load_noticias,
    map_color_options,
)
from utils.style import (
    DIMENSION_COLOR_MAPS,
    MAP_CENTER_CHILE,
    build_color_map,
    ensure_map_legend,
    inject,
    page_header,
    style_fig,
)

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
# en load_mapa_ubicaciones(). attach_map_dimensions() añade una columna *_primary por CADA
# dimensión clasificable del catálogo (DIMENSION_REGISTRY), para poder colorear por cualquiera.
mapa_full = attach_map_dimensions(mapa_full, df)
mapa = mapa_full[mapa_full["lat"].notna()].copy()

# Todas las clasificaciones de la base, no una lista recortada. Cuando una experiencia tiene
# varias etiquetas en una dimensión, el mapa usa la principal (la primera), igual que el resto
# de la plataforma.
DIM_OPTIONS = map_color_options()
DIM_HELP = {
    "Categoría macro": "De qué habla la experiencia, a nivel agregado (7 categorías). Ver Glosario.",
    "Categoría temática": "Categorías temáticas inductivas del análisis de contenido (varias por experiencia; se colorea por la principal).",
    "Metodología": "Método de facilitación con que se hizo la experiencia (se colorea por el principal).",
    "Actores institucionales": "Instituciones involucradas, normalizadas (se colorea por la principal).",
    "Eje GCAA": "Conexión con la Global Climate Action Agenda de la UNFCCC (6 ejes + 'No aplica'). Ver Glosario.",
    "Objetivo GCAA": "Objetivo específico dentro de la GCAA (se colorea por el principal). Ver Glosario.",
    "Atributo de resiliencia": "Atributo de resiliencia del CR2 que fortalece la experiencia (7 atributos + 'No aplica'). Ver Glosario.",
    "Sub-atributo de resiliencia": "Sub-atributo de resiliencia del CR2 (19 posibles; se colorea por el principal). Ver Glosario.",
    "Beneficiarios directos": "Quién se beneficia directamente de la experiencia (se colorea por el principal).",
    "Beneficiarios indirectos": "Quién se beneficia indirectamente de la experiencia (se colorea por el principal).",
    "Enfoque de género": "Si la experiencia tiene un foco explícito en mujeres, niñas u otra identidad de género.",
    "País": "País donde ocurre la experiencia.",
}
NOTA_PRIMARIA = (
    "Cuando una experiencia tiene varias etiquetas en esta dimensión, el mapa la colorea por "
    "su etiqueta principal (la primera), igual que el resto de la plataforma."
)

c1, c2 = st.columns([2, 1])
with c1:
    vista = st.radio(
        "Nivel de vista", ["Coordenadas específicas", "Ciudad / localidad", "País"], horizontal=True
    )
with c2:
    color_label = st.selectbox("Colorear por", list(DIM_OPTIONS.keys()))
    st.caption(DIM_HELP.get(color_label, NOTA_PRIMARIA))
color_col = DIM_OPTIONS[color_label]
# El orden y el mapa de color se derivan del catálogo completo (no de la vista actual), así una
# misma categoría mantiene su color y su lugar en la leyenda en las tres vistas.
order = dimension_order(mapa, color_col)
# Dimensiones con decenas de valores (p. ej. actores) colapsan la cola larga en "Otros" para
# que la leyenda del mapa siga siendo usable; las dimensiones acotadas no se tocan.
mapa[color_col], order = cap_categories(mapa[color_col], order)
color_map = DIMENSION_COLOR_MAPS.get(color_col) or build_color_map(order)
if "Otros" in order:
    st.caption(
        f"«{color_label}» tiene muchos valores distintos: se muestran los más frecuentes y el "
        "resto se agrupa en «Otros»."
    )

MAP_HEIGHT = 540

if vista == "Coordenadas específicas":
    fig = px.scatter_map(
        mapa, lat="lat", lon="lon", color=color_col,
        category_orders={color_col: order}, color_discrete_map=color_map,
        hover_name="titulo",
        hover_data={"lugar_texto": True, color_col: True, "lat": False, "lon": False},
        labels={color_col: color_label},
        center=MAP_CENTER_CHILE, zoom=3.0,
    )
    fig.update_layout(map_style="open-street-map")
    ensure_map_legend(fig, order, color_map)
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
        center=MAP_CENTER_CHILE, zoom=3.0, size_max=32,
    )
    fig.update_layout(map_style="open-street-map")
    ensure_map_legend(fig, order, color_map)
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
        center=MAP_CENTER_CHILE, zoom=1.5, size_max=45,
    )
    fig.update_layout(map_style="open-street-map")
    ensure_map_legend(fig, order, color_map)
    style_fig(fig, height=MAP_HEIGHT, title="Experiencias agrupadas por país", legend_title=color_label)
    st.plotly_chart(fig, width="stretch")
    st.dataframe(
        grp[["pais", "n"]].sort_values("n", ascending=False).rename(columns={"pais": "País", "n": "N° experiencias"}),
        hide_index=True, width="stretch", height=280,
    )

with st.expander("Por qué el color 'dominante' de una ciudad o país puede no coincidir con todos sus puntos"):
    st.markdown(
        "Cada ciudad o país agrupa varias experiencias, que pueden tener distintas categorías. "
        "El color de ese punto es la categoría **más frecuente dentro del grupo**, usando "
        "siempre la misma paleta que la vista de coordenadas — por eso el color de una misma "
        "categoría nunca cambia entre vistas. La **leyenda**, en cambio, siempre muestra la "
        "lista completa de categorías de la dimensión elegida (en el mismo orden y color en las "
        "tres vistas), aunque en la vista de país solo unas pocas lleguen a ser 'la más "
        "frecuente' de algún grupo."
    )
    st.markdown(
        f"El catálogo tiene **{len(mapa_full)}** menciones de sitio en total, pero "
        f"**{mapa_full['lat'].isna().sum()}** no tienen coordenadas porque son experiencias 100% online sin "
        "país específico, o describen 'varias regiones' sin un punto único que las represente."
    )
