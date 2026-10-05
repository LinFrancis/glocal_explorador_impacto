# -*- coding: utf-8 -*-
"""Variables analíticas propias: nuevas categorías que el equipo define (nombre, tipo y opciones de respuesta).

Ejemplo: «Tamaño del proyecto», opción única, con las opciones pequeño / mediano / grande. Cada variable
se guarda como una fila de la hoja `Variables` y como una columna `var_<nombre>` de Base_Datos, y se
registra en el esquema (`schema.registrar_variables`) para que formularios, tabla, filtros, exportación y
análisis la traten como cualquier otro campo. Este módulo es lógica pura (sin Streamlit ni disco).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from utils import schema as S

PREFIJO = "var_"
MAX_VARIABLES = 40
MAX_OPCIONES = 40
MAX_LARGO_NOMBRE = 60
MAX_LARGO_OPCION = 60
OPCIONES_SI_NO = ("Sí", "No")
SIN_DATO = "(sin dato)"

# tipo de variable -> (descripción para el usuario, tipo del campo en el esquema, ¿lleva lista de opciones?)
TIPOS: dict[str, tuple[str, str, bool]] = {
    "opcion": ("Opción única — se elige una de las opciones", S.OPCION, True),
    "etiquetas": ("Opciones múltiples — se pueden elegir varias", S.ETIQUETAS, True),
    "si_no": ("Sí / No", S.OPCION, False),
    "texto": ("Texto corto", S.TEXTO, False),
    "texto_largo": ("Texto largo", S.TEXTO_LARGO, False),
    "numero": ("Número (por ejemplo, presupuesto o personas)", S.NUMERO, False),
    "fecha": ("Fecha", S.FECHA, False),
    "url": ("Enlace (URL)", S.URL, False),
}
TIPOS_CON_OPCIONES = tuple(k for k, v in TIPOS.items() if v[2])


class ErrorVariable(Exception):
    """Datos de la variable inválidos; el mensaje está en español y se muestra tal cual."""


@dataclass(frozen=True)
class Variable:
    clave: str                        # nombre de la columna: var_tamano_proyecto
    etiqueta: str                     # cómo se muestra: «Tamaño del proyecto»
    tipo: str                         # llave de TIPOS
    opciones: tuple[str, ...] = ()
    descripcion: str = ""
    activa: bool = True
    orden: int = 0

    @property
    def lleva_opciones(self) -> bool:
        return self.tipo in TIPOS_CON_OPCIONES

    @property
    def multiple(self) -> bool:
        return self.tipo == "etiquetas"

    @property
    def es_de_opciones(self) -> bool:
        """True si sus valores salen de una lista cerrada (opción única, múltiple o sí/no)."""
        return self.tipo in TIPOS_CON_OPCIONES or self.tipo == "si_no"

    @property
    def opciones_efectivas(self) -> tuple[str, ...]:
        return OPCIONES_SI_NO if self.tipo == "si_no" else self.opciones


# ----------------------------------------------------------------------------- nombres
def sin_tildes(texto: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def slug(texto: str) -> str:
    """'Tamaño del proyecto' -> 'tamano_del_proyecto'."""
    s = re.sub(r"[^a-z0-9]+", "_", sin_tildes(str(texto)).lower()).strip("_")
    return s[:40].strip("_")


def clave_de(etiqueta: str) -> str:
    return PREFIJO + slug(etiqueta)


def limpiar_etiqueta(texto: str) -> str:
    """Nombre tal como lo escribió la persona, ordenado: espacios simples y, si lo escribió como identificador
    (`tamaño_proyecto`), con espacios en vez de guiones bajos y la primera letra en mayúscula."""
    e = " ".join(str(texto or "").split())
    if "_" in e and " " not in e:
        e = e.replace("_", " ")
        e = e[:1].upper() + e[1:]
    return e


# ----------------------------------------------------------------------------- opciones
def normalizar_opciones(opciones, tipo: str) -> tuple[str, ...]:
    """Lista de opciones limpia y validada (sin repetidas, aunque difieran en mayúsculas o tildes)."""
    if tipo == "si_no":
        return ()
    if tipo not in TIPOS_CON_OPCIONES:
        return ()
    if isinstance(opciones, str):
        opciones = opciones.splitlines()
    vistas: dict[str, str] = {}
    for o in opciones or []:
        o = " ".join(str(o).split())
        if not o:
            continue
        if ";" in o or "|" in o:
            raise ErrorVariable(f"La opción «{o[:30]}» no puede llevar «;» ni «|».")
        if len(o) > MAX_LARGO_OPCION:
            raise ErrorVariable(f"La opción «{o[:30]}…» es demasiado larga (máximo {MAX_LARGO_OPCION} caracteres).")
        clave = sin_tildes(o).lower()
        if clave in vistas:
            raise ErrorVariable(f"La opción «{o}» está repetida (también aparece como «{vistas[clave]}»).")
        vistas[clave] = o
    if len(vistas) < 2:
        raise ErrorVariable("Una variable de opciones necesita al menos 2 opciones de respuesta.")
    if len(vistas) > MAX_OPCIONES:
        raise ErrorVariable(f"Demasiadas opciones (máximo {MAX_OPCIONES}).")
    return tuple(vistas.values())


# ----------------------------------------------------------------------------- conversión
def a_campo(v: Variable) -> S.Campo:
    """La variable como campo del esquema."""
    _, tipo_campo, _ = TIPOS[v.tipo]
    return S.Campo(
        key=v.clave, label=v.etiqueta, tipo=tipo_campo, grupo=S.G_VARIABLES, editable=True,
        opciones=tuple(v.opciones_efectivas) if v.es_de_opciones else None, ayuda=v.descripcion,
        variable=True, activo=v.activa,
    )


def desde_filas(filas: list[dict]) -> list[Variable]:
    """Variables a partir de las filas de la hoja `Variables` (en texto), ordenadas por `orden`."""
    salida = []
    for i, f in enumerate(filas):
        clave, tipo = str(f.get("clave", "")).strip(), str(f.get("tipo", "")).strip()
        if not clave.startswith(PREFIJO) or tipo not in TIPOS:
            continue
        try:
            orden = int(float(str(f.get("orden") or i)))
        except ValueError:
            orden = i
        salida.append(Variable(
            clave=clave, etiqueta=str(f.get("etiqueta", "")).strip() or clave, tipo=tipo,
            opciones=tuple(S.dividir_etiquetas(f.get("opciones", ""))), descripcion=str(f.get("descripcion", "")).strip(),
            activa=str(f.get("activa", "True")).strip().lower() != "false", orden=orden))
    return sorted(salida, key=lambda v: (v.orden, v.clave))


def a_fila(v: Variable, usuario: str, fecha_hora: str) -> dict[str, str]:
    return {"clave": v.clave, "etiqueta": v.etiqueta, "tipo": v.tipo, "opciones": S.unir_etiquetas(v.opciones),
            "descripcion": v.descripcion, "activa": "True" if v.activa else "False", "orden": str(v.orden),
            "creada_por": usuario, "fecha_hora": fecha_hora}


def campos_de(variables: list[Variable]) -> list[S.Campo]:
    return [a_campo(v) for v in variables]


def validar_nueva(etiqueta: str, tipo: str, opciones, existentes: list[Variable]) -> tuple[str, str, tuple[str, ...]]:
    """Valida los datos de una variable nueva. Devuelve (etiqueta limpia, clave, opciones limpias)."""
    et = limpiar_etiqueta(etiqueta)
    if not et:
        raise ErrorVariable("Escribe el nombre de la variable.")
    if len(et) > MAX_LARGO_NOMBRE:
        raise ErrorVariable(f"El nombre es demasiado largo (máximo {MAX_LARGO_NOMBRE} caracteres).")
    if tipo not in TIPOS:
        raise ErrorVariable("Elige un tipo de variable válido.")
    clave = clave_de(et)
    if clave == PREFIJO:
        raise ErrorVariable("El nombre debe tener al menos una letra o un número.")
    if len(existentes) >= MAX_VARIABLES:
        raise ErrorVariable(f"Se alcanzó el máximo de {MAX_VARIABLES} variables.")
    nombres = {sin_tildes(v.etiqueta).lower() for v in existentes} | {sin_tildes(c.label).lower() for c in S.CAMPOS_BASE}
    if clave in {v.clave for v in existentes} or sin_tildes(et).lower() in nombres:
        raise ErrorVariable(f"Ya existe un campo o variable llamado «{et}».")
    return et, clave, normalizar_opciones(opciones, tipo)


# ----------------------------------------------------------------------------- valores contra la lista de opciones
def canonizar(campo, texto: str) -> str:
    """Si `campo` es una variable de opciones, devuelve `texto` con cada valor escrito como la opción oficial
    (acepta otras mayúsculas o tildes: «grande» -> «Grande»). Lo que no coincide queda tal cual."""
    if campo is None or not getattr(campo, "variable", False) or not isinstance(campo.opciones, tuple) or not campo.opciones:
        return texto
    por_clave = {sin_tildes(o).lower(): o for o in campo.opciones}
    partes = S.dividir_etiquetas(texto) if campo.tipo == S.ETIQUETAS else ([str(texto).strip()] if str(texto).strip() else [])
    nuevas = [por_clave.get(sin_tildes(p).lower(), p) for p in partes]
    return S.unir_etiquetas(nuevas) if campo.tipo == S.ETIQUETAS else (nuevas[0] if nuevas else "")


def valores_invalidos(campo, texto: str) -> list[str]:
    """Valores que NO son una opción de una variable propia de opciones (lista cerrada). [] si todo es válido."""
    if campo is None or not getattr(campo, "variable", False) or not isinstance(campo.opciones, tuple) or not campo.opciones:
        return []
    t = str(texto or "").strip()
    if not t:
        return []
    partes = S.dividir_etiquetas(t) if campo.tipo == S.ETIQUETAS else [t]
    return [p for p in partes if p not in campo.opciones]
