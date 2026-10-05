# -*- coding: utf-8 -*-
"""Página «Ficha de noticia»: selección, edición, clasificación asistida, bitácora, mapas y web."""
import pytest

from tests.apptest_util import apuntar_a, iniciar_sesion, nueva_app
from utils import geocoding, repo, scraper
from utils import schema as S
from utils.ui import K_FICHA

PAGINA = "app_pages/ficha.py"


@pytest.fixture
def app(monkeypatch, almacen):
    apuntar_a(monkeypatch, almacen)
    at = nueva_app()
    iniciar_sesion(at, nombre="Francis")
    at.switch_page(PAGINA).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _guardar(at, indice=0):
    [b for b in at.button if b.label == "Guardar cambios"][indice].click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]


def _fila(almacen, ide):
    return almacen.leer_base_texto().set_index("id_evento", drop=False).loc[ide]


def _abrir(at, ide):
    at.session_state[K_FICHA] = ide
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.selectbox(key="ficha_sel").value == ide


# ----------------------------------------------------------------------------- selección y cabecera
def test_muestra_la_primera_noticia_y_su_completitud(app):
    assert app.selectbox(key="ficha_sel").value == "EV0001"
    assert any(m.value.startswith("### ") for m in app.markdown)
    assert any("campos clave" in m.value for m in app.markdown)
    assert [t.label for t in app.tabs] == [":material/description: Datos", ":material/category: Clasificación",
                                           ":material/sticky_note_2: Bitácora", ":material/history: Historial",
                                           ":material/visibility: Vista de lectura"] or len(app.tabs) == 5
    assert any("Registro histórico" in c.value for c in app.caption)


def test_abrir_desde_otra_pagina_con_la_noticia_pedida(app):
    _abrir(app, "EV0042")
    assert K_FICHA not in app.session_state                           # el pedido se consume una vez
    app.selectbox(key="ficha_sel").select("EV0100").run()             # y después se puede cambiar a mano
    assert app.selectbox(key="ficha_sel").value == "EV0100"


def test_pedido_invalido_no_rompe(app):
    app.session_state[K_FICHA] = "EV9999"
    app.run()
    assert not app.exception and app.selectbox(key="ficha_sel").value == "EV0001"          # cae a la primera


# ----------------------------------------------------------------------------- edición
def test_editar_datos_registra_historial_y_muestra_quien_edito(app, almacen):
    antes = _fila(almacen, "EV0001")["lugar"]
    app.text_input(key="ficha_EV0001_0_lugar").set_value("Lugar editado desde la ficha")
    app.text_input(key="ficha_EV0001_0_fecha_publicacion_web").set_value("11 de julio de 2026")
    _guardar(app, 0)
    f = _fila(almacen, "EV0001")
    assert f["lugar"] == "Lugar editado desde la ficha" and f["fecha_publicacion_web"] == "2026-07-11"
    assert f["editado_por"] == "Francis"
    h = repo.historial_df(almacen, "EV0001")
    assert set(h["campo"]) == {"lugar", "fecha_publicacion_web"} and h["usuario"].eq("Francis").all()
    assert h[h["campo"] == "lugar"].iloc[0]["valor_antes"] == antes
    assert any("Se guardaron 2 cambio(s)" in s.value for s in app.success)
    assert any("Editado por Francis" in m.value for m in app.markdown)       # cabecera
    assert app.session_state["ficha_ver"] == 1


def test_sin_cambios_no_registra_nada(app, almacen):
    _guardar(app, 0)
    assert repo.historial_df(almacen).empty and any("No hay cambios" in i.value for i in app.info)


def test_formato_distinto_pero_mismo_valor_no_cuenta_como_cambio(app, almacen):
    """'a;b' guardado sin espacio y el widget devolviendo 'a; b' no debe registrar un cambio fantasma."""
    repo.aplicar_cambios([repo.Cambio("EV0002", "categorias", _fila(almacen, "EV0002")["categorias"], "Uno;Dos")],
                         "Ana", almacen=almacen)
    n = len(repo.historial_df(almacen))
    _abrir(app, "EV0002")
    _guardar(app, 1)
    assert len(repo.historial_df(almacen)) == n


def test_obligatorio_vacio_no_se_guarda_y_avisa(app, almacen):
    app.text_input(key="ficha_EV0001_0_titulo").set_value("")
    _guardar(app, 0)
    assert _fila(almacen, "EV0001")["titulo"] != "" and any("obligatorio" in e.value for e in app.error)


def test_aviso_de_validacion_no_bloquea(app, almacen):
    app.text_input(key="ficha_EV0001_0_url_noticia").set_value("esto no es una url")
    _guardar(app, 0)
    assert _fila(almacen, "EV0001")["url_noticia"] == "esto no es una url"
    assert any("URL" in w.value for w in app.warning)


def test_sin_nombre_no_deja_guardar(monkeypatch, almacen):
    apuntar_a(monkeypatch, almacen)
    at = nueva_app()
    iniciar_sesion(at)
    at.session_state["auth_nombre"] = None
    at.switch_page(PAGINA).run()
    assert all(b.disabled for b in at.button if b.label == "Guardar cambios")


# ----------------------------------------------------------------------------- clasificación asistida
def test_copiar_clasificacion_de_una_parecida(app, almacen):
    modelo = almacen.leer_base_texto().iloc[10]
    nueva = repo.agregar_filas([{
        "titulo": modelo["titulo"] + " (edición nueva)", "url_noticia": "https://glocalminds.com/catalogo/edicion-nueva/",
        "fuente": "glocalminds.com", "contenido_completo": modelo["contenido_completo"]}], "Ana", almacen=almacen).ids_creados[0]
    _abrir(app, nueva)
    copiar = [b for b in app.button if b.label == "Copiar clasificación" and not b.disabled]
    assert copiar, "debe sugerir noticias parecidas ya analizadas"
    copiar[0].click()
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    assert any("Se copió la clasificación" in i.value for i in app.info)
    elegidas = app.multiselect(key=f"ficha_{nueva}_0_categoria_macro").value
    assert elegidas and set(elegidas) <= set(S.dividir_etiquetas(modelo["categoria_macro"]) + elegidas)
    assert _fila(almacen, nueva)["categoria_macro"] == ""                       # copiar NO guarda
    _guardar(app, 1)
    f = _fila(almacen, nueva)
    assert f["categoria_macro"] != "" and f["editado_por"] == "Francis"
    assert set(repo.historial_df(almacen, nueva)["campo"]) >= {"categoria_macro"}


# ----------------------------------------------------------------------------- bitácora
def test_bitacora_agrega_y_lista_notas(app, almacen):
    area = next(t for t in app.text_area if t.label == "Nueva nota")
    area.set_value("Revisar el lugar con quien facilitó")
    next(b for b in app.button if b.label == "Agregar nota").click()
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    notas = repo.notas_df(almacen, "EV0001")
    assert notas["texto"].tolist() == ["Revisar el lugar con quien facilitó"] and notas["usuario"].tolist() == ["Francis"]
    assert any("Revisar el lugar" in m.value for m in app.markdown)
    assert any("Francis" in c.value and "hace" in c.value for c in app.caption)


def test_nota_vacia_da_error(app):
    next(b for b in app.button if b.label == "Agregar nota").click()
    app.run()
    assert any("vacía" in e.value for e in app.error)


# ----------------------------------------------------------------------------- historial
def test_historial_muestra_el_cambio_y_el_plan_de_restauracion(app, almacen, monkeypatch):
    f0 = _fila(almacen, "EV0001")
    monkeypatch.setattr(repo, "ahora", lambda: "2026-10-01T10:00:00")
    repo.aplicar_cambios([repo.Cambio("EV0001", "lugar", f0["lugar"], "Lugar nuevo")], "Ana", almacen=almacen)
    _abrir(app, "EV0001")
    tablas = [t.value for t in app.dataframe if "Quién" in getattr(t.value, "columns", [])]
    assert tablas and tablas[0].iloc[0]["Quién"] == "Ana" and tablas[0].iloc[0]["Campo"] == "Lugar"
    app.date_input(key="ficha_rest_f_EV0001").set_value(__import__("datetime").date(2026, 9, 30)).run()
    assert not app.exception
    planes = [t.value for t in app.dataframe if "Quedaría" in getattr(t.value, "columns", [])]
    assert planes and planes[0].iloc[0]["Campo"] == "Lugar" and planes[0].iloc[0]["Quedaría"] == f0["lugar"][:80]
    assert any(b.label == "Restaurar a esa fecha" for b in app.button)


# ----------------------------------------------------------------------------- coordenadas
def test_geocodificar_y_guardar_coordenadas(app, almacen, monkeypatch):
    ide = next(i for i, r in almacen.leer_base_texto().set_index("id_evento").iterrows() if r["lugar"] and not r["sitios_lat"]
               and "online" not in r["lugar"].lower() and "especificado" not in r["lugar"].lower())
    _abrir(app, ide)
    lugar = _fila(almacen, ide)["lugar"]
    n = len([p for p in lugar.split(";") if p.strip()])

    def falso(lugar, lat="", lon="", pais="", prec="", sesion=None, solo_faltantes=True, progreso=None):
        return geocoding.Resultado(
            valores={"sitios_lat": ";".join(["-33.1"] * n), "sitios_lon": ";".join(["-70.2"] * n),
                     "sitios_pais": ";".join(["Chile"] * n), "sitios_precision_geocodificacion": ";".join(["completo"] * n)},
            sitios=[], n_nuevos=n, n_fallidos=0)
    monkeypatch.setattr(geocoding, "completar", falso)
    next(b for b in app.button if b.label == "Buscar las coordenadas que faltan").click()
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    assert _fila(almacen, ide)["sitios_lat"] == ""                              # solo es una propuesta
    next(b for b in app.button if b.label == "Guardar coordenadas").click()
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    f = _fila(almacen, ide)
    assert f["sitios_lat"] == ";".join(["-33.1"] * n) and f["sitios_precision_geocodificacion"].startswith("completo")
    assert set(repo.historial_df(almacen, ide)["campo"]) == {"sitios_lat", "sitios_lon", "sitios_pais", "sitios_precision_geocodificacion"}


def test_error_del_servicio_de_mapas_se_informa(app, almacen, monkeypatch):
    ide = next(i for i, r in almacen.leer_base_texto().set_index("id_evento").iterrows() if r["lugar"] and not r["sitios_lat"]
               and "online" not in r["lugar"].lower() and "especificado" not in r["lugar"].lower())
    _abrir(app, ide)

    def falla(*a, **k):
        raise geocoding.ErrorGeocodificacion("No hay conexión con el servicio de mapas (OpenStreetMap).")
    monkeypatch.setattr(geocoding, "completar", falla)
    next(b for b in app.button if b.label == "Buscar las coordenadas que faltan").click()
    app.run()
    assert any("No hay conexión con el servicio de mapas" in e.value for e in app.error)


# ----------------------------------------------------------------------------- actualizar desde la web
def test_actualizar_desde_la_web(app, almacen, monkeypatch):
    repo.aplicar_cambios([repo.Cambio("EV0001", "wp_id", "", "777")], "sistema", almacen=almacen, forzar_no_editables=True)
    f = _fila(almacen, "EV0001")
    web = {"titulo": f["titulo"], "descripcion_catalogo": "Resumen actualizado desde la web",
           "contenido_completo": f["contenido_completo"], "fecha_modificacion_web": "2099-01-01T00:00:00"}
    monkeypatch.setattr(scraper, "descargar_uno", lambda clave, wp_id, sesion=None: (web, ""))
    _abrir(app, "EV0001")
    next(b for b in app.button if b.label == "Actualizar desde la web").click()
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    next(b for b in app.button if b.label == "Aplicar lo elegido").click()
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    g = _fila(almacen, "EV0001")
    assert g["descripcion_catalogo"] == "Resumen actualizado desde la web"
    assert g["fecha_modificacion_web"] != f["fecha_modificacion_web"]
    assert repo.historial_df(almacen, "EV0001").iloc[0]["accion"] == "sincronizar"


def test_actualizar_desde_la_web_sin_diferencias(app, almacen, monkeypatch):
    repo.aplicar_cambios([repo.Cambio("EV0001", "wp_id", "", "777")], "sistema", almacen=almacen, forzar_no_editables=True)
    f = _fila(almacen, "EV0001")
    monkeypatch.setattr(scraper, "descargar_uno", lambda c, w, sesion=None: (
        {k: f[k] for k in ("titulo", "descripcion_catalogo", "contenido_completo", "imagen_principal_url")}, ""))
    _abrir(app, "EV0001")
    next(b for b in app.button if b.label == "Actualizar desde la web").click()
    app.run()
    assert any("coincide con la web" in s.value for s in app.success)


def test_error_al_actualizar_desde_la_web(app, almacen, monkeypatch):
    repo.aplicar_cambios([repo.Cambio("EV0001", "wp_id", "", "777")], "sistema", almacen=almacen, forzar_no_editables=True)
    monkeypatch.setattr(scraper, "descargar_uno", lambda c, w, sesion=None: (None, "No hay conexión con glocalminds.com."))
    _abrir(app, "EV0001")
    next(b for b in app.button if b.label == "Actualizar desde la web").click()
    app.run()
    assert any("No hay conexión" in e.value for e in app.error)


# ----------------------------------------------------------------------------- vista de lectura y selección
def test_vista_de_lectura_y_marcar_para_exportar(app):
    assert any(m.value.startswith("### ") for m in app.markdown)
    app.toggle(key="ficha_sel_exp_EV0001_0").set_value(True).run()
    assert "EV0001" in app.session_state["sel_ids"]
