# -*- coding: utf-8 -*-
import pytest

from utils import dedupe as D


def _base():
    return [
        {"id_evento": "EV0001", "fuente": "glocalminds.com", "wp_id": "100",
         "url_noticia": "https://glocalminds.com/catalogo/encuentro-imaginarural-en-valparaiso/",
         "slug": "encuentro-imaginarural-en-valparaiso", "titulo": "Encuentro ImaginaRural en Valparaíso"},
        {"id_evento": "EV0002", "fuente": "fundacionglocal.org", "wp_id": "",
         "url_noticia": "https://fundacionglocal.org/mingamar/", "slug": "mingamar", "titulo": "Mingamar"},
        {"id_evento": "EV0003", "fuente": "glocalminds.com", "wp_id": "",
         "url_noticia": "https://glocalminds.com/catalogo/otro/", "slug": "otro", "titulo": "Liderazgo participativo"},
        {"id_evento": "EV0004", "fuente": "glocalminds.com", "wp_id": "",
         "url_noticia": "https://glocalminds.com/catalogo/otro-2/", "slug": "otro-2", "titulo": "Liderazgo Participativo!"},
    ]


def test_normalizaciones():
    assert D.normalizar_titulo("  Líderes climáticos: ¡Al Gore! ") == "lideres climaticos al gore"
    assert D.normalizar_url("HTTP://www.Glocalminds.com/catalogo/x/?utm=1#a") == "glocalminds.com/catalogo/x"
    assert D.normalizar_url("glocalminds.com/catalogo/x") == "glocalminds.com/catalogo/x"
    assert D.normalizar_url("") == ""


def test_nivel1_wp_id():
    idx = D.Indice(_base())
    m = idx.buscar({"fuente": "glocalminds.com", "wp_id": "100.0", "url_noticia": "https://otra.cl/", "slug": "z", "titulo": "Zzz"})
    assert [c.nivel for c in m] == [1] and m[0].segura
    # el mismo id en la OTRA fuente no es duplicado
    assert idx.buscar({"fuente": "fundacionglocal.org", "wp_id": "100"}) == []


def test_nivel2_url_normalizada():
    idx = D.Indice(_base())
    m = idx.buscar({"fuente": "glocalminds.com", "url_noticia": "http://www.glocalminds.com/catalogo/otro"})
    assert m and m[0].nivel == 2 and m[0].id_evento == "EV0003"


def test_nivel3_slug_misma_fuente():
    idx = D.Indice(_base())
    m = idx.buscar({"fuente": "glocalminds.com", "slug": "OTRO", "url_noticia": "https://x.cl/1"})
    assert m and m[0].nivel == 3
    assert idx.buscar({"fuente": "fundacionglocal.org", "slug": "otro", "url_noticia": "https://x.cl/1"}) == []


def test_slug_renombrado_cae_en_titulo_no_en_seguro():
    """Caso real: el slug de la web cambió; solo el título coincide -> aviso, no descarte."""
    idx = D.Indice(_base())
    m = idx.buscar({"fuente": "glocalminds.com", "wp_id": "999",
                    "url_noticia": "https://glocalminds.com/catalogo/encuentro-imaginarural-valparaiso/",
                    "slug": "encuentro-imaginarural-valparaiso", "titulo": "Encuentro ImaginaRural en Valparaíso"})
    assert [c.nivel for c in m] == [4]
    assert not D.es_duplicado_seguro(m) and not m[0].entre_fuentes


def test_titulo_entre_fuentes():
    idx = D.Indice(_base())
    m = idx.buscar({"fuente": "glocalminds.com", "titulo": "MINGAMAR", "url_noticia": "https://glocalminds.com/x/"})
    assert m and m[0].nivel == 4 and m[0].entre_fuentes


def test_ignorar_y_orden():
    idx = D.Indice(_base())
    m = idx.buscar(_base()[2], ignorar="EV0003")
    assert [c.id_evento for c in m] == ["EV0004"] and m[0].nivel == 4
    assert D.pares_sospechosos(_base()) == [("EV0003", "EV0004", False)]


@pytest.mark.parametrize("a,b", [("EV0076", "EV0099")])
def test_casos_reales_titulos_repetidos(almacen, a, b):
    """EV0076/EV0099 comparten título pero son eventos distintos: deben quedar solo como sospechosos."""
    base = almacen.leer_base_texto()
    filas = base.to_dict("records")
    pares = D.pares_sospechosos(filas)
    assert any({x, y} == {a, b} for x, y, _ in pares)
    idx = D.Indice(filas)
    fila_a = base[base["id_evento"] == a].iloc[0].to_dict()
    coincide = [c for c in idx.buscar(fila_a, ignorar=a) if c.id_evento == b]
    assert coincide and coincide[0].nivel == 4 and not coincide[0].segura
