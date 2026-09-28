# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from sections import cruces, cuencas, evolucion, mapa, resultados
from utils.data import load_noticias
from utils.filters import apply_search_filters, render_search_filters
from utils.style import inject, page_header

st.set_page_config(page_title="Explorador Glocal", layout="wide")
inject()

df_total = load_noticias()

with st.sidebar:
    criterios = render_search_filters(df_total)
    st.divider()
    st.markdown("**Ir a:**")
    st.markdown(
        "- [Resultados](#resultados)\n"
        "- [Mapa](#mapa)\n"
        "- [Evolución en el tiempo](#evolucion)\n"
        "- [Cruces y correlaciones](#cruces)\n"
        "- [Cuencas](#cuencas)"
    )

page_header(
    "Búsqueda multicriterio",
    "Explorador Glocal",
    "Combina cualquier número de filtros. Dentro de un mismo filtro se combina con 'o'; entre "
    "filtros distintos, con 'y'. Estos mismos criterios gobiernan todas las secciones de abajo "
    "(Mapa, Evolución, Cruces, Cuencas) — para ver todo, quita los filtros.",
)

df = apply_search_filters(df_total, criterios)
st.metric("Experiencias encontradas", f"{len(df)} de {len(df_total)}")

df_dedup = df[~df["es_duplicado_secundario"].astype(bool)] if "es_duplicado_secundario" in df.columns else df

st.markdown('<div id="resultados"></div>', unsafe_allow_html=True)
with st.expander(f"📋 Resultados ({len(df)})", expanded=False):
    resultados.render(df)

st.markdown('<div id="mapa"></div>', unsafe_allow_html=True)
with st.expander("🗺️ Mapa", expanded=False):
    mapa.render(df, criterios)

st.markdown('<div id="evolucion"></div>', unsafe_allow_html=True)
with st.expander("📈 Evolución en el Tiempo", expanded=False):
    evolucion.render(df_dedup, criterios)

st.markdown('<div id="cruces"></div>', unsafe_allow_html=True)
with st.expander("🔀 Cruces y Correlaciones", expanded=False):
    cruces.render(df_dedup, criterios)

st.markdown('<div id="cuencas"></div>', unsafe_allow_html=True)
with st.expander("🌊 Cuencas", expanded=False):
    cuencas.render(df_dedup, criterios)
