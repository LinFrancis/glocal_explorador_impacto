# -*- coding: utf-8 -*-
"""Pequeñas utilidades de interfaz compartidas por las páginas de gestión."""
from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).resolve().parent.parent
_FLASH_KEY = "_mensajes_pendientes"


def existe_pagina(ruta: str) -> bool:
    """True si la página (p. ej. 'app_pages/ficha.py') ya existe: permite enlazarla solo cuando está."""
    return (RAIZ / ruta).exists()
K_FICHA = "ficha_id_activo"            # id_evento de la ficha que debe abrir la página de Fichas
PAGINA_FICHA = "app_pages/ficha.py"


def abrir_ficha(id_evento: str) -> None:
    """Deja la noticia elegida y salta a la página de Fichas (usar como `on_click` de un botón)."""
    st.session_state[K_FICHA] = id_evento
    st.switch_page(PAGINA_FICHA)

_ICONOS = {
    "exito": ":material/check_circle:",
    "error": ":material/error:",
    "aviso": ":material/warning:",
    "info": ":material/info:",
}


def flash(tipo: str, texto: str) -> None:
    """Deja un mensaje para mostrarlo en el próximo rerun (sobrevive a st.rerun() y a cerrar un diálogo).

    tipo: 'exito' | 'error' | 'aviso' | 'info'.
    """
    st.session_state.setdefault(_FLASH_KEY, []).append((tipo, texto))


def mostrar_flash() -> None:
    """Muestra (y consume) los mensajes pendientes. `page_header()` lo llama automáticamente."""
    for tipo, texto in st.session_state.pop(_FLASH_KEY, []):
        {"exito": st.success, "error": st.error, "aviso": st.warning}.get(tipo, st.info)(
            texto, icon=_ICONOS.get(tipo, _ICONOS["info"])
        )
