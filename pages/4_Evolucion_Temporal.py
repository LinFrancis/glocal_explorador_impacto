# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.components import render_news_card
from utils.data import dimension_order, load_mapa_ubicaciones, load_noticias
from utils.style import DIMENSION_COLOR_MAPS, inject, page_header, section_label, style_fig

st.set_page_config(page_title="Evolución Temporal", layout="wide")
inject()
page_header(
    "Serie histórica y cronología",
    "Evolución en el Tiempo",
    "258 experiencias con fecha real, obtenida directamente del sitio web (2010–2026).",
)

df = load_noticias()
con_fecha = df[df["tiene_fecha"]].copy()
con_fecha["anio"] = con_fecha["anio"].astype(int)
anio_min, anio_max = int(con_fecha["anio"].min()), int(con_fecha["anio"].max())


@st.dialog("Ficha de la experiencia", width="large")
def _show_dialog(item_id: int):
    row = df[df["item"] == item_id].iloc[0]
    render_news_card(row)


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
    "Categoría macro": "categoria_macro_primary",
    "Eje GCAA": "eje_gcaa_primary",
    "Atributo de resiliencia": "atributos_resiliencia_primary",
}
dim_label = st.selectbox("Desglosar por", list(DIM_OPTIONS.keys()))
dim_col = DIM_OPTIONS[dim_label]
color_map = DIMENSION_COLOR_MAPS.get(dim_col)

# ==================================================================== SERIES POR AÑO
section_label(f"Experiencias por año ({len(con_fecha)} con fecha)")
por_anio = con_fecha.groupby("anio").size().reset_index(name="n")
fig1 = px.bar(por_anio, x="anio", y="n", labels={"anio": "Año", "n": "N° experiencias"})
fig1.update_traces(marker_color="#0B6E4F", name="Experiencias", showlegend=True)
style_fig(fig1, height=300, title="Cantidad de experiencias publicadas por año", legend_title="Serie")
st.plotly_chart(fig1, width="stretch")

section_label(f"Desglose por {dim_label.lower()} y año")
raw_col = dim_col.replace("_primary", "")
exploded = con_fecha.assign(**{raw_col: con_fecha[raw_col].str.split(";")}).explode(raw_col)
exploded[raw_col] = exploded[raw_col].str.strip()
exploded = exploded[(exploded[raw_col] != "") & (exploded[raw_col].str.lower() != "no aplica")]

if len(exploded):
    stacked = exploded.groupby(["anio", raw_col]).size().reset_index(name="n")
    order = [c for c in dimension_order(con_fecha, dim_col) if c in stacked[raw_col].unique()]
    fig2 = px.bar(
        stacked, x="anio", y="n", color=raw_col,
        category_orders={raw_col: order}, color_discrete_map=color_map,
        labels={"anio": "Año", "n": "N° experiencias", raw_col: dim_label},
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

# ==================================================================== ANIMACIONES
section_label("Avance dinámico por categoría")
st.caption("Presiona Play para ver cómo creció cada categoría macro, año a año.")

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

macro_order = dimension_order(con_fecha, "categoria_macro_primary")
macro_order = [c for c in macro_order if c in cum.columns]
long_df = cum.reset_index().melt(id_vars="anio", var_name="categoria_macro", value_name="acumulado")

fig_race = px.bar(
    long_df, x="acumulado", y="categoria_macro", color="categoria_macro",
    animation_frame="anio", orientation="h",
    range_x=[0, float(cum.values.max()) * 1.1],
    category_orders={"categoria_macro": macro_order},
    color_discrete_map=DIMENSION_COLOR_MAPS.get("categoria_macro_primary"),
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

section_label("Avance dinámico por zona geográfica")
st.caption("Presiona Play para ver cómo se expandió el catálogo en el mapa, año a año.")

mapa = load_mapa_ubicaciones()
mapa = mapa[mapa["lat"].notna()].copy()
mapa = mapa.merge(df[["item", "anio", "tiene_fecha"]], on="item", how="left")
mapa_fecha = mapa[mapa["tiene_fecha"] == True].copy()
mapa_fecha["anio"] = mapa_fecha["anio"].astype(int)
# categoria_macro_primary ya viene calculada de forma centralizada en load_mapa_ubicaciones()

mapa_fecha["marker_size"] = 1

# Plotly Express solo crea una traza animada por categoría si esta aparece en el PRIMER
# frame; si una categoría macro no tiene ningún punto geolocalizado en el año más antiguo,
# desaparece de la animación completa (incluso en años posteriores donde sí hay datos).
# Se agregan puntos "ancla" invisibles (tamaño 0) para las 7 categorías en cada frame, así
# la traza de cada categoría existe desde el inicio y nunca se pierde durante la animación.
lat_centro = mapa_fecha["lat"].mean()
lon_centro = mapa_fecha["lon"].mean()
anclas = pd.DataFrame({
    "categoria_macro_primary": macro_order,
    "lat": lat_centro,
    "lon": lon_centro,
    "titulo": "",
    "lugar_texto": "",
    "marker_size": 0,
})

frames = []
for y in range(anio_min, anio_max + 1):
    sub = mapa_fecha[mapa_fecha["anio"] <= y].copy()
    sub["frame_anio"] = y
    anclas_y = anclas.copy()
    anclas_y["frame_anio"] = y
    frames.append(pd.concat([sub, anclas_y], ignore_index=True))
cum_map_df = pd.concat(frames, ignore_index=True)

fig_map = px.scatter_map(
    cum_map_df, lat="lat", lon="lon", color="categoria_macro_primary",
    size="marker_size", size_max=9,
    category_orders={"categoria_macro_primary": macro_order},
    color_discrete_map=DIMENSION_COLOR_MAPS.get("categoria_macro_primary"),
    animation_frame="frame_anio", hover_name="titulo",
    hover_data={"lugar_texto": True, "lat": False, "lon": False, "marker_size": False},
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

st.divider()

# ==================================================================== CRONOLOGÍA
section_label("Cronología experiencia por experiencia")
st.caption("Cada punto es una experiencia individual, ordenada por su fecha real de publicación.")

carril_label = st.selectbox("Agrupar carriles por", list(DIM_OPTIONS.keys()), index=0, key="carril_sel")
carril_col = DIM_OPTIONS[carril_label]
carril_order = dimension_order(con_fecha, carril_col)
color_map_carril = DIMENSION_COLOR_MAPS.get(carril_col)

fig_swim = px.scatter(
    con_fecha, x="fecha_parsed", y=carril_col, color=carril_col,
    category_orders={carril_col: carril_order}, color_discrete_map=color_map_carril,
    hover_name="titulo",
    hover_data={"fecha_parsed": "|%d %b %Y", carril_col: False},
    labels={"fecha_parsed": "Fecha", carril_col: carril_label},
)
fig_swim.update_traces(marker=dict(size=9, line=dict(width=1, color="#FFFFFF")))
fig_swim.update_yaxes(title=None, categoryorder="array", categoryarray=carril_order)
fig_swim.update_xaxes(title="Fecha")
style_fig(fig_swim, height=460, legend_title=carril_label, title=f"Cronología de experiencias, agrupadas por {carril_label.lower()}")
st.plotly_chart(fig_swim, width="stretch")

st.divider()

# ==================================================================== EXPLORAR POR AÑO
section_label("Explorar experiencias por año")
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
