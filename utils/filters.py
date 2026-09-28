# -*- coding: utf-8 -*-
"""Criterios de búsqueda compartidos entre TODAS las vistas de la plataforma.

El Explorador (pages/2_Explorador.py) es quien renderiza los controles (render_search_filters),
pero el resultado se guarda en st.session_state para que Mapa, Evolución Temporal, Cruces y
Correlaciones y Cuencas —y el panorama de Inicio— lo apliquen también, vía get_filtered_df().
Streamlit comparte st.session_state entre todas las páginas de una misma sesión de navegador,
así que los criterios elegidos en el Explorador persisten al navegar a cualquier otra página.
"""
import streamlit as st

from utils.data import filter_by_multilabel, get_options, load_noticias

CRITERIOS_KEY = "criterios_busqueda"

CONSULTORA_OPCIONES = ["EIRL", "SpA", "Ltda"]


def render_search_filters(df) -> dict:
    """Sidebar de criterios de búsqueda. Se usa SOLO en el Explorador; el resultado queda
    guardado en session_state para que el resto de las páginas lo consuman con get_filtered_df().
    """
    actores_col = "actores_normalizados" if "actores_normalizados" in df.columns else "actores"

    st.markdown("**Criterios de búsqueda**")
    st.page_link("pages/8_Glosario.py", label="¿Qué significa cada categoría? → Glosario")

    texto = st.text_input("Buscar texto en título o contenido")

    f_fuente = st.multiselect("Fuente", get_options(df, "fuente")) if "fuente" in df.columns else []
    f_fg = st.radio(
        "Entidad: Fundación Glocal",
        ["Todas", "Solo Fundación Glocal", "Solo sin Fundación Glocal"],
        index=0,
    ) if "Fundación Glocal?" in df.columns else "Todas"
    f_consultora = st.multiselect("Consultora ejecutora", CONSULTORA_OPCIONES) if "Consultora" in df.columns else []

    st.divider()
    f_macro = st.multiselect("Categoría macro", get_options(df, "categoria_macro"))
    f_cat = st.multiselect("Categoría temática", get_options(df, "categorias"))
    f_meto = st.multiselect("Metodología", get_options(df, "metodologia"))
    f_actor = st.multiselect("Actores institucionales", get_options(df, actores_col))

    st.divider()
    f_gcaa_eje = st.multiselect("Eje GCAA", get_options(df, "eje_gcaa"))
    f_gcaa_obj = st.multiselect("Objetivo GCAA", get_options(df, "objetivo_gcaa"))
    f_resil = st.multiselect("Atributo de resiliencia", get_options(df, "atributos_resiliencia"))
    f_subresil = st.multiselect("Sub-atributo de resiliencia", get_options(df, "subatributos_resiliencia"))

    st.divider()
    f_benef_dir = st.multiselect("Beneficiarios directos", get_options(df, "beneficiarios_directos"))
    f_benef_ind = st.multiselect("Beneficiarios indirectos", get_options(df, "beneficiarios_indirectos"))
    f_genero = st.radio("Enfoque de género", ["Todos", "Solo con enfoque explícito", "Sin enfoque"], index=0)

    st.divider()
    f_anios = None
    f_incluir_sin_fecha = True
    if df["tiene_fecha"].any():
        anio_min, anio_max = int(df["anio"].min()), int(df["anio"].max())
        rango_sel = st.slider("Año", anio_min, anio_max, (anio_min, anio_max))
        f_incluir_sin_fecha = st.checkbox("Incluir experiencias sin fecha registrada", value=True)
        # Solo cuenta como "criterio activo" si de verdad recorta el rango completo del catálogo.
        if rango_sel != (anio_min, anio_max) or not f_incluir_sin_fecha:
            f_anios = rango_sel

    criterios = {
        "texto": texto,
        "fuente": f_fuente,
        "fundacion_glocal": f_fg,
        "consultora": f_consultora,
        "categoria_macro": f_macro,
        "categorias": f_cat,
        "metodologia": f_meto,
        "actores": f_actor,
        "eje_gcaa": f_gcaa_eje,
        "objetivo_gcaa": f_gcaa_obj,
        "atributos_resiliencia": f_resil,
        "subatributos_resiliencia": f_subresil,
        "beneficiarios_directos": f_benef_dir,
        "beneficiarios_indirectos": f_benef_ind,
        "genero": f_genero,
        "anios": f_anios,
        "incluir_sin_fecha": f_incluir_sin_fecha,
    }
    st.session_state[CRITERIOS_KEY] = criterios

    if st.button("Limpiar filtros"):
        st.session_state.pop(CRITERIOS_KEY, None)
        st.rerun()

    return criterios


def _n_criterios_activos(criterios: dict) -> int:
    if not criterios:
        return 0
    n = 0
    if criterios.get("texto"):
        n += 1
    for key in (
        "fuente", "consultora", "categoria_macro", "categorias", "metodologia", "actores",
        "eje_gcaa", "objetivo_gcaa", "atributos_resiliencia", "subatributos_resiliencia",
        "beneficiarios_directos", "beneficiarios_indirectos",
    ):
        if criterios.get(key):
            n += 1
    if criterios.get("fundacion_glocal") not in (None, "Todas"):
        n += 1
    if criterios.get("genero") not in (None, "Todos"):
        n += 1
    if criterios.get("anios") is not None:
        n += 1
    return n


def apply_search_filters(df, criterios: dict):
    """Aplica los criterios guardados por el Explorador sobre cualquier dataframe derivado
    de load_noticias() (mismas columnas base: categoria_macro, categorias, fuente, etc.)."""
    if not criterios:
        return df

    actores_col = "actores_normalizados" if "actores_normalizados" in df.columns else "actores"
    result = df

    texto = criterios.get("texto")
    if texto:
        t = texto.lower()
        result = result[
            result["titulo"].astype(str).str.lower().str.contains(t, na=False)
            | result["contenido_completo"].astype(str).str.lower().str.contains(t, na=False)
        ]

    if criterios.get("fuente") and "fuente" in result.columns:
        result = result[result["fuente"].isin(criterios["fuente"])]

    fg = criterios.get("fundacion_glocal")
    if fg == "Solo Fundación Glocal" and "Fundación Glocal?" in result.columns:
        result = result[result["Fundación Glocal?"].astype(str) == "Fundación Glocal"]
    elif fg == "Solo sin Fundación Glocal" and "Fundación Glocal?" in result.columns:
        result = result[result["Fundación Glocal?"].astype(str) != "Fundación Glocal"]

    if criterios.get("consultora") and "Consultora" in result.columns:
        result = result[result["Consultora"].astype(str).isin(criterios["consultora"])]

    result = filter_by_multilabel(result, "categoria_macro", criterios.get("categoria_macro"))
    result = filter_by_multilabel(result, "categorias", criterios.get("categorias"))
    result = filter_by_multilabel(result, "metodologia", criterios.get("metodologia"))
    result = filter_by_multilabel(result, actores_col, criterios.get("actores"))
    result = filter_by_multilabel(result, "eje_gcaa", criterios.get("eje_gcaa"))
    result = filter_by_multilabel(result, "objetivo_gcaa", criterios.get("objetivo_gcaa"))
    result = filter_by_multilabel(result, "atributos_resiliencia", criterios.get("atributos_resiliencia"))
    result = filter_by_multilabel(result, "subatributos_resiliencia", criterios.get("subatributos_resiliencia"))
    result = filter_by_multilabel(result, "beneficiarios_directos", criterios.get("beneficiarios_directos"))
    result = filter_by_multilabel(result, "beneficiarios_indirectos", criterios.get("beneficiarios_indirectos"))

    genero = criterios.get("genero")
    if genero == "Solo con enfoque explícito":
        result = result[result["enfoque_genero"].astype(str).str.startswith("Sí")]
    elif genero == "Sin enfoque":
        result = result[~result["enfoque_genero"].astype(str).str.startswith("Sí")]

    anios = criterios.get("anios")
    if anios is not None:
        mask_rango = result["anio"].between(anios[0], anios[1])
        if criterios.get("incluir_sin_fecha", True):
            mask_rango = mask_rango | (~result["tiene_fecha"])
        result = result[mask_rango]

    return result


def get_filtered_df(dedupe: bool = False):
    """Dataframe que deben usar TODAS las páginas de datos en vez de load_noticias() a secas:
    aplica los criterios de búsqueda activos (si el usuario ya pasó por el Explorador en esta
    sesión) y, si dedupe=True, excluye los duplicados secundarios (mismo evento en ambas
    fuentes) para no inflar conteos/gráficos agregados."""
    df = load_noticias()
    criterios = st.session_state.get(CRITERIOS_KEY)
    df = apply_search_filters(df, criterios)
    if dedupe and "es_duplicado_secundario" in df.columns:
        df = df[~df["es_duplicado_secundario"].astype(bool)]
    return df


def filters_summary_widget():
    """Componente compartido para el sidebar de cualquier página: cuántos criterios de
    búsqueda están activos + acceso rápido para editarlos o quitarlos, sin tener que volver
    al Explorador."""
    criterios = st.session_state.get(CRITERIOS_KEY)
    n = _n_criterios_activos(criterios)
    if n:
        st.caption(f"🔎 {n} criterio(s) de búsqueda activo(s) (definidos en el Explorador).")
        if st.button("Quitar todos los filtros", key="quitar_filtros_global"):
            st.session_state.pop(CRITERIOS_KEY, None)
            st.rerun()
    else:
        st.caption("🔎 Sin filtros — viendo todo el catálogo.")
    st.page_link("pages/2_Explorador.py", label="Editar criterios de búsqueda →")
    st.divider()
