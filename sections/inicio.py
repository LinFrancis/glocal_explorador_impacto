# -*- coding: utf-8 -*-
"""Panel de Inicio: estado de la base (gestión) + accesos rápidos + panorama analítico.

La parte de gestión usa el catálogo COMPLETO; el panorama analítico del final respeta los
criterios de búsqueda activos (definidos en Explorador Glocal).
"""
from html import escape
from pathlib import Path

import altair as alt
import plotly.express as px
import streamlit as st

from sections import ayuda
from utils import auth
from utils import schema as S
from utils import vistas
from utils.completitud import NIVEL_BASICA, NIVEL_COMPLETA, NIVEL_PARCIAL, NIVELES
from utils.data import get_options, leer_base_cruda, leer_hoja, load_mapa_ubicaciones, load_noticias
from utils.filters import entidad_titulo_sufijo, filters_summary_widget, get_filtered_df
from utils.style import COLOR_PRIMARY, dual_logo_html, inject, page_header, section_label, style_fig
from utils.ui import abrir_ficha

RAIZ = Path(__file__).resolve().parent.parent
COLOR_NIVEL = {NIVEL_COMPLETA: COLOR_PRIMARY, NIVEL_PARCIAL: "#B2531F", NIVEL_BASICA: "#B01E4B"}

# (ruta de la página, título, descripción, icono)
ACCESOS = [
    ("app_pages/explorador.py", "Explorador Glocal", "Busca, filtra, selecciona y exporta noticias.", ":material/travel_explore:"),
    ("app_pages/ficha.py", "Fichas de noticia", "Edita datos, categorías y notas de cada noticia.", ":material/article:"),
    ("app_pages/tabla.py", "Tabla de datos", "Edita la base completa como una planilla.", ":material/table_view:"),
    ("app_pages/carga.py", "Cargar información", "Agrega noticias a mano o desde un archivo.", ":material/upload_file:"),
    ("app_pages/sincronizar.py", "Sincronizar con la web", "Busca noticias nuevas en los dos sitios.", ":material/sync:"),
    ("app_pages/historial.py", "Historial de cambios", "Quién cambió qué, y deshacer.", ":material/history:"),
    ("app_pages/administracion.py", "Administración", "Categorías, calidad de datos y respaldo.", ":material/admin_panel_settings:"),
]


def _existe(ruta: str) -> bool:
    return (RAIZ / ruta).exists()


def _aviso_sincronizacion(hist) -> None:
    sync = hist[hist["accion"] == S.ACC_SINCRONIZAR] if len(hist) else hist
    if sync.empty:
        st.info("Aún no hay sincronizaciones registradas. Cuando quieras buscar noticias nuevas, "
                "usa «Sincronizar con la web».", icon=":material/sync:")
        return
    ultima = sync["fecha_hora"].max()
    dias = vistas.dias_desde(ultima)
    texto = f"Última sincronización con la web: {vistas.hace_cuanto(ultima)} ({vistas.fecha_corta(ultima)})."
    if dias is not None and dias >= S.DIAS_ALERTA_SINCRONIZACION:
        st.warning(f"{texto} Han pasado {dias} días: conviene revisar si hay noticias nuevas.",
                   icon=":material/sync_problem:")
    else:
        st.caption(f":material/sync: {texto}")


def _kpis_de_gestion(df_all, hist) -> None:
    total = len(df_all)
    n_glocal = int((df_all["fuente"] == "glocalminds.com").sum())
    n_fund = int((df_all["fuente"] == "fundacionglocal.org").sum())
    n_completas = int((df_all["completitud"] >= S.UMBRAL_COMPLETA).sum())
    n_dup = int(df_all["es_duplicado_secundario"].astype(bool).sum()) if "es_duplicado_secundario" in df_all else 0
    ultima = hist["fecha_hora"].max() if len(hist) else ""
    quien = hist.sort_values("id_cambio").iloc[-1]["usuario"] if len(hist) else ""
    n_campos = len(S.CLAVE_CONTENIDO_CAMPOS) + len(S.CLAVE_ANALISIS_CAMPOS)

    c1, c2, c3 = st.columns(3)
    c1.metric("Noticias en la base", f"{total}", f"{n_dup} duplicadas entre sitios" if n_dup else None,
              delta_color="off", delta_arrow="off")
    c2.metric("Glocalminds", f"{n_glocal}", "glocalminds.com", delta_color="off", delta_arrow="off")
    c3.metric("Fundación Glocal", f"{n_fund}", "fundacionglocal.org", delta_color="off", delta_arrow="off")
    c4, c5, c6 = st.columns(3)
    c4.metric("Completitud media", f"{df_all['completitud'].mean():.0f} %")
    c5.metric("Noticias completas", f"{n_completas}", f"{n_completas / total:.0%} de la base" if total else None,
              delta_color="off", delta_arrow="off",
              help=f"Completa = al menos {S.UMBRAL_COMPLETA} % de los {n_campos} campos clave.")
    c6.metric("Última edición", vistas.hace_cuanto(ultima) or "—",
              f"por {quien}" if quien else "Sin ediciones aún", delta_color="off", delta_arrow="off")


def _accesos_rapidos() -> None:
    accesos = [a for a in ACCESOS if _existe(a[0])]
    for i in range(0, len(accesos), 3):
        cols = st.columns(3)
        for col, (ruta, titulo, texto, icono) in zip(cols, accesos[i:i + 3]):
            with col, st.container(border=True):
                st.markdown(f"**{titulo}**")
                st.caption(texto)
                st.page_link(ruta, label="Abrir", icon=icono)


def _niveles(df_all) -> None:
    section_label("Noticias por nivel de completitud")
    niv = vistas.niveles_de_completitud(df_all)
    grafico = (
        alt.Chart(niv)
        .mark_bar(cornerRadiusEnd=3)
        .encode(
            y=alt.Y("Nivel:N", sort=list(NIVELES), title=None),
            x=alt.X("Noticias:Q", title=None),
            color=alt.Color("Nivel:N", legend=None,
                            scale=alt.Scale(domain=list(NIVELES), range=[COLOR_NIVEL[n] for n in NIVELES])),
            tooltip=["Nivel", "Noticias"],
        )
        .properties(height=120)
    )
    st.altair_chart(grafico)
    st.caption(f"Completa ≥ {S.UMBRAL_COMPLETA} % · Parcial {S.UMBRAL_PARCIAL}–{S.UMBRAL_COMPLETA - 1} % · "
               f"Básica < {S.UMBRAL_PARCIAL} %.")


def _bandeja(df_all) -> None:
    section_label("Bandeja de trabajo")
    st.caption("Las noticias con menos información: son las que conviene completar primero.")
    bandeja = vistas.bandeja_de_trabajo(df_all, 10)
    puede_abrir = _existe("app_pages/ficha.py")
    for r in bandeja.itertuples():
        with st.container(border=True):
            st.markdown(f"**{r.titulo[:110]}**")
            st.caption(f"{r.fuente} · {int(r.anio) if r.anio == r.anio and r.anio else 's/f'} · "
                       f"Falta: {r.faltan[:140] or '—'}")
            # Barra y botón en una fila que pasa a dos líneas si el ancho no alcanza
            with st.container(horizontal=True, vertical_alignment="center"):
                st.progress(min(1.0, r.completitud / 100), text=f"{r.completitud:.0f} %", width=240)
                if puede_abrir:
                    st.button("Abrir ficha", key=f"bandeja_{r.id_evento}", on_click=abrir_ficha,
                              args=(r.id_evento,), icon=":material/edit_note:", width="content")


def _actividad_reciente(hist, base) -> None:
    section_label("Actividad reciente")
    legible = vistas.historial_legible(hist.sort_values("id_cambio", ascending=False).head(8), base)
    if legible.empty:
        st.caption("Todavía no hay cambios registrados. Aquí aparecerán las ediciones, cargas y sincronizaciones.")
        return
    st.dataframe(legible[["Fecha", "Quién", "Acción", "Noticia", "Detalle"]], hide_index=True,
                 column_config={"Detalle": st.column_config.TextColumn(width="large")})


def _panorama_analitico() -> None:
    criterios = st.session_state.get("criterios_busqueda")
    df = get_filtered_df(dedupe=True)
    mapa_full = load_mapa_ubicaciones()
    mapa = mapa_full[mapa_full["item"].isin(df["item"])]

    section_label("Panorama analítico del catálogo")
    st.caption("Refleja los criterios de búsqueda activos en Explorador Glocal; sin criterios, el catálogo completo.")
    total = len(df)
    if total == 0:
        st.info("Ningún resultado con los criterios de búsqueda actuales.")
        return

    n_categorias = len(get_options(df, "categorias"))
    n_gcaa = (df["eje_gcaa"].str.strip().str.lower() != "no aplica").sum()
    n_resiliencia = (df["atributos_resiliencia"].str.strip().str.lower() != "no aplica").sum()
    n_genero = df["enfoque_genero"].astype(str).str.startswith("Sí").sum()
    n_con_fecha = df["tiene_fecha"].sum()
    n_puntos_geo = mapa["lat"].notna().sum()
    n_lugares_unicos = mapa.loc[mapa["lat"].notna(), "lugar_texto"].nunique()
    n_paises = mapa.loc[mapa["lat"].notna(), "pais"].nunique()
    actores_col = "actores_normalizados" if "actores_normalizados" in df.columns else "actores"
    n_actores = len(get_options(df, actores_col))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Experiencias catalogadas", f"{total}")
    c2.metric("Categorías temáticas", f"{n_categorias}")
    c3.metric("Metodologías identificadas", f"{len(get_options(df, 'metodologia'))}")
    c4.metric("Instituciones distintas", f"{n_actores}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Relevantes para acción climática", f"{n_gcaa}", f"{n_gcaa/total:.0%} del catálogo")
    c6.metric("Con atributo de resiliencia", f"{n_resiliencia}", f"{n_resiliencia/total:.0%} del catálogo")
    c7.metric("Con enfoque de género explícito", f"{n_genero}", f"{n_genero/total:.0%} del catálogo")
    c8.metric("Puntos geolocalizados", f"{n_puntos_geo}", f"{n_lugares_unicos} lugares únicos")

    c9, c10, c11, c12 = st.columns(4)
    c9.metric("Países alcanzados", f"{n_paises}")
    c10.metric("Con fecha registrada", f"{n_con_fecha}", f"de {total} totales")
    rango = f"{int(df['anio'].min())}–{int(df['anio'].max())}" if n_con_fecha else "s/d"
    c11.metric("Rango temporal", rango)
    c12.metric("Cuencas vinculadas", f"{mapa['NOM_CUENCA'].nunique() if 'NOM_CUENCA' in mapa.columns else '—'}")

    left, right = st.columns([3, 2])
    with left:
        st.markdown(
            f"""
Este catálogo reúne **{total} experiencias** de facilitación de procesos participativos,
sistematizadas y mapeadas en tres niveles:

**Temático.** De qué habla cada experiencia (categorías inductivas) y con qué método se hizo.

**Climático y de resiliencia.** Cuáles conectan con la Global Climate Action Agenda (GCAA) de la
UNFCCC y con los atributos de resiliencia del CR2.

**Social y territorial.** Quiénes se benefician (directa e indirectamente), si hay un enfoque de
género explícito, y dónde ocurre cada experiencia — hasta el nivel de cuenca hidrográfica cuando
es en Chile.
            """
        )
        nav1, nav2, nav3 = st.columns(3)
        nav1.page_link("app_pages/explorador.py", label="Explorador Glocal")
        nav2.page_link("app_pages/marco_teorico.py", label="Marco teórico y fuentes")
        nav3.page_link("app_pages/glosario.py", label="Glosario")

    with right:
        sufijo = entidad_titulo_sufijo(criterios)
        macro_counts = (
            df.assign(categoria_macro=df["categoria_macro"].str.split(";"))
            .explode("categoria_macro")
        )
        macro_counts["categoria_macro"] = macro_counts["categoria_macro"].str.strip()
        macro_counts = macro_counts[macro_counts["categoria_macro"] != ""]
        counts = macro_counts["categoria_macro"].value_counts().reset_index()
        counts.columns = ["Categoría macro", "N"]
        fig = px.bar(
            counts.sort_values("N"),
            x="N", y="Categoría macro", orientation="h",
            color="N", color_continuous_scale="Teal",
            labels={"N": "N° experiencias"},
        )
        fig.update_layout(coloraxis_showscale=False)
        style_fig(fig, height=320, title=f"Experiencias por categoría macro{sufijo}", showlegend=False)
        st.plotly_chart(fig, width="stretch")

    st.divider()
    st.caption(
        "Fuentes de los marcos usados: UNFCCC NAZCA Portal, Global Climate Action Agenda, "
        "y CR2 (Centro de Ciencia del Clima y Resiliencia). Ver detalle en Marco teórico y fuentes."
    )


def render():
    inject()
    with st.sidebar:
        filters_summary_widget()

    nombre = escape(auth.nombre_actual() or "equipo")
    st.markdown(dual_logo_html(height=56), unsafe_allow_html=True)
    page_header(
        "Plataforma interna",
        "Impacto Glocal",
        f"Hola, {nombre}. Aquí ves el estado de la información sobre impacto social de Glocal Minds y "
        "Fundación Glocal, y desde aquí accedes a cada módulo de trabajo.",
    )

    ayuda.render()

    df_all = load_noticias()
    hist = leer_hoja(S.HOJA_HISTORIAL)
    base = leer_base_cruda()

    _aviso_sincronizacion(hist)
    _kpis_de_gestion(df_all, hist)

    _niveles(df_all)

    section_label("Accesos rápidos")
    _accesos_rapidos()

    _bandeja(df_all)
    _actividad_reciente(hist, base)

    st.divider()
    _panorama_analitico()
