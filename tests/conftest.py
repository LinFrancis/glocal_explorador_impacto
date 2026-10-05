# -*- coding: utf-8 -*-
"""Fixtures comunes: un libro de trabajo temporal creado desde el Excel original real."""
import hashlib
import os
import shutil
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
os.environ["IMPACTO_ALMACEN"] = "local"            # las pruebas nunca tocan una hoja de Google real, aunque haya secretos
os.environ["GLOCAL_RECARGA_CODIGO"] = "0"      # AppTest ejecuta Inicio.py muchas veces en un mismo proceso
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from utils.storage import RUTA_SEMILLA, LocalStorage  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "vivo: usa la red real (solo lectura); se excluye por defecto")


def pytest_collection_modifyitems(config, items):
    if config.getoption("-m"):
        return
    saltar = pytest.mark.skip(reason="prueba 'vivo': ejecútala con  pytest -m vivo")
    for item in items:
        if "vivo" in item.keywords:
            item.add_marker(saltar)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(autouse=True)
def registro_limpio():
    """El registro de variables propias es global: cada prueba parte (y termina) sin variables."""
    from utils import schema
    schema.registrar_variables(())
    yield
    schema.registrar_variables(())


@pytest.fixture(scope="session")
def semilla() -> Path:
    return RUTA_SEMILLA


@pytest.fixture(scope="session")
def plantilla(tmp_path_factory, semilla) -> Path:
    """Libro de trabajo ya migrado, creado una sola vez por sesión (la migración tarda)."""
    sha_antes = _sha(semilla)
    d = tmp_path_factory.mktemp("plantilla")
    alm = LocalStorage(d / "plantilla.xlsx", semilla)
    alm.asegurar()
    assert _sha(semilla) == sha_antes, "el Excel original no debe modificarse"
    return alm.ruta


@pytest.fixture
def almacen(tmp_path, plantilla, semilla) -> LocalStorage:
    destino = tmp_path / "trabajo.xlsx"
    shutil.copy2(plantilla, destino)
    return LocalStorage(destino, semilla)
