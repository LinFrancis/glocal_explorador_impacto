# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import plotly.express as px
import streamlit as st

from utils.components import render_news_card
from utils.data import load_cuencas, load_mapa_ubicaciones, load_noticias, load_subcuencas
from utils.style import inject, page_header, section_label, style_fig

st.set_page_config(page_title="Cuencas", layout="wide")
inject()
page_header(
    "Dato territorial",
    "Cuencas hidrográficas",
    "Vinculación territorial de las experiencias a la jerarquía de cuencas de Chile (BNA/DGA).",
)

mapa = load_mapa_ubicaciones()
cuencas = load_cuencas()
subcuencas = load_subcuencas()
df = load_noticias()


@st.dialog("Ficha de la experiencia", width="large")
def _show_dialog(item_id: int):
    row = df[df["item"] == item_id].iloc[0]
    render_news_card(row)


c1, c2, c3 = st.columns(3)
c1.metric("Cuencas de Chile en la base", len(cuencas))
c2.metric("Subcuencas", len(subcuencas))
c3.metric("Experiencias vinculadas a una cuenca", int(mapa["NOM_CUENCA"].notna().sum()))

vinculadas = mapa[mapa["NOM_CUENCA"].notna()].copy()
ranking = (
    vinculadas.groupby("NOM_CUENCA")
    .agg(n=("item", "count"), lat=("lat", "mean"), lon=("lon", "mean"))
    .reset_index()
    .sort_values("n", ascending=False)
)

section_label("Mapa de cuencas activas")
fig2 = px.scatter_map(
    ranking, lat="lat", lon="lon", size="n", color="n",
    hover_name="NOM_CUENCA", color_continuous_scale="Teal",
    labels={"n": "N° experiencias"},
    zoom=3, size_max=40,
)
fig2.update_layout(map_style="open-street-map")
style_fig(fig2, height=480, title="Cuencas activas — tamaño y color = N° de experiencias")
st.plotly_chart(fig2, width="stretch")

section_label("Ranking de cuencas con más experiencias")
top = ranking.head(20)
fig = px.bar(
    top.sort_values("n"), x="n", y="NOM_CUENCA", orientation="h",
    color="n", color_continuous_scale="Teal",
    labels={"n": "N° experiencias", "NOM_CUENCA": "Cuenca"},
)
fig.update_layout(coloraxis_showscale=False)
style_fig(fig, height=440, title="Top 20 cuencas con más experiencias vinculadas", showlegend=False)
st.plotly_chart(fig, width="stretch")

st.divider()

section_label("Explorar una cuenca en detalle")
cuenca_sel = st.selectbox(
    "Elegir cuenca", ranking["NOM_CUENCA"].tolist(),
    format_func=lambda n: f"{n} ({int(ranking.loc[ranking['NOM_CUENCA']==n,'n'].iloc[0])} experiencias)",
)

col_a, col_b = st.columns([3, 2])
with col_a:
    st.markdown(f"**Experiencias en la cuenca {cuenca_sel}** — haz clic en una fila para ver la ficha")
    items_cuenca = (
        vinculadas[vinculadas["NOM_CUENCA"] == cuenca_sel][["item", "titulo", "lugar_texto"]]
        .drop_duplicates(subset="item")
        .reset_index(drop=True)
    )
    event = st.dataframe(
        items_cuenca, hide_index=True, width="stretch", height=240,
        on_select="rerun", selection_mode="single-row",
    )
    selected = event.selection.rows if event and event.selection else []
    if selected:
        _show_dialog(int(items_cuenca.iloc[selected[0]]["item"]))

with col_b:
    st.markdown(f"**Subcuencas de {cuenca_sel}** (jerarquía BNA, informativo)")
    cod_match = cuencas.loc[cuencas["NOM_CUEN"] == cuenca_sel, "COD_CUEN"]
    if len(cod_match):
        subc = subcuencas[subcuencas["COD_CUEN"] == cod_match.iloc[0]][["COD_SUBC", "NOM_SUBC", "num_subsubcuencas"]]
        st.dataframe(subc, hide_index=True, width="stretch", height=240)
    else:
        st.caption("Sin coincidencia en la tabla de referencia de cuencas.")

st.caption(
    "La vinculación experiencia → cuenca se hizo por unión espacial automática (punto dentro de polígono). "
    "El detalle de subcuenca es la jerarquía completa de esa cuenca, no una asignación experiencia-a-subcuenca."
)
