# -*- coding: utf-8 -*-
import pandas as pd
import pytest

from tests.apptest_util import apuntar_a
from utils import data, repo, similares
from utils import schema as S

ANALISIS = {k: "x" for k in S.CLAVE_ANALISIS_CAMPOS}


def _fila(ide, palabras, analizada=True, titulo=None):
    f = {"id_evento": ide, "titulo": titulo or ide, "_palabras_busqueda": tuple(sorted(palabras))}
    if analizada:
        f.update(ANALISIS)
    return f


def test_ranking_por_vocabulario_ponderado():
    df = pd.DataFrame([
        _fila("N", ["agua", "cuenca", "territorio", "taller"], analizada=False),          # la noticia nueva
        _fila("A", ["agua", "cuenca", "territorio", "gobernanza"]),                      # muy parecida
        _fila("B", ["agua", "taller", "juventud", "escuela"]),                           # algo parecida
        _fila("C", ["musica", "danza", "festival"]),                                      # nada que ver
        _fila("D", ["agua", "cuenca", "territorio", "taller"], analizada=False),          # idéntica pero sin análisis
    ])
    r = similares.similares(df, "N", k=5)
    assert [x["id_evento"] for x in r] == ["A", "B"]                                      # C no comparte nada; D no está analizada
    assert r[0]["puntaje"] > r[1]["puntaje"] > 0 and r[0]["puntaje"] <= 100
    assert set(r[0]["comunes"]) == {"agua", "cuenca", "territorio"}


def test_palabras_raras_pesan_mas_que_las_comunes():
    comunes = [f"comun{i}" for i in range(3)]
    base = [_fila(f"R{i}", comunes + [f"unica{i}"]) for i in range(10)]                       # las 3 palabras son comunes en todos
    df = pd.DataFrame(base + [
        _fila("RARA", ["rarisima", "otra"]),
        _fila("OBJ", comunes + ["rarisima"], analizada=False),
    ])
    mejor = similares.similares(df, "OBJ", k=1)[0]
    assert mejor["id_evento"] == "RARA" or mejor["puntaje"] > 0
    ranking = [x["id_evento"] for x in similares.similares(df, "OBJ", k=12)]
    assert ranking.index("RARA") < ranking.index("R0")                                    # comparte la palabra más informativa


def test_excluye_la_propia_y_casos_borde():
    df = pd.DataFrame([_fila("A", ["agua"]), _fila("B", [], analizada=False)])
    assert similares.similares(df, "A") == []                                             # solo existe ella misma
    assert similares.similares(df, "B") == [] and similares.similares(df, "ZZ") == []     # sin vocabulario / id inexistente


def test_umbral_de_analisis():
    casi = _fila("P", ["agua", "cuenca"])
    for k in list(S.CLAVE_ANALISIS_CAMPOS)[: len(S.CLAVE_ANALISIS_CAMPOS) - similares.MIN_ANALISIS + 1]:
        casi[k] = ""                                                                      # solo 5 de 8 -> no cuenta
    ok = _fila("Q", ["agua", "cuenca"])
    df = pd.DataFrame([_fila("N", ["agua", "cuenca"], analizada=False), casi, ok])
    assert [x["id_evento"] for x in similares.similares(df, "N")] == ["Q"]


def test_clasificacion_copiable():
    fila = {"categoria_macro": "A; B", "categorias": " ", "metodologia": "Art of Hosting", "titulo": "t"}
    assert similares.clasificacion_de(fila) == {"categoria_macro": "A; B", "metodologia": "Art of Hosting"}


def test_con_datos_reales_encuentra_parecidas_coherentes(monkeypatch, almacen):
    apuntar_a(monkeypatch, almacen)
    df = data.load_noticias()
    nueva = repo.agregar_filas([{"titulo": "Taller de gobernanza del agua y cuencas en el territorio",
                                 "url_noticia": "https://glocalminds.com/catalogo/gobernanza-agua/", "fuente": "glocalminds.com",
                                 "contenido_completo": "Taller participativo sobre gobernanza del agua, cuencas hidrográficas y territorio"}],
                               "Ana", almacen=almacen).ids_creados[0]
    df = data.load_noticias()
    r = similares.similares(df, nueva, k=5)
    assert 1 <= len(r) <= 5 and all(x["id_evento"] != nueva and x["puntaje"] > 0 for x in r)
    assert [x["puntaje"] for x in r] == sorted((x["puntaje"] for x in r), reverse=True)
    assert any(w in " ".join(x["comunes"]) for x in r for w in ("agua", "cuencas", "territorio", "gobernanza"))
