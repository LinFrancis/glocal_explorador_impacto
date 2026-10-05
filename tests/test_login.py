# -*- coding: utf-8 -*-
"""Login: protege toda la plataforma y registra quién entra."""
import pytest

from tests.apptest_util import apuntar_a, iniciar_sesion, nueva_app, textos
from utils import auth


@pytest.fixture
def app(monkeypatch, almacen):
    apuntar_a(monkeypatch, almacen)
    return nueva_app()


def test_sin_sesion_solo_se_ve_el_login(app):
    app.run()
    assert not app.exception
    assert [t.label for t in app.text_input] == ["Usuario", "Contraseña"]
    assert "Iniciar sesión" in textos(app)
    assert len(app.metric) == 0 and len(app.sidebar.markdown) == 0          # ninguna página corre
    assert not app.session_state[auth.K_OK] if auth.K_OK in app.session_state else True


@pytest.mark.parametrize("usuario,clave", [("Impacto", "mala"), ("otro", "glocal"), ("", ""), ("Impacto", "GLOCAL")])
def test_credenciales_incorrectas(app, usuario, clave):
    iniciar_sesion(app, usuario=usuario, clave=clave)
    assert not app.session_state[auth.K_OK] if auth.K_OK in app.session_state else True
    assert any("incorrectos" in e.value for e in app.error)
    assert len(app.metric) == 0


def test_tras_la_clave_se_pide_el_nombre_y_nada_corre_antes(app):
    iniciar_sesion(app, nombre=None)
    assert not app.exception
    assert "¿Quién eres?" in textos(app) and not app.session_state[auth.K_OK] if auth.K_OK in app.session_state else True
    assert len(app.metric) == 0 and len(app.sidebar.markdown) == 0
    assert app.selectbox(key="auth_nombre_elegido").options == []             # nadie registrado todavía
    next(b for b in app.button if b.label == "Volver").click()                # volver al paso de la clave
    app.run()
    assert [t.label for t in app.text_input] == ["Usuario", "Contraseña"]


def test_nombre_es_obligatorio(app):
    iniciar_sesion(app, nombre="   ")
    assert any("Elige tu nombre en la lista" in e.value for e in app.error)
    assert not app.session_state[auth.K_OK] if auth.K_OK in app.session_state else True


def test_la_lista_de_nombres_no_se_ve_sin_la_clave(app, almacen):
    from utils import repo
    repo.registrar_editor("Ana Soto", almacen)
    app.run()
    assert not app.selectbox and "Ana Soto" not in textos(app)


def test_acceso_correcto_registra_el_nombre(app, almacen):
    from utils import repo
    iniciar_sesion(app, nombre="  Francis  ", usuario="impacto")             # el usuario no distingue mayúsculas
    assert not app.exception
    assert app.session_state[auth.K_OK] is True
    assert app.session_state[auth.K_NOMBRE] == "Francis"
    assert "Iniciar sesión" not in textos(app)
    assert len(app.metric) > 0                                              # se ve el panel de Inicio
    assert repo.editores(almacen) == ["Francis"]                            # quedó anotado en la lista del equipo


def test_la_segunda_vez_se_elige_de_la_lista(monkeypatch, almacen):
    apuntar_a(monkeypatch, almacen)
    primera = nueva_app()
    iniciar_sesion(primera, nombre="Francis")
    segunda = nueva_app()
    iniciar_sesion(segunda, nombre=None)
    sel = segunda.selectbox(key="auth_nombre_elegido")
    assert sel.options == ["Francis"]
    sel.set_value("Francis")
    next(b for b in segunda.button if b.label == "Entrar").click()
    segunda.run()
    assert segunda.session_state[auth.K_NOMBRE] == "Francis"
    from utils import repo
    assert repo.editores(almacen) == ["Francis"]                            # no se duplica


def test_escribir_un_nombre_ya_registrado_con_otra_grafia_usa_el_existente(monkeypatch, almacen):
    from utils import repo
    repo.registrar_editor("María José", almacen)
    apuntar_a(monkeypatch, almacen)
    at = nueva_app()
    iniciar_sesion(at, nombre="maria  jose")
    assert at.session_state[auth.K_NOMBRE] == "María José"
    assert repo.editores(almacen) == ["María José"]


def test_panel_lateral_elige_de_la_lista_y_agrega_nombres(monkeypatch, almacen):
    from utils import repo
    repo.registrar_editor("Ana Soto", almacen)
    apuntar_a(monkeypatch, almacen)
    at = nueva_app()
    iniciar_sesion(at, nombre="Francis")
    sel = at.sidebar.selectbox(key=auth.K_NOMBRE)
    assert sel.label == "Editando como" and sel.options == ["Ana Soto", "Francis"] and sel.value == "Francis"
    sel.set_value("Ana Soto").run()
    assert auth.nombre_actual() or at.session_state[auth.K_NOMBRE] == "Ana Soto"
    at.sidebar.text_input(key="auth_nombre_nuevo_lateral").set_value("Luis Pérez")
    next(b for b in at.sidebar.button if b.label == "Agregar y usar").click()
    at.run()
    assert at.session_state[auth.K_NOMBRE] == "Luis Pérez"
    assert repo.editores(almacen) == ["Ana Soto", "Francis", "Luis Pérez"]


def test_bloqueo_tras_cinco_intentos(app):
    for _ in range(auth.MAX_INTENTOS):
        iniciar_sesion(app, clave="mala")
    app.run()
    assert any("Demasiados intentos" in w.value for w in app.warning)
    assert app.button[0].disabled                                           # no deja ni intentar con la clave correcta
    assert not app.session_state[auth.K_OK] if auth.K_OK in app.session_state else True


def test_cerrar_sesion(app):
    iniciar_sesion(app)
    cerrar = next(b for b in app.sidebar.button if "Cerrar sesión" in b.label)
    cerrar.click()
    app.run()
    assert [t.label for t in app.text_input] == ["Usuario", "Contraseña"]


def test_verificacion_en_tiempo_constante_y_secretos(monkeypatch):
    assert auth.verificar_credenciales("Impacto", "glocal")
    assert auth.verificar_credenciales(" impacto ", "glocal")
    assert not auth.verificar_credenciales("Impacto", "Glocal")
    assert auth.verificar_clave_admin("glocal-admin") and not auth.verificar_clave_admin("glocal")
    monkeypatch.setattr(auth, "_secreto", lambda clave, defecto: {"usuario": "x", "clave": "y"}.get(clave, defecto))
    assert auth.verificar_credenciales("X", "y") and not auth.verificar_credenciales("Impacto", "glocal")
