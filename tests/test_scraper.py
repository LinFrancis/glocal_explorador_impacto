# -*- coding: utf-8 -*-
"""Scraper: texto, mapeo de campos, paginación, errores en español, respaldo HTML y diferencial."""
import copy

import pytest
import requests

from utils import repo, scraper
from utils import schema as S
from utils.scraper import FUENTES_WEB

GLOCAL = FUENTES_WEB["glocalminds.com"]
FUND = FUENTES_WEB["fundacionglocal.org"]


# ============================================================================ doble de red
class Resp:
    def __init__(self, status=200, datos=None, headers=None, texto="", json_roto=False):
        self.status_code, self._datos, self.headers, self.text, self._roto = status, datos, headers or {}, texto, json_roto
        self.content = texto.encode() if texto else b"{}"

    def json(self):
        if self._roto:
            raise ValueError("no es JSON")
        return self._datos


class Sesion:
    """Responde según una función (url, params) -> Resp | excepción a lanzar."""

    def __init__(self, fn):
        self.fn, self.llamadas = fn, []

    def get(self, url, params=None, timeout=None):
        self.llamadas.append((url, dict(params or {})))
        r = self.fn(url, params or {})
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture(autouse=True)
def sin_pausas(monkeypatch):
    monkeypatch.setattr(scraper, "PAUSA_ENTRE_PAGINAS", 0)


def wp_item(i, titulo="Una noticia", slug=None, fecha="2026-08-09T22:39:59", mod="2026-08-09T22:49:19",
            contenido="<p class='x'>Primer párrafo.</p><p>Segundo <strong>párrafo</strong>.</p>", media=True):
    it = {
        "id": i, "date": fecha, "modified": mod, "slug": slug or f"noticia-{i}", "link": f"https://glocalminds.com/catalogo/{slug or f'noticia-{i}'}/",
        "title": {"rendered": titulo}, "excerpt": {"rendered": "<p>Resumen corto […]</p>"},
        "content": {"rendered": contenido}, "featured_media": 77 if media else 0,
        "_embedded": {"wp:featuredmedia": [{"source_url": f"https://glocalminds.com/wp-content/uploads/{i}.jpg", "alt_text": "alt"}]} if media else {},
    }
    return it


# ============================================================================ texto
def test_texto_respeta_bloques_y_espacios():
    html = ("<div><div><span>Santiago</span></div><div>Durante los días 9 y 10</div></div>"
            "<p>Hola <strong>mundo</strong>, qué&nbsp;tal</p><ul><li>uno</li><li>dos</li></ul>"
            "<script>alert(1)</script><style>.a{}</style>línea<br>siguiente")
    assert scraper.texto_desde_html(html).split("\n") == [
        "Santiago", "Durante los días 9 y 10", "Hola mundo, qué tal", "uno", "dos", "línea", "siguiente"]
    assert scraper.texto_desde_html("") == "" and scraper.texto_desde_html("   ") == ""


def test_enlaces_externos_excluye_el_propio_sitio():
    html = ('<a href="https://glocalminds.com/otra/">propia</a><a href="https://www.glocalminds.com/x">www</a>'
            '<a href="https://onu.org/a">onu</a><a href="https://onu.org/a">repetida</a><a href="mailto:a@b.cl">m</a>'
            '<a href="/relativo">r</a><a href="https://sub.glocalminds.com/z">sub</a><a href="http://ipcc.ch">ipcc</a>')
    assert scraper.enlaces_externos(html, "glocalminds.com") == ["https://onu.org/a", "http://ipcc.ch"]


# ============================================================================ mapeo de un elemento
def test_parsear_item_completo():
    fila, problemas = scraper.parsear_item(wp_item(5, "Líderes &#8211; Al Gore &amp; más", contenido=(
        "<p>Texto <a href='https://onu.org/x'>enlace</a>.</p>")), GLOCAL, ahora="2026-10-05T10:00:00")
    assert problemas == []
    assert fila["titulo"] == "Líderes – Al Gore & más" and fila["titulo_catalogo"] == fila["titulo"]
    assert (fila["wp_id"], fila["fuente"], fila["slug"]) == ("5", "glocalminds.com", "noticia-5")
    assert fila["contenido_completo"] == "Texto enlace." and fila["descripcion_catalogo"] == "Resumen corto"
    assert fila["imagen_principal_url"].endswith("/5.jpg") and fila["imagen_alt"] == "alt"
    assert fila["enlaces_externos"] == "https://onu.org/x" and fila["num_enlaces_externos"] == "1"
    assert fila["timestamp_extraccion"] == "2026-10-05T10:00:00"
    assert fila["Fundación Glocal?"] == "" and fila["Consultora"] == ""
    ffund, _ = scraper.parsear_item(wp_item(6), FUND)
    assert ffund["Fundación Glocal?"] == "Fundación Glocal" and ffund["Consultora"] == "0" and ffund["fuente"] == "fundacionglocal.org"


def test_parsear_item_sin_imagen_no_es_error():
    fila, problemas = scraper.parsear_item(wp_item(7, media=False), GLOCAL)
    assert problemas == [] and fila["imagen_principal_url"] == ""


def test_parsear_item_roto_deja_vacio_y_avisa():
    item = wp_item(8)
    del item["content"]
    del item["_embedded"]
    fila, problemas = scraper.parsear_item(item, GLOCAL)
    assert "contenido" in problemas and "imagen" in problemas
    assert fila["contenido_completo"] == "" and fila["imagen_principal_url"] == ""
    assert fila["titulo"] == "Una noticia"                      # lo demás se conserva


def test_resumen_cae_al_contenido_si_no_hay_extracto():
    item = wp_item(9)
    item["excerpt"]["rendered"] = ""
    fila, _ = scraper.parsear_item(item, GLOCAL)
    assert fila["descripcion_catalogo"].startswith("Primer párrafo.")


# ============================================================================ descarga
def _api_paginada(n_total=5, por_pagina=2):
    items = [wp_item(i) for i in range(1, n_total + 1)]
    paginas = [items[i:i + por_pagina] for i in range(0, n_total, por_pagina)]

    def fn(url, params):
        p = params.get("page", 1)
        if p > len(paginas):
            return Resp(400, {"code": "rest_post_invalid_page_number"})
        return Resp(200, paginas[p - 1], {"X-WP-Total": str(n_total), "X-WP-TotalPages": str(len(paginas))})
    return fn


def test_descargar_api_pagina_hasta_el_final():
    s = Sesion(_api_paginada())
    res = scraper.descargar_api(GLOCAL, s)
    assert [f["wp_id"] for f in res.items] == ["1", "2", "3", "4", "5"]
    assert res.total_web == 5 and res.completo and res.ok and res.modo == "api"
    assert [p["page"] for _, p in s.llamadas] == [1, 2, 3]
    assert s.llamadas[0][1]["_embed"] == "wp:featuredmedia" and s.llamadas[0][1]["per_page"] == 100


def test_descargar_cuenta_campos_vacios_y_omite_elementos_inservibles():
    roto = wp_item(2)
    del roto["content"]
    inservible = {"id": 3}

    def fn(url, params):
        return Resp(200, [wp_item(1), roto, inservible], {"X-WP-Total": "3", "X-WP-TotalPages": "1"})
    res = scraper.descargar("glocalminds.com", Sesion(fn))
    assert len(res.items) == 2 and res.n_campos_vacios >= 1
    assert any("no se pudo leer" in a for a in res.avisos) and any("omitió" in a for a in res.avisos)
    assert not res.completo or res.total_web == len(res.items)      # faltó uno: no es un catálogo completo


@pytest.mark.parametrize("excepcion,texto", [
    (requests.exceptions.ConnectTimeout(), "tardó demasiado"),
    (requests.exceptions.ReadTimeout(), "tardó demasiado"),
    (requests.exceptions.ConnectionError(), "No hay conexión"),
    (requests.exceptions.SSLError(), "conexión segura"),
])
def test_errores_de_red_en_espanol_y_sin_respaldo(excepcion, texto):
    s = Sesion(lambda url, p: excepcion)
    res = scraper.descargar("glocalminds.com", s)
    assert not res.ok and texto in res.error and "glocalminds.com" in res.error
    assert res.items == [] and len(s.llamadas) == 1                 # sin conexión no se prueba el respaldo


HTML_FUND = """<div class="e-loop-item e-loop-item-1 post-1" data-elementor-type="loop-item">
<div class="elementor-widget-image"><img src="https://fundacionglocal.org/thumb-a.jpg"></div>
<h2 class="elementor-heading-title"><a href="https://fundacionglocal.org/nota-a/">Nota A</a></h2></div>
<div class="e-loop-item e-loop-item-2" data-elementor-type="loop-item"><h2 class="elementor-heading-title"><a href="https://fundacionglocal.org/nota-b/">Nota B</a></h2></div>"""
HTML_GLOCAL = """<article class="eael-grid-post" data-id="10"><div class="eael-entry-thumbnail"><img src="https://glocalminds.com/a.jpg"></div>
<h3 class="eael-entry-title"><a class="eael-grid-post-link" href="https://glocalminds.com/catalogo/uno/">Uno</a></h3>
<span class="eael-posted-on"><time datetime="2026-07-12">12.07.2026</time></span></article>"""


def test_respaldo_html_si_la_api_responde_error():
    def fn(url, params):
        if "wp-json" in url:
            return Resp(403)
        if url.endswith("/buenas-noticias/"):
            return Resp(200, texto=HTML_FUND)
        return Resp(200, texto="<html></html>")                      # páginas siguientes: sin tarjetas
    res = scraper.descargar("fundacionglocal.org", Sesion(fn))
    assert res.ok and res.modo == "html" and not res.completo
    assert [(f["titulo"], f["slug"]) for f in res.items] == [("Nota A", "nota-a"), ("Nota B", "nota-b")]
    assert res.items[0]["imagen_principal_url"].endswith("thumb-a.jpg") and res.items[0]["Fundación Glocal?"] == "Fundación Glocal"
    assert res.avisos[0].startswith("Falló la API") and any("solo se trajeron" in a for a in res.avisos)


def test_respaldo_html_glocalminds_solo_primera_pagina_y_fecha():
    def fn(url, params):
        return Resp(404) if "wp-json" in url else Resp(200, texto=HTML_GLOCAL)
    s = Sesion(fn)
    res = scraper.descargar("glocalminds.com", s)
    assert res.modo == "html" and len(res.items) == 1 and res.items[0]["fecha_publicacion_web"] == "12.07.2026"
    assert sum("noticias" in u for u, _ in s.llamadas) == 1


def test_json_invalido_cae_al_respaldo_y_si_todo_falla_error_claro():
    res = scraper.descargar("fundacionglocal.org", Sesion(lambda u, p: Resp(200, json_roto=True, texto="<html>nada</html>")))
    assert not res.ok and "No se pudieron leer noticias" in res.error


def test_una_fuente_caida_no_afecta_a_la_otra():
    def fn(url, params):
        if "fundacionglocal" in url:
            return requests.exceptions.ConnectionError()
        return _api_paginada(2, 2)(url, params)
    s = Sesion(fn)
    a, b = scraper.descargar("glocalminds.com", s), scraper.descargar("fundacionglocal.org", s)
    assert a.ok and len(a.items) == 2 and not b.ok and "No hay conexión" in b.error


def test_descargar_uno():
    s = Sesion(lambda url, p: Resp(200, wp_item(42, "Solo esta")))
    fila, err = scraper.descargar_uno("glocalminds.com", "42", s)
    assert err == "" and fila["titulo"] == "Solo esta" and s.llamadas[0][0].endswith("/catalogo/42")
    fila, err = scraper.descargar_uno("glocalminds.com", "42", Sesion(lambda u, p: Resp(404)))
    assert fila is None and "404" in err


# ============================================================================ diferencial
def _web_desde_bd(fila_bd, **cambios):
    """Simula cómo vería la web una fila existente de la base."""
    web = {k: v for k, v in fila_bd.items() if k in {
        "titulo", "titulo_catalogo", "slug", "url_noticia", "fuente", "fecha_publicacion_web",
        "fecha_modificacion_web", "contenido_completo", "descripcion_catalogo", "imagen_principal_url",
        "imagen_alt", "enlaces_externos"}}
    web["wp_id"] = "5000"
    web.update(cambios)
    return web


@pytest.fixture
def base(almacen):
    return almacen.leer_base_texto().to_dict("records")


def _res(fuente, items, total=None):
    return scraper.ResultadoFuente(fuente, items=items, total_web=total if total is not None else len(items))


def test_diferencial_clasifica_cada_caso(base):
    gm = [f for f in base if f["fuente"] == "glocalminds.com"]
    inalterada, renombrada, modificada, solo_espacios, = gm[0], gm[1], gm[2], gm[3]
    web = [
        _web_desde_bd(inalterada),
        _web_desde_bd(renombrada, url_noticia="https://glocalminds.com/catalogo/slug-nuevo/", slug="slug-nuevo", wp_id="5001"),
        _web_desde_bd(modificada, fecha_modificacion_web="2099-01-01T10:00:00", contenido_completo="Texto totalmente nuevo.", wp_id="5002"),
        _web_desde_bd(solo_espacios, fecha_modificacion_web="2099-01-01T10:00:00", wp_id="5003",
                      contenido_completo=solo_espacios["contenido_completo"].replace(" ", "  ")),
        {"titulo": "Noticia nunca vista", "url_noticia": "https://glocalminds.com/catalogo/nunca-vista/", "slug": "nunca-vista",
         "fuente": "glocalminds.com", "wp_id": "6000", "fecha_publicacion_web": "2026-09-01T10:00:00"},
        {"titulo": gm[4]["titulo"], "url_noticia": "https://glocalminds.com/catalogo/segunda-edicion/", "slug": "segunda-edicion",
         "fuente": "glocalminds.com", "wp_id": "6001", "fecha_publicacion_web": "2031-01-01T10:00:00"},
    ]
    dif = scraper.calcular_diferencias([_res("glocalminds.com", web, total=len(web))], base)
    assert [n["fila"]["wp_id"] for n in dif.nuevas] == ["6001", "6000"] or {n["fila"]["wp_id"] for n in dif.nuevas} == {"6000", "6001"}
    sosp = {n["fila"]["wp_id"]: n["sospechosa"] for n in dif.nuevas}
    assert sosp == {"6000": False, "6001": True}
    assert [u["id_evento"] for u in dif.url_cambio] == [renombrada["id_evento"]]
    assert dif.url_cambio[0]["antes"] == renombrada["url_noticia"] and dif.url_cambio[0]["despues"].endswith("slug-nuevo/")
    assert [m["id_evento"] for m in dif.modificadas] == [modificada["id_evento"]]
    assert {c["campo"] for c in dif.modificadas[0]["campos"]} >= {"contenido_completo", "fecha_modificacion_web"}
    # wp_id pendiente en las que coinciden por URL y todavía no lo tenían
    assert {p["id_evento"] for p in dif.wp_pendientes} >= {inalterada["id_evento"], modificada["id_evento"], solo_espacios["id_evento"]}
    # catálogo "completo" del sitio: el resto de glocalminds aparece como "solo en la base"
    assert len(dif.solo_en_bd) == len(gm) - 4 and not dif.sin_diferencias


def test_fuente_incompleta_no_declara_solo_en_bd(base):
    web = [_web_desde_bd(base[0])]
    dif = scraper.calcular_diferencias([_res(base[0]["fuente"], web, total=999)], base)
    assert dif.solo_en_bd == []


def test_fuente_con_error_se_ignora(base):
    dif = scraper.calcular_diferencias([scraper.ResultadoFuente("glocalminds.com", error="sin conexión")], base)
    assert dif.sin_diferencias and dif.solo_en_bd == [] and dif.n_total == 0


def test_no_marca_modificada_si_la_fecha_no_avanza(base):
    f = base[0]
    web = _web_desde_bd(f, contenido_completo="Totalmente distinto")      # misma fecha de modificación
    dif = scraper.calcular_diferencias([_res(f["fuente"], [web])], base)
    assert dif.modificadas == []


def test_dos_noticias_reales_con_mismo_titulo_no_se_confunden(base):
    """EV0076/EV0099 comparten título: cada una debe emparejarse con su propia URL, sin 'nuevas'."""
    ids = {"EV0076", "EV0099"}
    filas = [f for f in base if f["id_evento"] in ids]
    web = [_web_desde_bd(f, wp_id=str(7000 + i)) for i, f in enumerate(filas)]
    dif = scraper.calcular_diferencias([_res(filas[0]["fuente"], web)], base)
    assert dif.nuevas == [] and dif.url_cambio == []


# ============================================================================ aplicar + "Todo actualizado"
def test_aplicar_sincronizacion_y_segunda_pasada_sin_diferencias(almacen):
    base = almacen.leer_base_texto().to_dict("records")
    gm = [f for f in base if f["fuente"] == "glocalminds.com"]
    renombrada = gm[1]
    nueva = {"titulo": "Noticia nunca vista", "url_noticia": "https://glocalminds.com/catalogo/nunca-vista/", "slug": "nunca-vista",
             "fuente": "glocalminds.com", "wp_id": "6000", "fecha_publicacion_web": "2026-09-01T10:00:00",
             "timestamp_extraccion": "2026-10-05T10:00:00"}
    web = [_web_desde_bd(f, wp_id=str(5000 + i)) for i, f in enumerate(gm)]
    web[1] = _web_desde_bd(renombrada, url_noticia="https://glocalminds.com/catalogo/slug-nuevo/", slug="slug-nuevo", wp_id="5001")
    web.append(nueva)
    resultado = _res("glocalminds.com", web)

    dif = scraper.calcular_diferencias([resultado], base)
    assert len(dif.nuevas) == 1 and len(dif.url_cambio) == 1 and len(dif.wp_pendientes) == len(gm) - 1
    cambios = []
    for u in dif.url_cambio:
        cambios += scraper.cambios_url(u)
    for p in dif.wp_pendientes:
        cambios += scraper.cambios_wp_id(p)
    res = repo.aplicar_sincronizacion([n["fila"] for n in dif.nuevas], cambios, "Francis", almacen)
    assert res.ids_creados == ["EV0275"] and not res.omitidos
    assert almacen.listar_respaldos(), "respaldo automático antes de sincronizar"

    nueva_bd = almacen.leer_base_texto().set_index("id_evento", drop=False)
    assert nueva_bd.at["EV0275", "origen"] == "scraping" and nueva_bd.at["EV0275", "cargado_por"] == "Francis"
    assert nueva_bd.at[renombrada["id_evento"], "url_noticia"].endswith("slug-nuevo/")
    assert nueva_bd.at[renombrada["id_evento"], "slug"] == "slug-nuevo"
    assert nueva_bd.at[gm[0]["id_evento"], "wp_id"] == "5000"
    h = repo.historial_df(almacen)
    assert set(h["accion"]) <= {"sincronizar"} and h["lote_id"].nunique() == 1

    # segunda pasada contra la misma web: nada que hacer -> «✓ Todo actualizado»
    base2 = almacen.leer_base_texto().to_dict("records")
    dif2 = scraper.calcular_diferencias([resultado], base2)
    assert dif2.sin_diferencias and dif2.wp_pendientes == [] and dif2.n_total == 0

    # y todo el lote se puede deshacer de una vez
    rev = repo.revertir_lote(res.lote_id, "Francis", almacen)
    assert rev.ids_eliminados == ["EV0275"] and len(almacen.leer_base_texto()) == 274
    assert almacen.leer_base_texto().set_index("id_evento", drop=False).at[renombrada["id_evento"], "slug"] == renombrada["slug"]


def test_aplicar_sincronizacion_actualiza_modificadas(almacen):
    base = almacen.leer_base_texto().to_dict("records")
    f = next(x for x in base if x["fuente"] == "glocalminds.com")
    web = _web_desde_bd(f, fecha_modificacion_web="2099-01-01T00:00:00", contenido_completo="Contenido nuevo desde la web", wp_id="5000")
    dif = scraper.calcular_diferencias([_res("glocalminds.com", [web])], base)
    res = repo.aplicar_sincronizacion([], scraper.cambios_modificada(dif.modificadas[0]), "Ana", almacen)
    fila = almacen.leer_base_texto().set_index("id_evento", drop=False).loc[f["id_evento"]]
    assert fila["contenido_completo"] == "Contenido nuevo desde la web" and fila["fecha_modificacion_web"] == "2099-01-01"
    assert fila["editado_por"] == "Ana" and res.ok


def test_sincronizacion_sin_nada_no_escribe(almacen):
    firma = almacen.firma()
    res = repo.aplicar_sincronizacion([], [], "Ana", almacen)
    assert res.n_aplicados == 0 and almacen.firma() == firma


# ============================================================================ prueba en vivo (solo lectura)
@pytest.mark.vivo
def test_en_vivo_ambas_apis_y_diferencial_contra_la_base_real(almacen):
    base = almacen.leer_base_texto().to_dict("records")
    resultados = [scraper.descargar(k) for k in FUENTES_WEB]
    for r in resultados:
        assert r.ok and r.modo == "api", r.error
        assert r.total_web == len(r.items) and r.completo
        assert all(f["titulo"] and f["url_noticia"] and f["wp_id"] for f in r.items)
        print(f"\n{r.fuente}: {len(r.items)} noticias, {r.n_campos_vacios} campos vacíos, avisos: {r.avisos[:2]}")
    dif = scraper.calcular_diferencias(resultados, base)
    por_fuente = lambda lista, k="fuente": {f: sum(1 for x in lista if (x.get(k) if k in x else x["fila"]["fuente"]) == f) for f in FUENTES_WEB}
    print("nuevas:", [(n["fila"]["fuente"], n["fila"]["titulo"][:50], n["sospechosa"]) for n in dif.nuevas])
    print("url_cambio:", [(u["id_evento"], u["antes"].rsplit("/", 2)[-2], "->", u["despues"].rsplit("/", 2)[-2]) for u in dif.url_cambio])
    print("modificadas:", len(dif.modificadas), "| wp_pendientes:", len(dif.wp_pendientes), "| solo_en_bd:", [(s['id_evento'], s['titulo'][:40]) for s in dif.solo_en_bd])
    assert len(dif.nuevas) < 20
