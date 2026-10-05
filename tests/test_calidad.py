# -*- coding: utf-8 -*-
import pandas as pd
import pytest

from utils import calidad, repo
from utils import schema as S


@pytest.fixture
def base(almacen):
    return almacen.leer_base_texto()


def _h(base, clave):
    return next(h for h in calidad.detectar(base) if h.clave == clave)


def _mini(**cols):
    """Base mínima de 1 fila con todas las columnas del esquema vacías salvo las indicadas."""
    fila = {c: "" for c in S.COLUMNAS}
    fila.update({"id_evento": "EV0001", "titulo": "T", "url_noticia": "https://glocalminds.com/x/", "fuente": "glocalminds.com"})
    fila.update(cols)
    return pd.DataFrame([fila])


# ----------------------------------------------------------------------------- sobre los datos reales
def test_la_base_real_tiene_los_problemas_conocidos(base):
    fechas = _h(base, "fechas_texto")
    assert fechas.n_noticias == 6 and fechas.n == 12 and fechas.corregible                  # 6 noticias x 2 columnas
    assert all(f["sugerido"].count(" de ") == 2 for f in fechas.filas)                      # «D de mes de AAAA» desde la fecha web
    uno_enero = _h(base, "fecha_1_enero")
    assert {f["id_evento"] for f in uno_enero.filas} == {"EV0164", "EV0222", "EV0251"} and not uno_enero.corregible
    assert _h(base, "obligatorios").n == 0 and _h(base, "urls").n == 0
    paises = _h(base, "paises")
    assert {f["sugerido"] for f in paises.filas} >= {"Chile"} or paises.n > 0
    assert paises.n >= 4 and all(f["actual"] != f["sugerido"] for f in paises.filas)


def test_paises_se_normalizan_elemento_a_elemento(base):
    paises = _h(base, "paises")
    nuevos = {f["id_evento"]: (f["actual"], f["sugerido"]) for f in paises.filas}
    for antes, despues in nuevos.values():
        assert len(antes.split(";")) == len(despues.split(";"))                              # las listas siguen alineadas
    todos = " ".join(a for a, _ in nuevos.values())
    assert any(k in todos for k in ("United States", "Sverige", "Canada", "Paraguay / Paraguái", "(CIMARQ)"))
    assert not any(k in " ".join(d for _, d in nuevos.values()) for k in ("United States", "Sverige", "(CIMARQ)", "/"))


def test_metodologias_unifica_los_alias_conocidos(base):
    h = _h(base, "metodologias")
    assert h.n >= 1 and h.corregible
    for f in h.filas:
        assert len(S.dividir_etiquetas(f["actual"])) == len(S.dividir_etiquetas(f["sugerido"]))
    sugeridos = " ".join(f["sugerido"] for f in h.filas)
    assert "Café Pro-Acción" not in sugeridos and "Café ProAcción" in sugeridos


def test_texto_mostrado_distinto_detecta_siglas_partidas(base):
    h = _h(base, "texto_mostrado")
    assert h.n >= 3 and not h.corregible and all(f["sugerido"] != f["actual"] for f in h.filas)


def test_lugares_sin_coordenadas_ignora_los_online(base):
    h = _h(base, "coordenadas")
    assert h.tipo == calidad.TIPO_GEOCODIFICAR and h.n >= 1
    assert not any("online" in f["actual"].lower() for f in h.filas)


# ----------------------------------------------------------------------------- casos sintéticos
def test_obligatorios_vacios_o_fuente_invalida():
    base = pd.concat([_mini(titulo="", id_evento="EV0001"), _mini(fuente="otro.com", id_evento="EV0002"),
                      _mini(url_noticia="", id_evento="EV0003")], ignore_index=True)
    h = calidad.obligatorios_vacios(base)
    assert {(f["id_evento"], f["campo"]) for f in h.filas} == {("EV0001", "titulo"), ("EV0002", "fuente"), ("EV0003", "url_noticia")}


def test_urls_mal_formadas():
    base = _mini(url_noticia="sin dominio", imagen_principal_url="https://ok.cl/a.jpg", og_url="http://a b.com")
    assert {f["campo"] for f in calidad.urls_mal_formadas(base).filas} == {"url_noticia", "og_url"}


def test_fecha_sin_fecha_web_queda_sin_sugerencia():
    h = calidad.fechas_texto_invalidas(_mini(fecha_publicacion="17 de hasta de 2019"))
    assert h.n == 1 and h.filas[0]["sugerido"] == "" and h.filas[0]["actual"] == "17 de hasta de 2019"


def test_metodologias_por_tildes_y_mayusculas():
    base = pd.concat([_mini(id_evento="EV0001", metodologia="Design Thinking; Art of Hosting"),
                      _mini(id_evento="EV0002", metodologia="design thinking"), _mini(id_evento="EV0003", metodologia="Design Thinking"),
                      _mini(id_evento="EV0004", metodologia="Art of Hosting")], ignore_index=True)
    h = calidad.metodologias_equivalentes(base)
    assert [(f["id_evento"], f["sugerido"]) for f in h.filas] == [("EV0002", "Design Thinking")]


def test_pais_con_nota_y_ya_correcto():
    h = calidad.paises_sin_normalizar(pd.concat([_mini(id_evento="EV0001", sitios_pais="Chile (CIMARQ);Chile;United States"),
                                                _mini(id_evento="EV0002", sitios_pais="Chile;Perú")], ignore_index=True))
    assert [(f["id_evento"], f["sugerido"]) for f in h.filas] == [("EV0001", "Chile;Chile;Estados Unidos")]


# ----------------------------------------------------------------------------- aplicar correcciones
def test_las_correcciones_se_aplican_en_un_lote_y_se_pueden_deshacer(base, almacen):
    h = _h(base, "fechas_texto")
    cambios = calidad.cambios_de(h)
    assert len(cambios) == 12
    res = repo.aplicar_cambios(cambios, "Francis", almacen=almacen)
    assert res.ok and len(res.aplicados) == 12 and res.n_noticias == 6
    nueva = almacen.leer_base_texto()
    assert calidad.fechas_texto_invalidas(nueva).n == 0
    assert repo.lotes_df(almacen).iloc[0]["n_cambios"] == 12
    repo.revertir_lote(res.lote_id, "Francis", almacen)
    assert calidad.fechas_texto_invalidas(almacen.leer_base_texto()).n == 12


def test_cambios_de_con_seleccion_parcial(base):
    h = _h(base, "fechas_texto")
    primero = (h.filas[0]["id_evento"], h.filas[0]["campo"])
    assert len(calidad.cambios_de(h, {primero})) == 1
    assert calidad.cambios_de(h, set()) == []
