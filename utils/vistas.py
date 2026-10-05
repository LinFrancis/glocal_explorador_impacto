# -*- coding: utf-8 -*-
"""Presentación de datos de gestión (historial, fechas relativas, bandeja de trabajo).

Solo transforma DataFrames: no escribe nada ni depende de la interfaz, así se puede probar sola.
"""
from __future__ import annotations

import json
from datetime import datetime

import pandas as pd

from utils import completitud
from utils import schema as S

REGISTRO = "(registro completo)"      # mismo valor que utils.repo.REGISTRO (se repite para no importar repo)


def parse_ts(ts) -> datetime | None:
    try:
        return datetime.fromisoformat(str(ts).replace(" ", "T")) if ts else None
    except ValueError:
        return None


def hace_cuanto(ts, ahora: datetime | None = None) -> str:
    """'2026-10-05T14:00:00' -> 'hace 3 horas' / 'ayer' / 'hace 12 días'. '' si no hay fecha."""
    dt = parse_ts(ts)
    if dt is None:
        return ""
    # Resta de fechas "de pared" (sin .timestamp()): no se desfasa con el cambio de horario.
    seg = ((ahora or datetime.now()) - dt).total_seconds()
    if seg < 60:
        return "hace un momento"
    if seg < 3600:
        m = int(seg // 60)
        return f"hace {m} minuto{'s' if m != 1 else ''}"
    if seg < 86400:
        h = int(seg // 3600)
        return f"hace {h} hora{'s' if h != 1 else ''}"
    dias = int(seg // 86400)
    if dias == 1:
        return "ayer"
    if dias < 60:
        return f"hace {dias} días"
    meses = dias // 30
    return f"hace {meses} meses" if meses < 24 else f"hace {dias // 365} años"


def dias_desde(ts, ahora: datetime | None = None) -> int | None:
    dt = parse_ts(ts)
    if dt is None:
        return None
    return max(0, ((ahora or datetime.now()) - dt).days)


def fecha_corta(ts) -> str:
    dt = parse_ts(ts)
    return dt.strftime("%d-%m-%Y %H:%M") if dt else ""


def _corto(texto: str, n: int = 60) -> str:
    texto = " ".join(str(texto).split())
    return texto if len(texto) <= n else texto[: n - 1] + "…"


def _titulo_de_snapshot(valor: str) -> str:
    try:
        return str(json.loads(valor).get("titulo", ""))
    except (ValueError, AttributeError):
        return ""


def historial_legible(hist: pd.DataFrame, base: pd.DataFrame) -> pd.DataFrame:
    """Historial listo para mostrar: fecha, quién, acción, noticia (título) y detalle antes → después."""
    cols = ["Fecha", "Quién", "Acción", "Noticia", "Campo", "Antes", "Después", "Detalle", "id_cambio", "id_evento", "lote_id"]
    if hist.empty:
        return pd.DataFrame(columns=cols)
    titulos = dict(zip(base["id_evento"], base["titulo"])) if len(base) else {}
    filas = []
    for e in hist.to_dict("records"):
        campo = e["campo"]
        es_registro = campo == REGISTRO
        titulo = titulos.get(e["id_evento"]) or _titulo_de_snapshot(e["valor_despues"] or e["valor_antes"]) or e["id_evento"]
        if es_registro:
            detalle = "Noticia agregada" if not e["valor_antes"] else "Noticia retirada"
            etq, antes, despues = "(noticia completa)", "", ""
        else:
            etq, antes, despues = S.etiqueta(campo), e["valor_antes"], e["valor_despues"]
            detalle = f"{etq}: «{_corto(antes, 40)}» → «{_corto(despues, 40)}»"
        filas.append({
            "Fecha": fecha_corta(e["fecha_hora"]), "Quién": e["usuario"],
            "Acción": S.ACCION_NOMBRE.get(e["accion"], e["accion"]), "Noticia": _corto(titulo, 70),
            "Campo": etq, "Antes": antes, "Después": despues, "Detalle": detalle,
            "id_cambio": e["id_cambio"], "id_evento": e["id_evento"], "lote_id": e["lote_id"],
        })
    return pd.DataFrame(filas, columns=cols)


def bandeja_de_trabajo(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Las `n` noticias con menor completitud (sin duplicados secundarios), con lo que les falta."""
    base = df
    if "es_duplicado_secundario" in base.columns:
        base = base[~base["es_duplicado_secundario"].astype(bool)]
    if base.empty:
        return pd.DataFrame(columns=["id_evento", "titulo", "fuente", "anio", "completitud", "faltan", "n_faltan"])
    orden = base.assign(_f=base["fecha_parsed"]).sort_values(["completitud", "_f"], ascending=[True, False]).head(n)
    filas = []
    for _, r in orden.iterrows():
        faltan = completitud.calcular(r).faltan
        filas.append({
            "id_evento": r["id_evento"], "titulo": r["titulo"], "fuente": r.get("fuente", ""),
            "anio": int(r["anio"]) if pd.notna(r.get("anio")) else None,
            "completitud": float(r["completitud"]), "faltan": ", ".join(S.etiqueta(k) for k in faltan),
            "n_faltan": len(faltan),
        })
    return pd.DataFrame(filas)


def niveles_de_completitud(df: pd.DataFrame) -> pd.DataFrame:
    """Conteo de noticias por nivel (Completa / Parcial / Básica), siempre con los 3 niveles."""
    niv = completitud.nivel_df(df["completitud"]).value_counts() if len(df) else pd.Series(dtype=int)
    return pd.DataFrame({"Nivel": list(completitud.NIVELES),
                         "Noticias": [int(niv.get(n, 0)) for n in completitud.NIVELES]})
