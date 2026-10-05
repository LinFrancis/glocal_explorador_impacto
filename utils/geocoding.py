# -*- coding: utf-8 -*-
"""Geocodificación de los lugares de una noticia con Nominatim (OpenStreetMap).

Rellena `sitios_lat`, `sitios_lon`, `sitios_pais` y `sitios_precision_geocodificacion` como listas
paralelas a `lugar` (un elemento por sitio, separados por ';'), con la misma convención de los datos
existentes: precision = «completo» (la dirección completa se encontró), «simplificado(-N)» (hubo que
quitar los N primeros segmentos de la dirección), «online» (modalidad sin lugar físico) o
«sin_dato» (no se encontró). La cuenca hidrográfica NO se completa aquí: requiere un cruce espacial
con la geometría BNA/DGA, que no está en el repositorio.

Política de uso de Nominatim: máximo 1 consulta por segundo y User-Agent identificable. Solo se envía
el texto del lugar. No importa Streamlit.
"""
from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import requests

NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "ImpactoGlocalGestor/1.0 (herramienta interna de gestión de noticias)"
INTERVALO = 1.1            # segundos entre consultas (política de uso: máx. 1/s)
TIMEOUT = (6, 20)
MAX_RECORTES = 3           # cuántos segmentos iniciales se pueden quitar al simplificar

_RE_ONLINE = re.compile(r"\b(online|en l[ií]nea|virtual|a distancia|sin pa[ií]s espec[ií]fico|no especificado)\b", re.I)
_candado = threading.Lock()
_ultima_consulta = 0.0
_cache: dict[str, dict | None] = {}


class ErrorGeocodificacion(Exception):
    """Fallo del servicio; el mensaje está en español y se muestra tal cual."""


@dataclass
class Sitio:
    lugar: str
    lat: str = ""
    lon: str = ""
    pais: str = ""
    precision: str = ""
    nombre_osm: str = ""

    @property
    def encontrado(self) -> bool:
        return bool(self.lat and self.lon)


@dataclass
class Resultado:
    valores: dict[str, str] = field(default_factory=dict)       # columnas listas para guardar
    sitios: list[Sitio] = field(default_factory=list)
    n_nuevos: int = 0
    n_fallidos: int = 0


def es_online(texto: str) -> bool:
    return bool(_RE_ONLINE.search(texto or ""))


def _esperar_turno() -> None:
    """Garantiza el intervalo mínimo entre consultas aunque haya varias sesiones a la vez."""
    global _ultima_consulta
    with _candado:
        espera = INTERVALO - (time.monotonic() - _ultima_consulta)
        if espera > 0:
            time.sleep(espera)
        _ultima_consulta = time.monotonic()


def consultar(texto: str, sesion=None) -> dict | None:
    """Una consulta (con caché). Devuelve el primer resultado de Nominatim o None si no hay."""
    clave = " ".join(texto.lower().split())
    if clave in _cache:
        return _cache[clave]
    sesion = sesion or requests
    _esperar_turno()
    try:
        r = sesion.get(NOMINATIM, params={"q": texto, "format": "jsonv2", "addressdetails": 1, "limit": 1,
                                          "accept-language": "es"},
                       headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    except requests.exceptions.Timeout as e:
        raise ErrorGeocodificacion("El servicio de mapas (OpenStreetMap) tardó demasiado en responder.") from e
    except requests.exceptions.RequestException as e:
        raise ErrorGeocodificacion("No hay conexión con el servicio de mapas (OpenStreetMap).") from e
    if r.status_code in (403, 429):
        raise ErrorGeocodificacion("El servicio de mapas rechazó las consultas por límite de uso. Espera unos minutos.")
    if r.status_code >= 400:
        raise ErrorGeocodificacion(f"El servicio de mapas respondió con un error ({r.status_code}).")
    try:
        datos = r.json()
    except ValueError as e:
        raise ErrorGeocodificacion("El servicio de mapas devolvió una respuesta que no se pudo interpretar.") from e
    resultado = datos[0] if isinstance(datos, list) and datos else None
    _cache[clave] = resultado
    return resultado


def geocodificar_lugar(lugar: str, sesion=None) -> Sitio:
    """Coordenadas de un lugar. Si la dirección completa no se encuentra, se quitan segmentos iniciales."""
    lugar = " ".join((lugar or "").split())
    if not lugar:
        return Sitio("", precision="sin_dato")
    if es_online(lugar):
        return Sitio(lugar, precision="online")
    segmentos = [s.strip() for s in lugar.split(",") if s.strip()]
    for recortados in range(0, min(MAX_RECORTES, max(0, len(segmentos) - 1)) + 1):
        consulta = ", ".join(segmentos[recortados:])
        hallado = consultar(consulta, sesion)
        if hallado:
            pais = (hallado.get("address") or {}).get("country", "")
            return Sitio(
                lugar, f"{float(hallado['lat']):.6f}", f"{float(hallado['lon']):.6f}", pais,
                "completo" if recortados == 0 else f"simplificado(-{recortados})", hallado.get("display_name", ""),
            )
    return Sitio(lugar, precision="sin_dato")


def _partes(texto: str, n: int) -> list[str]:
    partes = [p.strip() for p in (texto or "").split(";")]
    return (partes + [""] * n)[:n] if len(partes) < n else partes[:n]


def completar(lugar: str, lat: str = "", lon: str = "", pais: str = "", precision: str = "", sesion=None,
              solo_faltantes: bool = True, progreso: Callable[[str], None] | None = None) -> Resultado:
    """Geocodifica cada elemento de `lugar` (separados por ';') y devuelve las 4 columnas alineadas.

    solo_faltantes: respeta los sitios que ya tienen coordenadas (incluidas las corregidas a mano).
    """
    lugares = [p.strip() for p in (lugar or "").split(";") if p.strip()]
    n = len(lugares)
    lats, lons, paises, precs = (_partes(x, n) for x in (lat, lon, pais, precision))
    res = Resultado()
    for i, lg in enumerate(lugares):
        ya = bool(lats[i] and lons[i])
        if solo_faltantes and (ya or precs[i] in ("online", "corregido_manual")):
            res.sitios.append(Sitio(lg, lats[i], lons[i], paises[i], precs[i]))
            continue
        if progreso:
            progreso(f"Buscando «{lg[:50]}» ({i + 1} de {n})…")
        s = geocodificar_lugar(lg, sesion)
        res.sitios.append(s)
        lats[i], lons[i], paises[i], precs[i] = s.lat, s.lon, s.pais, s.precision
        if s.encontrado:
            res.n_nuevos += 1
        elif s.precision != "online":
            res.n_fallidos += 1
    res.valores = {
        "sitios_lat": ";".join(lats), "sitios_lon": ";".join(lons),
        "sitios_pais": ";".join(paises), "sitios_precision_geocodificacion": ";".join(precs),
    }
    return res
