# -*- coding: utf-8 -*-
"""Sección 'Cuencas' dentro de Explorador Glocal (antes página propia)."""
import plotly.express as px
import streamlit as st

from utils.components import render_news_card
from utils.data import load_cuencas, load_mapa_ubicaciones, load_subcuencas
from utils.filters import entidad_titulo_sufijo
from utils.style import MAP_CENTER_CHILE, section_label, style_fig


def render(df, criterios=None):
    sufijo = entidad_titulo_sufijo(criterios)

    if df.empty:
        st.info("Ningún resultado con los criterios de búsqueda actuales.")
        return

    cuencas = load_cuencas()
    subcuencas = load_subcuencas()
    mapa_full = load_mapa_ubicaciones()
    mapa = mapa_full[mapa_full["item"].isin(df["item"])]

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

    if ranking.empty:
        st.info("Ninguna experiencia filtrada está vinculada a una cuenca.")
        return

    section_label("Mapa de cuencas activas")
    fig2 = px.scatter_map(
        ranking, lat="lat", lon="lon", size="n", color="n",
        hover_name="NOM_CUENCA", color_continuous_scale="Teal",
        labels={"n": "N° experiencias"},
        center=MAP_CENTER_CHILE, zoom=3.2, size_max=40,
    )
    fig2.update_layout(map_style="open-street-map")
    style_fig(fig2, height=480, title=f"Cuencas activas — tamaño y color = N° de experiencias{sufijo}")
    st.plotly_chart(fig2, width="stretch", key="cuencas_fig_mapa")

    section_label("Ranking de cuencas con más experiencias")
    top = ranking.head(20)
    fig = px.bar(
        top.sort_values("n"), x="n", y="NOM_CUENCA", orientation="h",
        color="n", color_continuous_scale="Teal",
        labels={"n": "N° experiencias", "NOM_CUENCA": "Cuenca"},
    )
    fig.update_layout(coloraxis_showscale=False)
    style_fig(fig, height=440, title=f"Top 20 cuencas con más experiencias vinculadas{sufijo}", showlegend=False)
    st.plotly_chart(fig, width="stretch", key="cuencas_fig_ranking")

    st.divider()

    section_label("Explorar una cuenca en detalle")
    cuenca_sel = st.selectbox(
        "Elegir cuenca", ranking["NOM_CUENCA"].tolist(),
        format_func=lambda n: f"{n} ({int(ranking.loc[ranking['NOM_CUENCA']==n,'n'].iloc[0])} experiencias)",
        key="cuencas_cuenca_sel",
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
            on_select="rerun", selection_mode="single-row", key="cuencas_tabla_items",
        )
        selected = event.selection.rows if event and event.selection else []
        if selected:
            _show_dialog(int(items_cuenca.iloc[selected[0]]["item"]))

    with col_b:
        st.markdown(f"**Subcuencas de {cuenca_sel}** (jerarquía BNA, informativo)")
        cod_match = cuencas.loc[cuencas["NOM_CUEN"] == cuenca_sel, "COD_CUEN"]
        if len(cod_match):
            subc = subcuencas[subcuencas["COD_CUEN"] == cod_match.iloc[0]][["COD_SUBC", "NOM_SUBC", "num_subsubcuencas"]]
            st.dataframe(subc, hide_index=True, width="stretch", height=240, key="cuencas_tabla_subcuencas")
        else:
            st.caption("Sin coincidencia en la tabla de referencia de cuencas.")

    st.caption(
        "La vinculación experiencia → cuenca se hizo por unión espacial automática (punto dentro de polígono). "
        "El detalle de subcuenca es la jerarquía completa de esa cuenca, no una asignación experiencia-a-subcuenca."
    )
