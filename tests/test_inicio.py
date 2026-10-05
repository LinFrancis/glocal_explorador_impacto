# -*- coding: utf-8 -*-
"""Dashboard de Inicio: KPIs de gestión, bandeja de trabajo, aviso de sincronización y actividad."""
from datetime import datetime, timedelta

import pytest

from tests.apptest_util import apuntar_a, iniciar_sesion, nueva_app, textos
from utils import repo
from utils import schema as S
from utils import vistas
from utils.repo import Cambio


@pytest.fixture
def app(monkeypatch, almacen):
    apuntar_a(monkeypatch, almacen)
    return nueva_app()


def _metricas(at):
    return {m.label: m for m in at.metric}


def test_kpis_de_gestion_con_datos_reales(app):
    iniciar_sesion(app)
    assert not app.exception
    m = _metricas(app)
    assert m["Noticias en la base"].value == "274"
    assert (m["Glocalminds"].value, m["Fundación Glocal"].value) == ("258", "16")
    assert m["Completitud media"].value.endswith("%")
    assert m["Última edición"].value == "—" and m["Última edición"].delta == "Sin ediciones aún"
    assert any("Aún no hay sincronizaciones" in i.value for i in app.info)
    assert "Hola, Francis" in " ".join(e.value for e in app.markdown)


def test_nueva_noticia_pobre_encabeza_la_bandeja(app, almacen):
    repo.agregar_filas([{"titulo": "Noticia recién llegada sin análisis", "url_noticia": "https://glocalminds.com/x/",
                         "fuente": "glocalminds.com"}], "Ana", almacen=almacen)
    iniciar_sesion(app)
    assert not app.exception
    assert _metricas(app)["Noticias en la base"].value == "275"
    primero = [e.value for e in app.markdown if "Noticia recién llegada" in e.value]
    assert primero, "la noticia con menos información debe aparecer en la bandeja de trabajo"
    ultima = _metricas(app)["Última edición"]
    assert ultima.value == "hace un momento" and "Ana" in ultima.delta


def test_aviso_de_sincronizacion_segun_antiguedad(app, almacen, monkeypatch):
    hace_20 = (datetime.now() - timedelta(days=20)).isoformat(timespec="seconds")
    monkeypatch.setattr(repo, "ahora", lambda: hace_20)
    repo.agregar_filas([{"titulo": "N", "url_noticia": "https://glocalminds.com/n/", "fuente": "glocalminds.com"}],
                       "Ana", accion=S.ACC_SINCRONIZAR, origen="scraping", almacen=almacen)
    iniciar_sesion(app)
    assert any("Han pasado 20 días" in w.value for w in app.warning)

    reciente = datetime.now().isoformat(timespec="seconds")
    monkeypatch.setattr(repo, "ahora", lambda: reciente)
    repo.agregar_filas([{"titulo": "M", "url_noticia": "https://glocalminds.com/m/", "fuente": "glocalminds.com"}],
                       "Ana", accion=S.ACC_SINCRONIZAR, origen="scraping", almacen=almacen)
    app.run()
    assert not any("Han pasado" in w.value for w in app.warning)
    assert any("Última sincronización" in c.value for c in app.caption)


def test_actividad_reciente_muestra_los_cambios(app, almacen):
    antes = almacen.leer_base_texto().set_index("id_evento", drop=False).at["EV0001", "lugar"]
    repo.aplicar_cambios([Cambio("EV0001", "lugar", antes, "Lugar nuevo")], "Beto", almacen=almacen)
    iniciar_sesion(app)
    assert not app.exception
    tablas = [t.value for t in app.dataframe]
    assert tablas and "Beto" in tablas[0]["Quién"].tolist()
    assert any("Lugar nuevo" in d for d in tablas[0]["Detalle"])


# ----------------------------------------------------------------------------- utilidades de presentación
@pytest.mark.parametrize("delta,esperado", [
    (timedelta(seconds=10), "hace un momento"), (timedelta(minutes=5), "hace 5 minutos"),
    (timedelta(minutes=1), "hace 1 minuto"), (timedelta(hours=3), "hace 3 horas"),
    (timedelta(days=1, hours=2), "ayer"), (timedelta(days=12), "hace 12 días"),
    (timedelta(days=90), "hace 3 meses"),
])
def test_hace_cuanto(delta, esperado):
    ahora = datetime(2026, 10, 5, 12, 0, 0)
    assert vistas.hace_cuanto((ahora - delta).isoformat(), ahora) == esperado
    assert vistas.hace_cuanto("") == "" and vistas.hace_cuanto("basura") == ""


def test_historial_legible_registro_y_campos(almacen):
    res = repo.agregar_filas([{"titulo": "Una noticia", "url_noticia": "https://glocalminds.com/u/", "fuente": "glocalminds.com"}],
                             "Ana", almacen=almacen)
    ide = res.ids_creados[0]
    repo.aplicar_cambios([Cambio(ide, "lugar", "", "Valparaíso")], "Beto", almacen=almacen)
    legible = vistas.historial_legible(repo.historial_df(almacen), almacen.leer_base_texto())
    assert legible.iloc[0]["Detalle"] == "Lugar: «» → «Valparaíso»" and legible.iloc[0]["Noticia"] == "Una noticia"
    assert legible.iloc[1]["Detalle"] == "Noticia agregada"
    repo.revertir_lote(res.lote_id, "Ana", almacen=almacen)           # conflicto: Beto editó después
    assert vistas.historial_legible(repo.historial_df(almacen), almacen.leer_base_texto()).shape[0] == 2
