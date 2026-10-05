# -*- coding: utf-8 -*-
"""Detección de duplicados entre un registro candidato y la base.

Criterio, por prioridad (los niveles 1-3 son duplicado SEGURO y se omiten solos; el 4 solo se
avisa, porque hay títulos repetidos legítimos, p. ej. dos ediciones de un mismo taller):

  1. fuente + wp_id                 (id de WordPress: el más robusto, sobrevive a cambios de slug)
  2. URL normalizada                (sin esquema, www, query, fragmento ni "/" final)
  3. fuente + slug
  4. título normalizado             (sin tildes, mayúsculas ni puntuación)
        - misma fuente  -> "posible duplicado / la URL cambió"
        - otra fuente   -> "posible duplicado entre fuentes" (candidato a es_duplicado_secundario)
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from urllib.parse import urlparse

NIVEL_WP_ID = 1
NIVEL_URL = 2
NIVEL_SLUG = 3
NIVEL_TITULO = 4
MAX_NIVEL_SEGURO = 3

MOTIVOS = {
    NIVEL_WP_ID: "Mismo ID de WordPress",
    NIVEL_URL: "Misma URL",
    NIVEL_SLUG: "Mismo identificador (slug) en la misma fuente",
    NIVEL_TITULO: "Mismo título",
}


def sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def normalizar_titulo(titulo) -> str:
    s = sin_tildes(str(titulo or "")).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.strip()


def normalizar_url(url) -> str:
    s = str(url or "").strip().lower()
    if not s:
        return ""
    if "://" not in s:
        s = "https://" + s
    p = urlparse(s)
    host = p.netloc.removeprefix("www.")
    return f"{host}{p.path.rstrip('/')}"


def _wp(valor) -> str:
    s = str(valor or "").strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s if s.isdigit() else ""


@dataclass(frozen=True)
class Coincidencia:
    nivel: int
    id_evento: str
    motivo: str
    entre_fuentes: bool = False

    @property
    def segura(self) -> bool:
        return self.nivel <= MAX_NIVEL_SEGURO


class Indice:
    """Índice en memoria de la base (a partir de filas en forma de texto)."""

    def __init__(self, filas: Iterable[Mapping] = ()):
        self.por_wp: dict[tuple[str, str], str] = {}
        self.por_url: dict[str, str] = {}
        self.por_slug: dict[tuple[str, str], str] = {}
        self.por_titulo: dict[str, list[tuple[str, str]]] = {}
        for f in filas:
            self.agregar(f)

    def agregar(self, f: Mapping) -> None:
        """Suma un registro al índice (sirve para detectar repetidos dentro de un mismo archivo)."""
        ide = str(f.get("id_evento", "") or "")
        fuente = str(f.get("fuente", "") or "")
        wp = _wp(f.get("wp_id"))
        if wp:
            self.por_wp.setdefault((fuente, wp), ide)
        url = normalizar_url(f.get("url_noticia"))
        if url:
            self.por_url.setdefault(url, ide)
        slug = str(f.get("slug", "") or "").strip().lower()
        if slug:
            self.por_slug.setdefault((fuente, slug), ide)
        tit = normalizar_titulo(f.get("titulo"))
        if tit:
            self.por_titulo.setdefault(tit, []).append((ide, fuente))

    def buscar(self, cand: Mapping, ignorar: str | None = None) -> list[Coincidencia]:
        """Coincidencias del candidato, ordenadas de más a menos segura. `ignorar`: id a excluir
        (útil al comparar un registro de la base contra el resto)."""
        fuente = str(cand.get("fuente", "") or "")
        res: list[Coincidencia] = []
        vistos: set[str] = set()

        def agregar(nivel: int, ide: str, entre: bool = False):
            if ide and ide != ignorar and ide not in vistos:
                vistos.add(ide)
                res.append(Coincidencia(nivel, ide, MOTIVOS[nivel], entre))

        wp = _wp(cand.get("wp_id"))
        if wp:
            agregar(NIVEL_WP_ID, self.por_wp.get((fuente, wp), ""))
        url = normalizar_url(cand.get("url_noticia"))
        if url:
            agregar(NIVEL_URL, self.por_url.get(url, ""))
        slug = str(cand.get("slug", "") or "").strip().lower()
        if slug:
            agregar(NIVEL_SLUG, self.por_slug.get((fuente, slug), ""))
        tit = normalizar_titulo(cand.get("titulo"))
        if tit:
            for ide, f in self.por_titulo.get(tit, []):
                agregar(NIVEL_TITULO, ide, entre=(f != fuente))
        res.sort(key=lambda c: (c.nivel, c.id_evento))
        return res


def es_duplicado_seguro(coincidencias: list[Coincidencia]) -> bool:
    return any(c.segura for c in coincidencias)


def pares_sospechosos(filas: Iterable[Mapping]) -> list[tuple[str, str, bool]]:
    """Pares (id_a, id_b, entre_fuentes) de la propia base con el mismo título normalizado."""
    grupos: dict[str, list[tuple[str, str]]] = {}
    for f in filas:
        tit = normalizar_titulo(f.get("titulo"))
        if tit:
            grupos.setdefault(tit, []).append((str(f.get("id_evento", "")), str(f.get("fuente", ""))))
    pares = []
    for items in grupos.values():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                pares.append((items[i][0], items[j][0], items[i][1] != items[j][1]))
    return sorted(pares)
