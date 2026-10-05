# -*- coding: utf-8 -*-
"""Marco teórico vivo: las variables analíticas que crea el equipo y el libro de códigos completo.

Una variable propia nueva se comporta como una columna más del marco: su descripción y sus opciones de
respuesta se publican aquí (y en la hoja Libro_de_Codigos) apenas se crea.
"""
import streamlit as st

from utils import repo
from utils import schema as S
from utils import variables as V
from utils.data import almacen_actual, leer_base_cruda, libro_de_codigos
from utils.ui import existe_pagina

PAGINA_ADMIN = "app_pages/administracion.py"


def render_variables_propias() -> None:
    almacen = almacen_actual()
    leer_base_cruda()                                   # deja registradas las variables propias en el esquema
    variables = repo.listar_variables(almacen)
    if not variables:
        st.info("Todavía no hay variables propias. Cuando el equipo cree una (por ejemplo «Tamaño del proyecto»), "
                "aparecerá aquí con su descripción y sus opciones de respuesta.", icon=":material/tune:")
        if existe_pagina(PAGINA_ADMIN):
            st.page_link(PAGINA_ADMIN, label="Crear una variable en Administración", icon=":material/add:")
        return
    uso = repo.uso_variables(almacen)
    for v in sorted(variables, key=lambda x: (not x.activa, x.etiqueta.casefold())):
        u = uso.get(v.clave, {"con_dato": 0, "por_opcion": {}})
        with st.container(border=True):
            c1, c2 = st.columns([1, 3])
            with c1:
                st.markdown(f"**{v.etiqueta}**")
                st.code(v.clave, language=None)
                st.caption(V.TIPOS[v.tipo][0] + ("" if v.activa else " · desactivada"))
            with c2:
                st.markdown(v.descripcion or "_Sin descripción todavía: se puede agregar en Administración → Variables analíticas._")
                if v.es_de_opciones:
                    st.markdown("**Opciones de respuesta:** " + " · ".join(
                        f"{o} ({u['por_opcion'].get(o, 0)})" for o in v.opciones_efectivas))
                st.caption(f"{u['con_dato']} noticia(s) con dato"
                           + (" · entre paréntesis, cuántas noticias tienen cada opción." if v.es_de_opciones else "."))


def render_libro_de_codigos() -> None:
    libro = libro_de_codigos()
    if libro.empty:
        st.caption("El libro de códigos aún no está disponible.")
        return
    st.markdown(
        f"La descripción técnica de las **{len(libro)} columnas** de la base de datos: tipo de variable, opciones de "
        "respuesta y fuente de cada una. Incluye las variables propias que crea el equipo. Vive en la hoja "
        "**Libro_de_Codigos** del archivo de trabajo y se actualiza sola cuando cambian las variables.")
    tabla = libro.assign(Variable=[(S.CAMPO[k].label if k in S.CAMPO else k) for k in libro["columna"]])
    tabla = tabla[["Variable", "columna", "descripcion", "tipo_variable", "opciones_respuesta", "fuente"]].rename(columns={
        "columna": "Columna", "descripcion": "Descripción", "tipo_variable": "Tipo de variable",
        "opciones_respuesta": "Opciones de respuesta", "fuente": "Fuente"})
    st.dataframe(tabla, hide_index=True, height=420, column_config={
        "Descripción": st.column_config.TextColumn(width="large"),
        "Opciones de respuesta": st.column_config.TextColumn(width="large"),
        "Fuente": st.column_config.TextColumn(width="medium")})
    st.download_button("Descargar el libro de códigos (.csv)", data=lambda: tabla.to_csv(index=False).encode("utf-8-sig"),
                       file_name="libro_de_codigos.csv", mime="text/csv", icon=":material/download:",
                       on_click="ignore", key="libro_descargar")
