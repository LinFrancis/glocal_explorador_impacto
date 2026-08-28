# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from utils.data import (
    GCAA_EJE_ORDER,
    RESILIENCE_ATTR_DEFS,
    RESILIENCE_SUBATTR_DEFS,
    RESILIENCE_TAXONOMY,
    get_options,
    load_noticias,
)
from utils.style import inject, page_header, section_label

st.set_page_config(page_title="Glosario", layout="wide")
inject()
page_header(
    "Referencia",
    "Glosario",
    "Todas las categorías y conceptos clave del catálogo, en un solo lugar. Toda definición con una "
    "fuente externa real incluye su link.",
)

df = load_noticias()

# ---------------------------------------------------------------- fuentes reales verificadas
FUENTE_CR2 = ("CR2 — Race to Resilience Technical Secretariat (2023)", "https://drive.google.com/file/d/1M_1xSqTGVwwn4jfiV4Cg9EFSccys1MBR/view")
FUENTE_NAZCA = ("UNFCCC NAZCA Portal", "https://unfccc.int/NAZCA_portal")
FUENTE_GCAA_PROGRAMA = ("UNFCCC — Programa de Trabajo GCAA", "https://unfccc.int/news/new-global-climate-action-agenda-work-programme-and-structure-to-operationalize-five-year-vision")
FUENTE_GCAA_DOC = ("UNFCCC Documento 652935", "https://unfccc.int/documents/652935")
FUENTE_CLIMATE_CHAMPIONS = ("Climate Champions — Action Agenda", "https://www.climatechampions.net/our-work/action-agenda/")
FUENTE_UNFCCC = ("unfccc.int", "https://unfccc.int")
FUENTE_NOMINATIM = ("OpenStreetMap Nominatim", "https://nominatim.openstreetmap.org")
FUENTE_PROPIA = ("Codificación propia (análisis de contenido del catálogo Glocalminds)", None)
FUENTE_BNA = ("BNA/DGA — Biblioteca Nacional de Agua, Dirección General de Aguas (Chile)", None)


def _fuente_html(fuente):
    """fuente: (texto, url_o_None) -> HTML con link real cuando existe."""
    if not fuente:
        return ""
    texto, url = fuente
    if url:
        return f'<div class="gm-meta-row">Fuente: <a href="{url}" target="_blank">{texto} ↗</a></div>'
    return f'<div class="gm-meta-row">Fuente: {texto}</div>'


# ---------------------------------------------------------------- definiciones: (definicion, fuente)
CATEGORIAS_DEF = {
    "Bienestar organizacional y desarrollo de equipos": ("Fortalecimiento de dinámicas internas, liderazgo y clima laboral de un equipo u organización.", FUENTE_PROPIA),
    "Cooperación internacional y organismos multilaterales": ("Relación con agencias multilaterales (ONU, BID, FAO, etc.) y cooperación entre países.", FUENTE_PROPIA),
    "Cultura comunitaria y desarrollo cultural territorial": ("Procesos de identidad, patrimonio y expresión cultural de una comunidad o territorio.", FUENTE_PROPIA),
    "Educación (escolar, técnica y superior)": ("Procesos formativos en establecimientos escolares, técnicos o de educación superior.", FUENTE_PROPIA),
    "Formación y comunidad de práctica en facilitación": ("Talleres y espacios para formar facilitadores/as o fortalecer la práctica del oficio.", FUENTE_PROPIA),
    "Fortalecimiento del Estado y política pública": ("Procesos que apoyan a instituciones públicas en el diseño o implementación de políticas.", FUENTE_PROPIA),
    "Innovación social y ecosistemas de emprendimiento": ("Apoyo a emprendimientos, innovación social o ecosistemas de innovación.", FUENTE_PROPIA),
    "Interculturalidad, pueblos originarios, migración e inclusión": ("Procesos centrados en diversidad cultural, pueblos indígenas, migrantes o inclusión social.", FUENTE_PROPIA),
    "Juventud y formación de agentes de cambio": ("Procesos formativos o de liderazgo dirigidos a jóvenes.", FUENTE_PROPIA),
    "Medioambiente, conservación y cambio climático": ("Acción ambiental, conservación de ecosistemas o adaptación/mitigación climática.", FUENTE_PROPIA),
    "Regeneración ecosocial, economía circular y liderazgo regenerativo": ("Enfoques regenerativos que integran lo ecológico y lo social.", FUENTE_PROPIA),
    "Ruralidad, agricultura y gestión de recursos naturales": ("Procesos en contextos rurales, agrícolas o de manejo de recursos naturales.", FUENTE_PROPIA),
    "Sociedad civil, movilización ciudadana y procesos democráticos": ("Participación ciudadana, organizaciones de sociedad civil o procesos democráticos.", FUENTE_PROPIA),
    "Sostenibilidad corporativa y relación empresa-comunidad": ("Procesos de sostenibilidad o vinculación comunitaria impulsados por empresas.", FUENTE_PROPIA),
    "Turismo sostenible/regenerativo y ecoturismo": ("Desarrollo turístico con enfoque de sostenibilidad o regeneración.", FUENTE_PROPIA),
}

MACRO_DEF = {
    "Cooperación internacional": ("Experiencias vinculadas a organismos multilaterales y cooperación entre países.", FUENTE_PROPIA),
    "Desarrollo social, comunitario y humano": ("Experiencias centradas en comunidades, cultura, juventud, interculturalidad e inclusión.", FUENTE_PROPIA),
    "Educación": ("Experiencias en el sistema educativo escolar, técnico o superior.", FUENTE_PROPIA),
    "Empresas y sector privado": ("Experiencias impulsadas por o para empresas: sostenibilidad corporativa, relación con comunidades.", FUENTE_PROPIA),
    "Estado, política pública y sociedad civil": ("Experiencias con instituciones públicas, política pública y organizaciones de sociedad civil.", FUENTE_PROPIA),
    "Formación y comunidad de práctica (metodológica)": ("Experiencias orientadas a formar facilitadores/as o fortalecer el oficio de la facilitación.", FUENTE_PROPIA),
    "Territorio, medioambiente y sostenibilidad": ("Experiencias sobre medioambiente, cambio climático, ruralidad y regeneración ecosocial.", FUENTE_PROPIA),
}

METODOLOGIA_DEF = {
    "Art of Hosting": ("Enfoque de facilitación de conversaciones significativas basado en principios de anfitrionía participativa.", FUENTE_PROPIA),
    "Café Mundial": ("Diálogo en mesas pequeñas y rotativas para explorar preguntas colectivamente (World Café).", FUENTE_PROPIA),
    "Design Thinking": ("Proceso iterativo centrado en las personas: empatizar, definir, idear, prototipar y testear.", FUENTE_PROPIA),
    "Dragon Dreaming": ("Metodología de diseño de proyectos en cuatro fases cíclicas: soñar, planificar, actuar y celebrar.", FUENTE_PROPIA),
    "Espacio Abierto": ("Formato de conferencia auto-organizada, sin agenda fija predefinida (Open Space Technology).", FUENTE_PROPIA),
    "Sociocracia": ("Sistema de gobernanza colectiva basado en el consentimiento y la organización en círculos.", FUENTE_PROPIA),
    "Teoría U": ("Proceso de cambio profundo desarrollado por Otto Scharmer: sensar, presenciar y crear (Presencing Institute).", FUENTE_PROPIA),
    "Círculo": ("Formato de conversación circular, sin jerarquía, con turno de palabra.", FUENTE_PROPIA),
    "Backcasting": ("Planificación que parte de un futuro deseado y traza el camino hacia atrás hasta el presente.", FUENTE_PROPIA),
    "Cosecha Estratégica": ("Método de sistematización y síntesis colectiva de los aprendizajes de un proceso.", FUENTE_PROPIA),
    "Ecología Profunda": ("Enfoque que promueve la conexión con la naturaleza como base ética de la acción (Deep Ecology).", FUENTE_PROPIA),
    "Processwork": ("Facilitación de conflictos y procesos grupales basada en la psicología orientada a procesos (Arnold Mindell).", FUENTE_PROPIA),
    "Viaje de Aprendizaje": ("Visita de inmersión a terreno para observar y aprender de una realidad concreta (Learning Journey).", FUENTE_PROPIA),
    "Otra: Doble Diamante": ("Modelo de diseño en cuatro fases divergentes/convergentes: descubrir, definir, desarrollar, entregar.", FUENTE_PROPIA),
    "Otra: Enfoque Apreciativo": ("Indagación centrada en fortalezas y logros, no en problemas, para impulsar el cambio (Appreciative Inquiry).", FUENTE_PROPIA),
    "Otra: Indagación Apreciativa": ("Ver Enfoque Apreciativo — mismo enfoque, otra denominación.", FUENTE_PROPIA),
    "Otra: Marco de los Tres Horizontes": ("Herramienta de prospectiva para pensar la transición entre el presente y futuros posibles (Three Horizons).", FUENTE_PROPIA),
    "Otra: Pecera": ("Formato de discusión con un círculo interno que conversa y uno externo que observa (Fishbowl).", FUENTE_PROPIA),
    "Otra: Consejo de Todos los Seres": ("Práctica ritual de ecología profunda que da voz a otras formas de vida (Joanna Macy).", FUENTE_PROPIA),
    "Otra: Diseño Centrado en lo Humano": ("Marco de diseño centrado en las necesidades de las personas (Human-Centered Design).", FUENTE_PROPIA),
    "Otra: NABC": ("Estructura de presentación de propuestas: Necesidad, Aproximación, Beneficio, Competencia (SRI International).", FUENTE_PROPIA),
    "Otra: Retroprospectiva": ("Ejercicio de mirar hacia atrás y hacia adelante para extraer aprendizajes y proyectar futuro.", FUENTE_PROPIA),
    "Otra: Café ProAcción": ("Variante del Café Mundial orientada a generar acuerdos y compromisos de acción concretos.", FUENTE_PROPIA),
    "Otra: Café estratégico": ("Variante del Café Mundial aplicada a la definición de prioridades estratégicas.", FUENTE_PROPIA),
}

BENEFICIARIOS_DEF = {
    "Funcionarios/gobierno": ("Equipos de gobierno nacional, regional o municipal.", FUENTE_PROPIA),
    "Empresas/sector privado": ("Ejecutivos, trabajadores o gremios del sector privado.", FUENTE_PROPIA),
    "Comunidades locales/territoriales": ("Vecinos, dirigentes o población general de un territorio.", FUENTE_PROPIA),
    "Pueblos indígenas/originarios": ("Comunidades y organizaciones de pueblos originarios.", FUENTE_PROPIA),
    "Migrantes": ("Personas migrantes.", FUENTE_PROPIA),
    "Niñez, adolescencia y juventud": ("Niños, niñas, adolescentes y jóvenes.", FUENTE_PROPIA),
    "Mujeres y niñas": ("Mujeres y niñas como grupo destinatario específico.", FUENTE_PROPIA),
    "Personas con discapacidad": ("Personas en situación de discapacidad.", FUENTE_PROPIA),
    "Personas mayores": ("Adultos mayores.", FUENTE_PROPIA),
    "Comunidad educativa escolar": ("Estudiantes, docentes y directivos de colegios.", FUENTE_PROPIA),
    "Academia/comunidad universitaria": ("Estudiantes y académicos de educación superior.", FUENTE_PROPIA),
    "Sociedad civil/ONGs": ("Dirigentes u organizaciones de la sociedad civil.", FUENTE_PROPIA),
    "Red de facilitadores de Glocalminds": ("Comunidad de práctica propia: egresados y alumni de sus formaciones.", FUENTE_PROPIA),
    "Agricultores/pescadores/productores rurales": ("Productores del sector silvoagropecuario y pesquero.", FUENTE_PROPIA),
    "Público general/ciudadanía": ("Población general, sin un grupo específico identificado.", FUENTE_PROPIA),
    "Otro": ("Grupo específico que no calza en las categorías anteriores (se detalla en cada caso).", FUENTE_PROPIA),
}

TERMINOS_DEF = {
    "GCAA (Global Climate Action Agenda)": ("Marco 2026-2030 de la UNFCCC que organiza la acción climática global en seis ejes y cerca de treinta objetivos específicos, alineado con el Acuerdo de París y el Global Stocktake.", FUENTE_NAZCA),
    "UNFCCC": ("Convención Marco de las Naciones Unidas sobre el Cambio Climático, el tratado internacional que gobierna la acción climática global.", FUENTE_UNFCCC),
    "CR2": ("Centro de Ciencia del Clima y Resiliencia (Chile), fuente del marco de los siete atributos de resiliencia usado en este catálogo.", FUENTE_CR2),
    "Atributo de resiliencia": ("Una de siete capacidades (preparación, aprendizaje, agencia, colaboración social, flexibilidad, equidad, activos) que una experiencia puede fortalecer frente al cambio climático, según el marco del CR2.", FUENTE_CR2),
    "No aplica": ("Se usa cuando una experiencia genuinamente no conecta con el eje GCAA o el atributo de resiliencia correspondiente — no se fuerza el encaje.", FUENTE_PROPIA),
    "Beneficiario directo": ("Quien participa o recibe la intervención directamente (por ejemplo, asistentes a un taller).", FUENTE_PROPIA),
    "Beneficiario indirecto": ("Quien se beneficia río abajo sin participar directamente (comunidad ampliada, generaciones futuras, ecosistema).", FUENTE_PROPIA),
    "Enfoque de género": ("Se marca 'Sí' solo cuando el texto menciona explícitamente a mujeres, niñas u otra identidad de género como foco temático central — no basta con que haya mujeres participando.", FUENTE_PROPIA),
    "Cuenca hidrográfica": ("Territorio delimitado por la topografía cuyas aguas drenan hacia un mismo curso o cuerpo de agua. En Chile se organiza en cuencas y subcuencas (datos BNA/DGA).", FUENTE_BNA),
    "BNA / DGA": ("Biblioteca Nacional de Agua y Dirección General de Aguas, la fuente oficial de los datos de cuencas hidrográficas de Chile usados en este catálogo.", FUENTE_BNA),
    "Geocodificación": ("Proceso de convertir un nombre de lugar en coordenadas (latitud/longitud), realizado aquí con OpenStreetMap/Nominatim y validado por país y región.", FUENTE_NOMINATIM),
    "Actor normalizado": ("Nombre de una institución, limpiado de variantes de escritura (siglas, mayúsculas, tildes) para que la misma organización no se cuente dos veces.", FUENTE_PROPIA),
    "Categorías inductivas": ("Categorías que no se definieron de antemano, sino que emergieron de leer el contenido completo del catálogo (codificación abierta).", FUENTE_PROPIA),
}

SECCIONES = [
    ("Categorías temáticas", CATEGORIAS_DEF, "categorias"),
    ("Categorías macro", MACRO_DEF, "categoria_macro"),
    ("Metodologías de facilitación", METODOLOGIA_DEF, "metodologia"),
    ("Tipos de beneficiarios", BENEFICIARIOS_DEF, None),
    ("Términos técnicos", TERMINOS_DEF, None),
]

busqueda = st.text_input("Buscar en el glosario", placeholder="Ej: resiliencia, café mundial, cuenca...")
q = busqueda.strip().lower()
total_mostrados = 0

# ---------------------------------------------------------------- atributos y sub-atributos CR2 (jerárquico)
resil_matches = 0
resil_blocks = []
for atributo, subs in RESILIENCE_TAXONOMY.items():
    attr_def = RESILIENCE_ATTR_DEFS.get(atributo, "")
    sub_defs = [(s, RESILIENCE_SUBATTR_DEFS.get(s, "")) for s in subs]
    if q:
        attr_hit = q in atributo.lower() or q in attr_def.lower()
        sub_defs_f = [(s, d) for s, d in sub_defs if q in s.lower() or q in d.lower()]
        if not attr_hit and not sub_defs_f:
            continue
        if not attr_hit:
            sub_defs = sub_defs_f
    resil_blocks.append((atributo, attr_def, sub_defs))
    resil_matches += 1 + len(sub_defs)

if resil_blocks:
    total_mostrados += resil_matches
    section_label(f"Atributos y sub-atributos de resiliencia — CR2 ({len(resil_blocks)})")
    for atributo, attr_def, sub_defs in resil_blocks:
        with st.container(border=True):
            st.markdown(f"**{atributo}**")
            st.caption(attr_def)
            st.markdown(_fuente_html(FUENTE_CR2), unsafe_allow_html=True)
            for sub, sub_def in sub_defs:
                st.markdown(f"—&nbsp;&nbsp;**{sub}**")
                st.caption(f"　{sub_def}")

    st.divider()

# ---------------------------------------------------------------- ejes GCAA
gcaa_entradas = [e for e in GCAA_EJE_ORDER if e.lower() != "no aplica"]
if q:
    gcaa_entradas = [e for e in gcaa_entradas if q in e.lower()]
if gcaa_entradas:
    total_mostrados += len(gcaa_entradas)
    section_label(f"Ejes GCAA — Global Climate Action Agenda, UNFCCC ({len(gcaa_entradas)})")
    fuentes_gcaa = [FUENTE_NAZCA, FUENTE_GCAA_PROGRAMA, FUENTE_GCAA_DOC, FUENTE_CLIMATE_CHAMPIONS]
    for eje in gcaa_entradas:
        with st.container(border=True):
            st.markdown(f"**{eje}**")
            links = " · ".join(f'<a href="{u}" target="_blank">{t} ↗</a>' for t, u in fuentes_gcaa)
            st.markdown(f'<div class="gm-meta-row">Fuente: {links}</div>', unsafe_allow_html=True)
    st.caption("Ver también Objetivo GCAA en el Explorador para el detalle numerado dentro de cada eje.")
    st.divider()

for titulo_seccion, definiciones, data_col in SECCIONES:
    entradas = list(definiciones.items())
    if data_col:
        vivos = set(get_options(df, data_col))
        for extra in vivos:
            if extra not in definiciones:
                entradas.append((extra, ("", FUENTE_PROPIA)))
    entradas.sort(key=lambda x: x[0])

    if q:
        entradas = [e for e in entradas if q in e[0].lower() or q in e[1][0].lower()]
    if not entradas:
        continue
    total_mostrados += len(entradas)

    section_label(f"{titulo_seccion} ({len(entradas)})")
    for termino, (definicion, fuente) in entradas:
        with st.container(border=True):
            st.markdown(f"**{termino}**")
            if definicion:
                st.caption(definicion)
            st.markdown(_fuente_html(fuente), unsafe_allow_html=True)

if q and total_mostrados == 0:
    st.info("No se encontraron términos que coincidan con la búsqueda.")

st.divider()
st.markdown(
    "**Descripción técnica de cada columna** (tipo de variable, opciones de respuesta, fuente): "
    "hoja **Libro_de_Codigos** del archivo Excel del catálogo."
)
