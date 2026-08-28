# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from utils.data import get_options, load_noticias, load_sheet_as_text
from utils.style import inject, page_header

st.set_page_config(page_title="Marco Teórico y Fuentes", layout="wide")
inject()
page_header(
    "Marco conceptual",
    "Marco Teórico y Fuentes",
    "Qué significa cada dimensión del catálogo, y de dónde viene.",
)

df = load_noticias()

tab1, tab2 = st.tabs(["Cómo leer cada dimensión", "Fuentes reales citadas"])

with tab1:
    st.markdown(
        "Cada experiencia del catálogo fue analizada bajo varias lentes distintas. "
        "Estas son las que puedes filtrar y cruzar en el resto de la plataforma:"
    )

    secciones = [
        (
            "Categorías temáticas (inductivas)",
            "categorias / categoria_macro",
            "De qué habla la experiencia. Se construyeron leyendo el catálogo completo, sin categorías "
            "impuestas de antemano (codificación abierta): primero surgieron 14 categorías específicas, "
            "luego se agruparon en 6 categorías macro.",
        ),
        (
            "Metodología de facilitación",
            "metodologia",
            "Con qué método o proceso se facilitó la experiencia (Art of Hosting, Café Mundial, Teoría U, "
            "Design Thinking, Sociocracia, Dragon Dreaming, entre otros). Es un campo distinto de 'de qué habla': "
            "aquí se identifica el 'cómo', no el 'qué'.",
        ),
        (
            "Actores institucionales",
            "actores_normalizados",
            "Qué instituciones u organizaciones participaron: gobierno, empresas, sociedad civil, academia, "
            "organismos internacionales. Los nombres fueron normalizados (siglas, mayúsculas, variantes de "
            "escritura) para evitar contar la misma institución dos veces.",
        ),
        (
            "Eje GCAA / Objetivo GCAA",
            "eje_gcaa / objetivo_gcaa",
            "Si la experiencia conecta con la Global Climate Action Agenda (GCAA) de la UNFCCC — el marco "
            "internacional que organiza la acción climática global en 6 ejes y cerca de 30 objetivos específicos. "
            "Se marca 'No aplica' cuando genuinamente no hay conexión climática, sin forzar el encaje.",
        ),
        (
            "Atributo / Sub-atributo de resiliencia",
            "atributos_resiliencia / subatributos_resiliencia",
            "Si la experiencia fortalece alguno de los 7 atributos de resiliencia definidos por el CR2 "
            "(Centro de Ciencia del Clima y Resiliencia): preparación, aprendizaje, agencia, colaboración "
            "social, flexibilidad, equidad y activos.",
        ),
        (
            "Beneficiarios directos / indirectos",
            "beneficiarios_directos / beneficiarios_indirectos",
            "Quién participa o recibe la intervención directamente, versus quién se beneficia río abajo sin "
            "participar (comunidad ampliada, generaciones futuras, ecosistema).",
        ),
        (
            "Enfoque de género",
            "enfoque_genero",
            "Si la experiencia tiene un foco explícito en mujeres, niñas u otras identidades de género como "
            "tema central o grupo destinatario — no basta con que haya mujeres participando.",
        ),
        (
            "Ubicación y cuenca",
            "lugar / mapa / cuencas",
            "Dónde ocurrió cada experiencia, geocodificado a coordenadas específicas y, cuando es en Chile, "
            "vinculado a su cuenca, subcuenca y subsubcuenca hidrográfica (datos BNA/DGA).",
        ),
        (
            "Fecha de publicación",
            "fecha_publicacion_web",
            "Fecha real obtenida directamente del sitio web de Glocalminds (API de WordPress), no de texto "
            "libre. Cubre el 100% del catálogo, de 2010 a 2026.",
        ),
    ]

    for titulo, campo, texto in secciones:
        with st.container(border=True):
            c1, c2 = st.columns([1, 3])
            with c1:
                st.markdown(f"**{titulo}**")
                st.code(campo, language=None)
            with c2:
                st.markdown(texto)
                opts = []
                for col in campo.replace(" ", "").split("/"):
                    if col in df.columns:
                        opts = get_options(df, col)
                        break
                if opts:
                    preview = ", ".join(opts[:6]) + ("…" if len(opts) > 6 else "")
                    st.caption(f"{len(opts)} valores distintos presentes en el catálogo · {preview}")

with tab2:
    st.markdown("Fuentes citadas tal como fueron entregadas, sin adiciones:")
    lines = load_sheet_as_text("Fuentes_Reales")
    text = "\n".join(lines)
    st.markdown(text)
