# -*- coding: utf-8 -*-
"""Selección de noticias para exportar: un conjunto de `id_evento` por sesión.

Se usa `id_evento` (estable) y no `item` (posicional, cambia al agregar noticias). La selección
sobrevive al cambio de página y a las ediciones; las noticias que ya no existan se descartan al
usarla (`vigentes`).
"""
from __future__ import annotations

from collections.abc import Iterable

import streamlit as st

K_SEL = "sel_ids"
K_VERSION = "sel_version"      # cambia con las acciones masivas para refrescar las casillas de las tarjetas


def ids() -> set[str]:
    """Conjunto vivo de IDs seleccionados (se puede modificar en el sitio)."""
    return st.session_state.setdefault(K_SEL, set())


def version() -> int:
    return st.session_state.get(K_VERSION, 0)


def _subir_version() -> None:
    st.session_state[K_VERSION] = version() + 1


def contar() -> int:
    return len(ids())


def esta(id_evento: str) -> bool:
    return id_evento in ids()


def marcar(id_evento: str, valor: bool) -> None:
    (ids().add if valor else ids().discard)(id_evento)


def agregar(nuevos: Iterable[str]) -> None:
    ids().update(str(i) for i in nuevos)
    _subir_version()


def quitar(retirar: Iterable[str]) -> None:
    ids().difference_update(str(i) for i in retirar)
    _subir_version()


def vaciar() -> None:
    ids().clear()
    _subir_version()


def vigentes(existentes: Iterable[str]) -> list[str]:
    """Los seleccionados que todavía existen, en el orden de `existentes`."""
    sel = ids()
    return [i for i in existentes if i in sel]


def widget_sidebar() -> None:
    """Contador de la selección en el menú lateral (visible en todas las páginas)."""
    n = contar()
    with st.sidebar:
        if n:
            st.caption(f":material/checklist: **{n}** noticia(s) seleccionada(s) para exportar")
            st.button("Vaciar selección", key="sel_vaciar_sidebar", on_click=vaciar, type="tertiary",
                      icon=":material/deselect:")
        else:
            st.caption(":material/checklist: Sin noticias seleccionadas para exportar")
