# -*- coding: utf-8 -*-
"""Sincronizar con la web: busca noticias nuevas en los dos sitios y las compara con la base.

Siempre es manual (lo inicia una persona) y nada se guarda hasta confirmar. Cada sincronización
queda como un lote que se puede deshacer completo desde el historial.
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from utils import auth, repo, scraper
from utils import schema as S
from utils.data import almacen_actual, leer_base_cruda
from utils.repo import ErrorOperacion
from utils.storage import ErrorAlmacen
from utils.style import inject, page_header, section_label
from utils.ui import existe_pagina, flash
from utils.vistas import fecha_corta, hace_cuanto

K_RES = "sync_resultado"

st.set_page_config(page_title="Sincronizar con la web", layout="wide")
inject()
page_header(
    "Gestión", "Sincronizar con la web",
    "Busca noticias nuevas en glocalminds.com y fundacionglocal.org y las compara con la base. "
    "Solo se actualiza cuando tú lo pides y no se guarda nada hasta que confirmes.",
)

usuario = auth.nombre_actual()
if not usuario:
    st.warning("Elige tu nombre en «Editando como» (menú lateral): se registra quién sincroniza.", icon=":material/badge:")

almacen = almacen_actual()

# ----------------------------------------------------------------------------- búsqueda
fuentes = st.pills("Fuentes a consultar", list(scraper.FUENTES_WEB), selection_mode="multi",
                   default=list(scraper.FUENTES_WEB), format_func=lambda k: scraper.FUENTES_WEB[k].nombre,
                   key="sync_fuentes")
buscar = st.button("Buscar novedades", type="primary", icon=":material/search:", key="sync_buscar",
                   disabled=not fuentes)

if buscar:
    resultados = []
    with st.status("Consultando los sitios…", expanded=True) as estado:
        for clave in fuentes:
            nombre = scraper.FUENTES_WEB[clave].nombre
            linea = st.empty()
            res = scraper.descargar(clave, progreso=lambda msg, _l=linea: _l.write(msg))
            linea.write(f":material/check_circle: {nombre}: {len(res.items)} noticias leídas." if res.ok
                        else f":material/error: {nombre}: {res.error}")
            resultados.append(res)
        estado.update(label="Consulta terminada" if all(r.ok for r in resultados) else "Consulta terminada con problemas",
                      state="complete" if any(r.ok for r in resultados) else "error", expanded=False)
    st.session_state[K_RES] = {
        "resultados": resultados, "hora": datetime.now().isoformat(timespec="seconds"),
        "firma": None, "dif": None,
    }

estado_busqueda = st.session_state.get(K_RES)
if not estado_busqueda:
    st.caption("Pulsa «Buscar novedades» para comparar la web con tu base.")
    st.stop()

resultados = estado_busqueda["resultados"]
firma = almacen.firma()
if estado_busqueda["firma"] != firma:            # primera vez, o la base cambió: se recalcula la comparación
    estado_busqueda["dif"] = scraper.calcular_diferencias(resultados, leer_base_cruda().to_dict("records"))
    estado_busqueda["firma"] = firma
dif: scraper.Diferencial = estado_busqueda["dif"]

section_label("Resultado de la búsqueda")
st.caption(f"Consulta hecha {hace_cuanto(estado_busqueda['hora'])} ({fecha_corta(estado_busqueda['hora'])}).")
for r in resultados:
    nombre = scraper.FUENTES_WEB[r.fuente].nombre
    if not r.ok:
        st.error(f"**{nombre}:** {r.error}", icon=":material/error:")
        continue
    if r.modo == "html":
        st.warning(f"**{nombre}:** " + " ".join(r.avisos), icon=":material/warning:")
    elif r.avisos:
        with st.expander(f"{nombre}: {len(r.items)} noticias leídas, {r.n_campos_vacios} campo(s) quedaron vacíos"):
            for a in r.avisos[:30]:
                st.caption(f"• {a}")

if not any(r.ok for r in resultados):
    st.stop()

n_revisadas = sum(len(r.items) for r in resultados if r.ok)
if dif.sin_diferencias and not dif.wp_pendientes:
    st.success("✓ Todo actualizado", icon=":material/check_circle:")
    st.caption(f"Se compararon {n_revisadas} noticias de la web con la base: no hay nada nuevo ni cambiado.")
    if dif.solo_en_bd:
        st.caption(f"{len(dif.solo_en_bd)} noticia(s) de la base ya no aparecen en la web (se conservan).")
    st.stop()

# ----------------------------------------------------------------------------- diferencias
m1, m2, m3, m4 = st.columns(4)
m1.metric("Nuevas", len(dif.nuevas))
m2.metric("URL cambió", len(dif.url_cambio))
m3.metric("Cambiaron en la web", len(dif.modificadas))
m4.metric("Solo en la base", len(dif.solo_en_bd))

tab_n, tab_u, tab_m, tab_s = st.tabs([
    f"Nuevas ({len(dif.nuevas)})", f"URL cambió ({len(dif.url_cambio)})",
    f"Cambiaron en la web ({len(dif.modificadas)})", f"Solo en la base ({len(dif.solo_en_bd)})",
])
sufijo = f"{firma}"
ed_n = ed_u = ed_m = None          # se asignan dentro de cada pestaña si hay filas

with tab_n:
    if not dif.nuevas:
        st.caption("No hay noticias nuevas.")
    else:
        st.caption("Las nuevas entran con la información de la web (completitud baja hasta que se les asigne análisis). "
                   "Las marcadas como «posible duplicada» vienen desmarcadas: revisa si son otro evento.")
        tabla_n = pd.DataFrame({
            "Incluir": [not n["sospechosa"] for n in dif.nuevas],
            "Título": [n["fila"]["titulo"] for n in dif.nuevas],
            "Fuente": [n["fila"]["fuente"] for n in dif.nuevas],
            "Fecha": [(n["fila"].get("fecha_publicacion_web") or "")[:10] for n in dif.nuevas],
            "Imagen": [n["fila"].get("imagen_principal_url") or None for n in dif.nuevas],
            "Enlace": [n["fila"]["url_noticia"] for n in dif.nuevas],
            "Nota": [n["nota"] for n in dif.nuevas],
        })
        ed_n = st.data_editor(
            tabla_n, hide_index=True, key=f"sync_nuevas_{sufijo}", disabled=[c for c in tabla_n.columns if c != "Incluir"],
            column_config={
                "Incluir": st.column_config.CheckboxColumn(width="small"),
                "Título": st.column_config.TextColumn(width="large"),
                "Imagen": st.column_config.ImageColumn(width="small"),
                "Enlace": st.column_config.LinkColumn(display_text="Abrir ↗", width="small"),
                "Nota": st.column_config.TextColumn(width="medium"),
            })

with tab_u:
    if not dif.url_cambio:
        st.caption("Ninguna noticia cambió de dirección.")
    else:
        st.caption("Misma noticia (mismo título, fuente y fecha) con otra dirección en la web. Se actualiza el enlace y el "
                   "identificador, y se completa el ID de WordPress.")
        tabla_u = pd.DataFrame({
            "Incluir": [True] * len(dif.url_cambio), "ID": [u["id_evento"] for u in dif.url_cambio],
            "Título": [u["titulo"] for u in dif.url_cambio], "Enlace en la base": [u["antes"] for u in dif.url_cambio],
            "Enlace en la web": [u["despues"] for u in dif.url_cambio],
        })
        ed_u = st.data_editor(tabla_u, hide_index=True, key=f"sync_urls_{sufijo}",
                              disabled=[c for c in tabla_u.columns if c != "Incluir"],
                              column_config={"Incluir": st.column_config.CheckboxColumn(width="small"),
                                             "Título": st.column_config.TextColumn(width="large")})

with tab_m:
    if not dif.modificadas:
        st.caption("Ninguna noticia fue modificada en la web desde la última vez.")
    else:
        st.caption("La web las modificó después de lo que tenemos. Vienen desmarcadas para no pisar el trabajo de edición: "
                   "marca las que quieras refrescar (se registra el antes y el después en el historial).")
        tabla_m = pd.DataFrame({
            "Incluir": [False] * len(dif.modificadas), "ID": [m["id_evento"] for m in dif.modificadas],
            "Título": [m["titulo"] for m in dif.modificadas],
            "Cambió": [", ".join(S.etiqueta(c["campo"]) for c in m["campos"] if c["campo"] != "fecha_modificacion_web")
                       for m in dif.modificadas],
        })
        ed_m = st.data_editor(tabla_m, hide_index=True, key=f"sync_mods_{sufijo}",
                              disabled=[c for c in tabla_m.columns if c != "Incluir"],
                              column_config={"Incluir": st.column_config.CheckboxColumn(width="small"),
                                             "Título": st.column_config.TextColumn(width="large"),
                                             "Cambió": st.column_config.TextColumn(width="large")})

with tab_s:
    if not dif.solo_en_bd:
        st.caption("Todas las noticias de la base siguen en la web.")
    else:
        st.caption("Están en la base pero ya no aparecen en la web. No se borra nada.")
        st.dataframe(pd.DataFrame(dif.solo_en_bd).rename(columns={"id_evento": "ID", "titulo": "Título", "fuente": "Fuente", "url": "Enlace"}),
                     hide_index=True, column_config={"Enlace": st.column_config.LinkColumn(display_text="Abrir ↗")})

# ----------------------------------------------------------------------------- aplicar
completar_ids = True
if dif.wp_pendientes:
    completar_ids = st.checkbox(
        f"Completar el ID de WordPress en {len(dif.wp_pendientes)} noticia(s) existentes", value=True, key=f"sync_ids_{sufijo}",
        help="Se hace una sola vez. Permite reconocer cada noticia aunque cambie su dirección. No modifica nada visible.")

nuevas_sel = [dif.nuevas[i]["fila"] for i in ed_n.index[ed_n["Incluir"]]] if ed_n is not None else []
urls_sel = [dif.url_cambio[i] for i in ed_u.index[ed_u["Incluir"]]] if ed_u is not None else []
mods_sel = [dif.modificadas[i] for i in ed_m.index[ed_m["Incluir"]]] if ed_m is not None else []
cambios = []
ids_con_url = {u["id_evento"] for u in urls_sel}
for u in urls_sel:
    cambios += scraper.cambios_url(u)
for m in mods_sel:
    cambios += scraper.cambios_modificada(m)
if completar_ids:
    for p in dif.wp_pendientes:
        if p["id_evento"] not in ids_con_url:              # los de «URL cambió» ya incluyen su wp_id
            cambios += scraper.cambios_wp_id(p)
n_acciones = len(nuevas_sel) + len(urls_sel) + len(mods_sel) + (len(dif.wp_pendientes) if completar_ids else 0)

if st.button(f"Aplicar ({len(nuevas_sel)} nuevas, {len(urls_sel) + len(mods_sel)} actualizaciones"
             + (f", {len(dif.wp_pendientes)} IDs" if completar_ids and dif.wp_pendientes else "") + ")",
             type="primary", icon=":material/check:", key=f"sync_aplicar_{sufijo}", disabled=not usuario or n_acciones == 0):
    try:
        res = repo.aplicar_sincronizacion(nuevas_sel, cambios, usuario, almacen)
    except (ErrorOperacion, ErrorAlmacen) as e:
        st.error(str(e), icon=":material/error:")
    else:
        partes = []
        if res.ids_creados:
            partes.append(f"{len(res.ids_creados)} noticia(s) nueva(s)")
        if res.aplicados:
            partes.append(f"{len({a['id_evento'] for a in res.aplicados})} noticia(s) actualizada(s)")
        flash("exito", "Sincronización aplicada: " + (", ".join(partes) or "sin cambios") + ". "
                       "Si algo no te convence, puedes deshacerla completa desde el historial (pestaña Lotes).")
        for o in res.omitidos[:6]:
            flash("aviso", f"Omitido «{o['campo']}»: {o['motivo']}")
        st.rerun()
if existe_pagina("app_pages/historial.py"):
    st.page_link("app_pages/historial.py", label="Ver el historial de cambios", icon=":material/history:")
