# -*- coding: utf-8 -*-
"""Ayudas para pruebas de humo con streamlit.testing.v1.AppTest (sin navegador)."""
from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest

from utils import data, storage

RAIZ = Path(__file__).resolve().parent.parent


def apuntar_a(monkeypatch, almacen) -> None:
    """Hace que toda la app use el libro temporal `almacen` en vez del real."""
    monkeypatch.setattr(storage, "RUTA_TRABAJO", almacen.ruta)
    monkeypatch.setattr(data, "EXCEL_PATH", almacen.ruta)
    storage.olvidar_almacenes()
    st.cache_data.clear()


def nueva_app(timeout: int = 90) -> AppTest:
    return AppTest.from_file(str(RAIZ / "Inicio.py"), default_timeout=timeout)


def iniciar_sesion(at: AppTest, nombre: str | None = "Francis", usuario: str = "Impacto", clave: str = "glocal") -> AppTest:
    """Los dos pasos del acceso: usuario y clave, y luego el nombre (se escribe como «primera vez»;
    si ya está en la lista, se reconoce y se usa el registrado). `nombre=None`: se detiene tras la clave."""
    at.run()
    at.text_input[0].set_value(usuario)
    at.text_input[1].set_value(clave)
    next(b for b in at.button if b.label == "Continuar").click()
    at.run()
    if nombre is not None and any(b.label == "Entrar" for b in at.button):
        at.text_input(key="auth_nombre_nuevo").set_value(nombre)
        next(b for b in at.button if b.label == "Entrar").click()
        at.run()
    return at


def textos(at: AppTest) -> str:
    """Todo el texto visible (markdown, títulos, captions, alertas) en una sola cadena."""
    partes = []
    for coleccion in (at.markdown, at.title, at.header, at.subheader, at.caption, at.error, at.warning, at.success, at.info):
        partes += [e.value for e in coleccion]
    return "\n".join(partes)
