# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import plotly.express as px
import streamlit as st

from utils.data import extract_country, load_mapa_ubicaciones, load_noticias
from utils.style import inject, page_header, style_fig

st.set_page_config(page_title="Mapa", layout="wide")
inject()
page_header(
    "Vista geográfica",
    "Mapa de experiencias",
    "Tres niveles de vista: país, ciudad/localidad, y coordenadas específicas.",
)

mapa_full = load_mapa_ubicaciones()
df = load_noticias()

mapa = mapa_full[mapa_full["lat"].notna()].copy()
extra = df[["item", "atributos_resiliencia", "enfoque_genero"]]
mapa = mapa.merge(extra, on="item", how="left")


def _primary(value):
    if not isinstance(value, str) or not value.strip():
        return "Sin dato"
    first = value.split(";")[0].strip()
    return first if first else "Sin dato"


mapa["categoria_macro_p"] = mapa["categoria_macro"].apply(_primary)
mapa["eje_gcaa_p"] = mapa["eje_gcaa"].apply(_primary)
mapa["atributos_resiliencia_p"] = mapa["atributos_resiliencia"].apply(_primary)
mapa["enfoque_genero_p"] = mapa["enfoque_genero"].apply(
    lambda v: "Sí" if isinstance(v, str) and v.startswith("Sí") else "No"
)
mapa["pais"] = mapa["coincidencia_osm"].apply(extract_country).fillna("Sin dato")

DIM_OPTIONS = {
    "Categoría macro": "categoria_macro_p",
    "Eje GCAA": "eje_gcaa_p",
    "Atributo de resiliencia": "atributos_resiliencia_p",
    "Enfoque de género": "enfoque_genero_p",
}

c1, c2 = st.columns([2, 1])
with c1:
    vista = st.radio(
        "Nivel de vista", ["Coordenadas específicas", "Ciudad / localidad", "País"], horizontal=True
    )
with c2:
    color_label = st.selectbox("Colorear por", list(DIM_OPTIONS.keys()))
color_col = DIM_OPTIONS[color_label]

if vista == "Coordenadas específicas":
    fig = px.scatter_map(
        mapa, lat="lat", lon="lon", color=color_col,
        hover_name="titulo",
        hover_data={"lugar_texto": True, color_col: True, "lat": False, "lon": False},
        labels={color_col: color_label},
        zoom=2.2,
    )
    fig.update_layout(map_style="open-street-map", margin=dict(l=0, r=0, t=54, b=0))
    style_fig(fig, height=680, title=f"Ubicación exacta de cada experiencia, coloreado por {color_label.lower()}", legend_title=color_label)
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"{len(mapa)} puntos geolocalizados, de {mapa['lugar_texto'].nunique()} lugares únicos.")

elif vista == "Ciudad / localidad":
    grp = (
        mapa.groupby("lugar_texto")
        .agg(
            lat=("lat", "mean"),
            lon=("lon", "mean"),
            n=("item", "count"),
            dominante=(color_col, lambda s: s.mode().iat[0] if not s.mode().empty else "Sin dato"),
        )
        .reset_index()
    )
    fig = px.scatter_map(
        grp, lat="lat", lon="lon", size="n", color="dominante",
        hover_name="lugar_texto", hover_data={"n": True, "lat": False, "lon": False},
        labels={"dominante": color_label, "n": "N° experiencias"},
        zoom=2.2, size_max=38,
    )
    fig.update_layout(map_style="open-street-map", margin=dict(l=0, r=0, t=54, b=0))
    style_fig(fig, height=680, title="Experiencias agrupadas por ciudad / localidad", legend_title=color_label)
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"{len(grp)} lugares agregados. Color = {color_label.lower()} más frecuente en ese lugar; "
        "tamaño = N° de experiencias."
    )

else:  # País
    grp = (
        mapa.groupby("pais")
        .agg(
            lat=("lat", "mean"),
            lon=("lon", "mean"),
            n=("item", "count"),
            dominante=(color_col, lambda s: s.mode().iat[0] if not s.mode().empty else "Sin dato"),
        )
        .reset_index()
    )
    fig = px.scatter_map(
        grp, lat="lat", lon="lon", size="n", color="dominante",
        hover_name="pais", hover_data={"n": True, "lat": False, "lon": False},
        labels={"dominante": color_label, "n": "N° experiencias"},
        zoom=1.2, size_max=55,
    )
    fig.update_layout(map_style="open-street-map", margin=dict(l=0, r=0, t=54, b=0))
    style_fig(fig, height=560, title="Experiencias agrupadas por país", legend_title=color_label)
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(
        grp[["pais", "n"]].sort_values("n", ascending=False).rename(columns={"pais": "País", "n": "N° experiencias"}),
        hide_index=True, use_container_width=True,
    )

with st.expander("Por qué hay menos de 350 puntos en pantalla"):
    st.markdown(
        f"El catálogo tiene **{len(mapa_full)}** menciones de sitio en total, pero "
        f"**{mapa_full['lat'].isna().sum()}** no tienen coordenadas porque son experiencias 100% online sin "
        "país específico, o describen 'varias regiones' sin un punto único que las represente. "
        "El detalle de precisión de geocodificación está en la columna `precision_geocodificacion`."
    )
