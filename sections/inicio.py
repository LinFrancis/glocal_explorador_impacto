# -*- coding: utf-8 -*-
"""Panorama general (página 'Inicio'). Respeta los criterios de búsqueda activos."""
import plotly.express as px
import streamlit as st

from utils.data import get_options, load_mapa_ubicaciones
from utils.filters import entidad_titulo_sufijo, filters_summary_widget, get_filtered_df
from utils.style import dual_logo_html, inject, page_header, section_label, style_fig


def render():
    inject()

    with st.sidebar:
        filters_summary_widget()

    st.markdown(dual_logo_html(height=56), unsafe_allow_html=True)

    page_header(
        "Explorador Impacto Glocal",
        "Panorama general del catálogo",
        "Catálogo de experiencias de facilitación de Glocalminds y Fundación Glocal, mapeadas contra "
        "marcos internacionales de acción climática y resiliencia. Si hay criterios de búsqueda "
        "activos (definidos en Explorador Glocal), este panorama refleja ese subconjunto.",
    )

    criterios = st.session_state.get("criterios_busqueda")
    df = get_filtered_df(dedupe=True)
    mapa_full = load_mapa_ubicaciones()
    mapa = mapa_full[mapa_full["item"].isin(df["item"])]

    # ---------------------------------------------------------------- KPIs
    total = len(df)
    if total == 0:
        st.info("Ningún resultado con los criterios de búsqueda actuales.")
        return

    n_categorias = len(get_options(df, "categorias"))
    n_gcaa = (df["eje_gcaa"].str.strip().str.lower() != "no aplica").sum()
    n_resiliencia = (df["atributos_resiliencia"].str.strip().str.lower() != "no aplica").sum()
    n_genero = df["enfoque_genero"].astype(str).str.startswith("Sí").sum()
    n_con_fecha = df["tiene_fecha"].sum()
    n_puntos_geo = mapa["lat"].notna().sum()
    n_lugares_unicos = mapa.loc[mapa["lat"].notna(), "lugar_texto"].nunique()
    n_paises = mapa.loc[mapa["lat"].notna(), "pais"].nunique()
    actores_col = "actores_normalizados" if "actores_normalizados" in df.columns else "actores"
    n_actores = len(get_options(df, actores_col))

    section_label("Cifras generales")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Experiencias catalogadas", f"{total}")
    c2.metric("Categorías temáticas", f"{n_categorias}")
    c3.metric("Metodologías identificadas", f"{len(get_options(df, 'metodologia'))}")
    c4.metric("Instituciones distintas", f"{n_actores}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Relevantes para acción climática", f"{n_gcaa}", f"{n_gcaa/total:.0%} del catálogo")
    c6.metric("Con atributo de resiliencia", f"{n_resiliencia}", f"{n_resiliencia/total:.0%} del catálogo")
    c7.metric("Con enfoque de género explícito", f"{n_genero}", f"{n_genero/total:.0%} del catálogo")
    c8.metric("Puntos geolocalizados", f"{n_puntos_geo}", f"{n_lugares_unicos} lugares únicos")

    c9, c10, c11, c12 = st.columns(4)
    c9.metric("Países alcanzados", f"{n_paises}")
    c10.metric("Con fecha registrada", f"{n_con_fecha}", f"de {total} totales")
    rango = f"{int(df['anio'].min())}–{int(df['anio'].max())}" if n_con_fecha else "s/d"
    c11.metric("Rango temporal", rango)
    c12.metric("Cuencas vinculadas", f"{mapa['NOM_CUENCA'].nunique() if 'NOM_CUENCA' in mapa.columns else '—'}")

    left, right = st.columns([3, 2])

    with left:
        section_label("Qué hemos hecho")
        st.markdown(
            f"""
Este catálogo reúne **{total} experiencias** de facilitación de procesos participativos,
sistematizadas y mapeadas en tres niveles:

**Temático.** De qué habla cada experiencia (categorías inductivas) y con qué método se hizo.

**Climático y de resiliencia.** Cuáles conectan con la Global Climate Action Agenda (GCAA) de la
UNFCCC y con los atributos de resiliencia del CR2.

**Social y territorial.** Quiénes se benefician (directa e indirectamente), si hay un enfoque de
género explícito, y dónde ocurre cada experiencia — hasta el nivel de cuenca hidrográfica cuando
es en Chile.

Usa el menú de la izquierda para explorar en detalle.
            """
        )
        nav1, nav2, nav3 = st.columns(3)
        nav1.page_link("pages/2_Explorador.py", label="Explorador Glocal")
        nav2.page_link("pages/1_Marco_Teorico.py", label="Marco Teórico y Fuentes")
        nav3.page_link("pages/8_Glosario.py", label="Glosario")

    with right:
        sufijo = entidad_titulo_sufijo(criterios)
        section_label("Distribución por categoría macro")
        macro_counts = (
            df.assign(categoria_macro=df["categoria_macro"].str.split(";"))
            .explode("categoria_macro")
        )
        macro_counts["categoria_macro"] = macro_counts["categoria_macro"].str.strip()
        macro_counts = macro_counts[macro_counts["categoria_macro"] != ""]
        counts = macro_counts["categoria_macro"].value_counts().reset_index()
        counts.columns = ["Categoría macro", "N"]
        fig = px.bar(
            counts.sort_values("N"),
            x="N", y="Categoría macro", orientation="h",
            color="N", color_continuous_scale="Teal",
            labels={"N": "N° experiencias"},
        )
        fig.update_layout(coloraxis_showscale=False)
        style_fig(fig, height=320, title=f"Experiencias por categoría macro{sufijo}", showlegend=False)
        st.plotly_chart(fig, width="stretch")

    st.divider()
    st.caption(
        "Fuentes de los marcos usados: UNFCCC NAZCA Portal, Global Climate Action Agenda, "
        "y CR2 (Centro de Ciencia del Clima y Resiliencia). Ver detalle en Marco Teórico y Fuentes."
    )
