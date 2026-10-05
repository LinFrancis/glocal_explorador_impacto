# -*- coding: utf-8 -*-
"""Punto de entrada: login + navegación agrupada.

El login se resuelve ANTES de `st.navigation`, así que protege todas las páginas (también las
URL directas). Las páginas viven en `app_pages/` (más `sections/inicio.py` para el panel de Inicio).
"""
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

import streamlit as st

PAQUETES = ("utils", "sections")


def _recargar_si_cambio_el_codigo() -> None:
    """Descarta los módulos ya importados cuando el código cambió en disco.

    Streamlit no siempre detecta los cambios de `utils/` y `sections/` (por ejemplo, en carpetas sincronizadas
    con Google Drive): el servidor sigue con módulos viejos y aparecen errores como «no tiene el atributo…».
    Se compara una firma de los archivos .py en cada ejecución; si cambió, se vuelven a importar. En un servidor
    recién iniciado no hay nada que descartar, y la firma estable no cuesta nada en producción.
    """
    if os.environ.get("GLOCAL_RECARGA_CODIGO") == "0":          # las pruebas automáticas la desactivan
        return
    firma = tuple(sorted(
        (str(p), p.stat().st_mtime_ns) for paquete in PAQUETES for p in (RAIZ / paquete).glob("*.py")
    ))
    if getattr(sys, "_glocal_firma_codigo", None) == firma:
        return
    for nombre in [n for n in sys.modules if n.split(".")[0] in PAQUETES]:
        del sys.modules[nombre]
    sys._glocal_firma_codigo = firma
    st.cache_data.clear()


_recargar_si_cambio_el_codigo()

from sections import inicio as sec_inicio
from utils import auth, seleccion
from utils.data import almacen_actual
from utils.storage import ErrorAlmacen

st.set_page_config(page_title="Impacto Glocal", page_icon=":material/hub:", layout="wide")

auth.requerir_login()

try:
    almacen_actual()          # crea y migra el libro de trabajo la primera vez
except ErrorAlmacen as e:
    st.error(f"No se pudo abrir la base de datos. {e}", icon=":material/error:")
    st.stop()


secciones = {
    "Plataforma": [
        st.Page(sec_inicio.render, title="Inicio", icon=":material/home:", url_path="inicio", default=True),
        st.Page("app_pages/explorador.py", title="Explorador Glocal", icon=":material/travel_explore:", url_path="explorador-glocal"),
    ],
    "Gestión": [
        st.Page("app_pages/ficha.py", title="Fichas de noticia", icon=":material/article:", url_path="fichas"),
        st.Page("app_pages/tabla.py", title="Tabla de datos", icon=":material/table_view:", url_path="tabla"),
        st.Page("app_pages/carga.py", title="Cargar información", icon=":material/upload_file:", url_path="cargar"),
        st.Page("app_pages/sincronizar.py", title="Sincronizar con la web", icon=":material/sync:", url_path="sincronizar"),
        st.Page("app_pages/historial.py", title="Historial de cambios", icon=":material/history:", url_path="historial"),
    ],
    "Administración": [
        st.Page("app_pages/administracion.py", title="Administración", icon=":material/admin_panel_settings:", url_path="administracion"),
    ],
    "Referencia": [
        st.Page("app_pages/marco_teorico.py", title="Marco teórico", icon=":material/menu_book:", url_path="marco-teorico"),
        st.Page("app_pages/glosario.py", title="Glosario", icon=":material/translate:", url_path="glosario"),
    ],
}

navegacion = st.navigation(secciones, position="sidebar")
auth.widget_sesion()
seleccion.widget_sidebar()
navegacion.run()
