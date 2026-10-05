# -*- coding: utf-8 -*-
"""Widgets de Streamlit generados a partir del registro de campos (utils/schema.py).

`campo_widget` dibuja el control adecuado al tipo del campo y devuelve el valor en TEXTO canónico,
listo para validar (utils/validation.py) y guardar (utils/repo.py). Lo usan el formulario de
carga y la ficha de noticia.
"""
from __future__ import annotations

import streamlit as st

from utils import schema as S

_PLACEHOLDER = {
    S.FECHA: "AAAA-MM-DD  o  11 de julio de 2026",
    S.FECHA_TEXTO: "11 de julio de 2026",
    S.URL: "https://…",
    S.IMAGEN_URL: "https://…/imagen.jpg",
    S.NUMERO: "Número (ej.: 1500 o 12,5)",
    S.LISTA_NUMEROS: "-33.46;-70.66",
    S.LISTA_TEXTO: "Chile;Chile",
}

# Campos cuyas opciones solo se administran desde el catálogo / marcos fijos: no admiten valores nuevos.
_CERRADOS = {S.OPC_CAT_CATEGORIAS, S.OPC_CAT_MACRO, S.OPC_ATRIBUTOS, S.OPC_SUBATRIBUTOS, S.OPC_GCAA_EJE}


def es_cerrado(c: S.Campo) -> bool:
    return isinstance(c.opciones, tuple) or c.opciones in _CERRADOS


def campo_widget(c: S.Campo, valor: str, key: str, opciones: list[str] | None = None,
                 disabled: bool = False) -> str:
    """Dibuja el control de `c` con `valor` (texto) como valor inicial y devuelve el texto resultante.

    Si `key` ya tiene estado (p. ej. «Copiar clasificación» lo dejó escrito), ese estado manda y no se
    pasa valor inicial: así Streamlit no avisa de un valor doble.
    """
    etiqueta = c.label + (" *" if c.obligatorio else "")
    ayuda = c.ayuda or None
    valor = valor or ""
    t = c.tipo
    ya = key in st.session_state

    if t == S.TEXTO_LARGO:
        return st.text_area(etiqueta, value="" if ya else valor, key=key, height=170, help=ayuda, disabled=disabled)

    if t == S.LISTA_URL:
        return st.text_area(etiqueta, value="" if ya else valor.replace(" | ", "\n"), key=key, height=100, disabled=disabled,
                            placeholder="https://…\nhttps://…", help=(ayuda or "Un enlace por línea."))

    if t == S.BOOLEANO:
        activo = st.toggle(etiqueta, value=False if ya else valor.strip().lower() in ("true", "1", "sí", "si"),
                           key=key, help=ayuda, disabled=disabled)
        return "True" if activo else "False"

    if t == S.OPCION and opciones:
        opts = list(opciones)
        for v in (valor, st.session_state.get(key)):
            if v and v not in opts:
                opts.append(v)                       # un valor antiguo (o copiado de otra noticia) no se pierde
        indice = None if ya or valor not in opts else opts.index(valor)
        elegido = st.selectbox(etiqueta, opts, index=indice, key=key,
                               placeholder="Sin definir", help=ayuda, disabled=disabled,
                               accept_new_options=not es_cerrado(c))
        return elegido or ""

    if t == S.ETIQUETAS and opciones is not None:
        actuales = S.dividir_etiquetas(valor)
        en_estado = [v for v in (st.session_state.get(key) or []) if isinstance(v, str)]
        opts = list(dict.fromkeys(list(opciones) + actuales + en_estado))
        cerrado = es_cerrado(c)
        ayuda_cat = " Para crear categorías nuevas usa «Administración»." if c.opciones in (S.OPC_CAT_CATEGORIAS, S.OPC_CAT_MACRO) else ""
        elegidos = st.multiselect(etiqueta, opts, default=None if ya else actuales, key=key, disabled=disabled,
                                  placeholder="Elige" + ("" if cerrado else " o escribe una nueva"),
                                  help=((ayuda or "") + ayuda_cat).strip() or None,
                                  accept_new_options=not cerrado)
        return S.unir_etiquetas(elegidos)

    return st.text_input(etiqueta, value="" if ya else valor, key=key, help=ayuda, disabled=disabled,
                         placeholder=_PLACEHOLDER.get(t))
