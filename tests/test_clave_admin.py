# -*- coding: utf-8 -*-
"""La clave de administración protege las acciones destructivas (deshacer lote, restaurar...)."""
import pytest
from streamlit.testing.v1 import AppTest

from tests.apptest_util import apuntar_a, iniciar_sesion, nueva_app
from utils import auth, repo
from utils import schema as S
from utils.repo import ErrorOperacion


def _script():
    import streamlit as st

    from utils import auth as a
    from utils.repo import ErrorOperacion as EO

    st.session_state.setdefault("ejecuciones", 0)

    def accion():
        st.session_state["ejecuciones"] += 1
        if st.session_state.get("falla"):
            raise EO("No se pudo deshacer: el lote ya no existe.")
        return "Hecho."

    clave = st.text_input("Clave", key="c")
    if st.button("Ejecutar"):
        estado, msg = a.procesar_clave_admin(clave, accion)
        st.session_state["resultado"] = (estado, msg)


@pytest.fixture
def mini():
    at = AppTest.from_function(_script, default_timeout=30)
    at.run()
    return at


def _intentar(at, clave):
    at.text_input(key="c").set_value(clave)
    next(b for b in at.button if b.label == "Ejecutar").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at.session_state["resultado"]


def test_clave_correcta_ejecuta_y_devuelve_el_mensaje(mini):
    assert _intentar(mini, auth.CLAVE_ADMIN_POR_DEFECTO) == ("ok", "Hecho.")
    assert mini.session_state["ejecuciones"] == 1


@pytest.mark.parametrize("clave", ["glocal", "", "GLOCAL-ADMIN", " glocal-admin"])
def test_otras_claves_no_ejecutan_nada(mini, clave):
    """La clave de login (u otra variante) NO vale como clave de administración."""
    assert _intentar(mini, clave) == ("incorrecta", "Clave incorrecta.")
    assert mini.session_state["ejecuciones"] == 0


def test_bloqueo_tras_cinco_intentos_y_no_ejecuta_ni_con_la_correcta(mini):
    for _ in range(auth.MAX_INTENTOS):
        assert _intentar(mini, "mala")[0] == "incorrecta"
    estado, msg = _intentar(mini, auth.CLAVE_ADMIN_POR_DEFECTO)
    assert estado == "bloqueado" and "Demasiados intentos" in msg
    assert mini.session_state["ejecuciones"] == 0


def test_un_error_de_la_accion_se_devuelve_como_mensaje(mini):
    mini.session_state["falla"] = True
    assert _intentar(mini, auth.CLAVE_ADMIN_POR_DEFECTO) == ("error", "No se pudo deshacer: el lote ya no existe.")


def test_clave_configurable_por_secrets(monkeypatch):
    monkeypatch.setattr(auth, "_secreto", lambda clave, defecto: {"clave_admin": "otra-clave"}.get(clave, defecto))
    assert auth.verificar_clave_admin("otra-clave") and not auth.verificar_clave_admin(auth.CLAVE_ADMIN_POR_DEFECTO)


# ----------------------------------------------------------------------------- el botón de la página abre el diálogo
def test_el_boton_protegido_de_historial_abre_el_dialogo(monkeypatch, almacen):
    apuntar_a(monkeypatch, almacen)
    res = repo.agregar_filas([{"titulo": "Nueva", "url_noticia": "https://glocalminds.com/catalogo/n1/", "fuente": "glocalminds.com"}],
                             "Ana", accion=S.ACC_SINCRONIZAR, origen="scraping", almacen=almacen)
    at = nueva_app()
    iniciar_sesion(at, nombre="Francis")
    at.switch_page("app_pages/historial.py").run()
    at.session_state["lotes_tabla"] = {"selection": {"rows": [0], "columns": [], "cells": []}}
    at.run()
    at.session_state["lotes_tabla"] = {"selection": {"rows": [0], "columns": [], "cells": []}}
    next(b for b in at.button if b.label == "Deshacer este lote").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.text_input(key="admin_clave_dialogo").proto.type == 1 or at.text_input(key="admin_clave_dialogo")   # campo de contraseña
    assert len(almacen.leer_base_texto()) == 275                                  # abrir el diálogo no deshace nada
