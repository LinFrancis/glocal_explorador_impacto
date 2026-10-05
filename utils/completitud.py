# -*- coding: utf-8 -*-
"""Indicador de completitud de una noticia: % de campos clave con información.

14 campos clave de igual peso: 6 de contenido web (se obtienen al sincronizar) y 8 de análisis
(los completa una persona). Un campo cuenta como completo si no está vacío ni es
"No especificado"/"Sin dato"; **"No aplica" sí cuenta** porque es una codificación deliberada.
Umbrales en utils/schema.py: Completa >= 80 %, Parcial 50-79 %, Básica < 50 %.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from utils import schema as S

NIVEL_COMPLETA = "Completa"
NIVEL_PARCIAL = "Parcial"
NIVEL_BASICA = "Básica"
NIVELES = (NIVEL_COMPLETA, NIVEL_PARCIAL, NIVEL_BASICA)

# Si el campo de análisis está vacío se prueba con el alternativo (misma información).
_ALTERNATIVAS = {"actores_normalizados": "actores"}


def _texto(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and valor != valor:   # NaN
        return ""
    if type(valor).__name__ == "NaTType":
        return ""
    return str(valor).strip()


def campo_completo(valor) -> bool:
    """True si el valor aporta información (multi-etiqueta: basta una etiqueta con contenido)."""
    s = _texto(valor)
    if not s:
        return False
    partes = [p.strip().lower() for p in s.split(";")] if ";" in s else [s.lower()]
    return any(p and p not in S.VALORES_VACIOS for p in partes)


@dataclass(frozen=True)
class Completitud:
    pct: float                        # 0-100 sobre los 14 campos
    n_completos: int
    n_total: int
    pct_contenido: float
    pct_analisis: float
    faltan_contenido: tuple[str, ...]
    faltan_analisis: tuple[str, ...]
    nivel: str

    @property
    def faltan(self) -> tuple[str, ...]:
        return self.faltan_contenido + self.faltan_analisis


def nivel_de(pct: float) -> str:
    if pct >= S.UMBRAL_COMPLETA:
        return NIVEL_COMPLETA
    if pct >= S.UMBRAL_PARCIAL:
        return NIVEL_PARCIAL
    return NIVEL_BASICA


def _valor(fila: Mapping, key: str):
    v = fila.get(key)
    if not campo_completo(v) and key in _ALTERNATIVAS:
        return fila.get(_ALTERNATIVAS[key])
    return v


def calcular(fila: Mapping) -> Completitud:
    """Completitud de un registro (dict, Series o cualquier mapeo campo -> valor)."""
    faltan_c = tuple(k for k in S.CLAVE_CONTENIDO_CAMPOS if not campo_completo(_valor(fila, k)))
    faltan_a = tuple(k for k in S.CLAVE_ANALISIS_CAMPOS if not campo_completo(_valor(fila, k)))
    n_c, n_a = len(S.CLAVE_CONTENIDO_CAMPOS), len(S.CLAVE_ANALISIS_CAMPOS)
    ok_c, ok_a = n_c - len(faltan_c), n_a - len(faltan_a)
    total = n_c + n_a
    pct = 100.0 * (ok_c + ok_a) / total
    return Completitud(
        pct=round(pct, 1), n_completos=ok_c + ok_a, n_total=total,
        pct_contenido=round(100.0 * ok_c / n_c, 1), pct_analisis=round(100.0 * ok_a / n_a, 1),
        faltan_contenido=faltan_c, faltan_analisis=faltan_a, nivel=nivel_de(pct),
    )


def pct_df(df):
    """Serie con el % de completitud por fila de un DataFrame (índice conservado)."""
    import pandas as pd

    if len(df) == 0:
        return pd.Series([], dtype="float64", index=df.index)
    return df.apply(lambda fila: calcular(fila).pct, axis=1).astype("float64")


def nivel_df(pct_serie):
    return pct_serie.map(nivel_de)
