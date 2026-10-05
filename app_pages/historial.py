# -*- coding: utf-8 -*-
"""Historial de cambios: quién cambió qué y cuándo, deshacer lotes completos y repetir exportaciones."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from utils import auth, export, repo, vistas
from utils import schema as S
from utils.data import almacen_actual, leer_base_cruda, leer_hoja, load_noticias
from utils.repo import ErrorOperacion
from utils.style import inject, page_header, section_label
from utils.ui import PAGINA_FICHA, abrir_ficha, existe_pagina

MAX_FILAS = 1000
MIME = {"xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "csv": "text/csv"}

st.set_page_config(page_title="Historial de cambios", layout="wide")
inject()
page_header(
    "Gestión", "Historial de cambios",
    "Todo lo que se ha cargado, editado o sincronizado, con quién lo hizo. Nada se borra: revertir agrega una entrada nueva. "
    "Desde aquí puedes deshacer una carga o sincronización completa y repetir exportaciones anteriores.",
)

usuario = auth.nombre_actual()
almacen = almacen_actual()
base = leer_base_cruda()

tab_cambios, tab_lotes, tab_export = st.tabs([":material/list_alt: Cambios", ":material/layers: Lotes", ":material/download: Exportaciones"], key="historial_pestanas")

# ============================================================================ CAMBIOS
with tab_cambios:
    hist = leer_hoja(S.HOJA_HISTORIAL).sort_values("id_cambio", ascending=False)
    if hist.empty:
        st.info("Todavía no hay cambios registrados.", icon=":material/history:")
    else:
        legible = vistas.historial_legible(hist, base)
        legible["_dt"] = pd.to_datetime(hist["fecha_hora"].str.replace(" ", "T"), errors="coerce").values
        f1, f2, f3 = st.columns(3)
        quien = f1.multiselect("Quién", sorted(legible["Quién"].unique()), key="hist_quien")
        accion = f2.multiselect("Acción", sorted(legible["Acción"].unique()), key="hist_accion")
        campo = f3.multiselect("Campo", sorted(legible["Campo"].unique()), key="hist_campo")
        f4, f5 = st.columns([2, 1])
        buscar = f4.text_input("Buscar por ID o título de la noticia", key="hist_buscar", placeholder="Ej.: EV0123 o parte del título")
        rango = f5.date_input("Fechas", value=(), key="hist_fechas", help="Opcional: desde y hasta.")

        sel = legible
        if quien:
            sel = sel[sel["Quién"].isin(quien)]
        if accion:
            sel = sel[sel["Acción"].isin(accion)]
        if campo:
            sel = sel[sel["Campo"].isin(campo)]
        if buscar.strip():
            q = buscar.strip().lower()
            sel = sel[sel["id_evento"].str.lower().str.contains(q, regex=False) | sel["Noticia"].str.lower().str.contains(q, regex=False)]
        if isinstance(rango, (tuple, list)) and len(rango) == 2:
            ini, fin = pd.Timestamp(rango[0]), pd.Timestamp(rango[1]) + pd.Timedelta(days=1)
            sel = sel[(sel["_dt"] >= ini) & (sel["_dt"] < fin)]

        st.caption(f"{len(sel)} de {len(legible)} cambio(s)" + (f" · se muestran los {MAX_FILAS} más recientes" if len(sel) > MAX_FILAS else ""))
        mostrar = sel.head(MAX_FILAS).reset_index(drop=True)
        evento = st.dataframe(mostrar[["Fecha", "Quién", "Acción", "id_evento", "Noticia", "Campo", "Antes", "Después"]], hide_index=True,
                              on_select="rerun", selection_mode="single-row", key="hist_tabla", height=420,
                              column_config={"id_evento": st.column_config.TextColumn("ID", width="small"),
                                             "Antes": st.column_config.TextColumn(width="medium"),
                                             "Después": st.column_config.TextColumn(width="medium")})
        st.download_button("Descargar lo filtrado (CSV)", data=lambda: mostrar.drop(columns=["_dt"], errors="ignore").to_csv(index=False).encode("utf-8-sig"),
                           file_name="historial_de_cambios.csv", mime="text/csv", icon=":material/download:", on_click="ignore", key="hist_csv")
        filas = evento.selection.rows if evento and evento.selection else []
        if filas:
            e = mostrar.iloc[filas[0]]
            with st.container(border=True):
                st.markdown(f"**{e['Acción']}** por {e['Quién']} · {e['Fecha']} · lote `{e['lote_id']}`")
                st.markdown(f"{e['id_evento']} — {e['Noticia']}")
                st.markdown(e["Detalle"])
                if existe_pagina(PAGINA_FICHA) and e["id_evento"] in set(base["id_evento"]):
                    st.button("Abrir la ficha de esta noticia", key="hist_abrir_ficha", on_click=abrir_ficha, args=(e["id_evento"],),
                              icon=":material/article:")

# ============================================================================ LOTES
with tab_lotes:
    lotes = repo.lotes_df(almacen)
    if lotes.empty:
        st.info("Todavía no hay cargas, sincronizaciones ni ediciones masivas registradas.", icon=":material/layers:")
    else:
        st.caption("Cada carga, sincronización, importación, asignación de categorías o corrección en lote forma un lote. "
                   "Puedes deshacer un lote completo: se devuelven los valores anteriores y se retiran las noticias que ese lote agregó.")
        tabla = lotes.assign(Estado=lotes["revertido"].map({True: "Deshecho", False: "Vigente"}))
        evento = st.dataframe(
            tabla[["fecha_hora", "usuario", "accion", "n_noticias", "n_cambios", "Estado", "lote_id"]], hide_index=True,
            on_select="rerun", selection_mode="single-row", key="lotes_tabla",
            column_config={"fecha_hora": "Fecha", "usuario": "Quién", "accion": "Acción", "n_noticias": st.column_config.NumberColumn("Noticias", format="%d"),
                           "n_cambios": st.column_config.NumberColumn("Cambios", format="%d"), "lote_id": "Lote"})
        filas = evento.selection.rows if evento and evento.selection else []
        if filas:
            lote = lotes.iloc[filas[0]]
            section_label(f"Lote {lote['lote_id']}")
            st.caption(f"{lote['accion']} · {lote['usuario']} · {vistas.fecha_corta(lote['fecha_hora'])} · "
                       f"{lote['n_cambios']} cambio(s) en {lote['n_noticias']} noticia(s)")
            plan = repo.plan_lote(lote["lote_id"], almacen)
            if lote["revertido"] or not plan:
                st.info("Este lote ya fue deshecho (o no queda nada por deshacer).", icon=":material/check:")
            else:
                nombres = {"campo": "Devolver valor", "eliminar": "Retirar noticia", "recrear": "Restaurar noticia"}
                titulos = dict(zip(base["id_evento"], base["titulo"]))
                prev = pd.DataFrame([{
                    "Qué pasaría": nombres[p["tipo"]], "ID": p["id_evento"], "Noticia": titulos.get(p["id_evento"], "")[:50],
                    "Campo": S.etiqueta(p["campo"]) if p["campo"] != repo.REGISTRO else "(noticia completa)",
                    "Ahora": p["actual"][:50], "Quedaría": p["objetivo"][:50], "Conflicto": p["conflicto"]} for p in plan])
                n_conf = int((prev["Conflicto"] != "").sum())
                st.dataframe(prev, hide_index=True, height=min(420, 60 + 35 * len(prev)))
                if n_conf:
                    st.warning(f"{n_conf} elemento(s) tienen conflicto (alguien cambió esos datos después) y se omitirán; "
                               "el resto se deshace.", icon=":material/warning:")

                def _deshacer(lote_id=lote["lote_id"]) -> str:
                    r = repo.revertir_lote(lote_id, usuario, almacen)
                    omit = f" ({len(r.omitidos)} omitido(s) por conflicto)" if r.omitidos else ""
                    return f"Lote deshecho: {r.resumen()}{omit}."
                auth.accion_protegida(
                    "Deshacer este lote", f"Se deshará el lote {lote['lote_id']} ({len(plan) - n_conf} de {len(plan)} elemento(s)). "
                    "Antes se guarda un respaldo automático y todo queda registrado en el historial.", _deshacer,
                    key="lote_deshacer", icon=":material/undo:", type="primary", disabled=not usuario or n_conf == len(plan))

# ============================================================================ EXPORTACIONES
with tab_export:
    exportaciones = repo.exportaciones_df(almacen)
    if exportaciones.empty:
        st.info("Todavía no hay exportaciones registradas. Se registran al descargar desde el Explorador.", icon=":material/download:")
    else:
        st.caption("Aquí quedan las exportaciones hechas desde el Explorador. Puedes repetirlas: se vuelve a generar el archivo con "
                   "las mismas noticias y columnas, pero con los **datos de hoy** (no es una copia congelada).")
        t = exportaciones.assign(Noticias=exportaciones["ids"].map(lambda s: len([i for i in s.split(",") if i])))
        evento = st.dataframe(t[["fecha_hora", "usuario", "formato", "modo_historias", "Noticias", "contexto", "id_exportacion"]], hide_index=True,
                              on_select="rerun", selection_mode="single-row", key="exp_tabla",
                              column_config={"fecha_hora": "Fecha", "usuario": "Quién", "formato": "Formato", "modo_historias": "Qué noticias",
                                             "contexto": st.column_config.TextColumn("Para qué", width="large"), "id_exportacion": "ID"})
        filas = evento.selection.rows if evento and evento.selection else []
        if filas:
            x = exportaciones.iloc[filas[0]]
            ids = [i for i in x["ids"].split(",") if i]
            cols = [c for c in x["columnas"].split(",") if c]
            completa = cols == ["*"]
            lectura = load_noticias()
            vigentes = lectura[lectura["id_evento"].isin(ids)]
            orden = {i: n for n, i in enumerate(ids)}
            vigentes = vigentes.assign(_o=vigentes["id_evento"].map(orden)).sort_values("_o").drop(columns="_o")
            section_label(f"Exportación {x['id_exportacion']}")
            st.markdown(f"**{x['formato'].upper()}** · {vistas.fecha_corta(x['fecha_hora'])} · {x['usuario']}  \n"
                        f"Para: {x['contexto'] or '—'}  \nFiltros: {x['filtros'] or '—'}")
            st.caption(f"{len(ids)} noticia(s) en la exportación original; {len(vigentes)} existen hoy. "
                       + ("Información completa." if completa else f"{len(cols)} columna(s) elegida(s)."))
            fmt = x["formato"]
            columnas = None if completa else cols
            datos = (lambda: export.experiences_to_excel(vigentes, columnas)) if fmt == "xlsx" else \
                (lambda: export.experiences_to_word(vigentes, x["contexto"], campos=columnas, con_logos=True)) if fmt == "docx" else \
                (lambda: export.experiences_to_csv(vigentes, columnas))
            st.download_button(f"Descargar de nuevo ({fmt})", data=datos, file_name=f"{x['id_exportacion']}_{date.today():%Y%m%d}.{fmt}",
                               mime=MIME[fmt], icon=":material/download:", disabled=vigentes.empty, on_click="ignore", key=f"exp_rep_{x['id_exportacion']}")
