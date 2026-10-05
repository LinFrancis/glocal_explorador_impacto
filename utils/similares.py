# -*- coding: utf-8 -*-
"""Noticias parecidas YA ANALIZADAS, para sugerir una clasificación a una noticia nueva.

Similitud coseno sobre el vocabulario de cada noticia (`_palabras_busqueda`: palabras únicas de
título + texto, sin tildes), con peso IDF: las palabras raras en el catálogo pesan más que las
comunes. Solo se consideran como referencia las noticias con al menos `MIN_ANALISIS` de los 8
campos de análisis completos. No usa servicios externos: es una ayuda, la decisión es de la persona.
"""
from __future__ import annotations

import math
from collections import Counter

import pandas as pd

from utils import completitud
from utils import schema as S

MIN_ANALISIS = 6          # de los 8 campos de análisis
MIN_PALABRA = 3

# Campos de clasificación que «Copiar clasificación» traslada al formulario de la ficha.
CAMPOS_COPIABLES = (
    "categoria_macro", "categorias", "metodologia", "actores_normalizados", "eje_gcaa", "objetivo_gcaa",
    "atributos_resiliencia", "subatributos_resiliencia", "beneficiarios_directos", "beneficiarios_indirectos",
)


def _tokens(fila) -> set[str]:
    palabras = fila.get("_palabras_busqueda") or ()
    return {p for p in palabras if len(p) >= MIN_PALABRA}


def _n_analisis(fila) -> int:
    return len(S.CLAVE_ANALISIS_CAMPOS) - len(completitud.calcular(fila).faltan_analisis)


def similares(df: pd.DataFrame, id_evento: str, k: int = 5) -> list[dict]:
    """Top-k noticias analizadas más parecidas a `id_evento` (puntaje 0-100), de mayor a menor.

    Cada resultado: {id_evento, titulo, puntaje, comunes (palabras compartidas más informativas), fila}.
    """
    filas = df.to_dict("records")
    objetivo = next((f for f in filas if f["id_evento"] == id_evento), None)
    if objetivo is None:
        return []
    docs = {f["id_evento"]: _tokens(f) for f in filas}
    n = len(docs)
    df_cuenta = Counter(p for t in docs.values() for p in t)
    idf = {p: math.log((1 + n) / (1 + c)) + 1.0 for p, c in df_cuenta.items()}

    def norma(tokens: set[str]) -> float:
        return math.sqrt(sum(idf[p] ** 2 for p in tokens)) or 1.0

    t_obj = docs[id_evento]
    if not t_obj:
        return []
    n_obj = norma(t_obj)
    resultados = []
    for f in filas:
        ide = f["id_evento"]
        if ide == id_evento or _n_analisis(f) < MIN_ANALISIS:
            continue
        comunes = t_obj & docs[ide]
        if not comunes:
            continue
        puntaje = sum(idf[p] ** 2 for p in comunes) / (n_obj * norma(docs[ide]))
        resultados.append({
            "id_evento": ide, "titulo": f["titulo"], "puntaje": round(100 * puntaje, 1),
            "comunes": sorted(comunes, key=lambda p: -idf[p])[:6], "fila": f,
        })
    resultados.sort(key=lambda r: (-r["puntaje"], r["id_evento"]))
    return resultados[:k]


def clasificacion_de(fila: dict) -> dict[str, str]:
    """Campos de clasificación de una fila (solo los no vacíos), listos para copiar a un formulario."""
    return {k: str(fila.get(k, "") or "").strip() for k in CAMPOS_COPIABLES if str(fila.get(k, "") or "").strip()}
