# -*- coding: utf-8 -*-
"""Capa de datos: carga, cacheo y transformación del catálogo Glocalminds."""
import re
from pathlib import Path

import pandas as pd
import streamlit as st

EXCEL_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "experiencia_glocal_catálogo_web_histórico_hasta_10_Agosto_2026.xlsx"
)
CUENCAS_REF_PATH = Path(__file__).resolve().parent.parent / "data" / "cuencas_chile_bna.xlsx"

FUENTES_REALES_TEXT = """\
## Ejes y objetivos GCAA

**UNFCCC NAZCA Portal** — Portal oficial de acción climática de la UNFCCC con seguimiento \
de iniciativas globales. https://unfccc.int/NAZCA_portal

**UNFCCC — Global Climate Action Agenda (Programa de Trabajo)** — Comunicado oficial sobre \
el nuevo programa de trabajo y estructura para operacionalizar la visión de cinco años. \
https://unfccc.int/news/new-global-climate-action-agenda-work-programme-and-structure-to-operationalize-five-year-vision

**UNFCCC Documento 652935** — Documento oficial UNFCCC con definiciones y estructura de la \
Agenda de Acción Climática Global. https://unfccc.int/documents/652935

**Climate Champions — Action Agenda** — Descripción de la iniciativa de Campeones del Clima \
sobre la Agenda de Acción. https://www.climatechampions.net/our-work/action-agenda/

## Atributos y sub-atributos de resiliencia

**CR2 — Atributos de la Resiliencia** — Race to Resilience Technical Secretariat (2023), \
"Introduction to Resilience Attributes, Their Subcategories, and Their Role in the Race to \
Resilience Campaign". Documento oficial con la definición de los 7 atributos de resiliencia \
y sus 19 sub-atributos. https://drive.google.com/file/d/1M_1xSqTGVwwn4jfiV4Cg9EFSccys1MBR/view

Los 7 atributos: Preparedness and planning · Learning · Agency · Social Collaboration · \
Flexibility · Equity · Assets.

## Nota sobre las demás columnas

Las categorías temáticas inductivas, la metodología, los actores, los beneficiarios y el \
enfoque de género fueron codificados manualmente a partir del análisis de contenido del \
catálogo — no citan una fuente externa. El detalle completo por columna, con tipo de \
variable y opciones de respuesta, está en la hoja **Libro_de_Codigos** del archivo Excel.
"""

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
_DATE_RE = re.compile(r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", re.IGNORECASE)

# Variantes detectadas del mismo método, escritas distinto por distintos lotes de codificación.
_METODOLOGIA_ALIASES = {
    "otra: café pro-acción": "Otra: Café ProAcción",
    "otra: café proacción": "Otra: Café ProAcción",
    "otra: café pro acción": "Otra: Café ProAcción",
    "otra: diseño de acción sabia": "Otra: Diseño para la Acción Sabia",
    "otra: tres horizontes": "Otra: Marco de los Tres Horizontes",
}

MULTILABEL_COLS = [
    "categorias", "categoria_macro", "metodologia", "actores", "actores_normalizados",
    "eje_gcaa", "objetivo_gcaa",
    "atributos_resiliencia", "subatributos_resiliencia",
    "beneficiarios_directos", "beneficiarios_indirectos",
]

NON_VALUES = {"no aplica", "no especificado", ""}

# Taxonomía oficial: Race to Resilience Technical Secretariat (julio 2023),
# "Introduction to Resilience Attributes, Their Subcategories, and Their Role
# in the Race to Resilience Campaign" (fuente CR2). 7 atributos, 19 sub-atributos.
RESILIENCE_TAXONOMY = {
    "1. Preparación y planificación": ["S1.1 - Preparación", "S1.2 - Planificación"],
    "2. Aprendizaje": ["S2.1 - Aprendizaje experiencial", "S2.2 - Aprendizaje educativo"],
    "3. Agencia": ["S3.1 - Autonomía", "S3.2 - Liderazgo", "S3.3 - Toma de decisiones"],
    "4. Colaboración social": ["S4.1 - Participación colectiva", "S4.2 - Conectividad", "S4.3 - Coordinación"],
    "5. Flexibilidad": ["S5.1 - Diversidad", "S5.2 - Redundancia"],
    "6. Equidad": ["S6.1 - Equidad distributiva", "S6.2 - Equidad de acceso"],
    "7. Activos": [
        "S7.1 - Finanzas", "S7.2 - Infraestructura", "S7.3 - Recursos naturales",
        "S7.4 - Tecnologías", "S7.5 - Servicios básicos",
    ],
}

# Definiciones (resumen propio, no traducción literal) a partir de: Race to Resilience
# Technical Secretariat (2023), "Introduction to Resilience Attributes, Their
# Subcategories, and Their Role in the Race to Resilience Campaign", CR2.
RESILIENCE_ATTR_DEFS = {
    "1. Preparación y planificación": (
        "Capacidad de anticipar cambios e incertidumbre, detectar riesgos a tiempo y "
        "desarrollar estrategias de corto, mediano y largo plazo para responder a ellos."
    ),
    "2. Aprendizaje": (
        "Capacidad de generar, asimilar y aplicar nuevo conocimiento sobre cambio climático "
        "e incertidumbre, tanto desde la experiencia propia como desde procesos educativos."
    ),
    "3. Agencia": (
        "Capacidad de una persona, sistema o comunidad de tomar decisiones y actuar de forma "
        "autónoma frente a un cambio o desafío, transformando riesgos en oportunidades."
    ),
    "4. Colaboración social": (
        "Capacidad de auto-organización y acción colectiva coordinada: vínculos sociales, "
        "redes de apoyo y sistemas de gobernanza que fortalecen la resiliencia compartida."
    ),
    "5. Flexibilidad": (
        "Capacidad de alternar entre distintas estrategias de adaptación según la información "
        "disponible, manteniendo opciones diversas y de respaldo."
    ),
    "6. Equidad": (
        "Aseguramiento de un acceso justo a los recursos y de la inclusión de todos los actores "
        "afectados —especialmente los históricamente marginados— en la toma de decisiones."
    ),
    "7. Activos": (
        "Capacidad de acceder a recursos financieros, de infraestructura, naturales, "
        "tecnológicos y de servicios básicos en momentos de necesidad."
    ),
}

RESILIENCE_SUBATTR_DEFS = {
    "S1.1 - Preparación": "Habilidad de anticipar amenazas, activar sistemas de alerta y protocolos de acción antes de que un riesgo se materialice.",
    "S1.2 - Planificación": "Desarrollo de estrategias de corto, mediano y largo plazo que generan una visión de futuro resiliente frente al cambio climático.",
    "S2.1 - Aprendizaje experiencial": "Aprender de experiencias y errores pasados para evitar repetirlos y decidir con más cautela en el futuro.",
    "S2.2 - Aprendizaje educativo": "Generación y aplicación de conocimiento nuevo sobre cambio climático a través de educación formal, investigación y trabajo en terreno.",
    "S3.1 - Autonomía": "Capacidad de tomar decisiones y actuar de forma independiente frente a un desafío o cambio.",
    "S3.2 - Liderazgo": "Capacidad de influir, guiar y motivar a otros hacia objetivos comunes en momentos de adversidad.",
    "S3.3 - Toma de decisiones": "Capacidad de evaluar opciones y sus consecuencias, y elegir y ejecutar un curso de acción de forma efectiva.",
    "S4.1 - Participación colectiva": "Movilización de individuos y grupos hacia objetivos comunes, fortaleciendo la cohesión social y el arraigo territorial.",
    "S4.2 - Conectividad": "Calidad y solidez de las relaciones sociales dentro de un sistema o comunidad, que permiten compartir información y apoyo mutuo.",
    "S4.3 - Coordinación": "Capacidad de alinear personas, equipos u organizaciones hacia objetivos compartidos de forma eficiente.",
    "S5.1 - Diversidad": "Mantención de múltiples estrategias de adaptación disponibles para responder a distintos tipos de adversidad.",
    "S5.2 - Redundancia": "Mantención de estrategias o recursos de respaldo que aseguran continuidad si una opción principal falla.",
    "S6.1 - Equidad distributiva": "Distribución justa de los beneficios y costos de las estrategias de adaptación y recuperación, sin dejar a nadie atrás.",
    "S6.2 - Equidad de acceso": "Inclusión de todos los actores y perspectivas afectadas —incluyendo grupos históricamente marginados— en los procesos de decisión.",
    "S7.1 - Finanzas": "Capacidad de acceder, gestionar y usar eficazmente recursos financieros para implementar medidas de adaptación.",
    "S7.2 - Infraestructura": "Instalaciones físicas esenciales para el funcionamiento y bienestar de una comunidad, capaces de absorber y resistir perturbaciones.",
    "S7.3 - Recursos naturales": "Gestión y uso sostenible de los recursos que provee el entorno natural, asegurando su disponibilidad a largo plazo.",
    "S7.4 - Tecnologías": "Acceso y uso de tecnologías apropiadas que facilitan la adaptación al cambio climático y respaldan procesos ante catástrofes.",
    "S7.5 - Servicios básicos": "Acceso a servicios esenciales (salud, educación, infraestructura) que se mantienen funcionando durante y después de una crisis.",
}

# Órdenes fijos (misma secuencia y color en toda la plataforma, sin importar la vista).
MACRO_CATEGORY_ORDER = [
    "Territorio, medioambiente y sostenibilidad",
    "Desarrollo social, comunitario y humano",
    "Estado, política pública y sociedad civil",
    "Formación y comunidad de práctica (metodológica)",
    "Educación",
    "Empresas y sector privado",
    "Cooperación internacional",
]

GCAA_EJE_ORDER = [
    "A1 - Transición de energía, industria y transporte",
    "A2 - Bosques, océanos y biodiversidad",
    "A3 - Transformar agricultura y sistemas alimentarios",
    "A4 - Resiliencia de ciudades, infraestructura y agua",
    "A5 - Desarrollo humano y social",
    "A6 - Habilitadores y aceleradores",
    "No aplica",
]

GENERO_ORDER = ["Sí", "No"]

NA_LABELS = {"no aplica", "sin dato", "no especificado"}


def dimension_order(df: pd.DataFrame, col_primary: str) -> list[str]:
    """Orden a usar para una columna *_primary en CUALQUIER gráfico/mapa de la plataforma.

    categoria_macro y eje_gcaa usan un orden fijo (mismo orden siempre, sin importar cuántos
    puntos haya en la vista actual). atributos_resiliencia se ordena por frecuencia real,
    de menor a mayor, con 'No aplica' siempre al final. enfoque_genero usa Sí/No fijo.
    """
    if col_primary == "categoria_macro_primary":
        return MACRO_CATEGORY_ORDER
    if col_primary == "eje_gcaa_primary":
        return GCAA_EJE_ORDER
    if col_primary == "atributos_resiliencia_primary":
        return ordered_primary_categories(df, col_primary, ascending=True)
    if col_primary == "enfoque_genero_primary":
        return GENERO_ORDER
    return ordered_primary_categories(df, col_primary, ascending=True)


def ordered_primary_categories(df: pd.DataFrame, col_primary: str, ascending: bool = True) -> list[str]:
    """Categorías de una columna *_primary ordenadas por frecuencia real, con 'No aplica'/'Sin
    dato' siempre al final. Úsese para fijar category_orders en cualquier gráfico o mapa."""
    if col_primary not in df.columns:
        return []
    counts = df[col_primary].value_counts()
    normal = [c for c in counts.index if c.strip().lower() not in NA_LABELS]
    na = [c for c in counts.index if c.strip().lower() in NA_LABELS]
    normal_sorted = sorted(normal, key=lambda c: counts[c], reverse=not ascending)
    return normal_sorted + na


def parse_spanish_date(value):
    if not isinstance(value, str) or not value.strip():
        return pd.NaT
    m = _DATE_RE.search(value)
    if not m:
        return pd.NaT
    day, month_name, year = m.groups()
    month = MESES.get(month_name.lower())
    if not month:
        return pd.NaT
    try:
        return pd.Timestamp(year=int(year), month=month, day=int(day))
    except ValueError:
        return pd.NaT


def genero_label(value) -> str:
    """'Sí'/'No' binario a partir del texto libre de enfoque_genero (fuente única de verdad)."""
    return "Sí" if isinstance(value, str) and value.strip().startswith("Sí") else "No"


def primary_label(value) -> str:
    """Etiqueta única y canónica de una celda multi-etiqueta (para mapas y agregaciones de un solo color).

    Fuente central de verdad: cualquier visualización que necesite UN valor por
    experiencia (color de un punto, barra dominante, etc.) debe usar esta función,
    para que mapa / gráficos / tablas nunca muestren conjuntos de categorías distintos.
    """
    if not isinstance(value, str) or not value.strip():
        return "Sin dato"
    first = value.split(";")[0].strip()
    return first if first else "Sin dato"


PRIMARY_DIMENSIONS = ["categoria_macro", "eje_gcaa", "atributos_resiliencia"]

# Registro único de dimensiones filtrables/agrupables: nombre de columna -> metadatos.
# Toda página que ofrezca "elegir dimensión" debe leer este registro, no inventar su propia lista.
DIMENSION_REGISTRY = {
    "categoria_macro": {"label": "Categoría macro", "kind": "multilabel", "primary_col": "categoria_macro_primary"},
    "categorias": {"label": "Categoría temática", "kind": "multilabel", "primary_col": None},
    "metodologia": {"label": "Metodología", "kind": "multilabel", "primary_col": None},
    "actores_normalizados": {"label": "Actores institucionales", "kind": "multilabel", "primary_col": None},
    "eje_gcaa": {"label": "Eje GCAA", "kind": "multilabel", "primary_col": "eje_gcaa_primary"},
    "objetivo_gcaa": {"label": "Objetivo GCAA", "kind": "multilabel", "primary_col": None},
    "atributos_resiliencia": {"label": "Atributo de resiliencia", "kind": "multilabel", "primary_col": "atributos_resiliencia_primary"},
    "subatributos_resiliencia": {"label": "Sub-atributo de resiliencia", "kind": "multilabel", "primary_col": None},
    "beneficiarios_directos": {"label": "Beneficiarios directos", "kind": "multilabel", "primary_col": None},
    "beneficiarios_indirectos": {"label": "Beneficiarios indirectos", "kind": "multilabel", "primary_col": None},
    "enfoque_genero": {"label": "Enfoque de género", "kind": "single", "primary_col": None},
    "pais": {"label": "País", "kind": "single", "primary_col": None},
}


def _normalize_label(label):
    label = label.strip()
    return _METODOLOGIA_ALIASES.get(label.lower(), label)


def _normalize_multilabel_text(value):
    if not isinstance(value, str) or not value.strip():
        return value
    parts, seen = [], set()
    for p in value.split(";"):
        p = _normalize_label(p)
        if p and p not in seen:
            seen.add(p)
            parts.append(p)
    return "; ".join(parts)


@st.cache_data(show_spinner="Cargando catálogo de experiencias...")
def load_noticias() -> pd.DataFrame:
    df = pd.read_excel(EXCEL_PATH, sheet_name="Base_Datos", engine="openpyxl")
    df = df.dropna(subset=["titulo"]).reset_index(drop=True)
    df.insert(0, "item", range(1, len(df) + 1))

    df["metodologia"] = df["metodologia"].apply(_normalize_multilabel_text)

    if "fecha_publicacion_web" in df.columns:
        df["fecha_parsed"] = pd.to_datetime(df["fecha_publicacion_web"], errors="coerce")
    else:
        df["fecha_parsed"] = pd.NaT
    if df["fecha_parsed"].isna().any():
        fecha_raw = df["fecha_publicacion"].fillna(df.get("fecha_catalogo"))
        fallback = fecha_raw.apply(parse_spanish_date)
        df["fecha_parsed"] = df["fecha_parsed"].fillna(fallback)
    df["anio"] = df["fecha_parsed"].dt.year
    df["tiene_fecha"] = df["fecha_parsed"].notna()

    for col in MULTILABEL_COLS:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("")

    # Columnas primarias (fuente única de verdad para vistas que necesitan 1 valor por fila)
    for col in PRIMARY_DIMENSIONS:
        df[f"{col}_primary"] = df[col].apply(primary_label)
    df["enfoque_genero_binario"] = df["enfoque_genero"].apply(genero_label)

    df["enlaces_externos_lista"] = df.get("enlaces_externos", pd.Series([None] * len(df))).apply(
        lambda v: [u.strip() for u in str(v).split("|") if u.strip()] if isinstance(v, str) and v.strip() else []
    )

    return df


def _split_parallel(value) -> list[str]:
    """Divide un campo 'sitios_*' (lista paralela alineada con 'lugar') en sus elementos."""
    if not isinstance(value, str) or not value.strip():
        return []
    return [p.strip() for p in value.split(";")]


@st.cache_data(show_spinner=False)
def load_mapa_ubicaciones() -> pd.DataFrame:
    """Reconstruye la tabla larga (1 fila por sitio geográfico) a partir de las columnas
    paralelas lugar / sitios_lat / sitios_lon / sitios_pais / sitios_cuenca_nombre de
    Base_Datos. No se guarda una hoja aparte: la base de datos es una sola hoja, esta
    tabla se arma en memoria cada vez que se carga la app."""
    df = load_noticias()
    rows = []
    for _, row in df.iterrows():
        lugar_raw = row.get("lugar")
        if not isinstance(lugar_raw, str) or not lugar_raw.strip() or lugar_raw.strip().lower() == "no especificado":
            continue
        lugares = _split_parallel(lugar_raw)
        lats = _split_parallel(row.get("sitios_lat"))
        lons = _split_parallel(row.get("sitios_lon"))
        paises = _split_parallel(row.get("sitios_pais"))
        cuencas = _split_parallel(row.get("sitios_cuenca_nombre"))
        precisiones = _split_parallel(row.get("sitios_precision_geocodificacion"))

        def _at(lst, i):
            return lst[i] if i < len(lst) and lst[i] != "" else None

        for i, lugar_texto in enumerate(lugares):
            lat = _at(lats, i)
            lon = _at(lons, i)
            rows.append({
                "item": row["item"],
                "titulo": row["titulo"],
                "url": row.get("url_noticia"),
                "categoria_macro": row.get("categoria_macro"),
                "categorias": row.get("categorias"),
                "eje_gcaa": row.get("eje_gcaa"),
                "lugar_texto": lugar_texto,
                "lat": float(lat) if lat is not None else None,
                "lon": float(lon) if lon is not None else None,
                "pais": _at(paises, i) or "Sin dato",
                "NOM_CUENCA": _at(cuencas, i),
                "precision_geocodificacion": _at(precisiones, i),
            })
    mapa = pd.DataFrame(rows)
    for col in ("categoria_macro", "eje_gcaa"):
        mapa[f"{col}_primary"] = mapa[col].apply(primary_label)
    return mapa


@st.cache_data(show_spinner=False)
def load_cuencas() -> pd.DataFrame:
    return pd.read_excel(CUENCAS_REF_PATH, sheet_name="Cuencas", engine="openpyxl")


@st.cache_data(show_spinner=False)
def load_subcuencas() -> pd.DataFrame:
    return pd.read_excel(CUENCAS_REF_PATH, sheet_name="Subcuencas", engine="openpyxl")


def explode_multilabel(df: pd.DataFrame, col: str, extra_cols=None) -> pd.DataFrame:
    """Una fila por cada (item, etiqueta) de una columna separada por ';'."""
    extra_cols = extra_cols or []
    sub = df[["item", col] + extra_cols].copy()
    sub[col] = sub[col].fillna("").astype(str).apply(
        lambda v: [p.strip() for p in v.split(";") if p.strip()]
    )
    sub = sub.explode(col)
    sub = sub[sub[col].notna() & (sub[col].astype(str) != "")]
    return sub.rename(columns={col: "label"})


def get_options(df: pd.DataFrame, col: str, exclude_non_values: bool = True) -> list[str]:
    exploded = explode_multilabel(df, col)
    vals = exploded["label"].dropna().unique().tolist()
    if exclude_non_values:
        vals = [v for v in vals if v.strip().lower() not in NON_VALUES]
    return sorted(vals)


def filter_by_multilabel(df: pd.DataFrame, col: str, selected: list[str]) -> pd.DataFrame:
    if not selected:
        return df
    selected_set = set(selected)

    def _match(v):
        parts = {p.strip() for p in str(v).split(";") if p.strip()}
        return bool(parts & selected_set)

    return df[df[col].apply(_match)]


def resilience_counts(df: pd.DataFrame):
    """Conteos de atributos y sub-atributos de resiliencia, incluyendo 0 para los que no aparecen en el catálogo."""
    a_exp = explode_multilabel(df, "atributos_resiliencia")
    a_exp = a_exp[a_exp["label"].str.lower() != "no aplica"]
    a_counts = a_exp["label"].value_counts()

    s_exp = explode_multilabel(df, "subatributos_resiliencia")
    s_exp = s_exp[s_exp["label"].str.lower() != "no aplica"]
    s_counts = s_exp["label"].value_counts()

    df_attr = pd.DataFrame(
        [{"atributo": attr, "n": int(a_counts.get(attr, 0))} for attr in RESILIENCE_TAXONOMY]
    )
    df_sub = pd.DataFrame(
        [
            {"atributo": attr, "subatributo": sub, "n": int(s_counts.get(sub, 0))}
            for attr, subs in RESILIENCE_TAXONOMY.items()
            for sub in subs
        ]
    )
    return df_attr, df_sub


def extract_country(display_name: str) -> str | None:
    """Aproxima el país a partir del último segmento de una dirección OSM."""
    if not isinstance(display_name, str) or not display_name.strip():
        return None
    last = display_name.split(",")[-1].strip()
    return last or None


_MESES_INV = {v: k for k, v in MESES.items()}


def format_fecha_es(ts) -> str:
    """Formatea una fecha como 'D de Mes de AAAA'. Devuelve texto neutro si no hay fecha."""
    if ts is None or (hasattr(ts, "year") is False) or pd.isna(ts):
        return "Fecha no disponible"
    mes = _MESES_INV.get(ts.month, "")
    return f"{ts.day} de {mes.capitalize()} de {ts.year}"


COLUMN_LABELS = {
    "pais": "País",
    "categorias": "Categoría temática",
    "categoria_macro": "Categoría macro",
    "metodologia": "Metodología de facilitación",
    "actores": "Actores institucionales",
    "actores_normalizados": "Actores institucionales (normalizado)",
    "eje_gcaa": "Eje GCAA",
    "objetivo_gcaa": "Objetivo GCAA",
    "atributos_resiliencia": "Atributo de resiliencia",
    "subatributos_resiliencia": "Sub-atributo de resiliencia",
    "beneficiarios_directos": "Beneficiarios directos",
    "beneficiarios_indirectos": "Beneficiarios indirectos",
    "enfoque_genero": "Enfoque de género",
    "lugar": "Lugar",
}
