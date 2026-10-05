# -*- coding: utf-8 -*-
from datetime import datetime

import openpyxl
import pytest

from utils import schema as S
from utils import validation as V
from utils.completitud import NIVEL_BASICA, NIVEL_COMPLETA, NIVEL_PARCIAL, calcular, campo_completo


# ----------------------------------------------------------------------------- esquema
def test_registro_coincide_con_hoja_original(semilla):
    wb = openpyxl.load_workbook(semilla, read_only=True)
    cab = [c for c in next(wb["Base_Datos"].iter_rows(values_only=True)) if c]
    wb.close()
    assert tuple(cab) == S.COLUMNAS[:49]
    assert S.COLUMNAS[49:] == S.COLUMNAS_NUEVAS == S.COLUMNAS_SISTEMA + ("carpeta_proyecto", "documentos_proyecto")
    assert len(S.COLUMNAS) == 57 == len(set(S.COLUMNAS))


def test_obligatorios_y_campos_clave():
    assert set(S.OBLIGATORIOS) == {"titulo", "url_noticia", "fuente"}
    assert len(S.CLAVE_CONTENIDO_CAMPOS) == 6
    assert len(S.CLAVE_ANALISIS_CAMPOS) == 8
    assert "id_evento" not in {c.key for c in S.CAMPOS if c.editable}
    assert all(c.tipo in S.TIPO_NOMBRE for c in S.CAMPOS)


def test_etiquetas_helpers():
    assert S.dividir_etiquetas("a;b ; c;;a") == ["a", "b", "c"]
    assert S.unir_etiquetas(["a", "b", "a"]) == "a; b"
    assert S.opciones_de("tipo_informacion", ["x", "y", "x", None, "nan"]) == ["x", "y"]
    assert S.opciones_de("categoria_macro", catalogo={"categoria_macro": ["b", "A"]}) == ["A", "b"]


# ----------------------------------------------------------------------------- fechas
@pytest.mark.parametrize("texto,esperado", [
    ("2026-07-12", datetime(2026, 7, 12)),
    ("2026-07-12T14:54:37.771978", datetime(2026, 7, 12, 14, 54, 37)),
    ("2026-07-12 14:54:37", datetime(2026, 7, 12, 14, 54, 37)),
    ("12/07/2026", datetime(2026, 7, 12)),
    ("12.07.2026", datetime(2026, 7, 12)),
    ("11 de julio de 2026", datetime(2026, 7, 11)),
    ("1 de Septiembre de 2019", datetime(2019, 9, 1)),
    ("17 de hasta de 2019", None),        # basura real del Excel
    ("16 de y de 2017", None),
    ("31/02/2026", None),
    ("", None),
    (None, None),
])
def test_parse_fecha(texto, esperado):
    assert V.parse_fecha(texto) == esperado


# ----------------------------------------------------------------------------- texto <-> tipo
def test_a_texto_canonico():
    assert V.a_texto(None) == ""
    assert V.a_texto(float("nan")) == ""
    assert V.a_texto(4.0, S.ENTERO) == "4"
    assert V.a_texto(0) == "0" and V.a_texto("0") == "0"      # Consultora mezcla 0 (int) y '0' (str)
    assert V.a_texto(datetime(2026, 7, 12)) == "2026-07-12"
    assert V.a_texto(datetime(2026, 7, 12, 9, 30)) == "2026-07-12 09:30:00"
    assert V.a_texto(True) == "True"
    assert V.a_texto("  hola \n") == "hola"


def test_de_texto_tipado():
    assert V.de_texto("", S.ENTERO) is None
    assert V.de_texto("12", S.ENTERO) == 12
    assert V.de_texto("2026-07-12", S.FECHA) == datetime(2026, 7, 12)
    assert V.de_texto("sí", S.BOOLEANO) is True
    assert V.de_texto("False", S.BOOLEANO) is False
    assert V.de_texto("abc", S.ENTERO) == "abc"               # no convertible: se conserva el texto


# ----------------------------------------------------------------------------- normalización
def test_normalizar_url():
    c = S.CAMPO["url_noticia"]
    assert V.normalizar("glocalminds.com/catalogo/x/", c) == ("https://glocalminds.com/catalogo/x/", [])
    _, av = V.normalizar("http://a b.com", c)
    assert av and "espacios" in av[0]
    _, av = V.normalizar("no es url", c)
    assert av


def test_normalizar_fecha_y_entero_y_bool():
    f = S.CAMPO["fecha_publicacion_web"]
    assert V.normalizar("11 de julio de 2026", f) == ("2026-07-11", [])
    texto, av = V.normalizar("mañana", f)
    assert texto == "mañana" and av
    _, av = V.normalizar("1900-01-01", f)
    assert av and "fuera de rango" in av[0]
    assert V.normalizar("4.0", S.CAMPO["num_enlaces_externos"]) == ("4", [])
    assert V.normalizar("x", S.CAMPO["num_enlaces_externos"])[1]
    assert V.normalizar("sí", S.CAMPO["es_duplicado_secundario"]) == ("True", [])


def test_normalizar_etiquetas_con_opciones():
    c = S.CAMPO["categoria_macro"]
    texto, av = V.normalizar("A;B ; A", c, opciones=["A", "B"])
    assert texto == "A; B" and av == []
    _, av = V.normalizar("Z", c, opciones=["A"])
    assert av and "fuera de las opciones" in av[0]
    _, av = V.normalizar("No aplica", c, opciones=["A"])
    assert av == []


def test_validar_fila_solo_bloquea_obligatorios():
    fila, errores, avisos = V.validar_fila({"titulo": "T", "url_noticia": "x.cl/a", "fuente": "glocalminds.com",
                                            "fecha_publicacion_web": "rara"})
    assert errores == []
    assert fila["url_noticia"] == "https://x.cl/a"
    assert any("fecha" in a.lower() for a in avisos)
    _, errores, _ = V.validar_fila({"titulo": "T"})
    assert len(errores) == 2                                    # faltan url_noticia y fuente
    _, errores, avisos = V.validar_fila({"titulo": "T"}, requerir_obligatorios=False)
    assert errores == [] and any("recomienda" in a for a in avisos)


# ----------------------------------------------------------------------------- completitud
def _fila(n_contenido=0, n_analisis=0):
    fila = {}
    for k in S.CLAVE_CONTENIDO_CAMPOS[:n_contenido]:
        fila[k] = "x"
    for k in S.CLAVE_ANALISIS_CAMPOS[:n_analisis]:
        fila[k] = "x"
    return fila


@pytest.mark.parametrize("nc,na,pct,nivel", [
    (0, 0, 0.0, NIVEL_BASICA),
    (6, 0, 42.9, NIVEL_BASICA),            # noticia recién sincronizada
    (6, 1, 50.0, NIVEL_PARCIAL),
    (6, 5, 78.6, NIVEL_PARCIAL),
    (6, 6, 85.7, NIVEL_COMPLETA),          # 12 de 14
    (6, 8, 100.0, NIVEL_COMPLETA),
])
def test_completitud_umbrales(nc, na, pct, nivel):
    r = calcular(_fila(nc, na))
    assert r.pct == pct and r.nivel == nivel and r.n_total == 14


def test_completitud_valores_especiales():
    assert campo_completo("No aplica") is True                # codificación deliberada
    assert campo_completo("No especificado") is False
    assert campo_completo("Sin dato") is False
    assert campo_completo("No especificado; Sin dato") is False
    assert campo_completo("No especificado; Art of Hosting") is True
    assert campo_completo(float("nan")) is False
    fila = _fila(6, 8)
    fila.pop("actores_normalizados")
    assert calcular(fila).pct < 100
    fila["actores"] = "ONU"                                    # alternativa equivalente
    assert calcular(fila).pct == 100.0
