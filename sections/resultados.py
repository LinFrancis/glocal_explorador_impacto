# -*- coding: utf-8 -*-
"""Sección 'Resultados' dentro de Explorador Glocal: planilla + catálogo de lectura + selección +
exportación. Al presionar "Leer", la ficha reemplaza la lista al instante (no se agrega debajo:
así el usuario no tiene que hacer scroll para encontrarla).

La selección de noticias (para exportar) vive en `utils/seleccion.py` y usa `id_evento`.
"""
import streamlit as st

from sections import exportar
from utils import schema as S
from utils import seleccion
from utils.components import render_news_card
from utils.style import section_label
from utils.ui import PAGINA_FICHA, abrir_ficha, existe_pagina

ITEM_ACTIVO_KEY = "explorador_item_activo"      # id_evento de la ficha abierta en el catálogo
PAGINA_KEY = "explorador_pagina_catalogo"
TABLA_KEY = "resultados_tabla_planilla"
POR_PAGINA = 20


def _on_casilla(ide: str, key: str) -> None:
    seleccion.marcar(ide, bool(st.session_state.get(key)))


def render(df, df_total, criterios):
    catalogo = df.sort_values("fecha_parsed", ascending=False, na_position="last").reset_index(drop=True)

    item_activo = st.session_state.get(ITEM_ACTIVO_KEY)
    if item_activo is not None and item_activo not in set(catalogo["id_evento"]):
        item_activo = None
        st.session_state.pop(ITEM_ACTIVO_KEY, None)

    # -------------------------------------------------------- ficha (reemplaza la lista)
    if item_activo is not None:
        with st.container(horizontal=True, vertical_alignment="center"):
            if st.button("Volver a resultados", key="resultados_volver", icon=":material/arrow_back:"):
                st.session_state.pop(ITEM_ACTIVO_KEY, None)
                st.rerun()
            marcado = st.toggle("Incluir en la exportación", value=seleccion.esta(item_activo),
                                key=f"sel_ficha_{item_activo}_{seleccion.version()}")
            seleccion.marcar(item_activo, marcado)
            if existe_pagina(PAGINA_FICHA):
                st.button("Editar ficha", key="resultados_editar_ficha", on_click=abrir_ficha, args=(item_activo,),
                          icon=":material/edit_note:", type="primary")
        with st.container(border=True):
            render_news_card(catalogo[catalogo["id_evento"] == item_activo].iloc[0])
        return

    # -------------------------------------------------------- planilla (colapsada)
    ACTORES_COL = "actores_normalizados" if "actores_normalizados" in df.columns else "actores"
    COLUMN_ORDER = [
        ("id_evento", "ID", "text"),
        ("titulo", "Título", "text"),
        ("completitud", "Completitud", "progress"),
        ("anio", "Año", "year"),
        ("pais", "País", "text"),
        ("fuente", "Fuente", "text"),
        ("tipo_informacion", "Tipo de información", "text"),
        ("Fundación Glocal?", "Fundación Glocal", "text"),
        ("Consultora", "Consultora", "text"),
        ("descripcion_catalogo", "Resumen", "text"),
        ("contenido_completo", "Texto completo", "text"),
        ("url_noticia", "Enlace", "link"),
        ("categorias", "Categoría temática", "text"),
        ("categoria_macro", "Categoría macro", "text"),
        ("metodologia", "Metodología", "text"),
        (ACTORES_COL, "Actores institucionales", "text"),
        ("eje_gcaa", "Eje GCAA", "text"),
        ("objetivo_gcaa", "Objetivo GCAA", "text"),
        ("atributos_resiliencia", "Atributo de resiliencia", "text"),
        ("subatributos_resiliencia", "Sub-atributo de resiliencia", "text"),
        ("beneficiarios_directos", "Beneficiarios directos", "text"),
        ("beneficiarios_indirectos", "Beneficiarios indirectos", "text"),
        ("enfoque_genero", "Enfoque de género", "text"),
        ("lugar", "Lugar", "text"),
        ("carpeta_proyecto", "Carpeta del proyecto", "link"),
    ] + [(c.key, c.label, "text") for c in S.variables_activas()]
    cols_present = [(c, label, kind) for c, label, kind in COLUMN_ORDER if c in df.columns]
    display_df = df[[c for c, _, _ in cols_present]].reset_index(drop=True)

    col_cfg = {}
    for c, label, kind in cols_present:
        if kind == "year":
            col_cfg[c] = st.column_config.NumberColumn(label, format="%d", width="small")
        elif kind == "progress":
            col_cfg[c] = st.column_config.ProgressColumn(label, min_value=0, max_value=100, format="%d %%", width="small")
        elif kind == "link":
            col_cfg[c] = st.column_config.LinkColumn(label, display_text="Abrir ↗", width="small")
        elif c in ("descripcion_catalogo", "contenido_completo"):
            col_cfg[c] = st.column_config.TextColumn(label, width="large")
        else:
            col_cfg[c] = st.column_config.TextColumn(label, width="medium")

    with st.expander("Ver como planilla", expanded=False):
        st.caption("Marca una o varias filas con las casillas de la izquierda y pulsa «Agregar las filas marcadas» "
                   "para sumarlas a tu selección de exportación.")
        event = st.dataframe(
            display_df, width="stretch", hide_index=True, height=560,
            on_select="rerun", selection_mode="multi-row", column_config=col_cfg, key=TABLA_KEY,
        )
        filas_marcadas = event.selection.rows if event and event.selection else []
        ids_marcados = [display_df.iloc[i]["id_evento"] for i in filas_marcadas]
        st.button(f"Agregar las {len(ids_marcados)} fila(s) marcadas a la selección", key="resultados_sumar_marcadas",
                  on_click=seleccion.agregar, args=(ids_marcados,), disabled=not ids_marcados,
                  icon=":material/playlist_add_check:")

    # -------------------------------------------------------- catálogo de lectura
    section_label("Catálogo de resultados — elige una para leerla completa")

    n_total = len(catalogo)
    n_paginas = max(1, -(-n_total // POR_PAGINA))

    if PAGINA_KEY not in st.session_state:
        st.session_state[PAGINA_KEY] = 0
    st.session_state[PAGINA_KEY] = min(st.session_state[PAGINA_KEY], n_paginas - 1)

    if n_total == 0:
        st.info("Ningún resultado con los filtros actuales.")
        exportar.render(df, df_total, criterios)
        return

    inicio = st.session_state[PAGINA_KEY] * POR_PAGINA
    pagina_df = catalogo.iloc[inicio: inicio + POR_PAGINA]
    ids_pagina = list(pagina_df["id_evento"])

    # barra de selección: acciones masivas y contador
    with st.container(horizontal=True, vertical_alignment="center"):
        st.caption(f":material/checklist: **{seleccion.contar()}** seleccionada(s)")
        st.button(f"Seleccionar las {n_total} filtradas", key="sel_todas_filtradas", on_click=seleccion.agregar,
                  args=(list(catalogo["id_evento"]),), width="content")
        st.button("Seleccionar esta página", key="sel_esta_pagina", on_click=seleccion.agregar,
                  args=(ids_pagina,), width="content")
        st.button("Quitar las filtradas", key="sel_quitar_filtradas", on_click=seleccion.quitar,
                  args=(list(catalogo["id_evento"]),), width="content")
        st.button("Vaciar selección", key="sel_vaciar", on_click=seleccion.vaciar, width="content",
                  type="tertiary", icon=":material/deselect:")

    if n_paginas > 1:
        pc1, pc2, pc3 = st.columns([1, 2, 1])
        with pc1:
            if st.button("← Anteriores", disabled=st.session_state[PAGINA_KEY] <= 0, key="resultados_pag_ant"):
                st.session_state[PAGINA_KEY] -= 1
                st.rerun()
        with pc2:
            st.markdown(
                f"<div style='text-align:center'>Página {st.session_state[PAGINA_KEY] + 1} de {n_paginas}</div>",
                unsafe_allow_html=True,
            )
        with pc3:
            if st.button("Siguientes →", disabled=st.session_state[PAGINA_KEY] >= n_paginas - 1, key="resultados_pag_sig"):
                st.session_state[PAGINA_KEY] += 1
                st.rerun()

    ver = seleccion.version()
    for _, row in pagina_df.iterrows():
        ide = row["id_evento"]
        macro = str(row.get("categoria_macro_primary") or row.get("categoria_macro") or "").split(";")[0].strip() or "Sin categoría"
        fecha_txt = row["fecha_parsed"].strftime("%Y") if row.get("tiene_fecha") else "Sin fecha"
        lugar_txt = str(row.get("lugar") or "").split(";")[0].strip() or "Sin lugar"
        tipo_info = str(row.get("tipo_informacion") or "").strip()
        resumen = str(row.get("descripcion_catalogo") or row.get("preview_contenido") or "").strip()
        resumen_corto = (resumen[:160] + "…") if len(resumen) > 160 else resumen

        c1, c2 = st.columns([5, 1.4])
        with c1:
            st.markdown(f"**{row['titulo']}**")
            meta_bits = [fecha_txt, lugar_txt, macro] + ([tipo_info] if tipo_info else []) + [f"{row['completitud']:.0f} % completa"]
            st.caption(" · ".join(meta_bits))
            if resumen_corto:
                st.caption(resumen_corto)
        with c2:
            clave = f"sel_{ide}_{ver}"
            st.checkbox("Incluir", value=seleccion.esta(ide), key=clave, on_change=_on_casilla, args=(ide, clave))
            if st.button("Leer", key=f"resultados_leer_{ide}", width="stretch"):
                st.session_state[ITEM_ACTIVO_KEY] = ide
                st.rerun()
        st.divider()

    # -------------------------------------------------------- exportar
    exportar.render(df, df_total, criterios)
