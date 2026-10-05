# -*- coding: utf-8 -*-
"""Componentes compuestos reutilizables: ficha de noticia, badges, indicador de completitud.

Todo texto de los datos que se interpola en HTML pasa por `html.escape`: los datos son editables
por el equipo y se descargan de sitios externos, así que no se pueden tratar como confiables.
"""
import re
from html import escape

import altair as alt
import pandas as pd
import requests
import streamlit as st

from utils import completitud as comp
from utils import schema as S
from utils.data import format_fecha_es
from utils.style import COLOR_MUTED, COLOR_PRIMARY, entidad_logo_html

COLOR_NIVEL = {comp.NIVEL_COMPLETA: COLOR_PRIMARY, comp.NIVEL_PARCIAL: "#B2531F", comp.NIVEL_BASICA: "#B01E4B"}


def completitud_donut(pct: float, nivel: str, tamano: int = 120):
    """Dona minimalista (sin ejes ni leyenda) con el % en el centro, coloreada según el nivel."""
    datos = pd.DataFrame({"parte": ["completo", "falta"], "valor": [pct, max(0.0, 100.0 - pct)]})
    color = COLOR_NIVEL.get(nivel, COLOR_PRIMARY)
    arco = alt.Chart(datos).mark_arc(innerRadius=tamano * 0.34, outerRadius=tamano * 0.5, cornerRadius=3).encode(
        theta=alt.Theta("valor:Q", stack=True),
        color=alt.Color("parte:N", legend=None, scale=alt.Scale(domain=["completo", "falta"], range=[color, "#E9ECEF"])),
        order=alt.Order("parte:N", sort="descending"),
        tooltip=alt.value(None),
    )
    texto = alt.Chart(pd.DataFrame({"t": [f"{pct:.0f} %"]})).mark_text(
        fontSize=tamano * 0.19, fontWeight="bold", color=color).encode(text="t:N")
    return (arco + texto).properties(width=tamano, height=tamano).configure_view(strokeWidth=0)


def bloque_completitud(c: comp.Completitud) -> None:
    """Dona + contenido web / análisis + lista de lo que falta."""
    # Contenedor horizontal: dona y texto van lado a lado y pasan a dos líneas si no caben (sin superponerse).
    with st.container(horizontal=True, vertical_alignment="center", gap="medium"):
        st.altair_chart(completitud_donut(c.pct, c.nivel, 104), width="content")
        with st.container(width=240):
            st.markdown(f"**{c.nivel}** · {c.n_completos} de {c.n_total} campos clave")
            st.progress(c.pct_contenido / 100, text=f"Contenido web {c.pct_contenido:.0f} %")
            st.progress(c.pct_analisis / 100, text=f"Análisis {c.pct_analisis:.0f} %")
    if c.faltan:
        st.caption("Falta: " + ", ".join(S.etiqueta(k) for k in c.faltan))
    else:
        st.caption("Tiene todos los campos clave.")


@st.cache_data(ttl=3600, show_spinner=False)
def _image_is_valid(url: str) -> bool:
    if not isinstance(url, str) or not url.strip().lower().startswith(("http://", "https://")):
        return False
    try:
        resp = requests.head(url, timeout=4, allow_redirects=True)
        if resp.status_code >= 400:
            return False
        ctype = resp.headers.get("Content-Type", "")
        return ctype.startswith("image/") or ctype == "" or "octet-stream" in ctype
    except requests.RequestException:
        return False


def _sort_key(s: str):
    """Ordena por el número inicial del código (A5, 18., S7.2, 7. ...) y si no hay, alfabético."""
    m = re.match(r"^[A-Za-z]*\s*(\d+)(?:[.\-](\d+))?", s.strip())
    if m:
        return (0, int(m.group(1)), int(m.group(2) or 0), s)
    return (1, 0, 0, s)


def _split_sorted(value) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return []
    parts = [p.strip() for p in value.split(";") if p.strip()]
    return sorted(parts, key=_sort_key)


def _badges_html(values, outline=False):
    cls = "gm-badge-outline" if outline else "gm-badge"
    clean = [v for v in values if v and str(v).strip().lower() not in ("no aplica", "no especificado")]
    if not clean:
        return ""
    return "".join(f'<span class="{cls}">{escape(str(v))}</span>' for v in clean)


def _field_group(label: str, help_text: str, values: list[str], outline=False):
    if not values:
        return
    st.markdown(f'<div class="gm-field-label">{label}</div>', unsafe_allow_html=True)
    if help_text:
        st.caption(help_text)
    st.markdown(_badges_html(values, outline=outline), unsafe_allow_html=True)


def render_news_card(row: pd.Series):
    """Ficha completa de una experiencia: imagen, metadatos, clasificación agrupada y
    autoexplicativa, contenido completo, ubicación y enlaces. Muestra todo el contenido
    disponible del registro, no un resumen."""
    titulo = row.get("titulo", "Sin título")
    fecha = format_fecha_es(row.get("fecha_parsed"))
    lugares = _split_sorted(row.get("lugar")) or ["Ubicación no especificada"]
    macro = _split_sorted(row.get("categoria_macro"))
    macro_txt = macro[0] if macro else "Sin categoría"

    # -------------------------------------------------- imagen principal
    img_url = row.get("imagen_principal_url")
    if isinstance(img_url, str) and img_url.strip() and _image_is_valid(img_url):
        alt = row.get("imagen_alt") or titulo
        st.markdown(f'<img src="{escape(img_url.strip(), quote=True)}" alt="{escape(str(alt), quote=True)}" class="gm-hero-img">',
                    unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="gm-placeholder-img">{escape(macro_txt)}</div>', unsafe_allow_html=True)

    # -------------------------------------------------- titulo + meta
    st.markdown(f"### {titulo}")
    st.markdown(
        f'<div class="gm-meta-row">{escape(fecha)} &nbsp;·&nbsp; {escape(" / ".join(lugares))} &nbsp;·&nbsp; {escape(macro_txt)}</div>',
        unsafe_allow_html=True,
    )

    # -------------------------------------------------- badge fuente + logo de entidad ejecutora
    fuente = row.get("fuente")
    es_fg = str(row.get("Fundación Glocal?", "")).strip() == "Fundación Glocal"
    consultora = str(row.get("Consultora", "")).strip()
    if isinstance(fuente, str) and fuente.strip():
        st.markdown(_badges_html([fuente.strip()], outline=True), unsafe_allow_html=True)
    if es_fg or (consultora and consultora != "0"):
        st.markdown(entidad_logo_html(es_fg, height=24), unsafe_allow_html=True)

    # -------------------------------------------------- contenido completo
    # Ojo: NO se muestra también "descripcion_catalogo"/"preview_contenido" — son un resumen
    # hecho a partir de los primeros párrafos de este mismo texto, mostrar ambos duplica el
    # contenido en la ficha. El resumen queda solo como respaldo si el texto completo faltara.
    contenido = row.get("contenido_completo")
    if isinstance(contenido, str) and contenido.strip():
        st.markdown(contenido.strip())
    else:
        resumen = row.get("descripcion_catalogo") or row.get("preview_contenido")
        if isinstance(resumen, str) and resumen.strip():
            st.markdown(resumen.strip())

    st.divider()

    # -------------------------------------------------- clasificacion (agrupada y autoexplicativa)
    st.markdown('<div class="gm-section-label">Clasificación</div>', unsafe_allow_html=True)
    st.page_link("app_pages/glosario.py", label="Ver todas las definiciones en el Glosario →")

    _field_group("Categoría temática", "De qué habla la experiencia (codificación inductiva).", _split_sorted(row.get("categorias")))
    _field_group(
        "Eje GCAA", "Global Climate Action Agenda de la UNFCCC — marco internacional de acción climática.",
        _split_sorted(row.get("eje_gcaa")), outline=True,
    )
    _field_group("Objetivo GCAA", "Objetivo específico dentro del eje GCAA.", _split_sorted(row.get("objetivo_gcaa")), outline=True)
    _field_group(
        "Atributo de resiliencia", "Marco del CR2 (Race to Resilience) — capacidad que la experiencia fortalece.",
        _split_sorted(row.get("atributos_resiliencia")), outline=True,
    )
    _field_group("Sub-atributo de resiliencia", "", _split_sorted(row.get("subatributos_resiliencia")), outline=True)
    _field_group("Metodología de facilitación", "Con qué proceso o técnica se facilitó.", _split_sorted(row.get("metodologia")), outline=True)

    actores = _split_sorted(row.get("actores_normalizados") or row.get("actores"))
    if actores:
        st.markdown('<div class="gm-field-label">Actores institucionales</div>', unsafe_allow_html=True)
        st.markdown(_badges_html(actores, outline=True), unsafe_allow_html=True)

    st.divider()

    # -------------------------------------------------- beneficiarios y genero
    st.markdown('<div class="gm-section-label">Beneficiarios</div>', unsafe_allow_html=True)
    _field_group("Directos", "Quién participa o recibe la intervención directamente.", _split_sorted(row.get("beneficiarios_directos")))
    _field_group("Indirectos", "Quién se beneficia sin participar directamente.", _split_sorted(row.get("beneficiarios_indirectos")), outline=True)
    genero = row.get("enfoque_genero")
    if isinstance(genero, str) and genero.strip().lower() not in ("no", ""):
        st.markdown('<div class="gm-field-label">Enfoque de género</div>', unsafe_allow_html=True)
        st.markdown(genero)

    # -------------------------------------------------- variables propias (si hay)
    propias = [c for c in S.variables_activas() if str(row.get(c.key, "") or "").strip()]
    if propias:
        st.divider()
        st.markdown('<div class="gm-section-label">Variables propias</div>', unsafe_allow_html=True)
        for c in propias:
            valor = str(row.get(c.key)).strip()
            st.markdown(f'<div class="gm-field-label">{escape(c.label)}</div>', unsafe_allow_html=True)
            if c.tipo == S.ETIQUETAS or isinstance(c.opciones, tuple):
                st.markdown(_badges_html(S.dividir_etiquetas(valor), outline=True), unsafe_allow_html=True)
            else:
                st.markdown(valor)

    st.divider()

    # -------------------------------------------------- ubicacion detallada
    st.markdown('<div class="gm-section-label">Ubicación</div>', unsafe_allow_html=True)
    lats = [p.strip() for p in str(row.get("sitios_lat") or "").split(";")]
    lons = [p.strip() for p in str(row.get("sitios_lon") or "").split(";")]
    paises = [p.strip() for p in str(row.get("sitios_pais") or "").split(";")]
    cuencas = [p.strip() for p in str(row.get("sitios_cuenca_nombre") or "").split(";")]
    lugares_raw = [p.strip() for p in str(row.get("lugar") or "").split(";") if p.strip()]

    def _at(lst, i):
        return lst[i] if i < len(lst) and lst[i] else "—"

    if lugares_raw:
        sitios_rows = []
        for i, lg in enumerate(lugares_raw):
            sitios_rows.append({
                "Sitio": lg,
                "País": _at(paises, i),
                "Cuenca": _at(cuencas, i),
                "Lat": _at(lats, i),
                "Lon": _at(lons, i),
            })
        st.dataframe(pd.DataFrame(sitios_rows), hide_index=True, width="stretch")
    else:
        st.caption("Sin ubicación registrada.")

    st.divider()

    # -------------------------------------------------- enlaces
    st.markdown('<div class="gm-section-label">Enlaces</div>', unsafe_allow_html=True)
    url_original = row.get("url_noticia")
    if isinstance(url_original, str) and url_original.strip():
        st.link_button("Leer noticia original ↗", url_original)

    carpeta = row.get("carpeta_proyecto")
    if isinstance(carpeta, str) and carpeta.strip():
        st.link_button("Abrir carpeta del proyecto ↗", carpeta.strip(), type="primary")
    docs = [u.strip() for u in str(row.get("documentos_proyecto") or "").split("|") if u.strip()]
    if docs:
        with st.expander(f"Otros enlaces del proyecto ({len(docs)})"):
            for u in docs:
                st.markdown(f"- [{u}]({u})")

    extra_links = row.get("enlaces_externos_lista") or []
    if extra_links:
        with st.expander(f"Enlaces relacionados ({len(extra_links)})"):
            for link in extra_links:
                st.markdown(f"- [{link}]({link})")

    # -------------------------------------------------- metadatos tecnicos
    with st.expander("Metadatos técnicos"):
        meta = {
            "Identificador web (slug)": row.get("slug"),
            "Fecha de publicación (web)": format_fecha_es(row.get("fecha_parsed")),
            "Fecha de última modificación (web)": row.get("fecha_modificacion_web"),
            "Autor": row.get("autor") or "No informado",
            "N° de enlaces externos": row.get("num_enlaces_externos"),
            "Fecha/hora de extracción del registro": row.get("timestamp_extraccion"),
        }
        for k, v in meta.items():
            if v is None or v == "":
                continue
            if not isinstance(v, str) and pd.isna(v):
                continue
            st.markdown(f"**{k}:** {v}")
