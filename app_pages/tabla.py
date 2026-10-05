# -*- coding: utf-8 -*-
"""Tabla de datos: la base completa como una planilla editable (tipo Excel / Google Sheets).

Las ediciones no se guardan solas: se acumulan en la grilla, se muestran como «antes → después» y
se confirman con «Guardar cambios». Cada cambio queda en el historial con el nombre de quien edita.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from utils import auth, edicion, repo
from utils import schema as S
from utils.data import almacen_actual, leer_base_cruda, libro_de_codigos, opciones_de_campos
from utils.repo import ErrorOperacion
from utils.storage import ErrorAlmacen
from utils.style import inject, page_header, section_label
from utils.ui import flash
from utils.validation import normalizar

K_VERSION = "tabla_version"          # cambia al guardar o descartar: la grilla vuelve a empezar desde la base

st.set_page_config(page_title="Tabla de datos", layout="wide")
inject()
page_header(
    "Gestión", "Tabla de datos",
    "Edita la base como una planilla. Los cambios se acumulan y solo se guardan cuando pulsas «Guardar cambios»; "
    "cada uno queda registrado con quién lo hizo, qué cambió y cuándo.",
)

usuario = auth.nombre_actual()
almacen = almacen_actual()
if not usuario:
    st.warning("Elige tu nombre en «Editando como» (menú lateral) para poder guardar cambios.", icon=":material/badge:")


# ----------------------------------------------------------------------------- barra superior
base = leer_base_cruda()
libro = libro_de_codigos()
opciones = edicion.opciones_para_tabla(opciones_de_campos(), base, libro)       # las categorías del libro de códigos
vista = st.segmented_control("Columnas a mostrar", list(S.VISTAS), default="Esenciales", key="tabla_vista") or "Esenciales"

with st.container(horizontal=True, vertical_alignment="center"):
    if almacen.url:
        st.link_button("Abrir en Google Sheets", almacen.url, icon=":material/open_in_new:")
    else:
        st.button("Abrir en Google Sheets", disabled=True, icon=":material/cloud_off:", key="tabla_sheets_off",
                  help="La base está en un archivo local: falta configurar Google Sheets en los secretos (ver README).")
    st.download_button("Descargar copia (.xlsx)", data=lambda: almacen.exportar_xlsx(), file_name="catalogo_gestion.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       icon=":material/download:", key="tabla_descargar", on_click="ignore")
    st.caption(f"{len(base)} noticias · la base está en {almacen.descripcion}")

# ----------------------------------------------------------------------------- grilla
df = edicion.preparar_df(base, opciones)
columnas_vista = [c for c in S.VISTAS[vista] if c in df.columns]
orden = ["id_evento"] + [c for c in columnas_vista if c != "id_evento"] + [edicion.COL_COMPLETITUD]
orden = [c for c in dict.fromkeys(orden) if c in df.columns or c == "id_evento"]
version = st.session_state.setdefault(K_VERSION, 0)
clave = f"tabla_editor_{version}"

st.caption("Haz doble clic en una celda para editarla. Las columnas con candado las completa el sistema. "
           "**Las columnas de categorías se eligen de su lista** (la del libro de códigos), no se escriben: pasa el cursor "
           "sobre el nombre de la columna para ver qué significa y qué opciones tiene. Con la lupa de la tabla puedes buscar, "
           "y al pulsar el nombre de una columna se ordena.")
st.data_editor(
    df, key=clave, hide_index=False, height=560, num_rows="fixed",
    column_order=[c for c in orden if c != "id_evento"], column_config=edicion.column_config(opciones, libro),
    disabled=edicion.columnas_bloqueadas() + ["ID"],
)

# ----------------------------------------------------------------------------- cambios pendientes
editadas = (st.session_state.get(clave) or {}).get("edited_rows", {})
cambios = edicion.cambios_desde_edicion(base, editadas)

if not cambios:
    st.caption("Sin cambios pendientes.")
    st.stop()

titulos = dict(zip(base["id_evento"], base["titulo"]))
n_noticias = len({c.id_evento for c in cambios})
section_label(f"Cambios pendientes: {len(cambios)} celda(s) en {n_noticias} noticia(s)")
resumen = pd.DataFrame({
    "ID": [c.id_evento for c in cambios],
    "Noticia": [titulos.get(c.id_evento, "")[:60] for c in cambios],
    "Campo": [S.etiqueta(c.campo) for c in cambios],
    "Antes": [c.antes[:80] for c in cambios],
    "Después": [c.despues[:80] for c in cambios],
})
st.dataframe(resumen, hide_index=True, column_config={"Antes": st.column_config.TextColumn(width="medium"),
                                                      "Después": st.column_config.TextColumn(width="medium")})

# libro de códigos: lo que no respeta las categorías o el formato de la columna NO se puede guardar
errores = edicion.errores_de_codigos(cambios, opciones)
if errores:
    st.error(f"{len(errores)} cambio(s) no respetan el libro de códigos. Corrígelos o descártalos para poder guardar:",
             icon=":material/rule:")
    for (ide, _), mensaje in list(errores.items())[:20]:
        st.caption(f"• {ide} · {mensaje}")

# avisos de validación (no bloquean): se ven antes de guardar
avisos = []
for c in cambios:
    campo = S.CAMPO[c.campo]
    _, av = normalizar(c.despues, campo, opciones.get(c.campo))
    avisos += [f"{c.id_evento} · {campo.label}: {a}" for a in av]
if avisos:
    with st.expander(f"{len(avisos)} aviso(s) de validación (no impiden guardar)", expanded=False):
        for a in avisos[:40]:
            st.caption(f"• {a}")

with st.container(horizontal=True):
    if st.button(f"Guardar {len(cambios)} cambio(s)", type="primary", icon=":material/save:", key="tabla_guardar",
                 disabled=not usuario or bool(errores)):
        try:
            res = repo.aplicar_cambios(cambios, usuario, almacen=almacen)
        except (ErrorOperacion, ErrorAlmacen) as e:
            st.error(str(e), icon=":material/error:")
        else:
            if res.aplicados:
                flash("exito", f"Se guardaron {len(res.aplicados)} cambio(s) en {len({a['id_evento'] for a in res.aplicados})} noticia(s).")
            for o in res.omitidos[:10]:
                flash("error", f"No se guardó {o['id_evento']} · {S.etiqueta(o['campo'])}: {o['motivo']}")
            for a in res.avisos[:10]:
                flash("aviso", a)
            st.session_state[K_VERSION] = version + 1
            st.rerun()
    if st.button("Descartar cambios", icon=":material/undo:", key="tabla_descartar"):
        st.session_state[K_VERSION] = version + 1
        st.rerun()
