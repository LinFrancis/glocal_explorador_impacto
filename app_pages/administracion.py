# -*- coding: utf-8 -*-
"""Administración: categorías y variables analíticas, asignación en lote, bitácora general, calidad de datos,
duplicados, respaldo y equipo. Las acciones destructivas piden la clave de administración."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from utils import auth, calidad, dedupe, geocoding, repo, storage, vistas
from utils import variables as V
from utils import schema as S
from utils.data import almacen_actual, leer_base_cruda, leer_hoja
from utils.repo import Cambio, ErrorOperacion
from utils.storage import ErrorAlmacen
from utils.style import inject, page_header, section_label
from utils.ui import PAGINA_FICHA, abrir_ficha, existe_pagina, flash

MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_GEO = 25                      # lugares por tanda (el servicio de mapas permite 1 consulta por segundo)

st.set_page_config(page_title="Administración", layout="wide")
inject()
page_header(
    "Administración", "Administración de la plataforma",
    "Gestiona las categorías analíticas, revisa la calidad de los datos, resuelve duplicados y cuida los respaldos. "
    "Las acciones que cambian muchas noticias a la vez piden la clave de administración.",
)

usuario = auth.nombre_actual()
almacen = almacen_actual()
base = leer_base_cruda()
firma = almacen.firma()
if not usuario:
    st.warning("Elige tu nombre en «Editando como» (menú lateral): se registra quién hace cada cambio.", icon=":material/badge:")

(tab_cat, tab_var, tab_asig, tab_notas, tab_cal, tab_dup, tab_sync, tab_resp, tab_eq) = st.tabs([
    ":material/sell: Categorías macro y temática", ":material/tune: Variables analíticas",
    ":material/playlist_add_check: Asignar a noticias", ":material/sticky_note_2: Bitácora general",
    ":material/fact_check: Calidad de datos", ":material/difference: Duplicados", ":material/sync: Sincronización", ":material/backup: Respaldo",
    ":material/groups: Equipo"], key="admin_pestanas")      # con clave, la pestaña activa se conserva al guardar algo

NOMBRE_DIM = S.DIMENSIONES_CATALOGO


def _aviso_resultado(res: repo.Resultado, ok_msg: str) -> None:
    flash("exito", ok_msg)
    for o in res.omitidos[:6]:
        flash("error", f"No se aplicó {o['id_evento']} · {S.etiqueta(o['campo'])}: {o['motivo']}")
    for a in res.avisos[:6]:
        flash("aviso", a)


# ============================================================================ CATEGORÍAS
with tab_cat:
    section_label("Catálogo de categorías analíticas")
    st.caption("Son las categorías que se pueden asignar a las noticias (categoría macro y categoría temática). "
               "Los ejes GCAA y los atributos de resiliencia vienen de marcos externos y no se editan aquí.")
    cat = leer_hoja(S.HOJA_CATEGORIAS)
    uso = repo.uso_categorias(almacen)
    if cat.empty:
        st.info("El catálogo está vacío.")
    else:
        tabla = pd.DataFrame({
            "Dimensión": [NOMBRE_DIM[d] for d in cat["dimension"]], "Categoría": cat["nombre"], "Descripción": cat["descripcion"],
            "Noticias": [uso.get((d, n), 0) for d, n in zip(cat["dimension"], cat["nombre"])],
            "Activa": cat["activa"].str.lower() != "false"})
        ev = st.dataframe(tabla, hide_index=True, on_select="rerun", selection_mode="single-row", key="cat_tabla", height=340,
                          column_config={"Descripción": st.column_config.TextColumn(width="large"),
                                         "Noticias": st.column_config.NumberColumn(format="%d"), "Activa": st.column_config.CheckboxColumn()})
        filas = ev.selection.rows if ev and ev.selection else []
        if filas:
            c = cat.iloc[filas[0]]
            dim, nombre = c["dimension"], c["nombre"]
            activa = str(c["activa"]).lower() != "false"
            with st.container(border=True):
                st.markdown(f"**{nombre}** · {NOMBRE_DIM[dim]} · usada en {uso.get((dim, nombre), 0)} noticia(s)")
                nueva_desc = st.text_area("Descripción", value=c["descripcion"], key=f"cat_desc_{dim}_{nombre}", height=80)
                if st.button("Guardar descripción", icon=":material/save:", key=f"cat_desc_ok_{dim}_{nombre}"):
                    repo.actualizar_categoria(dim, nombre, almacen, descripcion=nueva_desc)
                    flash("exito", "Descripción guardada.")
                    st.rerun()
                nuevo_nombre = st.text_input("Nuevo nombre", key=f"cat_ren_{dim}_{nombre}", placeholder="Para renombrarla en todas las noticias")

                def _renombrar(dim=dim, nombre=nombre, nuevo=nuevo_nombre) -> str:
                    r = repo.renombrar_categoria(dim, nombre, nuevo, usuario, almacen)
                    return f"Categoría renombrada a «{nuevo}» en {r.n_noticias} noticia(s). Se puede deshacer desde el historial (Lotes)."
                with st.container(horizontal=True):
                    auth.accion_protegida("Renombrar", f"Se renombrará «{nombre}» a «{nuevo_nombre}» en el catálogo y en todas las noticias que la usan.",
                                          _renombrar, key=f"cat_ren_ok_{dim}_{nombre}", icon=":material/edit:",
                                          disabled=not usuario or not nuevo_nombre.strip() or nuevo_nombre.strip() == nombre)
                    if activa:
                        def _desactivar(dim=dim, nombre=nombre) -> str:
                            repo.actualizar_categoria(dim, nombre, almacen, activa=False)
                            return f"«{nombre}» quedó desactivada: ya no se ofrece al asignar, pero las noticias que la tienen la conservan."
                        auth.accion_protegida("Desactivar", f"«{nombre}» dejará de ofrecerse al asignar categorías.", _desactivar,
                                              key=f"cat_off_{dim}_{nombre}", icon=":material/block:")
                    elif st.button("Reactivar", icon=":material/check:", key=f"cat_on_{dim}_{nombre}"):
                        repo.actualizar_categoria(dim, nombre, almacen, activa=True)
                        flash("exito", f"«{nombre}» está activa otra vez.")
                        st.rerun()

    with st.expander("Crear una categoría nueva", expanded=cat.empty):
        with st.form("cat_nueva", clear_on_submit=True, border=False):
            dim_n = st.selectbox("Dimensión", list(NOMBRE_DIM), format_func=NOMBRE_DIM.get)
            nombre_n = st.text_input("Nombre *")
            desc_n = st.text_area("Descripción (opcional)", height=70)
            crear = st.form_submit_button("Crear categoría", type="primary", icon=":material/add:", disabled=not usuario)
        if crear:
            try:
                repo.crear_categoria(dim_n, nombre_n, desc_n, usuario, almacen)
            except (ErrorOperacion, ErrorAlmacen) as e:
                st.error(str(e), icon=":material/error:")
            else:
                flash("exito", f"Categoría «{nombre_n.strip()}» creada.")
                st.rerun()

# ============================================================================ VARIABLES ANALÍTICAS
with tab_var:
    section_label("Categorías analíticas propias (variables)")
    st.caption("Crea una nueva categoría analítica con su tipo y sus opciones de respuesta. Por ejemplo «Tamaño del proyecto» con las "
               "opciones Pequeño, Mediano y Grande. Una vez creada aparece en la ficha de cada noticia, en la tabla de datos, como filtro "
               "y gráfico en el Explorador, se puede exportar y queda registrada en el Marco teórico y en el libro de códigos.")
    variables = repo.listar_variables(almacen)
    uso_v = repo.uso_variables(almacen)
    n_form = st.session_state.setdefault("var_form_n", 0)

    # ---- crear
    with st.container(border=True):
        st.markdown("**Crear una variable nueva**")
        nombre_v = st.text_input("Nombre de la variable *", key=f"var_nombre_{n_form}", placeholder="Ej.: Tamaño del proyecto")
        tipo_v = st.selectbox("Tipo de variable *", list(V.TIPOS), format_func=lambda k: V.TIPOS[k][0], key=f"var_tipo_{n_form}")
        opciones_v = ""
        if tipo_v in V.TIPOS_CON_OPCIONES:
            opciones_v = st.text_area("Opciones de respuesta * (una por línea)", key=f"var_opciones_{n_form}", height=120,
                                      placeholder="Pequeño\nMediano\nGrande",
                                      help="Son las únicas respuestas posibles. Después puedes agregar, renombrar o quitar opciones.")
        elif tipo_v == "si_no":
            st.caption("Las respuestas serán «Sí» y «No».")
        desc_v = st.text_area("Descripción (opcional)", key=f"var_desc_{n_form}", height=70,
                              placeholder="Qué significa y cómo decidir cada opción.",
                              help="Se muestra como ayuda en la ficha y se publica en el Marco teórico y en el libro de códigos.")
        if nombre_v.strip():
            st.caption(f"Se creará la columna `{V.clave_de(V.limpiar_etiqueta(nombre_v))}` y la variable «{V.limpiar_etiqueta(nombre_v)}».")
        if st.button("Crear variable", type="primary", icon=":material/add:", key=f"var_crear_{n_form}", disabled=not usuario):
            try:
                nueva = repo.crear_variable(nombre_v, tipo_v, opciones_v, desc_v, usuario, almacen)
            except (ErrorOperacion, ErrorAlmacen) as e:
                st.error(str(e), icon=":material/error:")
            else:
                flash("exito", f"Variable «{nueva.etiqueta}» creada. Ya puedes asignarla en cada ficha o en lote desde «Asignar a noticias».")
                st.session_state["var_form_n"] = n_form + 1
                st.rerun()

    # ---- lista
    if not variables:
        st.info("Todavía no hay variables propias. Crea la primera arriba.", icon=":material/tune:")
    else:
        section_label("Variables creadas")
        tabla_v = pd.DataFrame({
            "Variable": [v.etiqueta for v in variables], "Tipo": [V.TIPOS[v.tipo][0].split(" — ")[0] for v in variables],
            "Opciones": [", ".join(v.opciones_efectivas) for v in variables],
            "Noticias con dato": [uso_v[v.clave]["con_dato"] for v in variables], "Activa": [v.activa for v in variables]})
        ev = st.dataframe(tabla_v, hide_index=True, on_select="rerun", selection_mode="single-row", key="var_tabla",
                          column_config={"Opciones": st.column_config.TextColumn(width="large"),
                                         "Noticias con dato": st.column_config.NumberColumn(format="%d"),
                                         "Activa": st.column_config.CheckboxColumn()})
        filas = ev.selection.rows if ev and ev.selection else []
        if filas:
            v = variables[filas[0]]
            u = uso_v[v.clave]
            with st.container(border=True):
                st.markdown(f"**{v.etiqueta}** · {V.TIPOS[v.tipo][0].split(' — ')[0]} · `{v.clave}` · {u['con_dato']} noticia(s) con dato")
                c1, c2 = st.columns(2)
                nuevo_nombre = c1.text_input("Nombre", value=v.etiqueta, key=f"var_nom_{v.clave}")
                nueva_desc = c2.text_input("Descripción", value=v.descripcion, key=f"var_des_{v.clave}")
                if st.button("Guardar nombre y descripción", icon=":material/save:", key=f"var_guardar_{v.clave}"):
                    try:
                        repo.actualizar_variable(v.clave, almacen, etiqueta=nuevo_nombre, descripcion=nueva_desc)
                    except (ErrorOperacion, ErrorAlmacen) as e:
                        st.error(str(e), icon=":material/error:")
                    else:
                        flash("exito", "Variable actualizada.")
                        st.rerun()

                if v.lleva_opciones:
                    st.markdown("**Opciones de respuesta**")
                    st.dataframe(pd.DataFrame({"Opción": list(v.opciones), "Noticias": [u["por_opcion"].get(o, 0) for o in v.opciones]}),
                                 hide_index=True, height=min(300, 60 + 35 * len(v.opciones)))
                    a1, a2 = st.columns([3, 1], vertical_alignment="bottom")
                    nueva_op = a1.text_input("Agregar una opción", key=f"var_nueva_op_{v.clave}_{len(v.opciones)}", placeholder="Ej.: Muy grande")
                    if a2.button("Agregar", icon=":material/add:", key=f"var_add_op_{v.clave}", disabled=not nueva_op.strip(), width="stretch"):
                        try:
                            repo.agregar_opcion(v.clave, nueva_op, almacen)
                        except (ErrorOperacion, ErrorAlmacen) as e:
                            st.error(str(e), icon=":material/error:")
                        else:
                            flash("exito", f"Opción «{nueva_op.strip()}» agregada.")
                            st.rerun()
                    b1, b2 = st.columns(2)
                    op_sel = b1.selectbox("Opción a renombrar o quitar", list(v.opciones), key=f"var_op_sel_{v.clave}")
                    nombre_op = b2.text_input("Nuevo nombre (para renombrar)", key=f"var_op_nuevo_{v.clave}")
                    with st.container(horizontal=True):
                        def _renombrar_op(clave=v.clave, viejo=op_sel, nuevo=nombre_op) -> str:
                            r = repo.renombrar_opcion(clave, viejo, nuevo, usuario, almacen)
                            return f"Opción «{viejo}» renombrada a «{nuevo.strip()}» en {r.n_noticias} noticia(s). Se puede deshacer desde el historial (Lotes)."
                        auth.accion_protegida("Renombrar opción", f"Se renombrará «{op_sel}» a «{nombre_op}» en la definición y en todas las noticias que la tienen.",
                                              _renombrar_op, key=f"var_ren_op_{v.clave}", icon=":material/edit:",
                                              disabled=not usuario or not nombre_op.strip() or nombre_op.strip() == op_sel)
                        if st.button("Quitar opción", icon=":material/remove:", key=f"var_quitar_op_{v.clave}"):
                            try:
                                repo.quitar_opcion(v.clave, op_sel, almacen)
                            except (ErrorOperacion, ErrorAlmacen) as e:
                                st.error(str(e), icon=":material/error:")
                            else:
                                flash("exito", f"Opción «{op_sel}» quitada.")
                                st.rerun()
                    st.caption("Una opción que alguna noticia usa no se puede quitar: primero cámbiala en esas noticias o renómbrala.")

                if v.activa:
                    def _desactivar_v(clave=v.clave, nombre=v.etiqueta) -> str:
                        repo.actualizar_variable(clave, almacen, activa=False)
                        return f"«{nombre}» quedó desactivada: ya no se ofrece en formularios ni filtros, pero los datos se conservan."
                    auth.accion_protegida("Desactivar variable", f"«{v.etiqueta}» dejará de ofrecerse en formularios, filtros y tablas. "
                                          "Los datos de las noticias se conservan.", _desactivar_v, key=f"var_off_{v.clave}", icon=":material/block:")
                elif st.button("Reactivar variable", icon=":material/check:", key=f"var_on_{v.clave}"):
                    repo.actualizar_variable(v.clave, almacen, activa=True)
                    flash("exito", f"«{v.etiqueta}» está activa otra vez.")
                    st.rerun()

# ============================================================================ ASIGNAR
with tab_asig:
    section_label("Asignar o quitar una categoría en varias noticias")
    catalogo = repo.catalogo_desde_df(leer_hoja(S.HOJA_CATEGORIAS))
    propias = [c for c in S.variables_activas() if isinstance(c.opciones, tuple)]            # variables de opciones (incluye Sí/No)
    dims_asignables = {**NOMBRE_DIM, **{c.key: c.label for c in propias}}
    for c in propias:
        catalogo[c.key] = list(c.opciones)
    c1, c2, c3 = st.columns([1, 2, 1])
    dim_a = c1.selectbox("Categoría analítica", list(dims_asignables), format_func=dims_asignables.get, key="asig_dim")
    cat_a = c2.selectbox("Opción", catalogo.get(dim_a, []), key=f"asig_cat_{dim_a}", placeholder="Elige una opción")
    es_unica = dim_a in S.CAMPO and S.CAMPO[dim_a].variable and S.CAMPO[dim_a].tipo == S.OPCION
    accion_a = c3.radio("Acción", ["Asignar" if es_unica else "Agregar", "Quitar"], horizontal=True, key=f"asig_accion_{'u' if es_unica else 'm'}")
    f1, f2, f3 = st.columns([2, 2, 1])
    texto_a = f1.text_input("Buscar en título", key="asig_texto", placeholder="Parte del título o ID")
    fuente_a = f2.multiselect("Fuente", list(S.FUENTES), key="asig_fuente")
    sin_a = f3.checkbox("Solo sin categoría", key="asig_sin", help="Noticias que no tienen nada en esta dimensión.")
    ver = base
    if texto_a.strip():
        q = texto_a.strip().lower()
        ver = ver[ver["titulo"].str.lower().str.contains(q, regex=False) | ver["id_evento"].str.lower().str.contains(q, regex=False)]
    if fuente_a:
        ver = ver[ver["fuente"].isin(fuente_a)]
    if sin_a:
        ver = ver[ver[dim_a].str.strip() == ""]
    if accion_a == "Quitar" and cat_a:
        ver = ver[ver[dim_a].map(lambda v: cat_a in S.dividir_etiquetas(v))]
    elif accion_a in ("Agregar", "Asignar") and cat_a:
        ver = ver[ver[dim_a].map(lambda v: cat_a not in S.dividir_etiquetas(v))]
    LIMITE = 400
    ver = ver.head(LIMITE)
    marcar_todas = st.checkbox(f"Marcar todas las mostradas ({len(ver)})", key=f"asig_todas_{dim_a}_{accion_a}_{cat_a}")
    tabla = pd.DataFrame({"Incluir": marcar_todas, "ID": ver["id_evento"].values, "Título": ver["titulo"].str[:90].values,
                          f"{dims_asignables[dim_a]} actual": ver[dim_a].values})
    editada = st.data_editor(tabla, hide_index=True, key=f"asig_tabla_{dim_a}_{accion_a}_{cat_a}_{marcar_todas}_{len(ver)}_{firma}",
                             disabled=["ID", "Título", f"{dims_asignables[dim_a]} actual"], height=min(420, 60 + 35 * max(1, len(tabla))),
                             column_config={"Incluir": st.column_config.CheckboxColumn(width="small"), "Título": st.column_config.TextColumn(width="large")})
    elegidos = editada.loc[editada["Incluir"], "ID"].tolist()
    if len(ver) == LIMITE:
        st.caption(f"Se muestran las primeras {LIMITE}; afina la búsqueda para ver otras.")
    if st.button(f"{accion_a} «{cat_a or '…'}» en {len(elegidos)} noticia(s)", type="primary", icon=":material/check:", key="asig_aplicar",
                 disabled=not usuario or not cat_a or not elegidos):
        try:
            res = repo.asignar_categoria(dim_a, cat_a, elegidos, usuario, "quitar" if accion_a == "Quitar" else "agregar", almacen)
        except (ErrorOperacion, ErrorAlmacen) as e:
            st.error(str(e), icon=":material/error:")
        else:
            _aviso_resultado(res, f"Listo: {accion_a.lower()} «{cat_a}» en {res.n_noticias} noticia(s). Se puede deshacer desde el historial (Lotes).")
            st.rerun()

# ============================================================================ BITÁCORA GENERAL
with tab_notas:
    section_label("Notas de todas las noticias")
    notas = leer_hoja(S.HOJA_NOTAS).sort_values("id_nota", ascending=False)
    if notas.empty:
        st.info("Todavía no hay notas. Se agregan desde la ficha de cada noticia.", icon=":material/sticky_note_2:")
    else:
        titulos = dict(zip(base["id_evento"], base["titulo"]))
        n1, n2 = st.columns([1, 2])
        autor = n1.multiselect("Quién", sorted(notas["usuario"].unique()), key="notas_autor")
        buscar = n2.text_input("Buscar en las notas", key="notas_buscar")
        sel = notas
        if autor:
            sel = sel[sel["usuario"].isin(autor)]
        if buscar.strip():
            sel = sel[sel["texto"].str.lower().str.contains(buscar.strip().lower(), regex=False)]
        vista = pd.DataFrame({"Fecha": sel["fecha_hora"].map(vistas.fecha_corta), "Quién": sel["usuario"], "ID": sel["id_evento"],
                              "Noticia": sel["id_evento"].map(lambda i: titulos.get(i, "")[:60]), "Nota": sel["texto"]}).reset_index(drop=True)
        st.caption(f"{len(vista)} nota(s)")
        ev = st.dataframe(vista, hide_index=True, on_select="rerun", selection_mode="single-row", key="notas_tabla",
                          column_config={"Nota": st.column_config.TextColumn(width="large")})
        filas = ev.selection.rows if ev and ev.selection else []
        if filas and existe_pagina(PAGINA_FICHA):
            st.button("Abrir la ficha de esta noticia", on_click=abrir_ficha, args=(vista.iloc[filas[0]]["ID"],), key="notas_abrir",
                      icon=":material/article:")

# ============================================================================ CALIDAD
with tab_cal:
    section_label("Calidad de los datos")
    st.caption("Revisión automática de la base. Las correcciones propuestas se aplican solo si las confirmas con la clave de "
               "administración, en un lote que se puede deshacer.")
    hallazgos = calidad.detectar(base)
    resumen = pd.DataFrame({"Revisión": [h.titulo for h in hallazgos], "Casos": [h.n for h in hallazgos],
                            "Noticias": [h.n_noticias for h in hallazgos]})
    st.dataframe(resumen, hide_index=True)
    for h in hallazgos:
        icono = "✓" if h.n == 0 else "•"
        with st.expander(f"{icono} {h.titulo} — {h.n} caso(s)", expanded=False):
            st.caption(h.ayuda)
            if h.n == 0:
                st.success("Sin problemas en esta revisión.", icon=":material/check_circle:")
                continue
            if h.tipo == calidad.TIPO_CAMBIOS:
                prop = pd.DataFrame({"Aplicar": [f["sugerido"] != f["actual"] and f["sugerido"] != "" for f in h.filas],
                                     "ID": [f["id_evento"] for f in h.filas], "Noticia": [f["titulo"] for f in h.filas],
                                     "Campo": [S.etiqueta(f["campo"]) for f in h.filas], "Actual": [f["actual"][:70] for f in h.filas],
                                     "Propuesta": [f["sugerido"][:70] for f in h.filas]})
                ed = st.data_editor(prop, hide_index=True, key=f"cal_{h.clave}_{firma}", disabled=["ID", "Noticia", "Campo", "Actual", "Propuesta"],
                                    column_config={"Aplicar": st.column_config.CheckboxColumn(width="small")}, height=min(380, 60 + 35 * len(prop)))
                elegidos = {(h.filas[i]["id_evento"], h.filas[i]["campo"]) for i in ed.index[ed["Aplicar"]]}
                cambios = calidad.cambios_de(h, elegidos)

                def _corregir(cambios=cambios, titulo=h.titulo) -> str:
                    r = repo.aplicar_cambios(cambios, usuario, almacen=almacen, respaldo="antes_de_correccion_calidad")
                    return f"Corrección aplicada ({titulo}): {r.resumen()}. Se puede deshacer desde el historial (Lotes)."
                auth.accion_protegida(f"Aplicar {len(cambios)} corrección(es)", f"Se aplicarán {len(cambios)} cambio(s) en «{h.titulo}».",
                                      _corregir, key=f"cal_ok_{h.clave}", icon=":material/auto_fix_high:", type="primary",
                                      disabled=not usuario or not cambios)
            elif h.tipo == calidad.TIPO_GEOCODIFICAR:
                geo = pd.DataFrame({"Incluir": [i < MAX_GEO for i in range(h.n)], "ID": [f["id_evento"] for f in h.filas],
                                    "Noticia": [f["titulo"] for f in h.filas], "Lugares sin coordenadas": [f["actual"][:90] for f in h.filas]})
                ed = st.data_editor(geo, hide_index=True, key=f"cal_{h.clave}_{firma}", disabled=["ID", "Noticia", "Lugares sin coordenadas"],
                                    column_config={"Incluir": st.column_config.CheckboxColumn(width="small")}, height=min(380, 60 + 35 * len(geo)))
                ids_geo = ed.loc[ed["Incluir"], "ID"].tolist()
                st.caption(f"Se consulta 1 lugar por segundo (política de OpenStreetMap). Máximo {MAX_GEO} noticias por tanda. "
                           "Las coordenadas son aproximadas: revísalas en la ficha de cada noticia.")

                def _geocodificar(ids=tuple(ids_geo[:MAX_GEO])) -> str:
                    por_id = base.set_index("id_evento", drop=False)
                    cambios_g, n_ok, n_mal = [], 0, 0
                    try:
                        for ide in ids:
                            f = por_id.loc[ide]
                            r = geocoding.completar(f["lugar"], f["sitios_lat"], f["sitios_lon"], f["sitios_pais"],
                                                    f["sitios_precision_geocodificacion"])
                            n_ok, n_mal = n_ok + r.n_nuevos, n_mal + r.n_fallidos
                            cambios_g += [Cambio(ide, k, f[k], v) for k, v in r.valores.items()]
                    except geocoding.ErrorGeocodificacion as e:
                        if not cambios_g:
                            raise ErrorOperacion(str(e)) from e
                        flash("aviso", f"Se detuvo antes de terminar: {e}")
                    res = repo.aplicar_cambios(cambios_g, usuario, almacen=almacen, respaldo="antes_de_geocodificar")
                    return f"Coordenadas: {n_ok} lugar(es) encontrado(s), {n_mal} no encontrado(s). {res.resumen()}."
                auth.accion_protegida(f"Buscar coordenadas de {min(len(ids_geo), MAX_GEO)} noticia(s)",
                                      f"Se consultará OpenStreetMap por los lugares de {min(len(ids_geo), MAX_GEO)} noticia(s) (≈ 1 segundo por lugar).",
                                      _geocodificar, key="cal_geo_ok", icon=":material/pin_drop:", type="primary",
                                      disabled=not usuario or not ids_geo)
            else:
                info = pd.DataFrame({"ID": [f["id_evento"] for f in h.filas], "Noticia": [f["titulo"] for f in h.filas],
                                     "Campo": [S.etiqueta(f["campo"]) for f in h.filas], "Valor": [f["actual"][:80] for f in h.filas],
                                     h.columna_sugerida: [f["sugerido"][:80] for f in h.filas]})
                if not info[h.columna_sugerida].astype(bool).any():
                    info = info.drop(columns=h.columna_sugerida)
                st.dataframe(info, hide_index=True, height=min(380, 60 + 35 * len(info)))

# ============================================================================ DUPLICADOS
with tab_dup:
    section_label("Posibles noticias duplicadas")
    st.caption("Pares con el mismo título. Pueden ser la misma noticia publicada en los dos sitios, o eventos distintos "
               "(p. ej. dos ediciones de un taller). Tú decides; lo marcado como duplicado secundario se excluye de los conteos.")
    filas_base = base.to_dict("records")
    decididos = {frozenset((r["id_a"], r["id_b"])) for r in leer_hoja(S.HOJA_DUPLICADOS).to_dict("records")}
    pares = [p for p in dedupe.pares_sospechosos(filas_base) if frozenset(p[:2]) not in decididos]
    por_id = base.set_index("id_evento", drop=False)
    if not pares:
        st.success("No hay pares pendientes de revisar.", icon=":material/check_circle:")
    else:
        st.caption(f"{len(pares)} par(es) pendiente(s). Se muestran los primeros 10.")
    for id_a, id_b, entre in pares[:10]:
        a, b = por_id.loc[id_a], por_id.loc[id_b]
        with st.expander(f"{id_a} ↔ {id_b} · {a['titulo'][:70]}" + (" · otra fuente" if entre else ""), expanded=False):
            col_a, col_b = st.columns(2)
            for col, r in ((col_a, a), (col_b, b)):
                with col, st.container(border=True):
                    st.markdown(f"**{r['id_evento']}** · {r['fuente']}")
                    st.caption(f"{vistas.fecha_corta(r['fecha_publicacion_web'])[:10]} · {r['lugar'][:60] or 'sin lugar'}")
                    st.caption(r["url_noticia"])
                    st.markdown((r["descripcion_catalogo"] or r["contenido_completo"])[:220] + "…")
                    st.caption(f"Categoría: {r['categoria_macro'][:70] or '—'} · {r['es_duplicado_secundario']}")
            sec = st.radio("Si son la misma, ¿cuál queda como secundaria (excluida de los conteos)?", [id_b, id_a], horizontal=True, key=f"dup_sec_{id_a}_{id_b}")
            with st.container(horizontal=True):
                if st.button("Son la misma noticia", icon=":material/merge:", key=f"dup_si_{id_a}_{id_b}", disabled=not usuario):
                    repo.registrar_decision_duplicado(id_a, id_b, "duplicado", usuario, secundaria=sec, almacen=almacen)
                    flash("exito", f"{sec} quedó marcada como duplicado secundario.")
                    st.rerun()
                if st.button("Son distintas", icon=":material/call_split:", key=f"dup_no_{id_a}_{id_b}", disabled=not usuario):
                    repo.registrar_decision_duplicado(id_a, id_b, "distintas", usuario, almacen=almacen)
                    flash("exito", "Anotado: son noticias distintas. No volverá a aparecer.")
                    st.rerun()

# ============================================================================ SINCRONIZACIÓN
with tab_sync:
    section_label("Sincronización con la web")
    hist = leer_hoja(S.HOJA_HISTORIAL)
    sync = hist[hist["accion"] == S.ACC_SINCRONIZAR] if len(hist) else hist
    if sync.empty:
        st.info("Aún no se ha sincronizado con la web.", icon=":material/sync:")
    else:
        ult = sync["fecha_hora"].max()
        quien = sync.sort_values("id_cambio").iloc[-1]["usuario"]
        st.metric("Última sincronización", vistas.hace_cuanto(ult), f"{vistas.fecha_corta(ult)} · {quien}", delta_color="off", delta_arrow="off")
    origen = base["origen"].replace("", "historico").value_counts()
    st.caption("Origen de las noticias: " + " · ".join(f"{k}: {v}" for k, v in origen.items()))
    if existe_pagina("app_pages/sincronizar.py"):
        st.page_link("app_pages/sincronizar.py", label="Ir a «Sincronizar con la web»", icon=":material/sync:")

# ============================================================================ RESPALDO
with tab_resp:
    section_label("Respaldo y libro de códigos")
    st.markdown(f"Los datos viven en {almacen.descripcion}. El Excel original (`{storage.RUTA_SEMILLA.name}`) no se modifica "
                "nunca: sirve de punto de partida.")
    with st.container(horizontal=True):
        st.download_button("Descargar el libro de trabajo (.xlsx)", data=lambda: almacen.exportar_xlsx(),
                           file_name=f"catalogo_gestion_{datetime.now():%Y%m%d_%H%M}.xlsx", mime=MIME_XLSX,
                           icon=":material/download:", on_click="ignore", key="resp_descargar")
        if st.button("Regenerar el libro de códigos", icon=":material/menu_book:", key="resp_libro",
                     help="Reescribe la hoja Libro_de_Codigos desde el registro de campos, con recuentos calculados de los datos."):
            repo.regenerar_libro_codigos(almacen)
            flash("exito", "Libro de códigos regenerado.")
            st.rerun()
    respaldos = almacen.respaldos()
    st.markdown(f"**Respaldos automáticos** ({len(respaldos)}; se conservan los últimos {storage.MAX_RESPALDOS})")
    if respaldos:
        st.dataframe(pd.DataFrame({
            "Respaldo": [r.nombre for r in respaldos],
            "Fecha": [r.fecha.strftime("%d-%m-%Y %H:%M") if r.fecha else "—" for r in respaldos],
            "Tamaño (KB)": [r.kb if r.kb is not None else "—" for r in respaldos]}), hide_index=True)
    else:
        st.caption("Aún no hay respaldos: se crean solos antes de importar, sincronizar o aplicar correcciones en lote.")

    section_label("Restablecer desde el original")
    st.caption("Reemplaza el libro de trabajo por una copia nueva del Excel original. Se pierden las ediciones, el historial, "
               "las notas, las categorías y variables nuevas y la lista del equipo. Antes se guarda un respaldo del libro actual.")

    def _restablecer() -> str:
        r = almacen.restablecer_desde_semilla()
        return f"Libro restablecido desde el Excel original. El libro anterior quedó en el respaldo «{getattr(r, 'name', r) or '—'}»."
    auth.accion_protegida("Restablecer desde el original", "Se reemplazará TODO el libro de trabajo por el Excel original. "
                          "Esta acción no se puede deshacer desde el historial (sí desde el respaldo que se guarda antes).",
                          _restablecer, key="resp_restablecer", icon=":material/restart_alt:", type="primary")

# ============================================================================ EQUIPO
with tab_eq:
    section_label("Equipo: nombres de quienes editan")
    st.caption("Cada persona se anota una vez (al entrar por primera vez) y después elige su nombre de esta lista, "
               "en el inicio de sesión y en «Editando como». Así el historial usa siempre el mismo nombre.")
    equipo = repo.equipo_df(almacen)
    if equipo.empty:
        st.info("Todavía no hay nombres registrados.", icon=":material/groups:")
    else:
        tabla = equipo.assign(Registrado=equipo["Registrado"].map(lambda f: vistas.fecha_corta(f) if f else "Antes de la lista"),
                              **{"Último cambio": equipo["Último cambio"].map(lambda f: vistas.hace_cuanto(f) if f else "—")})
        st.dataframe(tabla, hide_index=True, key="eq_tabla")

    with st.form("eq_agregar", border=False, clear_on_submit=True):
        c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
        nuevo = c1.text_input("Agregar un nombre", max_chars=80, key="eq_nuevo", placeholder="Ej.: Ana Soto")
        agregar = c2.form_submit_button("Agregar", icon=":material/person_add:", width="stretch")
    if agregar:
        try:
            antes = set(repo.editores(almacen))
            nombre = repo.registrar_editor(nuevo, almacen)
        except (ErrorOperacion, ErrorAlmacen) as e:
            st.error(str(e), icon=":material/error:")
        else:
            flash("exito" if nombre not in antes else "aviso",
                  f"«{nombre}» se agregó al equipo." if nombre not in antes else f"«{nombre}» ya estaba en la lista.")
            st.rerun()

    if not equipo.empty:
        quitar = st.selectbox("Quitar un nombre de la lista", list(equipo["Nombre"]), index=None, key="eq_quitar",
                              placeholder="Elige el nombre (por ejemplo, uno mal escrito)",
                              help="Sirve para corregir errores de escritura. Los cambios que esa persona ya hizo siguen en el historial.")
        if quitar:
            auth.accion_protegida(f"Quitar «{quitar}»", f"«{quitar}» dejará de aparecer en la lista del equipo. "
                                  "Su historial no se modifica.", lambda: repo.quitar_editor(quitar, almacen),
                                  key="eq_quitar_btn", icon=":material/person_remove:")
