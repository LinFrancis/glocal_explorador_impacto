# -*- coding: utf-8 -*-
"""Sistema de diseño v2: tipografía proporcional, spacing compacto, componentes reutilizables."""
import math

import streamlit as st

FONT_FAMILY = "'Montserrat', -apple-system, 'Segoe UI', sans-serif"

COLOR_PRIMARY = "#0B6E4F"
COLOR_PRIMARY_DARK = "#08402F"
COLOR_TEXT = "#111827"
COLOR_MUTED = "#6B7280"
COLOR_BORDER = "#E4E7EB"
COLOR_CARD_BG = "#F7F8FA"
COLOR_SIDEBAR_BG = "#F9FAFB"

CATEGORY_PALETTE = [
    "#0B6E4F", "#1F6FB2", "#B2531F", "#6B4FA0",
    "#B01E4B", "#3F7D20", "#7A5B1E", "#2B2D42",
    "#0E7C7B", "#9A3B7D",
]
COLOR_NA = "#B6BAC2"

# ------------------------------------------------------------ mapas de color fijos por dimensión
# Un mismo valor de categoría es SIEMPRE el mismo color en toda la plataforma
# (mapa, línea de tiempo, gráficos, radial), sin importar el nivel de agregación.
from utils.data import GCAA_EJE_ORDER, GENERO_ORDER, MACRO_CATEGORY_ORDER, RESILIENCE_TAXONOMY  # noqa: E402


def _build_color_map(categories):
    m = {c: CATEGORY_PALETTE[i % len(CATEGORY_PALETTE)] for i, c in enumerate(categories)}
    m["No aplica"] = COLOR_NA
    m["Sin dato"] = COLOR_NA
    m["No especificado"] = COLOR_NA
    return m


def build_color_map(categories):
    """Mapa {categoría: color fijo} determinista a partir de un orden de categorías.

    Para dimensiones que no tienen un mapa de color predefinido en DIMENSION_COLOR_MAPS.
    Al derivar el color del ORDEN (no del subconjunto presente en la vista), un mismo
    valor conserva su color en las tres vistas del mapa (coordenadas, ciudad y país).
    """
    return _build_color_map(list(categories))


COLOR_MAP_MACRO = _build_color_map(MACRO_CATEGORY_ORDER)
COLOR_MAP_GCAA = _build_color_map(GCAA_EJE_ORDER)
COLOR_MAP_RESILIENCIA = _build_color_map(list(RESILIENCE_TAXONOMY.keys()))
COLOR_MAP_GENERO = {"Sí": "#B01E4B", "No": "#B6BAC2"}

DIMENSION_COLOR_MAPS = {
    "categoria_macro_primary": COLOR_MAP_MACRO,
    "eje_gcaa_primary": COLOR_MAP_GCAA,
    "atributos_resiliencia_primary": COLOR_MAP_RESILIENCIA,
    "enfoque_genero_primary": COLOR_MAP_GENERO,
}

# ------------------------------------------------------------------ CSS global
_CSS = f"""
<style>
:root {{
    --gm-primary: {COLOR_PRIMARY};
    --gm-border: {COLOR_BORDER};
}}

html, body, [class*="css"], [data-testid="stAppViewContainer"] {{
    font-family: {FONT_FAMILY} !important;
}}

/* -------- spacing compacto -------- */
.block-container {{
    padding-top: 1.6rem !important;
    padding-bottom: 2rem !important;
    max-width: 1400px;
}}
div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column"] {{ gap: 0.5rem; }}
hr {{ margin: 0.6rem 0 !important; }}
.stTabs {{ margin-top: -0.3rem; }}

h1, h2, h3, h4, h5, h6 {{
    font-family: {FONT_FAMILY} !important;
    font-weight: 700 !important;
    letter-spacing: -0.01em;
    color: {COLOR_TEXT};
}}
h2 {{ font-size: 1.15rem !important; margin: 0.3rem 0 0.4rem 0 !important; }}
h3 {{ font-size: 1.0rem !important; margin: 0.2rem 0 0.3rem 0 !important; }}
p {{ margin-bottom: 0.4rem; }}

/* -------- sidebar -------- */
[data-testid="stSidebar"] {{
    background-color: {COLOR_SIDEBAR_BG};
    border-right: 1px solid {COLOR_BORDER};
}}
[data-testid="stSidebar"] .block-container {{ padding-top: 1.2rem; }}

/* -------- KPI cards -------- */
[data-testid="stMetric"] {{
    background: #FFFFFF;
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
    padding: 10px 14px 8px 14px;
    box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
}}
[data-testid="stMetricLabel"] {{
    font-size: 0.72rem;
    font-weight: 600;
    color: {COLOR_MUTED};
    text-transform: uppercase;
    letter-spacing: 0.02em;
    line-height: 1.2;
}}
[data-testid="stMetricValue"] {{
    font-weight: 700;
    font-size: 1.5rem !important;
    color: {COLOR_TEXT};
}}
[data-testid="stMetricDelta"] {{ font-size: 0.72rem; }}

/* -------- header banner -------- */
.gm-header {{
    padding: 14px 20px;
    margin-bottom: 12px;
    border-radius: 10px;
    background: linear-gradient(120deg, {COLOR_PRIMARY_DARK} 0%, {COLOR_PRIMARY} 100%);
}}
.gm-header .gm-eyebrow {{
    color: rgba(255,255,255,0.72);
    font-size: 0.70rem;
    font-weight: 600;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    margin: 0 0 2px 0;
}}
.gm-header h1 {{
    color: #FFFFFF !important;
    margin: 0 0 3px 0 !important;
    font-size: 1.35rem !important;
}}
.gm-header p {{
    color: rgba(255,255,255,0.88);
    margin: 0;
    font-size: 0.85rem;
    max-width: 900px;
    line-height: 1.35;
}}

/* -------- section label -------- */
.gm-section-label {{
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: {COLOR_MUTED};
    margin: 4px 0 2px 0;
    border-bottom: 2px solid {COLOR_PRIMARY};
    display: inline-block;
    padding-bottom: 2px;
}}

/* -------- cards / news detail -------- */
.gm-card {{
    background: {COLOR_CARD_BG};
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 8px;
}}
.gm-badge {{
    display: inline-block;
    background: {COLOR_PRIMARY};
    color: #FFFFFF;
    font-size: 0.68rem;
    font-weight: 600;
    padding: 2px 9px;
    border-radius: 999px;
    letter-spacing: 0.01em;
    margin: 0 4px 4px 0;
}}
.gm-badge-outline {{
    display: inline-block;
    background: #FFFFFF;
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER};
    font-size: 0.68rem;
    font-weight: 600;
    padding: 2px 9px;
    border-radius: 999px;
    margin: 0 4px 4px 0;
}}
.gm-meta-row {{
    color: {COLOR_MUTED};
    font-size: 0.82rem;
    margin: 2px 0 10px 0;
}}
.gm-field-label {{
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: {COLOR_MUTED};
    margin: 10px 0 4px 0;
}}
.gm-hero-img {{
    width: 100%;
    max-height: 340px;
    object-fit: cover;
    border-radius: 10px;
    margin-bottom: 10px;
}}
.gm-placeholder-img {{
    width: 100%;
    height: 140px;
    border-radius: 10px;
    margin-bottom: 10px;
    background: linear-gradient(120deg, {COLOR_PRIMARY_DARK}, {COLOR_PRIMARY});
    display: flex;
    align-items: center;
    justify-content: center;
    color: rgba(255,255,255,0.85);
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.03em;
    text-transform: uppercase;
}}

/* -------- tabs -------- */
[data-testid="stTabs"] button [data-testid="stMarkdownContainer"] p {{
    font-weight: 600;
    font-size: 0.86rem;
}}
button[data-baseweb="tab"] {{ padding: 6px 12px !important; }}

/* -------- buttons -------- */
.stButton > button, .stDownloadButton > button, .stLinkButton > a {{
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.84rem;
    border: 1px solid {COLOR_BORDER};
}}

/* -------- dataframe -------- */
[data-testid="stDataFrame"] {{ border: 1px solid {COLOR_BORDER}; border-radius: 8px; overflow: hidden; }}

/* -------- expander -------- */
[data-testid="stExpander"] summary {{ font-size: 0.86rem; font-weight: 600; }}

/* -------- captions -------- */
[data-testid="stCaptionContainer"] {{ font-size: 0.76rem; }}
</style>
"""


def inject():
    st.markdown(_CSS, unsafe_allow_html=True)


def page_header(eyebrow: str, title: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div class="gm-header">
            <p class="gm-eyebrow">{eyebrow}</p>
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_label(text: str):
    st.markdown(f'<div class="gm-section-label">{text}</div>', unsafe_allow_html=True)


# ------------------------------------------------------------ tipografía proporcional
def _scale(height: int) -> dict:
    """Tamaños de fuente proporcionales a la altura real del gráfico."""
    h = max(height, 200)
    title = min(18, max(13, round(11 + h / 90)))
    axis = min(13, max(10, round(9 + h / 220)))
    legend = min(12, max(9, round(9 + h / 260)))
    tick = max(9, axis - 1)
    return {"title": title, "axis": axis, "legend": legend, "tick": tick}


def style_fig(fig, height=380, legend_title=None, title=None, showlegend=None, compact_margins=False):
    """Aplica tipografía proporcional, título y fondo consistentes a una figura Plotly."""
    s = _scale(height)
    top_margin = 46 if title else 18
    margins = dict(l=8, r=8, t=top_margin, b=8) if compact_margins else dict(l=10, r=10, t=top_margin, b=10)

    layout_kwargs = dict(
        height=height,
        font=dict(family=FONT_FAMILY, color=COLOR_TEXT, size=s["axis"]),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=margins,
        colorway=CATEGORY_PALETTE,
        legend=dict(font=dict(size=s["legend"]), title=dict(font=dict(size=s["legend"] + 1))),
        hoverlabel=dict(font=dict(family=FONT_FAMILY, size=s["axis"])),
    )
    if legend_title is not None:
        layout_kwargs["legend_title_text"] = legend_title
    if title is not None:
        layout_kwargs["title"] = dict(
            text=title, font=dict(family=FONT_FAMILY, size=s["title"], color=COLOR_TEXT, weight=700),
            x=0.0, xanchor="left", y=0.97, yanchor="top",
        )
    if showlegend is not None:
        layout_kwargs["showlegend"] = showlegend
    fig.update_layout(**layout_kwargs)
    fig.update_xaxes(tickfont=dict(size=s["tick"]), title_font=dict(size=s["axis"]))
    fig.update_yaxes(tickfont=dict(size=s["tick"]), title_font=dict(size=s["axis"]))
    return fig


def ensure_map_legend(fig, order, color_map=None):
    """Fuerza que la leyenda de un mapa liste SIEMPRE todas las categorías de `order`.

    En las vistas agregadas (ciudad, país) cada punto se pinta con la categoría
    *dominante* de ese grupo, así que Plotly solo dibuja en la leyenda las categorías
    que llegan a ser dominantes en algún grupo — por eso la leyenda se encogía al pasar
    a "País". Esta función añade una traza vacía (sin puntos visibles) por cada categoría
    que falte, con su color fijo, y reordena las trazas para respetar `order`. El
    resultado: la misma lista de categorías, en el mismo orden y color, en las tres vistas.
    """
    import plotly.graph_objects as go

    present = {t.name for t in fig.data if getattr(t, "name", None)}
    for cat in order:
        if cat in present:
            continue
        marker = dict(size=10)
        if color_map and cat in color_map:
            marker["color"] = color_map[cat]
        fig.add_trace(
            go.Scattermap(
                lat=[None], lon=[None], mode="markers", marker=marker,
                name=cat, showlegend=True, hoverinfo="skip",
            )
        )

    rank = {cat: i for i, cat in enumerate(order)}
    fig.data = tuple(
        sorted(fig.data, key=lambda t: rank.get(getattr(t, "name", None), len(rank)))
    )
    return fig


# ------------------------------------------------------------ componentes reutilizables
def kpi_row(items: list[tuple[str, str, str]], per_row: int = 4):
    """items: lista de (label, value, delta_opcional). Distribuye en filas de `per_row` columnas."""
    for i in range(0, len(items), per_row):
        chunk = items[i:i + per_row]
        cols = st.columns(per_row)
        for col, item in zip(cols, chunk):
            label, value = item[0], item[1]
            delta = item[2] if len(item) > 2 else None
            col.metric(label, value, delta)


def dataframe_full(df, column_config=None, height=None, hide_index=True):
    """Wrapper estándar para tablas a ancho completo, con altura razonable."""
    n_rows = min(len(df), 12)
    calc_height = height or max(160, 38 + n_rows * 35)
    st.dataframe(
        df, width="stretch", hide_index=hide_index,
        column_config=column_config or {}, height=calc_height,
    )


def badge_list(values, outline=False):
    cls = "gm-badge-outline" if outline else "gm-badge"
    spans = "".join(f'<span class="{cls}">{v}</span>' for v in values if v)
    st.markdown(f'<div>{spans}</div>', unsafe_allow_html=True)
