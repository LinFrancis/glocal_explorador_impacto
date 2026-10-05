# -*- coding: utf-8 -*-
"""Tabla editable: preparación, conversión de ediciones a cambios y página."""
import pandas as pd
import pytest

from tests.apptest_util import apuntar_a, iniciar_sesion, nueva_app
from utils import edicion, repo
from utils import schema as S

PAGINA = "app_pages/tabla.py"


@pytest.fixture
def base(almacen):
    return almacen.leer_base_texto()


@pytest.fixture
def opciones(almacen, monkeypatch):
    apuntar_a(monkeypatch, almacen)
    from utils.data import opciones_de_campos
    return opciones_de_campos()


# ----------------------------------------------------------------------------- lógica pura
def test_preparar_df(base, opciones):
    df = edicion.preparar_df(base, opciones)
    assert df.index.name == "ID" and df.index[0] == "EV0001" and len(df) == 274
    assert df["es_duplicado_secundario"].dtype == bool and not df["es_duplicado_secundario"].any()
    assert df[edicion.COL_COMPLETITUD].between(0, 100).all()
    assert df["tipo_informacion"].isna().sum() == 0 and "Evidencia de acción realizada" in set(df["tipo_informacion"])
    vacio = base.copy()
    vacio.loc[0, "tipo_informacion"] = ""
    assert edicion.preparar_df(vacio, opciones).iloc[0]["tipo_informacion"] is None      # vacío -> lista desplegable sin valor


def test_column_config_cubre_todos_los_campos(opciones):
    cfg = edicion.column_config(opciones)
    assert set(S.COLUMNAS) | {edicion.COL_COMPLETITUD} == set(cfg)
    assert "id_evento" in edicion.columnas_bloqueadas() and "titulo" not in edicion.columnas_bloqueadas()
    assert {"wp_id", "slug", "editado_por", edicion.COL_COMPLETITUD} <= set(edicion.columnas_bloqueadas())


def test_texto_de_celda():
    t = edicion.texto_de_celda
    assert (t(None), t(float("nan")), t(True), t(False), t(4.0), t(" hola "), t(3)) == ("", "", "True", "False", "4", "hola", "3")


def test_cambios_desde_edicion_ignora_lo_que_no_cambio(base):
    editadas = {
        "0": {"titulo": base.iloc[0]["titulo"], "es_duplicado_secundario": False},      # igual que el original
        "1": {"lugar": "Nuevo lugar", "autor": None},                                  # autor ya estaba vacío
        2: {"es_duplicado_secundario": True, edicion.COL_COMPLETITUD: 5, "columna_fantasma": "x"},
        9999: {"titulo": "fila inexistente"},
    }
    cambios = edicion.cambios_desde_edicion(base, editadas)
    assert [(c.id_evento, c.campo, c.despues) for c in cambios] == [
        ("EV0002", "lugar", "Nuevo lugar"), ("EV0003", "es_duplicado_secundario", "True")]
    assert cambios[0].antes == base.iloc[1]["lugar"] and cambios[1].antes == "False"


def test_los_cambios_se_aplican_con_historial(base, almacen):
    cambios = edicion.cambios_desde_edicion(base, {0: {"lugar": "Lugar editado en la grilla"}, 5: {"autor": "Ana"}})
    res = repo.aplicar_cambios(cambios, "Francis", almacen=almacen)
    assert res.ok and len(res.aplicados) == 2
    assert repo.historial_df(almacen)["usuario"].eq("Francis").all()


# ----------------------------------------------------------------------------- página
@pytest.fixture
def app(monkeypatch, almacen):
    apuntar_a(monkeypatch, almacen)
    at = nueva_app()
    iniciar_sesion(at, nombre="Francis")
    at.switch_page(PAGINA).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_pagina_renderiza_y_muestra_estado(app):
    assert any("Sin cambios pendientes" in c.value for c in app.caption)
    assert any("274 noticias" in c.value and "archivo local" in c.value for c in app.caption)
    assert any(b.label == "Abrir en Google Sheets" and b.disabled for b in app.button)


@pytest.mark.parametrize("vista", list(S.VISTAS))
def test_cada_vista_renderiza(app, vista):
    app.segmented_control(key="tabla_vista").set_value(vista).run()
    assert not app.exception, [e.value for e in app.exception]


EDICIONES = {0: {"lugar": "Lugar desde la grilla"}, 1: {"titulo": ""}}


def _editar(at, version, ediciones=EDICIONES):
    """Simula lo que la grilla guarda al editar. En AppTest ese estado vale solo para la ejecución siguiente."""
    at.session_state[f"tabla_editor_{version}"] = {"edited_rows": ediciones, "added_rows": [], "deleted_rows": []}


def test_guardar_y_descartar_cambios_pendientes(app, almacen):
    _editar(app, 0)
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    assert any("Cambios pendientes: 2 celda(s) en 2 noticia(s)" in m.value for m in app.markdown)

    _editar(app, 0)                                                   # descartar: no escribe nada y limpia la grilla
    next(b for b in app.button if b.label == "Descartar cambios").click()
    app.run()
    assert app.session_state["tabla_version"] == 1
    assert any("Sin cambios pendientes" in c.value for c in app.caption) and repo.historial_df(almacen).empty

    _editar(app, 1)
    app.run()
    _editar(app, 1)
    next(b for b in app.button if b.label == "Guardar 2 cambio(s)").click()
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    fila = almacen.leer_base_texto().set_index("id_evento", drop=False)
    assert fila.at["EV0001", "lugar"] == "Lugar desde la grilla" and fila.at["EV0001", "editado_por"] == "Francis"
    assert fila.at["EV0002", "titulo"] != ""                          # el título obligatorio no se pudo vaciar
    assert any("Se guardaron 1 cambio(s)" in s.value for s in app.success)
    assert any("es obligatorio" in e.value for e in app.error)
    assert len(repo.historial_df(almacen)) == 1 and app.session_state["tabla_version"] == 2


def test_sin_nombre_no_deja_guardar(monkeypatch, almacen):
    apuntar_a(monkeypatch, almacen)
    at = nueva_app()
    iniciar_sesion(at)
    at.session_state["auth_nombre"] = None
    at.switch_page(PAGINA).run()
    at.session_state["tabla_editor_0"] = {"edited_rows": {0: {"lugar": "X"}}, "added_rows": [], "deleted_rows": []}
    at.run()
    assert next(b for b in at.button if b.label.startswith("Guardar")).disabled
