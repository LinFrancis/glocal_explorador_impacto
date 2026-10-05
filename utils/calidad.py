# -*- coding: utf-8 -*-
"""Calidad de datos: detectores que revisan la hoja cruda y proponen correcciones.

Cada detector devuelve un `Hallazgo` con filas {id_evento, titulo, campo, actual, sugerido}. Los de tipo
«cambios» traen una corrección propuesta (se aplica solo si la persona la confirma, en un lote deshacible);
los «info» solo señalan lo que hay que revisar a mano; el de «geocodificar» se resuelve con el servicio de
mapas. Trabajan sobre texto canónico, sin Streamlit.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

from utils import dedupe
from utils import schema as S
from utils.validation import normalizar_url, parse_fecha

TIPO_CAMBIOS, TIPO_INFO, TIPO_GEOCODIFICAR = "cambios", "info", "geocodificar"

_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
          "noviembre", "diciembre"]

# Nombres de país en otro idioma o con anotaciones -> forma en español usada en el resto de la base.
PAISES_ES = {
    "united states": "Estados Unidos", "united states of america": "Estados Unidos", "usa": "Estados Unidos",
    "canada": "Canadá", "sverige": "Suecia", "brazil": "Brasil", "deutschland": "Alemania", "germany": "Alemania",
    "france": "Francia", "italia": "Italia", "italy": "Italia", "spain": "España", "mexico": "México",
    "peru": "Perú", "united kingdom": "Reino Unido", "uk": "Reino Unido", "netherlands": "Países Bajos",
    "paraguay / paraguái": "Paraguay", "paraguay / paraguay": "Paraguay",
}


@dataclass
class Hallazgo:
    clave: str
    titulo: str
    ayuda: str
    tipo: str
    filas: list[dict] = field(default_factory=list)
    columna_sugerida: str = "Se vería"          # cómo se llama la columna «sugerido» en las tablas

    @property
    def n(self) -> int:
        return len(self.filas)

    @property
    def n_noticias(self) -> int:
        return len({f["id_evento"] for f in self.filas})

    @property
    def corregible(self) -> bool:
        return self.tipo == TIPO_CAMBIOS and any(f["sugerido"] != f["actual"] for f in self.filas)


def _fila(r, campo: str, actual: str, sugerido: str = "") -> dict:
    return {"id_evento": r["id_evento"], "titulo": str(r["titulo"])[:70], "campo": campo, "actual": actual, "sugerido": sugerido}


def _fecha_larga(dt) -> str:
    return f"{dt.day} de {_MESES[dt.month - 1]} de {dt.year}"


# ============================================================================ detectores
def obligatorios_vacios(base: pd.DataFrame) -> Hallazgo:
    h = Hallazgo("obligatorios", "Campos obligatorios vacíos o inválidos",
                 "Título, enlace y fuente son lo mínimo para que una noticia funcione.", TIPO_INFO)
    for r in base.to_dict("records"):
        for k in S.OBLIGATORIOS:
            v = str(r.get(k, "")).strip()
            if not v:
                h.filas.append(_fila(r, k, "", ""))
            elif k == "fuente" and v not in S.FUENTES:
                h.filas.append(_fila(r, k, v, ""))
    return h


def fechas_texto_invalidas(base: pd.DataFrame) -> Hallazgo:
    h = Hallazgo("fechas_texto", "Fechas de texto que no se reconocen",
                 "Columnas «fecha de publicación (texto)» y «fecha en el catálogo» con valores como «17 de hasta de 2019». "
                 "La corrección propuesta usa la fecha de publicación de la web, que es la confiable.", TIPO_CAMBIOS)
    for r in base.to_dict("records"):
        web = parse_fecha(r.get("fecha_publicacion_web"))
        for campo in ("fecha_publicacion", "fecha_catalogo"):
            v = str(r.get(campo, "")).strip()
            if v and parse_fecha(v) is None:
                h.filas.append(_fila(r, campo, v, _fecha_larga(web) if web else ""))
    return h


def fechas_web_primero_de_enero(base: pd.DataFrame) -> Hallazgo:
    h = Hallazgo("fecha_1_enero", "Fechas de publicación en 1 de enero",
                 "Puede ser una fecha por defecto del sitio web. Conviene confirmarlas con la noticia original.", TIPO_INFO)
    for r in base.to_dict("records"):
        f = parse_fecha(r.get("fecha_publicacion_web"))
        if f and f.month == 1 and f.day == 1:
            h.filas.append(_fila(r, "fecha_publicacion_web", f"{f:%Y-%m-%d}"))
    return h


def _clave_etiqueta(texto: str) -> str:
    s = dedupe.sin_tildes(texto).lower()
    return re.sub(r"[^a-z0-9]+", "", s)


def metodologias_equivalentes(base: pd.DataFrame) -> Hallazgo:
    """Variantes de escritura de una misma metodología (alias conocidos y diferencias de tildes, mayúsculas o espacios)."""
    h = Hallazgo("metodologias", "Metodologías escritas de varias formas",
                 "La misma metodología aparece con grafías distintas («Café ProAcción» / «Café Pro-Acción»). "
                 "Se propone unificarlas en la forma más usada.", TIPO_CAMBIOS)
    todas = [p for v in base["metodologia"] for p in S.dividir_etiquetas(v)]
    frecuencia = pd.Series(todas).value_counts() if todas else pd.Series(dtype=int)
    grupos: dict[str, list[str]] = {}
    for etiqueta in frecuencia.index:
        canon_alias = S.ALIAS_METODOLOGIA.get(etiqueta.lower(), etiqueta)
        grupos.setdefault(_clave_etiqueta(canon_alias), []).append(etiqueta)
    reemplazo: dict[str, str] = {}
    for variantes in grupos.values():
        if len(variantes) < 2 and S.ALIAS_METODOLOGIA.get(variantes[0].lower(), variantes[0]) == variantes[0]:
            continue
        # canónica: el alias definido si lo hay; si no, la grafía más frecuente
        con_alias = {S.ALIAS_METODOLOGIA[v.lower()] for v in variantes if v.lower() in S.ALIAS_METODOLOGIA}
        canonica = next(iter(con_alias)) if len(con_alias) == 1 else variantes[0]
        for v in variantes:
            if v != canonica:
                reemplazo[v] = canonica
    if not reemplazo:
        return h
    for r in base.to_dict("records"):
        actual = r["metodologia"]
        partes = S.dividir_etiquetas(actual)
        if any(p in reemplazo for p in partes):
            h.filas.append(_fila(r, "metodologia", actual, S.unir_etiquetas(reemplazo.get(p, p) for p in partes)))
    return h


def _pais_es(token: str) -> str:
    t = token.strip()
    if not t:
        return t
    sin_nota = re.sub(r"\s*\(.*\)\s*$", "", t).strip()               # «Chile (CIMARQ)» -> «Chile»
    return PAISES_ES.get(sin_nota.lower(), PAISES_ES.get(t.lower(), sin_nota))


def paises_sin_normalizar(base: pd.DataFrame) -> Hallazgo:
    h = Hallazgo("paises", "Países en otro idioma o con anotaciones",
                 "Nombres como «United States» o «Chile (CIMARQ)» se cuentan aparte de «Estados Unidos» y «Chile» "
                 "en los mapas y gráficos. Se propone la forma en español.", TIPO_CAMBIOS)
    for r in base.to_dict("records"):
        actual = r["sitios_pais"]
        if not actual.strip():
            continue
        nuevo = ";".join(_pais_es(t) for t in actual.split(";"))
        if nuevo != actual:
            h.filas.append(_fila(r, "sitios_pais", actual, nuevo))
    return h


def texto_mostrado_distinto(base: pd.DataFrame) -> Hallazgo:
    from utils.data import _fix_missing_spaces       # import perezoso: data.py depende de Streamlit

    h = Hallazgo("texto_mostrado", "Títulos que se muestran distinto de como están guardados",
                 "La vista de lectura corrige espacios faltantes y a veces parte siglas o marcas («P.A.R.E.S» → «P. A. R. E. S»). "
                 "Lo guardado está bien; esto es solo un aviso para revisar cómo se ve.", TIPO_INFO)
    for r in base.to_dict("records"):
        mostrado = _fix_missing_spaces(r["titulo"])
        if mostrado != r["titulo"]:
            h.filas.append(_fila(r, "titulo", r["titulo"], mostrado))
    return h


def urls_mal_formadas(base: pd.DataFrame) -> Hallazgo:
    h = Hallazgo("urls", "Enlaces mal formados",
                 "Enlaces de la noticia, de su imagen o de Open Graph que no parecen una URL válida.", TIPO_INFO)
    for r in base.to_dict("records"):
        for campo in ("url_noticia", "imagen_principal_url", "og_url", "carpeta_proyecto"):
            v = str(r.get(campo, "")).strip()
            if v and normalizar_url(v)[1]:
                h.filas.append(_fila(r, campo, v))
        for v in re.split(r"[|\n]+", str(r.get("documentos_proyecto", ""))):
            if v.strip() and normalizar_url(v.strip())[1]:
                h.filas.append(_fila(r, "documentos_proyecto", v.strip()))
    return h


def variables_fuera_de_opciones(base: pd.DataFrame) -> Hallazgo:
    """Valores de variables propias de opciones que no están entre sus opciones (p. ej. editados en el Excel a mano)."""
    from utils.variables import canonizar, valores_invalidos

    h = Hallazgo("variables_opciones", "Variables propias con valores fuera de sus opciones",
                 "Valores que no coinciden con ninguna opción definida para la variable. Revísalos en la ficha de la noticia "
                 "o agrega la opción en Administración → Variables analíticas.", TIPO_INFO,
                 columna_sugerida="Opciones válidas")
    for c in S.CAMPOS:
        if not c.variable or c.key not in base.columns:
            continue
        for r in base.to_dict("records"):
            valor = str(r.get(c.key, "")).strip()
            if valor and valores_invalidos(c, canonizar(c, valor)):
                h.filas.append(_fila(r, c.key, valor, ", ".join(c.opciones)))
    return h


def lugares_sin_coordenadas(base: pd.DataFrame) -> Hallazgo:
    from utils.geocoding import es_online

    h = Hallazgo("coordenadas", "Lugares sin coordenadas",
                 "Noticias con lugar físico pero sin latitud/longitud: no aparecen en el mapa. "
                 "Se pueden buscar con el servicio de mapas (OpenStreetMap).", TIPO_GEOCODIFICAR)
    for r in base.to_dict("records"):
        lugares = [p.strip() for p in r["lugar"].split(";") if p.strip()]
        fisicos = [(i, lg) for i, lg in enumerate(lugares) if not es_online(lg)]
        if not fisicos:
            continue
        lats = [p.strip() for p in r["sitios_lat"].split(";")] + [""] * len(lugares)
        faltan = [lg for i, lg in fisicos if not lats[i]]
        if faltan:
            h.filas.append(_fila(r, "lugar", "; ".join(faltan)))
    return h


def detectar(base: pd.DataFrame) -> list[Hallazgo]:
    """Todos los hallazgos, en orden de importancia."""
    return [
        obligatorios_vacios(base), fechas_texto_invalidas(base), fechas_web_primero_de_enero(base),
        metodologias_equivalentes(base), paises_sin_normalizar(base), urls_mal_formadas(base),
        variables_fuera_de_opciones(base), lugares_sin_coordenadas(base), texto_mostrado_distinto(base),
    ]


def cambios_de(hallazgo: Hallazgo, ids_elegidos: set[tuple[str, str]] | None = None):
    """Lista de Cambio para aplicar las correcciones propuestas (opcionalmente solo (id, campo) elegidos)."""
    from utils.repo import Cambio

    return [Cambio(f["id_evento"], f["campo"], f["actual"], f["sugerido"]) for f in hallazgo.filas
            if f["sugerido"] != f["actual"] and (ids_elegidos is None or (f["id_evento"], f["campo"]) in ids_elegidos)]
