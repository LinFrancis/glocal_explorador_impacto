# -*- coding: utf-8 -*-
"""Ficha de noticia: ver y editar todo lo de una noticia en un solo lugar.

Pestañas: Datos · Clasificación (con noticias parecidas ya analizadas) · Bitácora · Historial
(con reversión) · Vista de lectura. Cada guardado queda en el historial con el nombre de quien edita.
"""
import sys
from datetime import datetime, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from utils import auth, completitud, geocoding, repo, scraper, seleccion, similares, vistas
from utils import schema as S
from utils.components import bloque_completitud, render_news_card
from utils.data import almacen_actual, leer_base_cruda, leer_hoja, load_noticias, opciones_de_campos
from utils.formularios import campo_widget
from utils.repo import Cambio, ErrorOperacion
from utils.storage import ErrorAlmacen
from utils.style import inject, page_header, section_label
from utils.ui import K_FICHA, flash
from utils.validation import normalizar

K_SEL, K_VER = "ficha_sel", "ficha_ver"

CAMPOS_IDENTIFICACION = ("titulo", "url_noticia", "fuente", "fecha_publicacion_web", "tipo_informacion",
                         "Fundación Glocal?", "Consultora")
CAMPOS_CONTENIDO = ("descripcion_catalogo", "contenido_completo", "imagen_principal_url", "imagen_alt")
CAMPOS_PROYECTO = ("carpeta_proyecto", "documentos_proyecto")
CAMPOS_UBICACION = ("lugar",)
CAMPOS_CLASIFICACION = ("categoria_macro", "categorias", "metodologia", "actores_normalizados", "eje_gcaa", "objetivo_gcaa",
                        "atributos_resiliencia", "subatributos_resiliencia", "beneficiarios_directos",
                        "beneficiarios_indirectos", "enfoque_genero", "es_duplicado_secundario")
CAMPOS_METADATOS = ("slug", "wp_id", "fecha_modificacion_web", "timestamp_extraccion", "autor", "og_title", "og_description",
                    "og_url", "num_enlaces_externos", "origen", "cargado_por", "fecha_carga", "editado_por", "fecha_edicion")

st.set_page_config(page_title="Ficha de noticia", layout="wide")
inject()
page_header(
    "Gestión", "Ficha de noticia",
    "Todo lo de una noticia en un solo lugar: datos, clasificación, bitácora e historial de cambios. "
    "Cada cambio queda registrado con quién lo hizo, qué cambió y cuándo.",
)

usuario = auth.nombre_actual()
almacen = almacen_actual()
if not usuario:
    st.warning("Elige tu nombre en «Editando como» (menú lateral) para poder guardar cambios.", icon=":material/badge:")

base = leer_base_cruda()
if base.empty:
    st.info("Todavía no hay noticias en la base.")
    st.stop()
ids = base["id_evento"].tolist()
por_id = base.set_index("id_evento", drop=False)

# ----------------------------------------------------------------------------- selector
pedida = st.session_state.pop(K_FICHA, None)                      # viene de un botón «Abrir ficha»
if pedida in ids:
    st.session_state[K_SEL] = pedida
elif K_SEL not in st.session_state and st.query_params.get("id") in ids:
    st.session_state[K_SEL] = st.query_params.get("id")
if st.session_state.get(K_SEL) not in ids:
    st.session_state[K_SEL] = ids[0]


def _etiqueta(i: str) -> str:
    f = por_id.loc[i]
    return f"{i} · {str(f['titulo'])[:95]}"


def _al_cambiar_noticia() -> None:
    st.query_params["id"] = st.session_state[K_SEL]


ide = st.selectbox("Noticia", ids, format_func=_etiqueta, key=K_SEL, on_change=_al_cambiar_noticia,
                   help="Escribe parte del título o el ID para buscar.")
st.query_params["id"] = ide
fila = por_id.loc[ide].to_dict()
ver = st.session_state.setdefault(K_VER, 0)
opciones = opciones_de_campos()
lectura = load_noticias()
fila_lectura = lectura[lectura["id_evento"] == ide]
comp = completitud.calcular(fila)


def _k(campo: str) -> str:
    return f"ficha_{ide}_{ver}_{campo}"


# ----------------------------------------------------------------------------- cabecera
col_info, col_comp = st.columns([3, 2], vertical_alignment="top")
with col_info:
    st.markdown(f"### {fila['titulo']}")
    st.caption(f"{ide} · {fila['fuente'] or 'sin fuente'} · "
               f"{vistas.fecha_corta(fila.get('fecha_publicacion_web')) or 'sin fecha de publicación'}")
    if fila.get("editado_por"):
        st.markdown(f":material/edit: **Editado por {fila['editado_por']}** · {vistas.hace_cuanto(fila.get('fecha_edicion'))} "
                    f"({vistas.fecha_corta(fila.get('fecha_edicion'))})")
    elif fila.get("cargado_por"):
        st.markdown(f":material/upload: Cargada por **{fila['cargado_por']}** · {vistas.fecha_corta(fila.get('fecha_carga'))}")
    else:
        st.caption("Registro histórico, sin ediciones desde que se migró a la plataforma.")
    with st.container(horizontal=True, vertical_alignment="center"):
        if fila.get("url_noticia"):
            st.link_button("Ver en la web", fila["url_noticia"], icon=":material/open_in_new:")
        if fila.get("carpeta_proyecto"):
            st.link_button("Abrir carpeta del proyecto", fila["carpeta_proyecto"], icon=":material/folder_open:", type="primary")
        marcado = st.toggle("Incluir en la exportación", value=seleccion.esta(ide), key=f"ficha_sel_exp_{ide}_{seleccion.version()}")
        seleccion.marcar(ide, marcado)
with col_comp:
    bloque_completitud(comp)


# ----------------------------------------------------------------------------- utilidades de guardado
def _cambios(valores: dict[str, str]) -> list[Cambio]:
    """Solo lo que cambió de verdad (comparando ya normalizado, para no registrar diferencias de formato)."""
    cambios = []
    for k, v in valores.items():
        campo = S.CAMPO[k]
        nuevo, _ = normalizar(v, campo, opciones.get(k))
        viejo, _ = normalizar(fila.get(k, ""), campo)
        if nuevo != viejo:
            cambios.append(Cambio(ide, k, fila.get(k, ""), v))
    return cambios


def _guardar(valores: dict[str, str], accion: str = S.ACC_EDITAR, forzar: bool = False) -> None:
    cambios = _cambios(valores)
    if not cambios:
        st.info("No hay cambios que guardar.", icon=":material/info:")
        return
    try:
        res = repo.aplicar_cambios(cambios, usuario, accion=accion, almacen=almacen, forzar_no_editables=forzar)
    except (ErrorOperacion, ErrorAlmacen) as e:
        st.error(str(e), icon=":material/error:")
        return
    if res.aplicados:
        flash("exito", f"Se guardaron {len(res.aplicados)} cambio(s): " + ", ".join(S.etiqueta(a["campo"]) for a in res.aplicados[:6]) + ".")
    for o in res.omitidos:
        flash("error", f"No se guardó «{S.etiqueta(o['campo'])}»: {o['motivo']}")
    for a in res.avisos[:8]:
        flash("aviso", a)
    st.session_state[K_VER] = ver + 1
    st.rerun()


def _formulario(nombre: str, claves: tuple[str, ...]) -> None:
    with st.form(f"form_{nombre}_{ide}_{ver}", border=False):
        valores = {k: campo_widget(S.CAMPO[k], fila.get(k, ""), _k(k), opciones.get(k)) for k in claves}
        enviado = st.form_submit_button("Guardar cambios", type="primary", icon=":material/save:", disabled=not usuario)
    if enviado:
        _guardar(valores)


# ----------------------------------------------------------------------------- pestañas
tab_datos, tab_clasif, tab_notas, tab_hist, tab_lectura = st.tabs([
    ":material/description: Datos", ":material/category: Clasificación", ":material/sticky_note_2: Bitácora",
    ":material/history: Historial", ":material/visibility: Vista de lectura"], key="ficha_pestanas")

# ============================================================================ DATOS
with tab_datos:
    section_label("Datos de la noticia")
    _formulario("datos", CAMPOS_IDENTIFICACION + CAMPOS_CONTENIDO + CAMPOS_PROYECTO + CAMPOS_UBICACION)

    # ---- ubicación: geocodificar
    with st.expander("Coordenadas del lugar", expanded=False):
        lugares = [p.strip() for p in str(fila.get("lugar", "")).split(";") if p.strip()]
        if not lugares:
            st.caption("Esta noticia no tiene lugar. Indica uno en el formulario de arriba para poder buscar sus coordenadas.")
        else:
            def _tabla_sitios(lat, lon, pais, prec) -> pd.DataFrame:
                n = len(lugares)
                p = lambda t: (([x.strip() for x in str(t or "").split(";")] + [""] * n)[:n])
                return pd.DataFrame({"Lugar": lugares, "Latitud": p(lat), "Longitud": p(lon), "País": p(pais), "Precisión": p(prec)})
            st.dataframe(_tabla_sitios(fila["sitios_lat"], fila["sitios_lon"], fila["sitios_pais"],
                                       fila["sitios_precision_geocodificacion"]), hide_index=True)
            st.caption("La cuenca hidrográfica no se completa sola (requiere el cruce con el mapa de cuencas).")
            clave_geo = f"ficha_geo_{ide}"
            if st.button("Buscar las coordenadas que faltan", icon=":material/pin_drop:", key=f"ficha_geo_btn_{ide}"):
                try:
                    with st.status("Consultando el servicio de mapas (OpenStreetMap)…", expanded=True) as estado:
                        res = geocoding.completar(fila["lugar"], fila["sitios_lat"], fila["sitios_lon"], fila["sitios_pais"],
                                                  fila["sitios_precision_geocodificacion"], progreso=st.write)
                        estado.update(label="Consulta terminada", state="complete", expanded=False)
                    st.session_state[clave_geo] = res
                except geocoding.ErrorGeocodificacion as e:
                    st.error(str(e), icon=":material/error:")
            pend = st.session_state.get(clave_geo)
            if pend is not None:
                st.markdown("**Propuesta** (revísala antes de guardar):")
                v = pend.valores
                st.dataframe(_tabla_sitios(v["sitios_lat"], v["sitios_lon"], v["sitios_pais"], v["sitios_precision_geocodificacion"]),
                             hide_index=True)
                st.caption(f"{pend.n_nuevos} lugar(es) encontrado(s), {pend.n_fallidos} no encontrado(s). "
                           "Las coordenadas vienen de OpenStreetMap y pueden ser aproximadas.")
                if st.button("Guardar coordenadas", type="primary", icon=":material/save:", key=f"ficha_geo_ok_{ide}",
                             disabled=not usuario):
                    st.session_state.pop(clave_geo, None)
                    _guardar(v)

    # ---- metadatos descargados de la web (solo lectura) + actualizar
    with st.expander("Metadatos descargados de la web (solo lectura)", expanded=False):
        meta = {S.etiqueta(k): fila.get(k, "") for k in CAMPOS_METADATOS if fila.get(k, "")}
        st.table(meta) if meta else st.caption("Sin metadatos.")
        enlaces = [u for u in str(fila.get("enlaces_externos", "")).split("|") if u.strip()]
        if enlaces:
            st.markdown("**Enlaces externos de la noticia:**\n" + "\n".join(f"- {u.strip()}" for u in enlaces[:30]))
        if fila.get("wp_id") and fila.get("fuente") in scraper.FUENTES_WEB:
            clave_web = f"ficha_web_{ide}"
            if st.button("Actualizar desde la web", icon=":material/sync:", key=f"ficha_web_btn_{ide}",
                         help="Descarga solo esta noticia y muestra qué cambió respecto de lo guardado."):
                with st.spinner("Consultando el sitio…"):
                    web, error = scraper.descargar_uno(fila["fuente"], fila["wp_id"])
                if error:
                    st.error(error, icon=":material/error:")
                else:
                    st.session_state[clave_web] = scraper.diferencias_de_fila(fila, web)
            diffs = st.session_state.get(clave_web)
            if diffs is not None:
                if not diffs:
                    st.success("✓ La noticia coincide con la web.", icon=":material/check_circle:")
                else:
                    elegidos = st.multiselect("Campos a actualizar con lo que dice la web",
                                              [d["campo"] for d in diffs], default=[d["campo"] for d in diffs],
                                              format_func=S.etiqueta, key=f"ficha_web_sel_{ide}_{ver}")
                    st.dataframe(pd.DataFrame([{"Campo": S.etiqueta(d["campo"]), "En la base": d["antes"][:120],
                                                "En la web": d["despues"][:120]} for d in diffs]), hide_index=True)
                    if st.button("Aplicar lo elegido", type="primary", key=f"ficha_web_ok_{ide}", icon=":material/check:",
                                 disabled=not usuario or not elegidos):
                        st.session_state.pop(clave_web, None)
                        _guardar({d["campo"]: d["despues"] for d in diffs if d["campo"] in elegidos}, accion=S.ACC_SINCRONIZAR, forzar=True)

# ============================================================================ CLASIFICACIÓN
with tab_clasif:
    section_label("Noticias parecidas ya analizadas")
    parecidas = similares.similares(lectura, ide, k=5)
    with st.expander(f"{len(parecidas)} sugerencia(s) a partir de noticias con análisis completo", expanded=comp.pct_analisis < 75):
        st.caption("Se comparan los textos con las noticias que ya tienen análisis. Es solo una ayuda: «Copiar clasificación» "
                   "rellena el formulario de abajo y no guarda nada hasta que pulses «Guardar cambios».")
        if not parecidas:
            st.caption("No hay noticias analizadas con vocabulario en común.")
        for p in parecidas:
            clasif = similares.clasificacion_de(p["fila"])

            def _copiar(clasif=clasif, titulo=p["titulo"]) -> None:
                for k, v in clasif.items():
                    st.session_state[_k(k)] = S.dividir_etiquetas(v) if S.CAMPO[k].tipo == S.ETIQUETAS else v
                flash("info", f"Se copió la clasificación de «{titulo[:60]}» al formulario. Revísala y guarda.")

            with st.container(border=True):
                st.markdown(f"**{p['titulo'][:100]}** · parecido {p['puntaje']:.0f} %")
                st.caption(f"{p['id_evento']} · Categoría: {clasif.get('categoria_macro', '—')[:80]} · "
                           f"Palabras en común: {', '.join(p['comunes'])}")
                st.button("Copiar clasificación", key=f"ficha_copiar_{ide}_{p['id_evento']}_{ver}", on_click=_copiar,
                          icon=":material/content_copy:", disabled=not clasif)

    section_label("Clasificación")
    _formulario("clasificacion", CAMPOS_CLASIFICACION)

    section_label("Variables propias")
    propias = tuple(c.key for c in S.variables_activas())
    if propias:
        st.caption("Categorías analíticas creadas por el equipo en Administración → Variables analíticas.")
        _formulario("variables", propias)
    else:
        st.caption("Aún no hay variables propias. Puedes crear una (por ejemplo «Tamaño del proyecto» con sus opciones de respuesta) en "
                   "Administración → Variables analíticas.")

# ============================================================================ BITÁCORA
with tab_notas:
    section_label("Bitácora de notas")
    with st.form(f"form_nota_{ide}_{ver}", clear_on_submit=True, border=False):
        texto = st.text_area("Nueva nota", placeholder="Ej.: Falta confirmar el lugar con la persona que facilitó el taller.",
                             height=100)
        enviar = st.form_submit_button("Agregar nota", icon=":material/add:", disabled=not usuario)
    if enviar:
        try:
            repo.agregar_nota(ide, texto, usuario, almacen)
        except (ErrorOperacion, ErrorAlmacen) as e:
            st.error(str(e), icon=":material/error:")
        else:
            flash("exito", "Nota agregada.")
            st.rerun()
    notas = leer_hoja(S.HOJA_NOTAS)
    notas = notas[notas["id_evento"] == ide].sort_values("id_nota", ascending=False)
    if notas.empty:
        st.caption("Todavía no hay notas para esta noticia.")
    for n in notas.itertuples():
        with st.container(border=True):
            st.markdown(n.texto)
            st.caption(f"{n.usuario} · {vistas.fecha_corta(n.fecha_hora)} ({vistas.hace_cuanto(n.fecha_hora)})")

# ============================================================================ HISTORIAL
with tab_hist:
    section_label("Historial de cambios de esta noticia")
    hist = repo.historial_df(almacen, ide)
    legible = vistas.historial_legible(hist, base)
    if legible.empty:
        st.caption("Esta noticia no tiene cambios registrados.")
    else:
        st.caption("Elige una fila para ver el detalle y poder revertir ese cambio.")
        evento = st.dataframe(legible[["Fecha", "Quién", "Acción", "Campo", "Antes", "Después"]], hide_index=True,
                              on_select="rerun", selection_mode="single-row", key=f"ficha_hist_{ide}_{ver}",
                              column_config={"Antes": st.column_config.TextColumn(width="medium"),
                                             "Después": st.column_config.TextColumn(width="medium")})
        filas = evento.selection.rows if evento and evento.selection else []
        if filas:
            e = legible.iloc[filas[0]]
            actual = str(fila.get(next((k for k in S.COLUMNAS if S.etiqueta(k) == e["Campo"]), ""), "")) if e["Campo"] != "(noticia completa)" else ""
            with st.container(border=True):
                st.markdown(f"**{e['Acción']}** por {e['Quién']} · {e['Fecha']}")
                if e["Campo"] == "(noticia completa)":
                    st.caption("Es el alta o baja de la noticia completa: se deshace desde «Historial de cambios» → Lotes.")
                else:
                    st.markdown(f"**{e['Campo']}**")
                    st.markdown(f"Antes: «{e['Antes'] or '(vacío)'}»  \nDespués: «{e['Después'] or '(vacío)'}»  \nAhora: «{actual or '(vacío)'}»")
                    clave_rev = f"ficha_rev_{e['id_cambio']}"
                    forzar = st.checkbox("Revertir aunque el valor actual sea distinto del «Después»", key=clave_rev + "_f") \
                        if actual != e["Después"] else False
                    if st.button("Revertir este cambio", icon=":material/undo:", key=clave_rev, disabled=not usuario):
                        try:
                            res = repo.revertir_cambio(e["id_cambio"], usuario, almacen, forzar=forzar)
                        except (ErrorOperacion, ErrorAlmacen) as err:
                            st.error(str(err), icon=":material/error:")
                        else:
                            if res.aplicados:
                                flash("exito", f"Se revirtió «{e['Campo']}» a su valor anterior.")
                                st.session_state[K_VER] = ver + 1
                                st.rerun()
                            else:
                                st.warning(" ".join(o["motivo"] for o in res.omitidos) or "No había nada que revertir.",
                                           icon=":material/warning:")

        # restaurar la noticia a una fecha (acción protegida)
        with st.expander("Restaurar la noticia a una fecha anterior", expanded=False):
            c1, c2 = st.columns(2)
            dia = c1.date_input("Fecha", value=datetime.now().date(), key=f"ficha_rest_f_{ide}")
            hora = c2.time_input("Hora", value=time(23, 59), key=f"ficha_rest_h_{ide}")
            hasta = f"{dia:%Y-%m-%d} {hora:%H:%M:%S}"
            try:
                plan = repo.plan_restauracion(ide, hasta, almacen)
            except ErrorOperacion as err:
                plan = None
                st.warning(str(err), icon=":material/warning:")
            if plan is not None:
                if not plan:
                    st.caption("A esa fecha la noticia estaba igual que ahora: no hay nada que restaurar.")
                else:
                    st.dataframe(pd.DataFrame([{"Campo": S.etiqueta(p["campo"]), "Ahora": p["actual"][:80], "Quedaría": p["objetivo"][:80]}
                                               for p in plan]), hide_index=True)

                    def _restaurar(ide=ide, hasta=hasta) -> str:
                        r = repo.restaurar_noticia(ide, hasta, usuario, almacen)
                        st.session_state[K_VER] = st.session_state.get(K_VER, 0) + 1
                        return f"Noticia restaurada a su estado del {hasta}: {r.resumen()}."
                    auth.accion_protegida("Restaurar a esa fecha", f"Se devolverán {len(plan)} campo(s) de {ide} a como estaban "
                                          f"el {hasta}. Queda registrado en el historial.", _restaurar,
                                          key=f"ficha_rest_{ide}", icon=":material/restore:", disabled=not usuario)

# ============================================================================ VISTA DE LECTURA
with tab_lectura:
    if fila_lectura.empty:
        st.info("Esta noticia aún no está en la vista de lectura.")
    else:
        render_news_card(fila_lectura.iloc[0])
