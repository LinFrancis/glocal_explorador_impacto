# -*- coding: utf-8 -*-
"""Página «Sincronizar con la web» con la red simulada: flujo normal y errores."""
import pytest

from tests.apptest_util import apuntar_a, iniciar_sesion, nueva_app
from utils import repo, scraper
from utils.scraper import ResultadoFuente

PAGINA = "app_pages/sincronizar.py"


def _web_desde_bd(f, i):
    web = {k: f[k] for k in ("titulo", "titulo_catalogo", "slug", "url_noticia", "fuente", "fecha_publicacion_web",
                              "fecha_modificacion_web", "contenido_completo", "descripcion_catalogo",
                              "imagen_principal_url", "imagen_alt", "enlaces_externos")}
    web["wp_id"] = str(5000 + i)
    return web


def _web_falsa(base, con_nueva=True, error_fund=""):
    """Lo que 'vería' la web: toda la base actual (+ una noticia nueva)."""
    por_fuente: dict[str, list] = {"glocalminds.com": [], "fundacionglocal.org": []}
    for i, f in enumerate(base):
        por_fuente[f["fuente"]].append(_web_desde_bd(f, i))
    if con_nueva:
        por_fuente["glocalminds.com"].append({
            "titulo": "Diplomado nuevo desde la web", "titulo_catalogo": "Diplomado nuevo desde la web", "slug": "diplomado-nuevo",
            "url_noticia": "https://glocalminds.com/catalogo/diplomado-nuevo/", "fuente": "glocalminds.com", "wp_id": "9001",
            "fecha_publicacion_web": "2026-09-30T10:00:00", "timestamp_extraccion": "2026-10-05T10:00:00",
            "contenido_completo": "Texto del diplomado.", "descripcion_catalogo": "Resumen del diplomado."})

    def fake(clave, sesion=None, progreso=None):
        if clave == "fundacionglocal.org" and error_fund:
            return ResultadoFuente(clave, error=error_fund)
        items = por_fuente[clave]
        return ResultadoFuente(clave, items=items, total_web=len(items))
    return fake


@pytest.fixture
def app(monkeypatch, almacen):
    apuntar_a(monkeypatch, almacen)
    at = nueva_app()
    iniciar_sesion(at, nombre="Francis")
    at.switch_page(PAGINA).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _buscar(at):
    next(b for b in at.button if b.label == "Buscar novedades").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]


def _metricas(at):
    return {m.label: m.value for m in at.metric}


def test_pagina_inicial_sin_busqueda(app):
    assert any("Pulsa «Buscar novedades»" in c.value for c in app.caption)
    assert not app.metric
    assert not app.toggle                                              # sin «modo de prueba»: la sincronización trabaja sobre la base real


def test_flujo_completo_hasta_todo_actualizado(app, almacen, monkeypatch):
    base = almacen.leer_base_texto().to_dict("records")
    monkeypatch.setattr(scraper, "descargar", _web_falsa(base))
    _buscar(app)
    assert _metricas(app) == {"Nuevas": "1", "URL cambió": "0", "Cambiaron en la web": "0", "Solo en la base": "0"}
    aplicar = next(b for b in app.button if b.label.startswith("Aplicar"))
    assert aplicar.label == "Aplicar (1 nuevas, 0 actualizaciones, 274 IDs)"
    aplicar.click()
    app.run()
    assert not app.exception, [e.value for e in app.exception]

    fila = almacen.leer_base_texto().set_index("id_evento", drop=False)
    assert len(fila) == 275 and fila.at["EV0275", "titulo"] == "Diplomado nuevo desde la web"
    assert fila.at["EV0275", "origen"] == "scraping" and fila.at["EV0001", "wp_id"] == "5000"
    assert any("Sincronización aplicada: 1 noticia(s) nueva(s), 274 noticia(s) actualizada(s)" in s.value for s in app.success)
    # la comparación se recalcula sola contra la web ya descargada: ahora no hay nada pendiente
    assert any(s.value == "✓ Todo actualizado" for s in app.success)
    assert not any(b.label.startswith("Aplicar") for b in app.button)
    lotes = repo.lotes_df(almacen)
    assert len(lotes) == 1 and lotes.iloc[0]["accion"] == "Sincronización"


def test_fuente_caida_se_informa_y_la_otra_sigue(app, almacen, monkeypatch):
    base = almacen.leer_base_texto().to_dict("records")
    monkeypatch.setattr(scraper, "descargar", _web_falsa(base, con_nueva=False, error_fund="No hay conexión con fundacionglocal.org."))
    _buscar(app)
    assert any("No hay conexión con fundacionglocal.org" in e.value for e in app.error)
    assert _metricas(app)["Nuevas"] == "0"                         # glocalminds sí se comparó
    assert len(almacen.leer_base_texto()) == 274


def test_todas_las_fuentes_caidas_no_muestra_comparacion(app, monkeypatch):
    monkeypatch.setattr(scraper, "descargar", lambda c, sesion=None, progreso=None: ResultadoFuente(c, error=f"No hay conexión con {c}."))
    _buscar(app)
    assert len([e for e in app.error if "No hay conexión" in e.value]) == 2
    assert not app.metric and not any(s.value == "✓ Todo actualizado" for s in app.success)
