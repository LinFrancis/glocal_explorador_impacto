# -*- coding: utf-8 -*-
"""Criterios de búsqueda compartidos entre TODAS las vistas de la plataforma.

El Explorador (app_pages/explorador.py) es quien renderiza los controles (render_search_filters),
pero el resultado se guarda en st.session_state para que Mapa, Evolución Temporal, Cruces y
Correlaciones y Cuencas —y el panorama de Inicio— lo apliquen también, vía get_filtered_df().
Streamlit comparte st.session_state entre todas las páginas de una misma sesión de navegador,
así que los criterios elegidos en el Explorador persisten al navegar a cualquier otra página.
"""
import pandas as pd
import streamlit as st

from utils import completitud
from utils import schema as S
from utils.variables import SIN_DATO
from utils.data import filter_by_multilabel, get_options, load_noticias, search_tokens
from utils.style import logo_fundacion_html, logo_glocalminds_html

# rapidfuzz es la opción rápida (C++) para el buscador difuso; si el entorno de despliegue no
# llegó a instalarla (p. ej. un rebuild de Streamlit Cloud que todavía no tomó el requirements.txt
# nuevo), se cae a una implementación equivalente en difflib de la librería estándar — más lenta,
# pero la app nunca debe romperse por esto.
try:
    from rapidfuzz import fuzz as _fuzz

    def _ratio(a: str, b: str) -> float:
        return _fuzz.ratio(a, b)
except ImportError:
    import difflib

    def _ratio(a: str, b: str) -> float:
        return difflib.SequenceMatcher(None, a, b).ratio() * 100

CRITERIOS_KEY = "criterios_busqueda"

# Una opción por cada personalidad jurídica real que ejecuta las experiencias del catálogo.
PERSONALIDAD_OPCIONES = ["Fundación Glocal", "Consultora EIRL", "Consultora SpA", "Consultora Ltda"]


# Claves de los widgets del panel de filtros. Los criterios guardados (CRITERIOS_KEY) son la fuente
# de verdad: al volver al Explorador desde otra página los widgets se re-inicializan desde ellos, y
# "Limpiar filtros" borra criterios y widgets a la vez.
K_TEXTO, K_FUZZY, K_FUENTE, K_TIPO, K_PERSONALIDAD = "f_texto", "filtro_fuzzy_umbral", "f_fuente", "f_tipo", "f_personalidad"
K_MACRO, K_CAT, K_METO, K_ACTOR = "f_macro", "f_cat", "f_meto", "f_actor"
K_EJE, K_OBJ, K_RESIL, K_SUBRESIL = "f_eje", "f_obj", "f_resil", "f_subresil"
K_BENEF_DIR, K_BENEF_IND, K_GENERO = "f_benef_dir", "f_benef_ind", "f_genero"
K_ANIOS, K_SIN_FECHA, K_COMPLETITUD = "f_anios", "f_sin_fecha", "f_completitud"
PREFIJO_VAR = "f_var_"                      # widgets de las variables propias: f_var_<clave>
_WIDGET_KEYS = (
    K_TEXTO, K_FUZZY, K_FUENTE, K_TIPO, K_PERSONALIDAD, K_MACRO, K_CAT, K_METO, K_ACTOR, K_EJE, K_OBJ,
    K_RESIL, K_SUBRESIL, K_BENEF_DIR, K_BENEF_IND, K_GENERO, K_ANIOS, K_SIN_FECHA, K_COMPLETITUD,
)


def limpiar_filtros() -> None:
    """Borra los criterios y el estado de todos los widgets. Úsalo como `on_click` (se ejecuta antes
    de que los widgets se vuelvan a dibujar, por eso puede modificar su estado)."""
    st.session_state.pop(CRITERIOS_KEY, None)
    for k in _WIDGET_KEYS:
        st.session_state.pop(k, None)
    for k in [k for k in st.session_state if str(k).startswith(PREFIJO_VAR)]:
        st.session_state.pop(k, None)


def _sembrar(key: str, valor, opciones=None) -> None:
    """Si el widget no tiene estado (primera vez o volvió de otra página), parte del criterio guardado."""
    if key in st.session_state:
        return
    if opciones is not None:
        st.session_state[key] = [v for v in (valor or []) if v in opciones]
    elif valor is not None:
        st.session_state[key] = valor


def _multi(etiqueta: str, key: str, opciones: list[str], guardados: dict, criterio: str) -> list[str]:
    _sembrar(key, guardados.get(criterio), opciones)
    return st.multiselect(etiqueta, opciones, key=key)


def render_search_filters(df) -> dict:
    """Sidebar de criterios de búsqueda. Se usa SOLO en el Explorador; el resultado queda
    guardado en session_state para que el resto de las páginas lo consuman con get_filtered_df().
    """
    actores_col = "actores_normalizados" if "actores_normalizados" in df.columns else "actores"
    g = st.session_state.get(CRITERIOS_KEY) or {}

    st.markdown("**Criterios de búsqueda**")
    st.page_link("app_pages/glosario.py", label="¿Qué significa cada categoría? → Glosario")

    _sembrar(K_TEXTO, g.get("texto"))
    texto = st.text_input("Buscar texto en título o contenido", key=K_TEXTO)
    _sembrar(K_FUZZY, g.get("fuzzy_umbral"))
    f_fuzzy = st.slider(
        "Nivel de coincidencia del buscador", min_value=50, max_value=100, value=100, step=5,
        format="%d%%", key=K_FUZZY,
        help="100% = coincidencia exacta/literal. Bajar el porcentaje encuentra resultados "
             "aunque falte una tilde, haya un error de tipeo o solo una parte de la palabra "
             "coincida (p. ej. 'plan' con umbral bajo encuentra 'planificación').",
    )

    f_fuente = _multi("Fuente", K_FUENTE, get_options(df, "fuente"), g, "fuente") if "fuente" in df.columns else []
    f_tipo_info = (_multi("Tipo de información", K_TIPO, get_options(df, "tipo_informacion"), g, "tipo_informacion")
                   if "tipo_informacion" in df.columns else [])

    f_personalidad = []
    if "Fundación Glocal?" in df.columns or "Consultora" in df.columns:
        f_personalidad = _multi("Personalidad jurídica ejecutora", K_PERSONALIDAD, PERSONALIDAD_OPCIONES, g, "personalidad_juridica")
        sufijo_preview = entidad_titulo_sufijo({"personalidad_juridica": f_personalidad})
        if sufijo_preview:
            logos_html = ""
            if "Fundación Glocal" in f_personalidad:
                logos_html += logo_fundacion_html(22)
            if any(o != "Fundación Glocal" for o in f_personalidad):
                logos_html += logo_glocalminds_html(22)
            if logos_html:
                st.markdown(logos_html, unsafe_allow_html=True)

    f_completitud = _multi("Nivel de completitud", K_COMPLETITUD, list(completitud.NIVELES), g, "completitud")

    # ---- variables propias (categorías analíticas creadas por el equipo)
    f_variables: dict = {}
    propias = [c for c in S.variables_activas() if c.key in df.columns]
    if propias:
        st.divider()
        st.markdown("**Variables propias**")
        guardadas = g.get("variables") or {}
        for c in propias:
            key = PREFIJO_VAR + c.key
            if isinstance(c.opciones, tuple):                     # opción única / múltiple / Sí-No: lista de opciones
                opciones_v = list(c.opciones) + [SIN_DATO]
                _sembrar(key, guardadas.get(c.key), opciones_v)
                f_variables[c.key] = st.multiselect(c.label, opciones_v, key=key)
            elif c.tipo == S.NUMERO:
                nums = pd.to_numeric(df[c.key].astype(str).str.replace(",", "."), errors="coerce").dropna()
                if nums.empty or nums.min() == nums.max():
                    continue
                lo, hi = float(nums.min()), float(nums.max())
                previo = guardadas.get(c.key)
                if previo and key not in st.session_state:
                    st.session_state[key] = (max(lo, float(previo[0])), min(hi, float(previo[1])))
                rango = st.slider(c.label, lo, hi, (lo, hi), key=key)
                f_variables[c.key] = list(rango) if rango != (lo, hi) else None
            elif c.tipo in (S.TEXTO, S.TEXTO_LARGO, S.URL):
                _sembrar(key, guardadas.get(c.key))
                f_variables[c.key] = st.text_input(f"{c.label} (contiene)", key=key)
        f_variables = {k: v for k, v in f_variables.items() if v}

    st.divider()
    f_macro = _multi("Categoría macro", K_MACRO, get_options(df, "categoria_macro"), g, "categoria_macro")
    f_cat = _multi("Categoría temática", K_CAT, get_options(df, "categorias"), g, "categorias")
    f_meto = _multi("Metodología", K_METO, get_options(df, "metodologia"), g, "metodologia")
    f_actor = _multi("Actores institucionales", K_ACTOR, get_options(df, actores_col), g, "actores")

    st.divider()
    f_gcaa_eje = _multi("Eje GCAA", K_EJE, get_options(df, "eje_gcaa"), g, "eje_gcaa")
    f_gcaa_obj = _multi("Objetivo GCAA", K_OBJ, get_options(df, "objetivo_gcaa"), g, "objetivo_gcaa")
    f_resil = _multi("Atributo de resiliencia", K_RESIL, get_options(df, "atributos_resiliencia"), g, "atributos_resiliencia")
    f_subresil = _multi("Sub-atributo de resiliencia", K_SUBRESIL, get_options(df, "subatributos_resiliencia"), g, "subatributos_resiliencia")

    st.divider()
    f_benef_dir = _multi("Beneficiarios directos", K_BENEF_DIR, get_options(df, "beneficiarios_directos"), g, "beneficiarios_directos")
    f_benef_ind = _multi("Beneficiarios indirectos", K_BENEF_IND, get_options(df, "beneficiarios_indirectos"), g, "beneficiarios_indirectos")
    opciones_genero = ["Todos", "Solo con enfoque explícito", "Sin enfoque"]
    _sembrar(K_GENERO, g.get("genero") if g.get("genero") in opciones_genero else None)
    f_genero = st.radio("Enfoque de género", opciones_genero, key=K_GENERO)

    st.divider()
    f_anios = None
    f_incluir_sin_fecha = True
    if df["tiene_fecha"].any():
        anio_min, anio_max = int(df["anio"].min()), int(df["anio"].max())
        previo = g.get("anios")
        if previo is not None and K_ANIOS not in st.session_state:
            st.session_state[K_ANIOS] = (max(anio_min, previo[0]), min(anio_max, previo[1]))
        rango_sel = st.slider("Año", anio_min, anio_max, (anio_min, anio_max), key=K_ANIOS)
        _sembrar(K_SIN_FECHA, g.get("incluir_sin_fecha"))
        f_incluir_sin_fecha = st.checkbox("Incluir experiencias sin fecha registrada", value=True, key=K_SIN_FECHA)
        # Solo cuenta como "criterio activo" si de verdad recorta el rango completo del catálogo.
        if rango_sel != (anio_min, anio_max) or not f_incluir_sin_fecha:
            f_anios = rango_sel

    criterios = {
        "texto": texto,
        "fuzzy_umbral": f_fuzzy,
        "fuente": f_fuente,
        "tipo_informacion": f_tipo_info,
        "personalidad_juridica": f_personalidad,
        "completitud": f_completitud,
        "variables": f_variables,
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

    st.button("Limpiar filtros", on_click=limpiar_filtros, key="limpiar_filtros_explorador", icon=":material/filter_alt_off:")

    return criterios


def _n_criterios_activos(criterios: dict) -> int:
    if not criterios:
        return 0
    n = 0
    if criterios.get("texto"):
        n += 1
    for key in (
        "fuente", "tipo_informacion", "personalidad_juridica", "completitud", "categoria_macro", "categorias",
        "metodologia", "actores", "eje_gcaa", "objetivo_gcaa", "atributos_resiliencia",
        "subatributos_resiliencia", "beneficiarios_directos", "beneficiarios_indirectos",
    ):
        if criterios.get(key):
            n += 1
    n += len(criterios.get("variables") or {})
    if criterios.get("genero") not in (None, "Todos"):
        n += 1
    if criterios.get("anios") is not None:
        n += 1
    return n


def entidad_titulo_sufijo(criterios: dict) -> str:
    """Sufijo para agregar al título de cada gráfico cuando hay un filtro de personalidad
    jurídica activo, para que el gráfico se lea en su contexto (p. ej. " — Fundación Glocal")."""
    seleccion = (criterios or {}).get("personalidad_juridica") or []
    if not seleccion or len(seleccion) >= len(PERSONALIDAD_OPCIONES):
        return ""
    return " — " + " + ".join(seleccion)


def _score_palabra(query_tok: str, palabra: str) -> float:
    """Similitud entre una palabra buscada y una palabra del catálogo (ambas ya sin tildes y en
    minúscula). Exacta -> 100. Una es prefijo de la otra (p. ej. 'plan' de 'planificación') ->
    96, para que aparezca al bajar apenas el umbral desde 100 sin inundar la búsqueda estricta
    de falsos positivos cortos (fuzz.partial_ratio a secas hace justamente eso con palabras
    de 4-5 letras). El resto de los casos (tildes distintas, errores de tipeo, género/plural)
    se resuelve con la razón de Levenshtein completa."""
    if query_tok == palabra:
        return 100
    if len(query_tok) >= 3 and (palabra.startswith(query_tok) or query_tok.startswith(palabra)):
        return 96
    return _ratio(query_tok, palabra)


def _coincide_difuso(palabras: list[str], query_tokens: list[str], umbral: int) -> bool:
    """True si CADA palabra de la búsqueda encuentra, entre las palabras de la fila, alguna lo
    bastante parecida (umbral 100 = literal/exacta; más bajo tolera tildes, errores de tipeo o
    coincidencia parcial, p. ej. 'plan' ~ 'planificación')."""
    if not query_tokens:
        return True
    if not palabras:
        return False
    for qt in query_tokens:
        mejor = max((_score_palabra(qt, palabra) for palabra in palabras), default=0)
        if mejor < umbral:
            return False
    return True


def apply_search_filters(df, criterios: dict):
    """Aplica los criterios guardados por el Explorador sobre cualquier dataframe derivado
    de load_noticias() (mismas columnas base: categoria_macro, categorias, fuente, etc.)."""
    if not criterios:
        return df

    actores_col = "actores_normalizados" if "actores_normalizados" in df.columns else "actores"
    result = df

    texto = criterios.get("texto")
    if texto and texto.strip():
        query_tokens = search_tokens(texto)
        umbral = criterios.get("fuzzy_umbral", 100)
        if query_tokens and "_palabras_busqueda" in result.columns:
            result = result[result["_palabras_busqueda"].apply(
                lambda palabras: _coincide_difuso(palabras, query_tokens, umbral)
            )]
        elif query_tokens:
            t = texto.lower()
            result = result[
                result["titulo"].astype(str).str.lower().str.contains(t, na=False)
                | result["contenido_completo"].astype(str).str.lower().str.contains(t, na=False)
            ]

    if criterios.get("fuente") and "fuente" in result.columns:
        result = result[result["fuente"].isin(criterios["fuente"])]

    if criterios.get("tipo_informacion") and "tipo_informacion" in result.columns:
        result = result[result["tipo_informacion"].isin(criterios["tipo_informacion"])]

    personalidad = criterios.get("personalidad_juridica")
    if personalidad and ("Fundación Glocal?" in result.columns or "Consultora" in result.columns):
        mask = False
        if "Fundación Glocal" in personalidad and "Fundación Glocal?" in result.columns:
            mask = mask | (result["Fundación Glocal?"].astype(str) == "Fundación Glocal")
        consultora_tipos = [o.replace("Consultora ", "") for o in personalidad if o != "Fundación Glocal"]
        if consultora_tipos and "Consultora" in result.columns:
            mask = mask | result["Consultora"].astype(str).isin(consultora_tipos)
        result = result[mask]

    niveles = criterios.get("completitud")
    if niveles and "completitud" in result.columns:
        result = result[completitud.nivel_df(result["completitud"]).isin(niveles)]

    for clave, valor in (criterios.get("variables") or {}).items():
        campo = S.CAMPO.get(clave)
        if not valor or campo is None or clave not in result.columns:
            continue
        col = result[clave].fillna("").astype(str)
        if isinstance(campo.opciones, tuple):                          # lista de opciones: cualquiera de las elegidas
            elegidas = set(valor)
            con_vacio = SIN_DATO in elegidas

            def _coincide(celda, elegidas=elegidas, con_vacio=con_vacio):
                partes = S.dividir_etiquetas(celda)
                return (not partes and con_vacio) or any(p in elegidas for p in partes)
            result = result[col.map(_coincide)]
        elif campo.tipo == S.NUMERO:                                   # rango [mín, máx]
            nums = pd.to_numeric(col.str.replace(",", "."), errors="coerce")
            result = result[nums.between(float(valor[0]), float(valor[1]))]
        else:                                                           # texto: contiene
            result = result[col.str.lower().str.contains(str(valor).strip().lower(), regex=False)]

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
        st.caption(f"{n} criterio(s) de búsqueda activo(s) (definidos en el Explorador).")
        st.button("Quitar todos los filtros", key="quitar_filtros_global", on_click=limpiar_filtros)
    else:
        st.caption("Sin filtros — viendo todo el catálogo.")
    st.page_link("app_pages/explorador.py", label="Editar criterios de búsqueda →")
    st.divider()
