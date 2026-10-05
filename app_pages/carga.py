# -*- coding: utf-8 -*-
"""Cargar información: formulario manual o importación de un archivo Excel/CSV.

Todo lo que entra queda registrado (quién, cuándo, de dónde) y se valida por tipo sin ser
invasivo: solo bloquean los obligatorios vacíos y los duplicados seguros.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from utils import auth, dedupe, importar, repo
from utils import schema as S
from utils.data import almacen_actual, leer_base_cruda, opciones_de_campos
from utils.formularios import campo_widget
from utils.repo import ErrorOperacion
from utils.storage import ErrorAlmacen
from utils.style import inject, page_header, section_label
from utils.ui import PAGINA_FICHA, abrir_ficha, existe_pagina, flash
from utils.validation import validar_fila

MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Campos del formulario manual, por bloque.
CAMPOS_BASICOS = ("titulo", "url_noticia", "fuente")
CAMPOS_CONTENIDO = ("fecha_publicacion_web", "descripcion_catalogo", "contenido_completo",
                    "imagen_principal_url", "tipo_informacion")
CAMPOS_CLASIFICACION = ("categoria_macro", "categorias", "metodologia", "actores_normalizados", "eje_gcaa",
                        "atributos_resiliencia", "beneficiarios_directos", "enfoque_genero")
CAMPOS_EJECUTORA = ("Fundación Glocal?", "Consultora", "lugar")
CAMPOS_PROYECTO = ("carpeta_proyecto", "documentos_proyecto")

st.set_page_config(page_title="Cargar información", layout="wide")
inject()
page_header(
    "Gestión", "Cargar información",
    "Agrega noticias nuevas escribiéndolas a mano o subiendo un Excel/CSV. Cada carga queda registrada "
    "con quién la hizo y se puede deshacer desde el historial.",
)

usuario = auth.nombre_actual()
almacen = almacen_actual()
if not usuario:
    st.warning("Elige tu nombre en «Editando como» (menú lateral) para poder registrar quién carga la información.",
               icon=":material/badge:")
else:
    st.caption(f":material/person: Cargando como **{usuario}**")


def _titulos_por_id() -> dict[str, dict]:
    base = leer_base_cruda()
    return base.set_index("id_evento", drop=False).to_dict("index") if len(base) else {}


def _tabla_coincidencias(coincidencias) -> pd.DataFrame:
    base = _titulos_por_id()
    filas = []
    for c in coincidencias:
        b = base.get(c.id_evento, {})
        filas.append({"ID": c.id_evento, "Título": b.get("titulo", ""), "Fuente": b.get("fuente", ""),
                      "Fecha": b.get("fecha_publicacion_web", ""), "Por qué": c.motivo})
    return pd.DataFrame(filas)


def _guardar_manual(fila: dict, avisos: list[str]) -> None:
    try:
        res = repo.agregar_filas([fila], usuario, accion=S.ACC_CREAR, origen="manual", almacen=almacen)
    except (ErrorOperacion, ErrorAlmacen) as e:
        st.error(str(e), icon=":material/error:")
        return
    if res.ids_creados:
        ide = res.ids_creados[0]
        flash("exito", f"Noticia agregada con el ID {ide}: {fila['titulo'][:90]}.")
        for a in avisos:
            flash("aviso", a)
        st.session_state["carga_ultimo_id"] = ide
        st.session_state["carga_form_n"] = st.session_state.get("carga_form_n", 0) + 1
        st.session_state.pop("carga_pendiente", None)
        st.rerun()
    else:
        st.error(" ".join(o["motivo"] for o in res.omitidos) or "No se agregó la noticia.", icon=":material/error:")


def _bloque_ultima_agregada() -> None:
    ide = st.session_state.get("carga_ultimo_id")
    if ide and existe_pagina(PAGINA_FICHA):
        with st.container(horizontal=True, vertical_alignment="center"):
            st.caption(f"Última noticia agregada: **{ide}**")
            st.button("Abrir su ficha", key="carga_abrir_ultima", on_click=abrir_ficha, args=(ide,),
                      icon=":material/article:", type="tertiary")


def _bloque_pendiente() -> bool:
    """Si hay una noticia con posible duplicado esperando decisión, la muestra. True si bloquea el formulario."""
    pend = st.session_state.get("carga_pendiente")
    if not pend:
        return False
    st.warning("Ya existen noticias con el **mismo título**. Puede ser otro evento (p. ej. una nueva edición) "
               "o una repetida. Revisa la tabla y decide.", icon=":material/difference:")
    st.dataframe(_tabla_coincidencias(pend["coincidencias"]), hide_index=True)
    st.caption(f"Se agregaría: **{pend['fila'].get('titulo', '')[:100]}**")
    with st.container(horizontal=True):
        if st.button("Agregar igualmente", type="primary", icon=":material/add:", key="carga_forzar", disabled=not usuario):
            _guardar_manual(pend["fila"], pend["avisos"])
        if st.button("Cancelar y revisar el formulario", icon=":material/undo:", key="carga_cancelar"):
            st.session_state.pop("carga_pendiente", None)
            st.rerun()
    return True


def _procesar_envio(valores: dict[str, str]) -> None:
    fila = {k: v for k, v in valores.items() if v and v.strip()}
    if not fila.get("fuente") and fila.get("url_noticia"):
        fila["fuente"] = importar.inferir_fuente(fila["url_noticia"])
    fila_norm, errores, avisos = validar_fila(fila)
    if errores:
        st.error("\n\n".join(errores), icon=":material/error:")
        return
    coincidencias = dedupe.Indice(leer_base_cruda().to_dict("records")).buscar(fila_norm)
    seguras = [c for c in coincidencias if c.segura]
    if seguras:
        st.error(f"Esta noticia ya está en la base ({seguras[0].motivo.lower()}). No se agregó.",
                 icon=":material/block:")
        st.dataframe(_tabla_coincidencias(seguras), hide_index=True)
        if existe_pagina(PAGINA_FICHA):
            st.button("Abrir la ficha existente", key="carga_abrir_existente", on_click=abrir_ficha,
                      args=(seguras[0].id_evento,), icon=":material/article:")
        return
    if coincidencias:
        st.session_state["carga_pendiente"] = {"fila": fila_norm, "avisos": avisos, "coincidencias": coincidencias}
        st.rerun()
    _guardar_manual(fila_norm, avisos)


# ============================================================================ pestañas
tab_form, tab_arch = st.tabs([":material/edit_note: Formulario", ":material/upload_file: Subir archivo"], key="carga_pestanas")

with tab_form:
    _bloque_ultima_agregada()
    if not _bloque_pendiente():
        opciones = opciones_de_campos()
        n = st.session_state.setdefault("carga_form_n", 0)
        with st.form(f"carga_{n}", border=True):
            valores: dict[str, str] = {}
            section_label("Datos obligatorios")
            for key in CAMPOS_BASICOS:
                valores[key] = campo_widget(S.CAMPO[key], "", f"carga_{n}_{key}", opciones.get(key))
            for titulo, claves, abierto in (
                ("Contenido", CAMPOS_CONTENIDO, False),
                ("Clasificación (opcional)", CAMPOS_CLASIFICACION, False),
                ("Entidad ejecutora y lugar (opcional)", CAMPOS_EJECUTORA, False),
                ("Carpeta del proyecto y variables propias (opcional)", CAMPOS_PROYECTO + tuple(c.key for c in S.variables_activas()), False),
            ):
                with st.expander(titulo, expanded=abierto):
                    for key in claves:
                        valores[key] = campo_widget(S.CAMPO[key], "", f"carga_{n}_{key}", opciones.get(key))
            enviado = st.form_submit_button("Agregar noticia", type="primary", icon=":material/add:",
                                            disabled=not usuario)
        st.caption("Los campos con * son obligatorios. Si dejas la fuente vacía, se deduce del dominio del enlace. "
                   "Lo demás se puede completar después desde la ficha de la noticia.")
        if enviado:
            _procesar_envio(valores)

with tab_arch:
    st.markdown("Sube un Excel (`.xlsx`) o un CSV. Las columnas se reconocen por su nombre; "
                "antes de importar verás qué se agregará, qué ya existe y qué tiene problemas.")
    st.download_button("Descargar plantilla de ejemplo", data=importar.plantilla_xlsx, file_name="plantilla_noticias.xlsx",
                       mime=MIME_XLSX, icon=":material/download:", key="carga_plantilla")
    n_arch = st.session_state.setdefault("carga_arch_n", 0)
    archivo = st.file_uploader("Archivo Excel o CSV", type=["xlsx", "csv"], key=f"carga_archivo_{n_arch}")

    if archivo is not None:
        datos = archivo.getvalue()
        fid = archivo.file_id
        try:
            hojas = importar.hojas_de(datos, archivo.name)
            hoja = None
            if len(hojas) > 1:
                hoja = st.selectbox("Hoja del Excel", hojas, index=hojas.index("Base_Datos") if "Base_Datos" in hojas else 0,
                                    key=f"carga_hoja_{fid}")
            df = importar.leer_archivo(datos, archivo.name, hoja)
        except importar.ErrorImportacion as e:
            st.error(str(e), icon=":material/error:")
            df = None

        if df is not None:
            mapa = importar.mapear_columnas(list(df.columns))
            with st.expander(f"Correspondencia de columnas — {len(mapa)} de {df.shape[1]} reconocidas", expanded=len(mapa) < 3):
                opciones_campo = {S.etiqueta(c.key): c.key for c in S.CAMPOS
                                  if c.key != "id_evento" and c.key not in S.COLUMNAS_SISTEMA}
                etiquetas = ["(ignorar)"] + list(opciones_campo)
                mapa_final: dict[str, str] = {}
                for h in df.columns:
                    actual = mapa.get(h)
                    elegido = st.selectbox(h, etiquetas, key=f"carga_map_{fid}_{h}",
                                           index=etiquetas.index(S.etiqueta(actual)) if actual else 0)
                    if elegido != "(ignorar)" and opciones_campo[elegido] not in mapa_final.values():
                        mapa_final[h] = opciones_campo[elegido]

            faltan = [S.etiqueta(k) for k in S.OBLIGATORIOS if k not in mapa_final.values() and k != "fuente"]
            if faltan:
                st.error(f"Falta mapear columnas obligatorias: {', '.join(faltan)}.", icon=":material/error:")
            else:
                filas = importar.filas_desde_df(df, mapa_final)
                indice = dedupe.Indice(leer_base_cruda().to_dict("records"))
                evaluaciones = importar.evaluar(filas, indice)
                conteo = pd.Series([e.estado for e in evaluaciones]).value_counts()

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Filas en el archivo", len(evaluaciones))
                c2.metric("Se pueden importar", int(conteo.get(importar.ESTADO_NUEVA, 0) + conteo.get(importar.ESTADO_AVISOS, 0)))
                c3.metric("Ya existen", int(conteo.get(importar.ESTADO_DUPLICADA, 0)))
                c4.metric("Con errores o dudas", int(conteo.get(importar.ESTADO_ERROR, 0) + conteo.get(importar.ESTADO_SOSPECHOSA, 0)))

                tabla = pd.DataFrame({
                    "Incluir": [e.importable for e in evaluaciones],
                    "Fila": [e.n for e in evaluaciones],
                    "Estado": [e.estado for e in evaluaciones],
                    "Título": [e.fila.get("titulo", "") for e in evaluaciones],
                    "Fuente": [e.fila.get("fuente", "") for e in evaluaciones],
                    "Detalle": [e.detalle for e in evaluaciones],
                })
                st.caption("Marca o desmarca qué filas importar. Las que tienen errores o ya existen vienen desmarcadas; "
                           "las «posibles duplicadas» puedes incluirlas si son otro evento.")
                editada = st.data_editor(
                    tabla, hide_index=True, key=f"carga_tabla_{fid}", height=min(520, 60 + 35 * len(tabla)),
                    disabled=["Fila", "Estado", "Título", "Fuente", "Detalle"],
                    column_config={
                        "Incluir": st.column_config.CheckboxColumn("Incluir", width="small"),
                        "Fila": st.column_config.NumberColumn("Fila", format="%d", width="small"),
                        "Estado": st.column_config.TextColumn("Estado", width="small"),
                        "Título": st.column_config.TextColumn("Título", width="large"),
                        "Detalle": st.column_config.TextColumn("Detalle", width="large"),
                    },
                )
                elegidas = [evaluaciones[i] for i in editada.index[editada["Incluir"]]
                            if evaluaciones[i].estado != importar.ESTADO_ERROR]
                if st.button(f"Importar {len(elegidas)} noticia(s)", type="primary", icon=":material/upload:",
                             disabled=not usuario or not elegidas, key=f"carga_importar_{fid}"):
                    try:
                        res = repo.agregar_filas([e.fila for e in elegidas], usuario, accion=S.ACC_CARGA,
                                                 origen="archivo", almacen=almacen, respaldo="antes_de_importar")
                    except (ErrorOperacion, ErrorAlmacen) as e:
                        st.error(str(e), icon=":material/error:")
                    else:
                        flash("exito", f"Se importaron {len(res.ids_creados)} noticia(s) desde «{archivo.name}». "
                                       "Puedes deshacer la carga completa desde el historial (pestaña Lotes).")
                        for o in res.omitidos[:8]:
                            flash("aviso", f"Omitida «{o['campo']}»: {o['motivo']}")
                        if res.avisos:
                            flash("aviso", f"{len(res.avisos)} aviso(s) de validación; revisa las fichas importadas.")
                        st.session_state["carga_arch_n"] = n_arch + 1
                        st.rerun()
