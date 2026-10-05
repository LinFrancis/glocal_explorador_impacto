# -*- coding: utf-8 -*-
"""Página «Cargar información»: formulario manual."""
import pytest

from tests.apptest_util import apuntar_a, iniciar_sesion, nueva_app
from utils import repo

PAGINA = "app_pages/carga.py"


@pytest.fixture
def app(monkeypatch, almacen):
    apuntar_a(monkeypatch, almacen)
    at = nueva_app()
    iniciar_sesion(at, nombre="Francis")
    at.switch_page(PAGINA).run()
    assert not at.exception
    return at


def _enviar(at):
    next(b for b in at.button if b.label == "Agregar noticia").click()
    at.run()


def _llenar(at, titulo="", url="", fuente=None, n=0, **extra):
    at.text_input(key=f"carga_{n}_titulo").set_value(titulo)
    at.text_input(key=f"carga_{n}_url_noticia").set_value(url)
    if fuente:
        at.selectbox(key=f"carga_{n}_fuente").select(fuente)
    for k, v in extra.items():
        at.text_input(key=f"carga_{n}_{k}").set_value(v)


def test_faltan_obligatorios_no_guarda(app, almacen):
    _llenar(app, titulo="Solo título")
    _enviar(app)
    assert any("obligatorio" in e.value for e in app.error)
    assert len(almacen.leer_base_texto()) == 274


def test_agrega_noticia_y_registra_quien(app, almacen):
    _llenar(app, titulo="Taller de prueba", url="glocalminds.com/catalogo/taller-prueba", fuente="glocalminds.com",
            fecha_publicacion_web="11 de julio de 2026")
    _enviar(app)
    assert not app.exception
    fila = almacen.leer_base_texto().set_index("id_evento").loc["EV0275"]
    assert (fila["titulo"], fila["origen"], fila["cargado_por"]) == ("Taller de prueba", "manual", "Francis")
    assert fila["url_noticia"] == "https://glocalminds.com/catalogo/taller-prueba"      # esquema agregado
    assert fila["fecha_publicacion_web"] == "2026-07-11"                                # fecha normalizada
    assert any("EV0275" in s.value for s in app.success)
    assert app.session_state["carga_form_n"] == 1                                       # formulario nuevo y vacío
    assert app.text_input(key="carga_1_titulo").value == ""


def test_fuente_se_deduce_del_enlace(app, almacen):
    _llenar(app, titulo="Sin fuente explícita", url="https://fundacionglocal.org/algo-nuevo/")
    _enviar(app)
    assert almacen.leer_base_texto().set_index("id_evento").loc["EV0275"]["fuente"] == "fundacionglocal.org"


def test_duplicado_seguro_se_bloquea(app, almacen):
    existente = almacen.leer_base_texto().iloc[0]
    _llenar(app, titulo="Otro título", url=existente["url_noticia"], fuente=existente["fuente"])
    _enviar(app)
    assert any("ya está en la base" in e.value for e in app.error)
    assert len(almacen.leer_base_texto()) == 274


def test_mismo_titulo_pide_decision_y_permite_forzar(app, almacen):
    existente = almacen.leer_base_texto().iloc[0]
    _llenar(app, titulo=existente["titulo"], url="https://glocalminds.com/catalogo/edicion-2/", fuente="glocalminds.com")
    _enviar(app)
    assert any("mismo título" in w.value for w in app.warning)
    assert len(almacen.leer_base_texto()) == 274                                        # aún no se guardó
    next(b for b in app.button if b.label == "Agregar igualmente").click()
    app.run()
    assert not app.exception and len(almacen.leer_base_texto()) == 275
    assert repo.historial_df(almacen).iloc[0]["accion"] == "crear"


def test_cancelar_vuelve_al_formulario(app, almacen):
    existente = almacen.leer_base_texto().iloc[0]
    _llenar(app, titulo=existente["titulo"], url="https://glocalminds.com/catalogo/x/", fuente="glocalminds.com")
    _enviar(app)
    next(b for b in app.button if "Cancelar" in b.label).click()
    app.run()
    assert "carga_pendiente" not in app.session_state
    assert len(almacen.leer_base_texto()) == 274
    assert any(b.label == "Agregar noticia" for b in app.button)


def test_aviso_de_validacion_no_bloquea(app, almacen):
    _llenar(app, titulo="Con fecha rara", url="https://glocalminds.com/catalogo/rara/", fuente="glocalminds.com",
            fecha_publicacion_web="un día cualquiera")
    _enviar(app)
    assert len(almacen.leer_base_texto()) == 275                                        # se guardó igual
    assert any("fecha" in w.value.lower() for w in app.warning)


def _subir(at, csv_texto: str, nombre="noticias.csv"):
    at.file_uploader[0].set_value((nombre, csv_texto.encode("utf-8"), "text/csv"))
    at.run()


def test_importar_archivo_de_punta_a_punta(app, almacen):
    existente = almacen.leer_base_texto().iloc[0]
    _subir(app, "Título,Enlace,Fecha,Categoría macro\n"
                "Noticia importada uno,https://glocalminds.com/catalogo/imp-1/,2026-09-15,Educación\n"
                f"Repetida,{existente['url_noticia']},2026-01-01,Educación\n"
                ",https://glocalminds.com/catalogo/sin-titulo/,2026-01-01,Educación\n")
    assert not app.exception, [e.value for e in app.exception]
    m = {x.label: x.value for x in app.metric}
    assert m == {"Filas en el archivo": "3", "Se pueden importar": "1", "Ya existen": "1", "Con errores o dudas": "1"}
    boton = next(b for b in app.button if b.label.startswith("Importar"))
    assert boton.label == "Importar 1 noticia(s)"
    boton.click()
    app.run()
    assert not app.exception
    base = almacen.leer_base_texto().set_index("id_evento")
    assert len(base) == 275
    fila = base.loc["EV0275"]
    assert (fila["titulo"], fila["origen"], fila["cargado_por"], fila["fuente"]) == \
           ("Noticia importada uno", "archivo", "Francis", "glocalminds.com")
    h = repo.historial_df(almacen)
    assert h.iloc[0]["accion"] == "carga" and h.iloc[0]["lote_id"]
    assert almacen.listar_respaldos(), "se guarda un respaldo antes de importar"
    assert any("Se importaron 1 noticia" in s.value for s in app.success)
    # y se puede deshacer completa
    res = repo.revertir_lote(h.iloc[0]["lote_id"], "Francis", almacen)
    assert res.ids_eliminados == ["EV0275"]


def test_archivo_ilegible_da_mensaje_claro(app):
    app.file_uploader[0].set_value(("roto.xlsx", b"esto no es un excel", "application/octet-stream"))
    app.run()
    assert not app.exception
    assert any("No se pudo" in e.value for e in app.error)


def test_columnas_obligatorias_sin_mapear(app):
    _subir(app, "Lugar,Resumen\nValparaíso,algo\n")
    assert any("Falta mapear columnas obligatorias" in e.value for e in app.error)


def test_sin_nombre_no_se_puede_enviar(monkeypatch, almacen):
    apuntar_a(monkeypatch, almacen)
    at = nueva_app()
    iniciar_sesion(at)
    at.session_state["auth_nombre"] = None
    at.switch_page(PAGINA).run()
    assert any("Elige tu nombre" in w.value for w in at.warning)
    assert next(b for b in at.button if b.label == "Agregar noticia").disabled
