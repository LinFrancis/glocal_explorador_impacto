# -*- coding: utf-8 -*-
"""Componentes compuestos reutilizables: ficha de noticia, badges, listas de enlaces."""
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


def _badges_html(values, outline=False):
    cls = "gm-badge-outline" if outline else "gm-badge"
    clean = [v for v in values if v and str(v).strip().lower() not in ("no aplica", "no especificado")]
    if not clean:
        return ""
    return "".join(f'<span class="{cls}">{v}</span>' for v in clean)


def _split_multilabel(value) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return []
    return [p.strip() for p in value.split(";") if p.strip()]


def render_news_card(row: pd.Series):
    """Ficha completa de una experiencia: imagen, metadatos, clasificación, contenido y enlaces."""
    titulo = row.get("titulo", "Sin título")
    fecha = format_fecha_es(row.get("fecha_parsed"))
    lugar = row.get("lugar") or "Ubicación no especificada"
    macro = _split_multilabel(row.get("categoria_macro"))
    macro_txt = macro[0] if macro else "Sin categoría"

    # -------------------------------------------------- imagen principal
    img_url = row.get("imagen_principal_url")
    if isinstance(img_url, str) and img_url.strip() and _image_is_valid(img_url):
        alt = row.get("imagen_alt") or titulo
        st.markdown(
            f'<img src="{img_url}" alt="{alt}" class="gm-hero-img">',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="gm-placeholder-img">{macro_txt}</div>',
            unsafe_allow_html=True,
        )

    # -------------------------------------------------- titulo + meta
    st.markdown(f"### {titulo}")
    st.markdown(
        f'<div class="gm-meta-row">{fecha} &nbsp;·&nbsp; {lugar} &nbsp;·&nbsp; {macro_txt}</div>',
        unsafe_allow_html=True,
    )

    # -------------------------------------------------- resumen
    resumen = row.get("descripcion_catalogo") or row.get("preview_contenido")
    if isinstance(resumen, str) and resumen.strip():
        st.markdown(resumen.strip())

    # -------------------------------------------------- clasificacion
    clasif_html = ""
    clasif_html += _badges_html(_split_multilabel(row.get("categorias")))
    clasif_html += _badges_html(_split_multilabel(row.get("eje_gcaa")), outline=True)
    clasif_html += _badges_html(_split_multilabel(row.get("atributos_resiliencia")), outline=True)
    if clasif_html:
        st.markdown('<div class="gm-field-label">Clasificación</div>', unsafe_allow_html=True)
        st.markdown(f"<div>{clasif_html}</div>", unsafe_allow_html=True)

    metodologia = _split_multilabel(row.get("metodologia"))
    actores = _split_multilabel(row.get("actores_normalizados") or row.get("actores"))
    if metodologia or actores:
        c1, c2 = st.columns(2)
        with c1:
            if metodologia:
                st.markdown('<div class="gm-field-label">Metodología</div>', unsafe_allow_html=True)
                st.markdown(_badges_html(metodologia, outline=True), unsafe_allow_html=True)
        with c2:
            if actores:
                st.markdown('<div class="gm-field-label">Actores institucionales</div>', unsafe_allow_html=True)
                st.markdown(_badges_html(actores[:8], outline=True), unsafe_allow_html=True)
                if len(actores) > 8:
                    st.caption(f"+ {len(actores) - 8} más")

    benef_dir = _split_multilabel(row.get("beneficiarios_directos"))
    benef_ind = _split_multilabel(row.get("beneficiarios_indirectos"))
    genero = row.get("enfoque_genero")
    if benef_dir or benef_ind or (isinstance(genero, str) and genero.startswith("Sí")):
        st.markdown('<div class="gm-field-label">Beneficiarios</div>', unsafe_allow_html=True)
        if benef_dir:
            st.markdown(f"**Directos:** {_badges_html(benef_dir)}", unsafe_allow_html=True)
        if benef_ind:
            st.markdown(f"**Indirectos:** {_badges_html(benef_ind)}", unsafe_allow_html=True)
        if isinstance(genero, str) and genero.startswith("Sí"):
            st.markdown(f"**Enfoque de género:** {genero}")

    # -------------------------------------------------- contenido completo
    contenido = row.get("contenido_completo")
    if isinstance(contenido, str) and contenido.strip():
        with st.expander("Leer contenido completo"):
            st.write(contenido.strip())

    # -------------------------------------------------- enlaces
    st.markdown('<div class="gm-field-label">Enlaces</div>', unsafe_allow_html=True)
    url_original = row.get("url_noticia")
    if isinstance(url_original, str) and url_original.strip():
        st.link_button("Leer noticia original ↗", url_original, width="content")

    extra_links = row.get("enlaces_externos_lista") or []
    if extra_links:
        with st.expander(f"Enlaces relacionados ({len(extra_links)})"):
            for link in extra_links:
                st.markdown(f"- [{link}]({link})")
