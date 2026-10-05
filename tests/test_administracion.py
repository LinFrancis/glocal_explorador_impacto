# -*- coding: utf-8 -*-
"""Página «Administración»: categorías, asignación en lote, notas, calidad, duplicados y respaldo."""
import pytest

from tests.apptest_util import apuntar_a, iniciar_sesion, nueva_app
from utils import repo
from utils import schema as S

PAGINA = "app_pages/administracion.py"


@pytest.fixture
def app(monkeypatch, almacen):
    apuntar_a(monkeypatch, almacen)
    at = nueva_app()
    iniciar_sesion(at, nombre="Francis")
    at.switch_page(PAGINA).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _boton(at, etiqueta):
    return next(b for b in at.button if b.label == etiqueta)


def _fila(almacen, ide):
    return almacen.leer_base_texto().set_index("id_evento", drop=False).loc[ide]


def _tablas(at, columna):
    return [t.value for t in at.dataframe if columna in getattr(t.value, "columns", [])]


def test_renderiza_las_nueve_pestanas(app):
    assert len(app.tabs) == 9
    assert not app.exception


# ----------------------------------------------------------------------------- categorías
def test_catalogo_sembrado_con_uso(app):
    t = _tablas(app, "Categoría")[0]
    assert len(t) >= 20 and {"Categoría macro", "Categoría temática"} <= set(t["Dimensión"])
    assert t["Noticias"].sum() > 274 and t["Activa"].all()


def test_crear_categoria(app, almacen):
    next(s for s in app.selectbox if s.label == "Dimensión" and s.key != "asig_dim").select("categorias")
    next(t for t in app.text_input if t.label == "Nombre *").set_value("Categoría nueva de prueba")
    next(b for b in app.button if b.label == "Crear categoría").click()
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    assert "Categoría nueva de prueba" in repo.catalogo_activo(almacen)["categorias"]
    assert any("creada" in s.value for s in app.success)


def test_crear_categoria_duplicada_da_error(app, almacen):
    existente = repo.catalogo_activo(almacen)["categoria_macro"][0]
    next(t for t in app.text_input if t.label == "Nombre *").set_value(existente.upper())
    next(b for b in app.button if b.label == "Crear categoría").click()
    app.run()
    assert any("ya existe" in e.value for e in app.error)


def test_sin_nombre_no_se_puede_crear(monkeypatch, almacen):
    apuntar_a(monkeypatch, almacen)
    at = nueva_app()
    iniciar_sesion(at)
    at.session_state["auth_nombre"] = None
    at.switch_page(PAGINA).run()
    assert next(b for b in at.button if b.label == "Crear categoría").disabled


# ----------------------------------------------------------------------------- asignar
def test_asignar_categoria_en_lote_y_deshacer(app, almacen):
    repo.crear_categoria("categorias", "Etiqueta de prueba", "", "Ana", almacen)
    app.run()
    app.selectbox(key="asig_dim").select("categorias").run()
    app.selectbox(key="asig_cat_categorias").select("Etiqueta de prueba").run()
    app.text_input(key="asig_texto").set_value("EV0001").run()
    app.checkbox(key="asig_todas_categorias_Agregar_Etiqueta de prueba").check().run()
    assert not app.exception, [e.value for e in app.exception]
    boton = next(b for b in app.button if b.label.startswith("Agregar «Etiqueta de prueba»"))
    assert boton.label == "Agregar «Etiqueta de prueba» en 1 noticia(s)"
    boton.click()
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    assert "Etiqueta de prueba" in S.dividir_etiquetas(_fila(almacen, "EV0001")["categorias"])
    lote = repo.lotes_df(almacen).iloc[0]
    assert lote["accion"] == "Categoría" and lote["n_noticias"] == 1
    repo.revertir_lote(lote["lote_id"], "Francis", almacen)
    assert "Etiqueta de prueba" not in _fila(almacen, "EV0001")["categorias"]


def test_asignar_sin_categoria_elegida_no_deja_aplicar(app):
    assert next(b for b in app.button if b.label.startswith("Agregar «")).disabled


# ----------------------------------------------------------------------------- bitácora
def test_bitacora_general_lista_notas(app, almacen):
    repo.agregar_nota("EV0001", "Primera nota del equipo", "Ana", almacen)
    repo.agregar_nota("EV0002", "Otra nota distinta", "Beto", almacen)
    app.run()
    t = _tablas(app, "Nota")[0]
    assert t["Nota"].tolist() == ["Otra nota distinta", "Primera nota del equipo"] and t["Quién"].tolist() == ["Beto", "Ana"]
    app.text_input(key="notas_buscar").set_value("equipo").run()
    assert _tablas(app, "Nota")[0]["Nota"].tolist() == ["Primera nota del equipo"]


def test_bitacora_vacia(app):
    assert any("Todavía no hay notas" in i.value for i in app.info)


# ----------------------------------------------------------------------------- calidad
def test_resumen_de_calidad(app):
    t = _tablas(app, "Revisión")[0].set_index("Revisión")
    assert t.loc["Fechas de texto que no se reconocen", "Casos"] == 12 and t.loc["Fechas de texto que no se reconocen", "Noticias"] == 6
    assert t.loc["Fechas de publicación en 1 de enero", "Casos"] == 3
    assert t.loc["Campos obligatorios vacíos o inválidos", "Casos"] == 0
    assert any(b.label.startswith("Aplicar") and b.label.endswith("corrección(es)") for b in app.button)


# ----------------------------------------------------------------------------- duplicados
def test_duplicados_marcar_como_misma(app, almacen):
    assert any("par(es) pendiente(s)" in c.value for c in app.caption)
    _boton(app, "Son la misma noticia").click()
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    d = repo.decisiones_duplicados(almacen)
    assert len(d) == 1 and d.iloc[0]["decision"] == "duplicado"
    secundarias = almacen.leer_base_texto()["es_duplicado_secundario"].eq("True").sum()
    assert secundarias == 1
    assert any("duplicado secundario" in s.value for s in app.success)


def test_duplicados_son_distintas_no_vuelve_a_aparecer(app, almacen):
    antes = int(next(c.value for c in app.caption if "par(es) pendiente(s)" in c.value).split()[0])
    _boton(app, "Son distintas").click()
    app.run()
    despues_txt = [c.value for c in app.caption if "par(es) pendiente(s)" in c.value]
    despues = int(despues_txt[0].split()[0]) if despues_txt else 0
    assert despues == antes - 1
    assert repo.decisiones_duplicados(almacen).iloc[0]["decision"] == "distintas"
    assert not (almacen.leer_base_texto()["es_duplicado_secundario"] == "True").any()


# ----------------------------------------------------------------------------- sincronización y respaldo
def test_sincronizacion_sin_historial(app):
    assert any("Aún no se ha sincronizado" in i.value for i in app.info)
    assert any("Origen de las noticias: historico: 274" in c.value for c in app.caption)


def test_regenerar_libro_de_codigos(app, almacen):
    n = len(almacen.leer_hoja_texto(S.HOJA_LIBRO))
    _boton(app, "Regenerar el libro de códigos").click()
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    assert any("Libro de códigos regenerado" in s.value for s in app.success)
    assert len(almacen.leer_hoja_texto(S.HOJA_LIBRO)) == n


def test_respaldos_listados_y_restablecer_protegido(app, almacen):
    almacen.respaldar("prueba")
    app.run()
    t = _tablas(app, "Archivo")[0]
    assert len(t) == 1 and "BACKUP" in t.iloc[0]["Archivo"] and t.iloc[0]["Tamaño (KB)"] > 0
    repo.agregar_nota("EV0001", "no debe perderse sin la clave", "Ana", almacen)
    _boton(app, "Restablecer desde el original").click()
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    assert len(repo.notas_df(almacen)) == 1                                     # abrir el diálogo no restablece nada
