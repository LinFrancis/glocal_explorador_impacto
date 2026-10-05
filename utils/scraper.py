# -*- coding: utf-8 -*-
"""Sincronización manual con los dos sitios: descarga, normalización y diferencial contra la base.

Fuente de datos: la API REST de WordPress de cada sitio (mismos datos que las páginas públicas,
más estable que parsear HTML). Si la API falla (no por falta de conexión), se cae al listado HTML
con los campos mínimos (título, enlace, imagen) y el resto queda vacío.

Reglas de errores: nunca se lanza una excepción hacia la interfaz con texto técnico. Cada fuente
devuelve un `ResultadoFuente` con `error` en español; si un campo no se puede leer queda vacío y
se cuenta en `n_campos_vacios`; si una fuente falla, la otra sigue.

No importa Streamlit (se prueba con respuestas simuladas).
"""
from __future__ import annotations

import html as _html
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from utils import dedupe
from utils import schema as S
from utils.repo import Cambio
from utils.validation import a_texto, parse_fecha

USER_AGENT = "ImpactoGlocalGestor/1.0 (herramienta interna de sincronización)"
TIMEOUT = (8, 40)          # (conexión, lectura) en segundos
POR_PAGINA = 100           # máximo permitido por WordPress
MAX_PAGINAS = 30
PAUSA_ENTRE_PAGINAS = 0.3
LARGO_VISTA_PREVIA = 300

# Campos que la web "posee" y que se pueden refrescar si la noticia cambió allá.
CAMPOS_ACTUALIZABLES = (
    "titulo", "descripcion_catalogo", "contenido_completo", "imagen_principal_url", "imagen_alt",
    "enlaces_externos",
)
_BLOQUES = ("p", "div", "section", "article", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6",
            "blockquote", "figure", "figcaption", "tr", "table", "br", "header", "footer")


@dataclass(frozen=True)
class FuenteWeb:
    clave: str            # dominio = valor de la columna `fuente`
    nombre: str
    api: str
    listado: str          # página pública (respaldo HTML)
    campos_api: str = "id,date,modified,slug,link,title,excerpt,content,featured_media,_links,_embedded"


FUENTES_WEB: dict[str, FuenteWeb] = {
    "glocalminds.com": FuenteWeb(
        "glocalminds.com", "Glocalminds",
        "https://glocalminds.com/wp-json/wp/v2/catalogo", "https://glocalminds.com/noticias/"),
    "fundacionglocal.org": FuenteWeb(
        "fundacionglocal.org", "Fundación Glocal",
        "https://fundacionglocal.org/wp-json/wp/v2/posts", "https://fundacionglocal.org/buenas-noticias/"),
}


class ErrorWeb(Exception):
    """Fallo al consultar un sitio. `recuperable`: tiene sentido probar el respaldo HTML."""

    def __init__(self, mensaje: str, recuperable: bool = False):
        super().__init__(mensaje)
        self.recuperable = recuperable


# ============================================================================ red
def crear_sesion() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json, text/html;q=0.8"})
    reintentos = Retry(total=3, backoff_factor=0.8, status_forcelist=(429, 500, 502, 503, 504),
                       allowed_methods=("GET",), respect_retry_after_header=True)
    s.mount("https://", HTTPAdapter(max_retries=reintentos))
    s.mount("http://", HTTPAdapter(max_retries=reintentos))
    return s


def mensaje_de_error(exc: Exception, sitio: str) -> str:
    """Texto claro en español para un error de red/HTTP."""
    if isinstance(exc, requests.exceptions.Timeout):
        return f"{sitio} tardó demasiado en responder. Inténtalo de nuevo en unos minutos."
    if isinstance(exc, requests.exceptions.SSLError):
        return f"No se pudo establecer una conexión segura con {sitio}."
    if isinstance(exc, requests.exceptions.ConnectionError):
        return f"No hay conexión con {sitio}. Revisa tu conexión a internet."
    if isinstance(exc, requests.exceptions.RetryError):
        return f"{sitio} respondió con errores repetidos y puede estar caído. Inténtalo más tarde."
    if isinstance(exc, requests.exceptions.HTTPError):
        codigo = exc.response.status_code if exc.response is not None else "?"
        return f"{sitio} respondió con un error ({codigo}). Puede ser temporal; inténtalo más tarde."
    if isinstance(exc, ValueError):
        return f"{sitio} devolvió una respuesta que no se pudo interpretar."
    return f"No se pudo consultar {sitio} ({type(exc).__name__})."


def _get(sesion, url: str, params: dict | None = None):
    """GET con manejo de errores. Devuelve la respuesta o lanza ErrorWeb."""
    sitio = urlparse(url).netloc
    try:
        r = sesion.get(url, params=params, timeout=TIMEOUT)
        if r.status_code >= 400:
            raise ErrorWeb(f"{sitio} respondió con un error ({r.status_code}).", recuperable=True) from None
        return r
    except ErrorWeb:
        raise
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
        raise ErrorWeb(mensaje_de_error(e, sitio), recuperable=False) from e
    except Exception as e:  # noqa: BLE001
        raise ErrorWeb(mensaje_de_error(e, sitio), recuperable=True) from e


def _json(resp, sitio: str):
    try:
        return resp.json()
    except Exception as e:  # noqa: BLE001
        raise ErrorWeb(mensaje_de_error(ValueError(), sitio), recuperable=True) from e


# ============================================================================ HTML -> texto
def texto_desde_html(html: str) -> str:
    """Texto limpio de un fragmento HTML. Los bloques se separan con saltos de línea y el espacio
    original entre elementos en línea se respeta (evita las "palabras pegadas" del scraping antiguo)."""
    if not html or not str(html).strip():
        return ""
    soup = BeautifulSoup(str(html), "html.parser")
    for t in soup(["script", "style", "noscript", "template"]):
        t.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for t in soup.find_all([b for b in _BLOQUES if b != "br"]):
        t.insert_before("\n")
        t.append("\n")
    texto = soup.get_text("")
    texto = texto.replace("\xa0", " ").replace("​", "")
    lineas = [re.sub(r"[ \t]+", " ", ln).strip() for ln in texto.splitlines()]
    return "\n".join(ln for ln in lineas if ln)


def enlaces_externos(html: str, dominio: str) -> list[str]:
    if not html:
        return []
    soup = BeautifulSoup(str(html), "html.parser")
    vistos: dict[str, None] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not re.match(r"^https?://", href, re.IGNORECASE):
            continue
        host = urlparse(href).netloc.lower().removeprefix("www.")
        if host and host != dominio and not host.endswith("." + dominio):
            vistos[href] = None
    return list(vistos)


def _titulo_plano(titulo_html: str) -> str:
    return " ".join(_html.unescape(BeautifulSoup(titulo_html or "", "html.parser").get_text(" ")).split())


def _extracto(excerpt_html: str) -> str:
    t = texto_desde_html(excerpt_html).replace("\n", " ")
    t = re.sub(r"\s*(\[…\]|\[&hellip;\]|\[\.\.\.\]|…|\.\.\.)\s*$", "", t)
    t = re.sub(r"\s*(Leer más|Seguir leyendo|Continue reading|Read more).*$", "", t, flags=re.IGNORECASE)
    return t.strip()


def _corto(texto: str, n: int = LARGO_VISTA_PREVIA) -> str:
    texto = " ".join(texto.split())
    if len(texto) <= n:
        return texto
    return texto[:n].rsplit(" ", 1)[0] + "…"


# ============================================================================ normalización de un elemento
def parsear_item(item: dict, fuente: FuenteWeb, ahora: str | None = None) -> tuple[dict[str, str], list[str]]:
    """Convierte un elemento de la API en un registro con los campos de la base.

    Devuelve (fila, problemas). Un campo que falla queda vacío y se anota en `problemas`.
    """
    problemas: list[str] = []

    def seguro(nombre: str, fn, defecto: str = "") -> str:
        try:
            v = fn()
            return v if v is not None else defecto
        except Exception:  # noqa: BLE001
            problemas.append(nombre)
            return defecto

    titulo = seguro("título", lambda: _titulo_plano(item["title"]["rendered"]))
    contenido_html = seguro("contenido", lambda: item["content"]["rendered"])
    contenido = seguro("contenido", lambda: texto_desde_html(contenido_html))
    resumen = seguro("resumen", lambda: _extracto(item["excerpt"]["rendered"]))
    if not resumen and contenido:
        resumen = _corto(contenido, 240)

    def imagen() -> tuple[str, str]:
        if not item.get("featured_media"):
            return "", ""
        media = item["_embedded"]["wp:featuredmedia"][0]
        return str(media.get("source_url", "") or ""), str(media.get("alt_text", "") or "")

    try:
        img_url, img_alt = imagen()
    except Exception:  # noqa: BLE001
        problemas.append("imagen")
        img_url, img_alt = "", ""

    enlaces = seguro("enlaces", lambda: enlaces_externos(contenido_html, fuente.clave), defecto=[])
    es_fundacion = fuente.clave == "fundacionglocal.org"
    fila = {
        "titulo": titulo, "titulo_catalogo": titulo,
        "slug": str(item.get("slug", "") or ""), "url_noticia": str(item.get("link", "") or ""),
        "wp_id": str(item.get("id", "") or ""), "fuente": fuente.clave,
        "fecha_publicacion_web": str(item.get("date", "") or ""),
        "fecha_modificacion_web": str(item.get("modified", "") or ""),
        "preview_contenido": _corto(contenido), "contenido_completo": contenido,
        "descripcion_catalogo": resumen,
        "imagen_principal_url": img_url, "imagen_alt": img_alt,
        "enlaces_externos": S.SEPARADOR_ENLACES.join(enlaces), "num_enlaces_externos": str(len(enlaces)),
        "timestamp_extraccion": ahora or datetime.now().isoformat(timespec="seconds"),
        "Fundación Glocal?": "Fundación Glocal" if es_fundacion else "",
        "Consultora": "0" if es_fundacion else "",
    }
    for faltante in ("titulo", "url_noticia", "wp_id"):
        if not fila[faltante]:
            problemas.append(faltante)
    return fila, problemas


# ============================================================================ descarga
@dataclass
class ResultadoFuente:
    fuente: str
    items: list[dict[str, str]] = field(default_factory=list)
    modo: str = "api"                      # "api" (completo) | "html" (reducido)
    total_web: int | None = None
    error: str = ""
    avisos: list[str] = field(default_factory=list)
    n_campos_vacios: int = 0

    @property
    def ok(self) -> bool:
        return not self.error

    @property
    def completo(self) -> bool:
        """True si trae TODO el catálogo de la fuente (solo así tiene sentido el «solo en la base»)."""
        return self.ok and self.modo == "api" and (self.total_web is None or self.total_web == len(self.items))


Progreso = Callable[[str], None] | None


def descargar_api(fuente: FuenteWeb, sesion=None, progreso: Progreso = None) -> ResultadoFuente:
    sesion = sesion or crear_sesion()
    res = ResultadoFuente(fuente.clave)
    ahora = datetime.now().isoformat(timespec="seconds")
    pagina, total_paginas = 1, 1
    while pagina <= min(total_paginas, MAX_PAGINAS):
        if progreso:
            progreso(f"Descargando {fuente.nombre}: página {pagina} de {total_paginas}…")
        params = {"per_page": POR_PAGINA, "page": pagina, "_embed": "wp:featuredmedia", "_fields": fuente.campos_api}
        try:
            r = _get(sesion, fuente.api, params)
        except ErrorWeb as e:
            if pagina > 1 and "(400)" in str(e):      # WordPress responde 400 al pedir una página inexistente
                break
            raise
        datos = _json(r, fuente.clave)
        if not isinstance(datos, list):
            raise ErrorWeb(mensaje_de_error(ValueError(), fuente.clave), recuperable=True)
        if pagina == 1:
            try:
                res.total_web = int(r.headers.get("X-WP-Total", len(datos)))
                total_paginas = int(r.headers.get("X-WP-TotalPages", 1))
            except (TypeError, ValueError):
                total_paginas = 1
        if not datos:
            break
        for item in datos:
            fila, problemas = parsear_item(item, fuente, ahora)
            if "titulo" in problemas and "url_noticia" in problemas:
                res.avisos.append(f"Se omitió un elemento sin título ni enlace (ID {item.get('id', '?')}).")
                continue
            if problemas:
                res.n_campos_vacios += len(problemas)
                res.avisos.append(f"«{fila['titulo'][:50] or fila['url_noticia']}»: no se pudo leer {', '.join(sorted(set(problemas)))}; quedó vacío.")
            res.items.append(fila)
        pagina += 1
        if pagina <= min(total_paginas, MAX_PAGINAS):
            time.sleep(PAUSA_ENTRE_PAGINAS)
    return res


def _slug_de_url(url: str) -> str:
    return urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]


def parsear_listado_html(html: str, fuente: FuenteWeb) -> list[dict[str, str]]:
    """Tarjetas de un listado público: solo título, enlace, imagen y (si existe) fecha."""
    soup = BeautifulSoup(html, "html.parser")
    filas = []
    if fuente.clave == "fundacionglocal.org":
        tarjetas = soup.select('div.e-loop-item[data-elementor-type="loop-item"]') or soup.select("div.e-loop-item")
        for t in tarjetas:
            a = t.select_one("h2.elementor-heading-title a") or t.select_one("a[href]")
            if not a or not a.get("href"):
                continue
            img = t.select_one(".elementor-widget-image img")
            filas.append({"titulo": " ".join(a.get_text(" ").split()), "url": a["href"],
                          "imagen": (img.get("src") if img else "") or "", "fecha": ""})
    else:
        for t in soup.select("article.eael-grid-post"):
            a = t.select_one("h3.eael-entry-title a") or t.select_one("a[href]")
            if not a or not a.get("href"):
                continue
            img = t.select_one(".eael-entry-thumbnail img")
            tiempo = t.select_one("time")
            fecha = (tiempo.get_text(strip=True) if tiempo else "")
            filas.append({"titulo": " ".join(a.get_text(" ").split()), "url": a["href"],
                          "imagen": (img.get("src") if img else "") or "", "fecha": fecha})
    return filas


def descargar_html(fuente: FuenteWeb, sesion=None, progreso: Progreso = None) -> ResultadoFuente:
    """Respaldo: lee el listado público (campos mínimos). Para glocalminds.com solo la primera página
    (las siguientes se cargan con JavaScript)."""
    sesion = sesion or crear_sesion()
    res = ResultadoFuente(fuente.clave, modo="html")
    ahora = datetime.now().isoformat(timespec="seconds")
    es_fundacion = fuente.clave == "fundacionglocal.org"
    pagina = 1
    while pagina <= (MAX_PAGINAS if es_fundacion else 1):
        if progreso:
            progreso(f"Leyendo el listado de {fuente.nombre} (página {pagina})…")
        url = fuente.listado if pagina == 1 else f"{fuente.listado.rstrip('/')}/{pagina}/"
        tarjetas = parsear_listado_html(_get(sesion, url).text, fuente)
        if not tarjetas:
            break
        for t in tarjetas:
            res.items.append({
                "titulo": t["titulo"], "titulo_catalogo": t["titulo"], "url_noticia": t["url"],
                "slug": _slug_de_url(t["url"]), "fuente": fuente.clave,
                "imagen_principal_url": t["imagen"], "fecha_publicacion_web": t["fecha"],
                "timestamp_extraccion": ahora,
                "Fundación Glocal?": "Fundación Glocal" if es_fundacion else "",
                "Consultora": "0" if es_fundacion else "",
            })
        pagina += 1
        time.sleep(PAUSA_ENTRE_PAGINAS)
    res.avisos.append(
        "La API del sitio no respondió y se usó el listado público: solo se trajeron título, enlace e imagen "
        "(el resto de los campos quedó vacío)." + ("" if es_fundacion else " De glocalminds.com solo se ven las más recientes."))
    return res


def descargar(clave: str, sesion=None, progreso: Progreso = None) -> ResultadoFuente:
    """Descarga una fuente. Nunca lanza: los problemas quedan en `resultado.error` (en español)."""
    fuente = FUENTES_WEB[clave]
    sesion = sesion or crear_sesion()
    try:
        return descargar_api(fuente, sesion, progreso)
    except ErrorWeb as e:
        if not e.recuperable:
            return ResultadoFuente(clave, error=str(e))
        motivo = str(e)
    try:
        res = descargar_html(fuente, sesion, progreso)
        res.avisos.insert(0, f"Falló la API ({motivo})")
        if not res.items:
            res.error = f"No se pudieron leer noticias de {fuente.nombre}: {motivo}"
        return res
    except ErrorWeb as e2:
        return ResultadoFuente(clave, error=str(e2))
    except Exception as e2:  # noqa: BLE001
        return ResultadoFuente(clave, error=mensaje_de_error(e2, fuente.clave))


def descargar_uno(clave: str, wp_id: str, sesion=None) -> tuple[dict[str, str] | None, str]:
    """Una sola noticia por su ID de WordPress. Devuelve (fila, error)."""
    fuente = FUENTES_WEB[clave]
    sesion = sesion or crear_sesion()
    try:
        r = _get(sesion, f"{fuente.api}/{wp_id}", {"_embed": "wp:featuredmedia", "_fields": fuente.campos_api})
        item = _json(r, clave)
        fila, _ = parsear_item(item, fuente)
        return fila, ""
    except ErrorWeb as e:
        return None, str(e)


# ============================================================================ diferencial
@dataclass
class Diferencial:
    nuevas: list[dict] = field(default_factory=list)        # {"fila", "nota", "sospechosa"}
    url_cambio: list[dict] = field(default_factory=list)    # {"id_evento","titulo","fuente","antes","despues","fila"}
    modificadas: list[dict] = field(default_factory=list)   # {"id_evento","titulo","fuente","campos":[...],"fila"}
    wp_pendientes: list[dict] = field(default_factory=list)  # {"id_evento","wp_id","fuente"}
    solo_en_bd: list[dict] = field(default_factory=list)    # {"id_evento","titulo","fuente","url"}

    @property
    def sin_diferencias(self) -> bool:
        """Nada que agregar ni actualizar (los IDs de WordPress pendientes se completan aparte)."""
        return not (self.nuevas or self.url_cambio or self.modificadas)

    @property
    def n_total(self) -> int:
        return len(self.nuevas) + len(self.url_cambio) + len(self.modificadas) + len(self.wp_pendientes)


def _fecha(texto) -> datetime | None:
    return parse_fecha(a_texto(texto)) if texto else None


def _sin_espacios(t: str) -> str:
    return re.sub(r"\s+", "", t or "")


def calcular_diferencias(resultados: list[ResultadoFuente], base: list[dict]) -> Diferencial:
    """Compara lo descargado con la base (filas en texto canónico).

    - nueva: no coincide con nada (o coincide solo por título: se marca «sospechosa»).
    - url_cambio: misma noticia (mismo título, fuente y fecha) cuyo enlace/slug cambió en la web.
    - modificada: coincide y la web la modificó después de lo que tenemos; solo se listan los campos
      cuyo texto realmente difiere (ignorando espacios).
    - wp_pendientes: noticia existente sin ID de WordPress que ahora se puede completar.
    - solo_en_bd: filas de una fuente descargada COMPLETA que ya no aparecen en la web.
    """
    por_id = {str(f["id_evento"]): f for f in base}
    indice = dedupe.Indice(base)
    dif = Diferencial()
    usadas: set[str] = set()
    fuentes_completas: set[str] = set()

    for res in resultados:
        if not res.ok:
            continue
        if res.completo:
            fuentes_completas.add(res.fuente)
        for fila in res.items:
            coin = indice.buscar(fila)
            seguras = [c for c in coin if c.segura and c.id_evento not in usadas]
            if seguras:
                c = seguras[0]
                usadas.add(c.id_evento)
                _comparar_existente(dif, por_id[c.id_evento], fila, c)
                continue
            if any(c.segura for c in coin):          # ya emparejada con otra fila web (repetida en la web)
                continue
            mismos = [c for c in coin if c.nivel == dedupe.NIVEL_TITULO and not c.entre_fuentes
                      and c.id_evento not in usadas]
            candidato = None
            for c in mismos:
                fila_bd = por_id[c.id_evento]
                f_web, f_bd = _fecha(fila.get("fecha_publicacion_web")), _fecha(fila_bd.get("fecha_publicacion_web"))
                if f_web and f_bd and f_web.date() == f_bd.date() and not (fila_bd.get("wp_id") or "").strip():
                    candidato = fila_bd
                    break
            if candidato is not None:
                usadas.add(candidato["id_evento"])
                dif.url_cambio.append({
                    "id_evento": candidato["id_evento"], "titulo": candidato["titulo"], "fuente": fila["fuente"],
                    "antes": candidato["url_noticia"], "despues": fila["url_noticia"], "fila": fila,
                    "slug_antes": candidato.get("slug", ""),
                })
                continue
            nota = ""
            if coin:
                c = coin[0]
                nota = (f"Mismo título que {c.id_evento}" + (" (otra fuente)" if c.entre_fuentes else "")
                        + ": revisa si es un evento distinto.")
            dif.nuevas.append({"fila": fila, "nota": nota, "sospechosa": bool(coin)})

    for f in base:
        if f.get("fuente") in fuentes_completas and f["id_evento"] not in usadas:
            dif.solo_en_bd.append({"id_evento": f["id_evento"], "titulo": f["titulo"], "fuente": f["fuente"],
                                   "url": f["url_noticia"]})
    dif.nuevas.sort(key=lambda n: n["fila"].get("fecha_publicacion_web", ""), reverse=True)
    return dif


def _comparar_existente(dif: Diferencial, fila_bd: dict, fila_web: dict, c: dedupe.Coincidencia) -> None:
    ide, titulo = fila_bd["id_evento"], fila_bd["titulo"]
    if not (fila_bd.get("wp_id") or "").strip() and fila_web.get("wp_id"):
        dif.wp_pendientes.append({"id_evento": ide, "wp_id": fila_web["wp_id"], "fuente": fila_web["fuente"]})
    if (c.nivel == dedupe.NIVEL_WP_ID
            and dedupe.normalizar_url(fila_bd.get("url_noticia")) != dedupe.normalizar_url(fila_web.get("url_noticia"))):
        dif.url_cambio.append({"id_evento": ide, "titulo": titulo, "fuente": fila_web["fuente"],
                               "antes": fila_bd["url_noticia"], "despues": fila_web["url_noticia"],
                               "fila": fila_web, "slug_antes": fila_bd.get("slug", "")})
    mod_web, mod_bd = _fecha(fila_web.get("fecha_modificacion_web")), _fecha(fila_bd.get("fecha_modificacion_web"))
    if mod_web and (mod_bd is None or mod_web.date() > mod_bd.date()):
        campos = diferencias_de_fila(fila_bd, fila_web)
        if campos:
            dif.modificadas.append({"id_evento": ide, "titulo": titulo, "fuente": fila_web["fuente"],
                                    "campos": campos, "fila": fila_web})


def diferencias_de_fila(fila_bd: dict, fila_web: dict) -> list[dict]:
    """Campos que la web tiene distintos a la base: [{campo, antes, despues}].

    Compara ignorando espacios (el texto antiguo tenía palabras pegadas) y solo propone valores que la
    web trae. Si hay diferencias, agrega también la fecha de modificación de la web.
    """
    campos = []
    for campo in CAMPOS_ACTUALIZABLES:
        nuevo, actual = fila_web.get(campo, ""), fila_bd.get(campo, "")
        if nuevo and _sin_espacios(nuevo) != _sin_espacios(actual):
            campos.append({"campo": campo, "antes": actual, "despues": nuevo})
    if campos and fila_web.get("fecha_modificacion_web"):
        campos.append({"campo": "fecha_modificacion_web", "antes": fila_bd.get("fecha_modificacion_web", ""),
                       "despues": fila_web["fecha_modificacion_web"]})
    return campos


# ---------------------------------------------------------------- de selección a cambios
def cambios_wp_id(item: dict) -> list[Cambio]:
    return [Cambio(item["id_evento"], "wp_id", "", item["wp_id"])]


def cambios_url(item: dict) -> list[Cambio]:
    f, ide = item["fila"], item["id_evento"]
    cambios = [Cambio(ide, "url_noticia", item["antes"], item["despues"])]
    if f.get("slug"):
        cambios.append(Cambio(ide, "slug", item.get("slug_antes", ""), f["slug"]))
    if f.get("wp_id"):
        cambios.append(Cambio(ide, "wp_id", "", f["wp_id"]))
    return cambios


def cambios_modificada(item: dict) -> list[Cambio]:
    return [Cambio(item["id_evento"], c["campo"], c["antes"], c["despues"]) for c in item["campos"]]
