# -*- coding: utf-8 -*-
"""Punto de entrada: define la navegación explícita de 4 páginas (Inicio, Explorador Glocal,
Marco Teórico, Glosario). Mapa/Evolución/Cruces/Cuencas ya no son páginas propias — viven como
secciones dentro de Explorador Glocal (ver sections/ y pages/2_Explorador.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

from sections import inicio as sec_inicio

st.set_page_config(page_title="Explorador Impacto Glocal", layout="wide")

pages = [
    st.Page(sec_inicio.render, title="Inicio", default=True, url_path="inicio"),
    st.Page("pages/2_Explorador.py", title="Explorador Glocal", url_path="explorador-glocal"),
    st.Page("pages/1_Marco_Teorico.py", title="Marco Teórico", url_path="marco-teorico"),
    st.Page("pages/8_Glosario.py", title="Glosario", url_path="glosario"),
]

st.navigation(pages).run()
