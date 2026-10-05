# -*- coding: utf-8 -*-
"""Conversión y validación por tipo de variable.

Dos responsabilidades:
1. Conversión texto <-> valor tipado (`a_texto` / `de_texto`). Toda comparación de celdas
   (diferencias, historial) se hace sobre la forma de texto canónica, así una celda sin
   cambios nunca aparece como modificada por diferencias de formato (0 vs "0", 4.0 vs 4...).
2. Validación NO invasiva (`normalizar`): normaliza lo que se puede y devuelve avisos. El único
   bloqueo es que falte un campo obligatorio al crear un registro (`validar_fila`).
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime
from urllib.parse import urlparse

from utils import schema as S

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
_RE_ES = re.compile(r"^\s*(\d{1,2})\s+de\s+([a-záéíóúñ]+)\s+de\s+(\d{4})\s*$", re.IGNORECASE)
_RE_ISO = re.compile(r"^\s*(\d{4})-(\d{1,2})-(\d{1,2})(?:[T ](\d{1,2}):(\d{2})(?::(\d{2}))?(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?\s*$")
_RE_DMY = re.compile(r"^\s*(\d{1,2})[./-](\d{1,2})[./-](\d{4})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?\s*$")
_RE_YMD_SLASH = re.compile(r"^\s*(\d{4})/(\d{1,2})/(\d{1,2})\s*$")

ANIO_MIN = 1990
VERDADEROS = {"true", "1", "sí", "si", "x", "verdadero", "yes"}
FALSOS = {"false", "0", "no", "falso", ""}


# ----------------------------------------------------------------------------- fechas
def parse_fecha(texto) -> datetime | None:
    """Acepta ISO, dd/mm/aaaa, dd.mm.aaaa, aaaa/mm/dd y 'D de mes de AAAA'. None si no se reconoce."""
    if texto is None:
        return None
    if isinstance(texto, datetime):
        return texto
    if isinstance(texto, date):
        return datetime(texto.year, texto.month, texto.day)
    s = str(texto).strip()
    if not s:
        return None
    try:
        m = _RE_ISO.match(s)
        if m:
            y, mo, d, hh, mm, ss = m.groups()
            return datetime(int(y), int(mo), int(d), int(hh or 0), int(mm or 0), int(ss or 0))
        m = _RE_DMY.match(s)
        if m:
            d, mo, y, hh, mm, ss = m.groups()
            return datetime(int(y), int(mo), int(d), int(hh or 0), int(mm or 0), int(ss or 0))
        m = _RE_YMD_SLASH.match(s)
        if m:
            y, mo, d = m.groups()
            return datetime(int(y), int(mo), int(d))
        m = _RE_ES.match(s)
        if m:
            d, mes, y = m.groups()
            mes_n = MESES.get(mes.lower())
            if mes_n:
                return datetime(int(y), mes_n, int(d))
    except ValueError:  # fecha imposible (31 de febrero...)
        return None
    return None


def parse_numero(texto) -> float | int | None:
    """'12', '12.5', '12,5', '1.234,5' -> número. None si no es un número. Devuelve int si es entero."""
    s = str(texto if texto is not None else "").strip().replace(" ", "")
    if not s:
        return None
    if "," in s and "." in s:                                  # «1.234,5» (miles con punto, decimal con coma)
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        n = float(s)
    except ValueError:
        return None
    if math.isnan(n) or math.isinf(n):
        return None
    return int(n) if n.is_integer() and abs(n) < 1e15 else n


# ----------------------------------------------------------------------------- texto <-> tipo
def a_texto(valor, tipo: str | None = None) -> str:
    """Forma de texto canónica de un valor de celda."""
    if valor is None or type(valor).__name__ == "NaTType":
        return ""
    if isinstance(valor, float):
        if math.isnan(valor):
            return ""
        if valor.is_integer() and tipo in (S.ENTERO, S.NUMERO, S.TEXTO, S.OPCION, None):
            return str(int(valor))
        return f"{valor:.15g}"
    if isinstance(valor, bool):
        return "True" if valor else "False"
    if isinstance(valor, datetime):
        if valor.hour == valor.minute == valor.second == valor.microsecond == 0:
            return valor.strftime("%Y-%m-%d")
        return valor.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(valor, date):
        return valor.strftime("%Y-%m-%d")
    if hasattr(valor, "item") and not isinstance(valor, str):   # escalares de numpy/pandas
        try:
            return a_texto(valor.item(), tipo)
        except Exception:  # noqa: BLE001
            pass
    return str(valor).strip()


def de_texto(texto, tipo: str):
    """Valor tipado para escribir en una celda. Vacío -> None. Si no se puede convertir, texto."""
    s = a_texto(texto, tipo)
    if s == "":
        return None
    if tipo == S.ENTERO:
        try:
            return int(float(s))
        except ValueError:
            return s
    if tipo == S.NUMERO:
        n = parse_numero(s)
        return n if n is not None else s
    if tipo == S.FECHA:
        return parse_fecha(s) or s
    if tipo == S.BOOLEANO:
        low = s.lower()
        if low in VERDADEROS:
            return True
        if low in FALSOS:
            return False
        return s
    return s


# ----------------------------------------------------------------------------- normalización
def normalizar_url(texto: str) -> tuple[str, str | None]:
    """Devuelve (url normalizada, aviso). Antepone https:// si falta el esquema."""
    s = texto.strip()
    if not s:
        return "", None
    if " " in s:
        return s, "La URL contiene espacios."
    if not re.match(r"^[a-z][a-z0-9+.-]*://", s, re.IGNORECASE):
        if "." in s.split("/")[0] and not s.startswith("/"):
            s = "https://" + s
        else:
            return s, "No parece una URL válida (falta el dominio)."
    p = urlparse(s)
    if p.scheme not in ("http", "https"):
        return s, "La URL debería comenzar con http:// o https://."
    if not p.netloc or "." not in p.netloc:
        return s, "No parece una URL válida (dominio incompleto)."
    return s, None


def normalizar(texto, campo: S.Campo, opciones: list[str] | None = None) -> tuple[str, list[str]]:
    """Normaliza un valor (en texto) según el tipo del campo. Devuelve (texto, avisos)."""
    avisos: list[str] = []
    s = a_texto(texto, campo.tipo)
    if s == "":
        return "", avisos
    t = campo.tipo

    if t in (S.TEXTO, S.TEXTO_LARGO):
        return s, avisos

    if t in (S.URL, S.IMAGEN_URL):
        s, aviso = normalizar_url(s)
        if aviso:
            avisos.append(aviso)
        return s, avisos

    if t == S.LISTA_URL:
        partes = [p.strip() for p in re.split(r"[|\n]+", s) if p.strip()]       # «|» o un enlace por línea
        norm = []
        for p in partes:
            u, aviso = normalizar_url(p)
            if aviso:
                avisos.append(f"{p[:60]}: {aviso}")
            norm.append(u)
        return S.SEPARADOR_ENLACES.join(dict.fromkeys(norm)), avisos

    if t == S.FECHA:
        dt = parse_fecha(s)
        if dt is None:
            avisos.append(f"No se reconoce como fecha: «{s[:40]}». Usa AAAA-MM-DD o «11 de julio de 2026».")
            return s, avisos
        if dt.year < ANIO_MIN or dt > datetime.now().replace(year=datetime.now().year + 1):
            avisos.append(f"La fecha {dt:%Y-%m-%d} parece fuera de rango.")
        return a_texto(dt), avisos

    if t == S.FECHA_TEXTO:
        if parse_fecha(s) is None:
            avisos.append(f"El texto «{s[:40]}» no se reconoce como fecha.")
        return s, avisos

    if t == S.ENTERO:
        try:
            return str(int(float(s))), avisos
        except ValueError:
            avisos.append(f"«{s[:30]}» no es un número entero.")
            return s, avisos

    if t == S.NUMERO:
        n = parse_numero(s)
        if n is None:
            avisos.append(f"«{s[:30]}» no es un número.")
            return s, avisos
        return a_texto(n, S.NUMERO), avisos

    if t == S.BOOLEANO:
        low = s.lower()
        if low in VERDADEROS:
            return "True", avisos
        if low in FALSOS:
            return "False", avisos
        avisos.append(f"«{s[:30]}» no es Sí/No.")
        return s, avisos

    if t == S.OPCION:
        if opciones and s not in opciones:
            avisos.append(f"«{s[:40]}» no está entre las opciones habituales de «{campo.label}».")
        return s, avisos

    if t == S.ETIQUETAS:
        partes = S.dividir_etiquetas(s)
        if opciones:
            fuera = [p for p in partes if p not in opciones and p.lower() not in S.VALORES_NO_ETIQUETA]
            if fuera:
                avisos.append(f"Valores fuera de las opciones de «{campo.label}»: {', '.join(fuera[:3])}"
                              + ("…" if len(fuera) > 3 else "") + ".")
        return S.unir_etiquetas(partes), avisos

    if t == S.LISTA_NUMEROS:
        partes = [p.strip() for p in s.split(";") if p.strip()]
        for p in partes:
            try:
                float(p)
            except ValueError:
                avisos.append(f"«{p[:20]}» no es un número.")
                break
        return ";".join(partes), avisos

    if t == S.LISTA_TEXTO:
        return ";".join(p.strip() for p in s.split(";") if p.strip()), avisos

    return s, avisos


# ----------------------------------------------------------------------------- por fila
def validar_fila(fila: dict, requerir_obligatorios: bool = True,
                 opciones: dict[str, list[str]] | None = None) -> tuple[dict, list[str], list[str]]:
    """Valida y normaliza un registro completo (dict campo -> texto).

    Devuelve (fila_normalizada, errores, avisos). Solo son *errores* los obligatorios vacíos
    (si requerir_obligatorios); todo lo demás es aviso.
    """
    opciones = opciones or {}
    salida: dict[str, str] = {}
    errores: list[str] = []
    avisos: list[str] = []
    for key, valor in fila.items():
        c = S.CAMPO.get(key)
        if c is None:
            continue
        texto, av = normalizar(valor, c, opciones.get(key))
        salida[key] = texto
        avisos.extend(f"{c.label}: {a}" for a in av)
    if requerir_obligatorios:
        for key in S.OBLIGATORIOS:
            if not salida.get(key, "").strip():
                errores.append(f"Falta el campo obligatorio «{S.etiqueta(key)}».")
    if not salida.get("fecha_publicacion_web", "").strip():
        c = S.CAMPO["fecha_publicacion_web"]
        if c.recomendado:
            avisos.append(f"Se recomienda indicar «{c.label}».")
    return salida, errores, avisos
