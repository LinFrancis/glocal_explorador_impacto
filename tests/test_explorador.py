# -*- coding: utf-8 -*-
"""Explorador: filtros que persisten y se limpian, filtro de completitud, selección y panel de exportación."""
import pytest

from tests.apptest_util import apuntar_a, iniciar_sesion, nueva_app
from utils import seleccion
from utils.filters import CRITERIOS_KEY

PAGINA = "app_pages/explorador.py"
OTRA = "app_pages/glosario.py"


@pytest.fixture
def app(monkeypatch, almacen):
    apuntar_a(monkeypatch, almacen)
    at = nueva_app()
    iniciar_sesion(at, nombre="Francis")
    at.switch_page(PAGINA).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _encontradas(at):
    return next(m.value for m in at.metric if m.label == "Experiencias encontradas")


def _boton(at, etiqueta):
    return next(b for b in at.button if b.label == etiqueta)


def test_sin_filtros_se_ven_todas(app):
    assert _encontradas(app) == "274 de 274"


def test_filtro_de_completitud(app):
    app.multiselect(key="f_completitud").set_value(["Parcial"]).run()
    assert not app.exception
    assert _encontradas(app) == "3 de 274"                      # las 3 noticias con 79 % (ver dashboard)
    assert app.session_state[CRITERIOS_KEY]["completitud"] == ["Parcial"]
    app.multiselect(key="f_completitud").set_value(["Completa", "Parcial"]).run()
    assert _encontradas(app) == "274 de 274"


def test_limpiar_filtros_realmente_limpia(app):
    app.multiselect(key="f_fuente").set_value(["fundacionglocal.org"]).run()
    app.text_input(key="f_texto").set_value("agua").run()
    assert _encontradas(app).endswith("de 274") and not _encontradas(app).startswith("274")
    _boton(app, "Limpiar filtros").click().run()
    assert not app.exception
    assert _encontradas(app) == "274 de 274"
    assert app.text_input(key="f_texto").value == "" and app.multiselect(key="f_fuente").value == []


def test_los_filtros_persisten_al_volver_al_explorador(app):
    app.multiselect(key="f_fuente").set_value(["fundacionglocal.org"]).run()
    assert _encontradas(app) == "16 de 274"
    app.switch_page(OTRA).run()                               # se va a otra página: los widgets desaparecen
    app.switch_page(PAGINA).run()
    assert not app.exception
    assert _encontradas(app) == "16 de 274"                  # y al volver se restauran desde los criterios
    assert app.multiselect(key="f_fuente").value == ["fundacionglocal.org"]


def test_quitar_filtros_desde_inicio(monkeypatch, almacen):
    """El botón de Inicio borra criterios y estado de los widgets; al volver al Explorador no queda nada."""
    apuntar_a(monkeypatch, almacen)
    at = nueva_app()
    iniciar_sesion(at)
    at.switch_page(PAGINA).run()
    at.multiselect(key="f_fuente").set_value(["fundacionglocal.org"]).run()
    assert at.session_state[CRITERIOS_KEY]["fuente"] == ["fundacionglocal.org"]
    at.switch_page(OTRA).run()
    # Inicio es una página-función (no se puede abrir con switch_page): nueva sesión con los mismos criterios
    inicio = nueva_app()
    inicio.session_state["auth_ok"], inicio.session_state["auth_nombre"] = True, "Francis"
    inicio.session_state[CRITERIOS_KEY] = dict(at.session_state[CRITERIOS_KEY])
    inicio.session_state["f_fuente"] = ["fundacionglocal.org"]
    inicio.run()
    assert not inicio.exception, [e.value for e in inicio.exception]
    _boton(inicio, "Quitar todos los filtros").click().run()
    assert CRITERIOS_KEY not in inicio.session_state and "f_fuente" not in inicio.session_state
    inicio.switch_page(PAGINA).run()
    assert _encontradas(inicio) == "274 de 274" and inicio.multiselect(key="f_fuente").value == []


# ----------------------------------------------------------------------------- selección
def test_seleccion_masiva_y_contador_en_el_sidebar(app):
    _boton(app, "Seleccionar esta página").click().run()
    assert not app.exception
    assert len(app.session_state[seleccion.K_SEL]) == 20
    assert any("20" in c.value and "seleccionada" in c.value for c in app.sidebar.caption)
    _boton(app, "Seleccionar las 274 filtradas").click().run()
    assert len(app.session_state[seleccion.K_SEL]) == 274
    _boton(app, "Quitar las filtradas").click().run()
    assert len(app.session_state[seleccion.K_SEL]) == 0
    assert any("Sin noticias seleccionadas" in c.value for c in app.sidebar.caption)


def test_casilla_individual_y_persistencia_entre_paginas(app):
    primera = next(c for c in app.checkbox if c.key and c.key.startswith("sel_"))
    ide = primera.key.split("_")[1]
    primera.check().run()
    assert app.session_state[seleccion.K_SEL] == {ide}
    app.switch_page(OTRA).run()
    assert any("1" in c.value and "seleccionada" in c.value for c in app.sidebar.caption)    # el contador sigue en el sidebar
    app.switch_page(PAGINA).run()
    assert app.session_state[seleccion.K_SEL] == {ide}
    assert app.checkbox(key=primera.key).value is True                                          # la casilla vuelve marcada


def test_la_seleccion_respeta_los_filtros_al_agregar_todas(app):
    app.multiselect(key="f_fuente").set_value(["fundacionglocal.org"]).run()
    _boton(app, "Seleccionar las 16 filtradas").click().run()
    assert len(app.session_state[seleccion.K_SEL]) == 16 and all(i.startswith("EV") for i in app.session_state[seleccion.K_SEL])


# ----------------------------------------------------------------------------- panel de exportación
def test_panel_exportar_por_defecto_usa_las_filtradas_o_la_seleccion(app):
    assert any("Se exportarán 274 noticia(s)." in c.value for c in app.caption)
    _boton(app, "Seleccionar esta página").click().run()
    # al haber selección, el modo por defecto pasa a «Mi selección» solo si el widget aún no tenía estado:
    app.segmented_control(key="exp_historias").set_value("seleccion").run()
    assert any("Se exportarán 20 noticia(s)." in c.value for c in app.caption)
    app.segmented_control(key="exp_historias").set_value("base").run()
    assert any("Se exportarán 274 noticia(s)." in c.value for c in app.caption)


def test_exportar_solo_columnas_elegidas(app):
    app.radio(key="exp_info").set_value("Solo las columnas que elijo").run()
    assert not app.exception
    assert any("columna(s) elegida(s)" in c.value for c in app.caption)
    _boton(app, "Mínimo").click().run()
    assert any("5 columna(s) elegida(s)." in c.value for c in app.caption)
    _boton(app, "Ninguna").click().run()
    assert any("0 columna(s) elegida(s)." in c.value for c in app.caption)
    descargas = [e for e in app.get("download_button")]
    assert descargas and all(d.proto.disabled for d in descargas)              # sin columnas no se puede exportar
    _boton(app, "Todas").click().run()
    assert any("columna(s) elegida(s)." in c.value and not c.value.startswith("0 ") for c in app.caption)


def test_exportar_sin_seleccion_en_modo_seleccion_avisa(app):
    app.segmented_control(key="exp_historias").set_value("seleccion").run()
    assert any("Aún no seleccionaste noticias" in i.value for i in app.info)
    assert all(d.proto.disabled for d in app.get("download_button"))
