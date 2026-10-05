# -*- coding: utf-8 -*-
"""Acceso a la plataforma: login con clave compartida + clave de administración.

Esto NO es autenticación individual: la clave la conoce todo el equipo. Tras la clave, cada persona
elige su nombre de una lista (la primera vez lo escribe y queda registrado), para que el historial
atribuya los cambios de forma consistente. Es una barrera razonable para una herramienta interna;
para identidad real habría que usar `st.login` (OIDC).

Las credenciales se leen de `.streamlit/secrets.toml` (sección [auth], o [oauth] con username y password)
y, si no existen, se usan los valores por defecto de desarrollo. En producción conviene fijarlas en los secrets:

    [auth]
    usuario = "Impacto"
    clave = "..."
    clave_admin = "..."
"""
from __future__ import annotations

import hmac
import time

import streamlit as st

from utils.storage import ErrorAlmacen
from utils.style import dual_logo_html, inject
from utils.ui import flash

USUARIO_POR_DEFECTO = "Impacto"
CLAVE_POR_DEFECTO = "glocal"
CLAVE_ADMIN_POR_DEFECTO = "glocal-admin"

MAX_INTENTOS = 5
ESPERA_SEGUNDOS = 30

K_OK = "auth_ok"
K_NOMBRE = "auth_nombre"
K_CLAVE_OK = "auth_clave_ok"            # clave correcta; falta elegir el nombre
K_INTENTOS = "auth_intentos"
K_BLOQUEO = "auth_bloqueo_hasta"
K_INTENTOS_ADMIN = "auth_admin_intentos"
K_BLOQUEO_ADMIN = "auth_admin_bloqueo_hasta"


# ----------------------------------------------------------------------------- credenciales
def _secreto(clave: str, defecto: str) -> str:
    """Valor de los secretos: sección [auth] (usuario, clave, clave_admin) o, para el acceso, [oauth] (username, password)."""
    alias_oauth = {"usuario": "username", "clave": "password"}
    for seccion, nombre in (("auth", clave), ("oauth", alias_oauth.get(clave, ""))):
        try:
            valor = st.secrets[seccion][nombre]
            if valor:
                return str(valor)
        except Exception:  # noqa: BLE001  (sin secrets.toml, sin esa sección o sin esa clave)
            continue
    return defecto


def _iguales(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def verificar_credenciales(usuario: str, clave: str) -> bool:
    """Compara en tiempo constante. El usuario no distingue mayúsculas; la clave sí."""
    u_ok = _iguales(usuario.strip().casefold(), _secreto("usuario", USUARIO_POR_DEFECTO).casefold())
    c_ok = _iguales(clave, _secreto("clave", CLAVE_POR_DEFECTO))
    return u_ok and c_ok


def verificar_clave_admin(clave: str) -> bool:
    return _iguales(clave, _secreto("clave_admin", CLAVE_ADMIN_POR_DEFECTO))


def _segundos_de_espera(k_bloqueo: str) -> int:
    return max(0, int(st.session_state.get(k_bloqueo, 0) - time.time()))


def _registrar_fallo(k_intentos: str, k_bloqueo: str) -> None:
    n = st.session_state.get(k_intentos, 0) + 1
    st.session_state[k_intentos] = n
    if n >= MAX_INTENTOS:
        st.session_state[k_bloqueo] = time.time() + ESPERA_SEGUNDOS
        st.session_state[k_intentos] = 0


# ----------------------------------------------------------------------------- sesión
def esta_autenticado() -> bool:
    return bool(st.session_state.get(K_OK))


def nombre_actual() -> str:
    """Nombre con el que se registran los cambios de esta sesión."""
    return str(st.session_state.get(K_NOMBRE) or "").strip()


def cerrar_sesion() -> None:
    for k in (K_OK, K_NOMBRE, K_CLAVE_OK, K_INTENTOS, K_BLOQUEO, K_INTENTOS_ADMIN, K_BLOQUEO_ADMIN):
        st.session_state.pop(k, None)


def _nombres_registrados() -> list[str]:
    """Lista del equipo (hoja «Editores» + quienes figuran en el historial); vacía si no se puede leer.
    Se lee con la caché por firma del archivo: no cuesta nada en cada ejecución de la página."""
    from utils import repo
    from utils import schema as S
    from utils.data import leer_hoja
    try:
        return repo.nombres_desde_hojas(leer_hoja(S.HOJA_EDITORES), leer_hoja(S.HOJA_HISTORIAL))
    except Exception:  # noqa: BLE001  (sin lista, la persona escribe su nombre y se registra)
        return []


def requerir_login() -> None:
    """Muestra el login y detiene el script si no hay sesión. Se llama en el entrypoint, antes de
    `st.navigation`, así que protege todas las páginas (también las URL directas)."""
    if not esta_autenticado():
        _render_login()
        st.stop()


def _render_login() -> None:
    inject(sidebar_logos=False)
    _, centro, _ = st.columns([1, 1.5, 1])
    with centro:
        st.markdown(
            f"""
            <div class="gm-login-brand">
                {dual_logo_html(height=46, separator=False, sobre="oscuro")}
                <p class="gm-eyebrow">Plataforma interna</p>
                <h1>Impacto Glocal</h1>
                <p>Gestión de información sobre impacto social de Glocal Minds y Fundación Glocal.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            if st.session_state.get(K_CLAVE_OK):
                _paso_nombre()
            else:
                _paso_clave()
        st.caption("¿Problemas para entrar? Pide la clave a quien administra la plataforma.")


def _paso_clave() -> None:
    espera = _segundos_de_espera(K_BLOQUEO)
    st.subheader("Iniciar sesión")
    with st.form("login", border=False):
        usuario = st.text_input("Usuario", autocomplete="username")
        clave = st.text_input("Contraseña", type="password", autocomplete="current-password")
        enviado = st.form_submit_button("Continuar", type="primary", width="stretch",
                                        icon=":material/login:", disabled=espera > 0)
    if espera > 0:
        st.warning(f"Demasiados intentos fallidos. Vuelve a intentarlo en {espera} segundos.",
                   icon=":material/lock_clock:")
    elif enviado:
        if verificar_credenciales(usuario, clave):
            st.session_state[K_CLAVE_OK] = True
            st.session_state.pop(K_INTENTOS, None)
            st.rerun()
        else:
            _registrar_fallo(K_INTENTOS, K_BLOQUEO)
            st.error("Usuario o contraseña incorrectos.")


def _paso_nombre() -> None:
    """Segundo paso: elegir el nombre de la lista del equipo (o escribirlo la primera vez)."""
    from utils import repo
    st.subheader("¿Quién eres?")
    st.caption("Tu nombre queda en el historial como autor de tus cambios. Elígelo de la lista; "
               "si es tu primera vez, escríbelo abajo y quedará registrado para las próximas.")
    with st.form("nombre", border=False):
        nombre = st.selectbox("Tu nombre", _nombres_registrados(), index=None, placeholder="Elige tu nombre en la lista",
                              key="auth_nombre_elegido")
        nuevo = st.text_input("¿Primera vez? Escribe tu nombre", key="auth_nombre_nuevo", max_chars=80,
                              placeholder="Ej.: Francis Mason",
                              help="Solo si no apareces en la lista. Se agrega al equipo y la próxima vez lo eliges arriba.")
        entrar = st.form_submit_button("Entrar", type="primary", width="stretch", icon=":material/login:")
    if st.button("Volver", icon=":material/arrow_back:", key="auth_volver", type="tertiary"):
        st.session_state.pop(K_CLAVE_OK, None)
        st.rerun()
    if entrar:
        if not (nuevo or "").strip() and not nombre:
            st.error("Elige tu nombre en la lista o escríbelo si es tu primera vez: se usa para registrar quién hace cada cambio.")
            return
        try:
            elegido = repo.registrar_editor((nuevo or "").strip() or nombre)       # lo escrito manda sobre lo elegido
        except (repo.ErrorOperacion, ErrorAlmacen) as e:
            st.error(str(e))
            return
        st.session_state[K_OK] = True
        st.session_state[K_NOMBRE] = elegido
        st.session_state.pop(K_CLAVE_OK, None)
        st.rerun()


def _agregar_nombre() -> None:
    """Registra el nombre escrito en el panel lateral y lo deja como «Editando como»."""
    from utils import repo
    texto = st.session_state.get("auth_nombre_nuevo_lateral", "")
    try:
        st.session_state[K_NOMBRE] = repo.registrar_editor(texto)
    except (repo.ErrorOperacion, ErrorAlmacen) as e:
        flash("error", str(e))
        return
    st.session_state["auth_nombre_nuevo_lateral"] = ""


def widget_sesion() -> None:
    """Bloque del sidebar: quién está editando (se elige de la lista del equipo) + cerrar sesión."""
    if not st.session_state.get(K_NOMBRE):
        st.session_state.pop(K_NOMBRE, None)              # un valor vacío no es una opción de la lista
    nombres = _nombres_registrados()
    actual = nombre_actual()
    if actual and actual not in nombres:
        nombres = sorted(nombres + [actual], key=str.casefold)
    with st.sidebar:
        with st.container(border=True):
            # La clave del widget ES el nombre vigente de la sesión (se puede cambiar aquí).
            st.selectbox("Editando como", nombres, index=None, key=K_NOMBRE, placeholder="Elige tu nombre",
                         help="Este nombre queda en el historial de cambios. Elígelo de la lista del equipo.")
            with st.popover("Agregar un nombre", icon=":material/person_add:", width="stretch"):
                st.text_input("Nombre nuevo", key="auth_nombre_nuevo_lateral", max_chars=80,
                              help="Se agrega a la lista del equipo y pasa a ser tu nombre en esta sesión.")
                st.button("Agregar y usar", key="auth_nombre_agregar", on_click=_agregar_nombre, width="stretch")
            st.button("Cerrar sesión", icon=":material/logout:", on_click=cerrar_sesion, width="stretch")


# ----------------------------------------------------------------------------- clave de administración
def procesar_clave_admin(clave: str, ejecutar) -> tuple[str, str]:
    """Verifica la clave de administración y, si es correcta, ejecuta la acción.

    Devuelve (estado, mensaje): "ok" (mensaje = resultado de `ejecutar`), "error" (la acción falló con un
    mensaje apto para el usuario), "incorrecta" o "bloqueado" (demasiados intentos; se espera unos segundos).
    """
    from utils.repo import ErrorOperacion
    from utils.storage import ErrorAlmacen

    espera = _segundos_de_espera(K_BLOQUEO_ADMIN)
    if espera > 0:
        return "bloqueado", f"Demasiados intentos. Espera {espera} segundos."
    if not verificar_clave_admin(clave):
        _registrar_fallo(K_INTENTOS_ADMIN, K_BLOQUEO_ADMIN)
        return "incorrecta", "Clave incorrecta."
    st.session_state.pop(K_INTENTOS_ADMIN, None)
    try:
        return "ok", ejecutar() or "Listo."
    except (ErrorOperacion, ErrorAlmacen) as e:
        return "error", str(e)


@st.dialog("Confirmar con la clave de administración")
def _dialogo_clave(titulo: str, descripcion: str, ejecutar) -> None:
    st.markdown(f"**{titulo}**")
    st.write(descripcion)
    espera = _segundos_de_espera(K_BLOQUEO_ADMIN)
    clave = st.text_input("Clave de administración", type="password", key="admin_clave_dialogo")
    if espera > 0:
        st.warning(f"Demasiados intentos. Espera {espera} segundos.")
    if st.button("Confirmar", type="primary", disabled=espera > 0, key="admin_confirmar"):
        estado, mensaje = procesar_clave_admin(clave, ejecutar)
        if estado in ("ok", "error"):
            flash("exito" if estado == "ok" else "error", mensaje)
            st.rerun()
        else:
            st.error(mensaje)


def accion_protegida(etiqueta: str, descripcion: str, ejecutar, *, key: str, icon: str | None = None,
                     type: str = "secondary", width="content", help: str | None = None,
                     disabled: bool = False) -> None:
    """Botón que pide la clave de administración antes de ejecutar `ejecutar()`.

    `ejecutar` no recibe argumentos y devuelve el mensaje de éxito (str). Si lanza ErrorOperacion
    o ErrorAlmacen, el mensaje se muestra como error. El resultado se informa tras recargar.
    """
    if st.button(etiqueta, key=key, icon=icon, type=type, width=width, help=help, disabled=disabled):
        _dialogo_clave(etiqueta, descripcion, ejecutar)
