# -*- coding: utf-8 -*-
"""Página «Historial de cambios»: cambios filtrables, lotes (deshacer) y exportaciones (repetir)."""
import pytest

from tests.apptest_util import apuntar_a, iniciar_sesion, nueva_app
from utils import repo
from utils import schema as S
from utils.repo import Cambio

PAGINA = "app_pages/historial.py"


@pytest.fixture
def app(monkeypatch, almacen):
    apuntar_a(monkeypatch, almacen)
    at = nueva_app()
    iniciar_sesion(at, nombre="Francis")
    at.switch_page(PAGINA).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _seleccionar(at, clave, fila=0):
    """Simula la fila elegida en una tabla; en AppTest ese estado vale solo para la ejecución siguiente."""
    at.session_state[clave] = {"selection": {"rows": [fila], "columns": [], "cells": []}}


def _tablas(at, columna):
    return [t.value for t in at.dataframe if columna in getattr(t.value, "columns", [])]


def _hacer_cambios(almacen):
    f = almacen.leer_base_texto().set_index("id_evento", drop=False)
    repo.aplicar_cambios([Cambio("EV0001", "lugar", f.at["EV0001", "lugar"], "Lugar A")], "Ana", almacen=almacen)
    repo.aplicar_cambios([Cambio("EV0002", "autor", "", "Beto")], "Beto", almacen=almacen)
    return repo.agregar_filas([{"titulo": "Noticia nueva", "url_noticia": "https://glocalminds.com/catalogo/n1/", "fuente": "glocalminds.com"}],
                              "Ana", accion=S.ACC_SINCRONIZAR, origen="scraping", almacen=almacen)


# ----------------------------------------------------------------------------- vacío
def test_estados_vacios(app):
    assert len([i for i in app.info if "Todavía no hay" in i.value]) == 3                 # cambios, lotes, exportaciones


# ----------------------------------------------------------------------------- cambios
def test_lista_y_filtra_los_cambios(app, almacen):
    _hacer_cambios(almacen)
    app.run()
    t = _tablas(app, "Quién")[0]
    assert len(t) == 3 and set(t["Quién"]) == {"Ana", "Beto"} and t.iloc[0]["Acción"] == "Sincronización"       # más reciente primero
    assert any("3 de 3 cambio(s)" in c.value for c in app.caption)
    app.multiselect(key="hist_quien").set_value(["Beto"]).run()
    assert len(_tablas(app, "Quién")[0]) == 1 and any("1 de 3 cambio(s)" in c.value for c in app.caption)
    app.multiselect(key="hist_quien").set_value([]).run()
    app.text_input(key="hist_buscar").set_value("EV0001").run()
    t = _tablas(app, "Quién")[0]
    assert len(t) == 1 and t.iloc[0]["Campo"] == "Lugar"
    app.text_input(key="hist_buscar").set_value("noticia nueva").run()
    assert len(_tablas(app, "Quién")[0]) == 1
    app.text_input(key="hist_buscar").set_value("no existe nada así").run()
    assert not app.exception


def test_detalle_de_un_cambio_seleccionado(app, almacen):
    _hacer_cambios(almacen)
    app.run()
    _seleccionar(app, "hist_tabla", 1)
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    assert any("por Beto" in m.value or "por Ana" in m.value for m in app.markdown)


# ----------------------------------------------------------------------------- lotes
def test_lotes_vista_previa_y_boton_protegido(app, almacen):
    res = _hacer_cambios(almacen)
    app.run()
    lotes = _tablas(app, "Estado")[0]
    assert len(lotes) == 3 and "Vigente" in set(lotes["Estado"])
    i = lotes.index[lotes["lote_id"] == res.lote_id][0]
    _seleccionar(app, "lotes_tabla", int(i))
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    prev = _tablas(app, "Qué pasaría")[0]
    assert prev.iloc[0]["Qué pasaría"] == "Retirar noticia" and prev.iloc[0]["Conflicto"] == ""
    assert any(b.label == "Deshacer este lote" and not b.disabled for b in app.button)


def test_lote_con_conflicto_avisa(app, almacen):
    res = _hacer_cambios(almacen)
    repo.aplicar_cambios([Cambio("EV0275", "autor", "", "Otra persona")], "Beto", almacen=almacen)
    app.run()
    lotes = _tablas(app, "Estado")[0]
    _seleccionar(app, "lotes_tabla", int(lotes.index[lotes["lote_id"] == res.lote_id][0]))
    app.run()
    assert any("tienen conflicto" in w.value for w in app.warning)
    assert any(b.label == "Deshacer este lote" and b.disabled for b in app.button)         # no queda nada que se pueda deshacer


def test_lote_ya_deshecho(app, almacen):
    res = _hacer_cambios(almacen)
    repo.revertir_lote(res.lote_id, "Ana", almacen)
    app.run()
    lotes = _tablas(app, "Estado")[0]
    assert "Deshecho" in set(lotes["Estado"])
    _seleccionar(app, "lotes_tabla", int(lotes.index[lotes["lote_id"] == res.lote_id][0]))
    app.run()
    assert any("ya fue deshecho" in i.value for i in app.info)


# ----------------------------------------------------------------------------- exportaciones
def test_exportaciones_se_pueden_repetir(app, almacen):
    repo.registrar_exportacion("Ana", "Fondo X", "xlsx", "seleccion", ["EV0001", "EV0003", "EV9999"], ["titulo", "anio"], "texto=agua", almacen)
    repo.registrar_exportacion("Beto", "", "docx", "filtradas", ["EV0002"], ["*"], "", almacen)
    app.run()
    t = _tablas(app, "Noticias")[0]
    assert t["Noticias"].tolist() == [1, 3] and t["usuario"].tolist() == ["Beto", "Ana"] if "usuario" in t else True
    _seleccionar(app, "exp_tabla", 1)
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    assert any("2 existen hoy" in c.value and "2 columna(s)" in c.value for c in app.caption)
    botones = [d for d in app.get("download_button") if "Descargar de nuevo" in d.proto.label]
    assert botones and not botones[0].proto.disabled
