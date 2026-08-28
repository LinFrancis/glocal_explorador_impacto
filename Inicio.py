# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import plotly.express as px
import streamlit as st

from utils.data import get_options, load_mapa_ubicaciones, load_noticias
from utils.style import inject, page_header, section_label, style_fig

st.set_page_config(
    page_title="Explorador Impacto Glocal",
    layout="wide",
)
inject()

page_header(
    "Explorador Impacto Glocal",
    "Panorama general del catálogo",
    "Catálogo de experiencias de facilitación de Glocalminds, mapeadas contra marcos internacionales "
    "de acción climática y resiliencia.",
)

df = load_noticias()
mapa = load_mapa_ubicaciones()

# ---------------------------------------------------------------- KPIs
total = len(df)
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
    nav1.page_link("pages/2_Explorador.py", label="Explorador Avanzado")
    nav2.page_link("pages/3_Mapa.py", label="Mapa")
    nav3.page_link("pages/4_Evolucion_Temporal.py", label="Evolución en el Tiempo")
    nav4, nav5, nav6 = st.columns(3)
    nav4.page_link("pages/1_Marco_Teorico.py", label="Marco Teórico y Fuentes")
    nav5.page_link("pages/8_Glosario.py", label="Glosario")
    nav6.page_link("pages/5_Cruces_y_Correlaciones.py", label="Cruces y Correlaciones")

with right:
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
    style_fig(fig, height=320, title="Experiencias por categoría macro", showlegend=False)
    st.plotly_chart(fig, width="stretch")

st.divider()
st.caption(
    "Fuentes de los marcos usados: UNFCCC NAZCA Portal, Global Climate Action Agenda, "
    "y CR2 (Centro de Ciencia del Clima y Resiliencia). Ver detalle en Marco Teórico y Fuentes."
)
