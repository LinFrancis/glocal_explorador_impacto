# -*- coding: utf-8 -*-
"""Sistema de diseño compartido: tipografía, paleta, tarjetas y tema de gráficos."""
import streamlit as st

FONT_FAMILY = "'Montserrat', -apple-system, 'Segoe UI', sans-serif"

COLOR_PRIMARY = "#0B6E4F"
COLOR_PRIMARY_DARK = "#08402F"
COLOR_TEXT = "#111827"
COLOR_MUTED = "#6B7280"
COLOR_BORDER = "#E4E7EB"
COLOR_CARD_BG = "#F7F8FA"
COLOR_SIDEBAR_BG = "#F4F5F7"

SEQUENTIAL_SCALE = "Teal"
DIVERGING_SCALE = "RdYlGn"
CATEGORY_PALETTE = [
    "#0B6E4F", "#1F6FB2", "#B2531F", "#6B4FA0",
    "#B01E4B", "#3F7D20", "#7A5B1E", "#2B2D42",
]

PLOTLY_FONT = dict(family=FONT_FAMILY, color=COLOR_TEXT, size=13)

_CSS = f"""
<style>
html, body, [class*="css"], [data-testid="stAppViewContainer"] {{
    font-family: {FONT_FAMILY} !important;
}}

h1, h2, h3, h4, h5, h6 {{
    font-family: {FONT_FAMILY} !important;
    font-weight: 700 !important;
    letter-spacing: -0.01em;
    color: {COLOR_TEXT};
}}

[data-testid="stSidebar"] {{
    background-color: {COLOR_SIDEBAR_BG};
    border-right: 1px solid {COLOR_BORDER};
}}

[data-testid="stMetric"] {{
    background: #FFFFFF;
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
    padding: 14px 18px 10px 18px;
    box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
}}
[data-testid="stMetricLabel"] {{
    font-size: 0.80rem;
    font-weight: 600;
    color: {COLOR_MUTED};
    text-transform: uppercase;
    letter-spacing: 0.03em;
}}
[data-testid="stMetricValue"] {{
    font-weight: 700;
    color: {COLOR_TEXT};
}}

.gm-header {{
    padding: 20px 24px;
    margin-bottom: 18px;
    border-radius: 12px;
    background: linear-gradient(120deg, {COLOR_PRIMARY_DARK} 0%, {COLOR_PRIMARY} 100%);
}}
.gm-header .gm-eyebrow {{
    color: rgba(255,255,255,0.72);
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.10em;
    text-transform: uppercase;
    margin: 0 0 4px 0;
}}
.gm-header h1 {{
    color: #FFFFFF !important;
    margin: 0 0 6px 0 !important;
    font-size: 1.65rem !important;
}}
.gm-header p {{
    color: rgba(255,255,255,0.88);
    margin: 0;
    font-size: 0.95rem;
    max-width: 900px;
}}

.gm-section-label {{
    font-size: 0.76rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {COLOR_MUTED};
    margin: 6px 0 2px 0;
    border-bottom: 2px solid {COLOR_PRIMARY};
    display: inline-block;
    padding-bottom: 2px;
}}

.gm-card {{
    background: {COLOR_CARD_BG};
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
    padding: 16px 18px;
    margin-bottom: 10px;
}}

.gm-badge {{
    display: inline-block;
    background: {COLOR_PRIMARY};
    color: #FFFFFF;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 2px 9px;
    border-radius: 999px;
    letter-spacing: 0.02em;
}}

[data-testid="stTabs"] button [data-testid="stMarkdownContainer"] p {{
    font-weight: 600;
    font-size: 0.92rem;
}}

.stButton > button, .stDownloadButton > button {{
    border-radius: 8px;
    font-weight: 600;
    border: 1px solid {COLOR_BORDER};
}}
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


def style_fig(fig, height=None, legend_title=None, title=None, showlegend=None):
    """Aplica tipografía, título y fondo consistentes a una figura Plotly."""
    layout_kwargs = dict(
        font=PLOTLY_FONT,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=54 if title else 30, b=10),
        colorway=CATEGORY_PALETTE,
    )
    if height:
        layout_kwargs["height"] = height
    if legend_title is not None:
        layout_kwargs["legend_title_text"] = legend_title
    if title is not None:
        layout_kwargs["title"] = dict(
            text=title, font=dict(family=FONT_FAMILY, size=17, color=COLOR_TEXT, weight=700), x=0.0, xanchor="left",
        )
    if showlegend is not None:
        layout_kwargs["showlegend"] = showlegend
    fig.update_layout(**layout_kwargs)
    return fig
