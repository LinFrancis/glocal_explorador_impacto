# -*- coding: utf-8 -*-
"""Smoke de cada página: con sesión iniciada debe renderizar sin excepciones sobre el libro temporal."""
from pathlib import Path

import pytest

from tests.apptest_util import RAIZ, apuntar_a, iniciar_sesion, nueva_app

PAGINAS_EXISTENTES = [
    p for p in (
        "app_pages/explorador.py", "app_pages/marco_teorico.py", "app_pages/glosario.py",
        "app_pages/ficha.py", "app_pages/tabla.py", "app_pages/carga.py", "app_pages/sincronizar.py",
        "app_pages/historial.py", "app_pages/administracion.py",
    ) if (Path(RAIZ) / p).exists()
]


@pytest.fixture
def app(monkeypatch, almacen):
    apuntar_a(monkeypatch, almacen)
    at = nueva_app()
    iniciar_sesion(at)
    assert not at.exception
    return at


def test_la_carpeta_pages_antigua_ya_no_existe():
    assert not (Path(RAIZ) / "pages").exists()


@pytest.mark.parametrize("pagina", PAGINAS_EXISTENTES)
def test_pagina_renderiza_sin_excepciones(app, pagina):
    app.switch_page(pagina).run()
    assert not app.exception, [e.value for e in app.exception]


@pytest.mark.parametrize("pagina", PAGINAS_EXISTENTES)
def test_pagina_exige_sesion(monkeypatch, almacen, pagina):
    """Sin sesión no se ejecuta ninguna página: se ve solo el login."""
    apuntar_a(monkeypatch, almacen)
    at = nueva_app()
    at.switch_page(pagina).run()
    assert [t.label for t in at.text_input] == ["Usuario", "Contraseña"]
    assert len(at.metric) == 0
