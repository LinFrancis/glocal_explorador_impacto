# -*- coding: utf-8 -*-
"""Componentes compuestos reutilizables: ficha de noticia, badges, listas de enlaces."""
import re

import pandas as pd
import requests
import streamlit as st

from utils.data import format_fecha_es


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
    return "".join(f'<span class="{cls}">{v}</span>' for v in clean)


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
        st.markdown(f'<img src="{img_url}" alt="{alt}" class="gm-hero-img">', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="gm-placeholder-img">{macro_txt}</div>', unsafe_allow_html=True)

    # -------------------------------------------------- titulo + meta
    st.markdown(f"### {titulo}")
    st.markdown(
        f'<div class="gm-meta-row">{fecha} &nbsp;·&nbsp; {" / ".join(lugares)} &nbsp;·&nbsp; {macro_txt}</div>',
        unsafe_allow_html=True,
    )

    # -------------------------------------------------- resumen + contenido completo
    resumen = row.get("descripcion_catalogo") or row.get("preview_contenido")
    if isinstance(resumen, str) and resumen.strip():
        st.markdown(f"**{resumen.strip()}**")

    contenido = row.get("contenido_completo")
    if isinstance(contenido, str) and contenido.strip() and contenido.strip() != (resumen or "").strip():
        st.markdown(contenido.strip())

    st.divider()

    # -------------------------------------------------- clasificacion (agrupada y autoexplicativa)
    st.markdown('<div class="gm-section-label">Clasificación</div>', unsafe_allow_html=True)
    st.page_link("pages/8_Glosario.py", label="Ver todas las definiciones en el Glosario →")

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

    extra_links = row.get("enlaces_externos_lista") or []
    if extra_links:
        with st.expander(f"Enlaces relacionados ({len(extra_links)})"):
            for link in extra_links:
                st.markdown(f"- [{link}]({link})")

    # -------------------------------------------------- metadatos tecnicos
    with st.expander("Metadatos técnicos"):
        meta = {
            "Slug": row.get("slug"),
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
