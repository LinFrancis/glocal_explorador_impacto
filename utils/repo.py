# -*- coding: utf-8 -*-
"""Operaciones de negocio sobre el libro: toda escritura pasa por aquí y deja historial.

Principios:
- Cada operación abre UNA transacción (bloqueo + relectura del archivo vigente + guardado
  atómico). Si falla algo, no se guarda nada.
- Cada cambio de celda se registra en la hoja Historial (quién, qué, cuándo, antes → después).
  El historial es solo-agregar: revertir agrega nuevas entradas, nunca borra.
- Antes de cambiar una celda se comprueba que su valor actual sea el que la persona vio
  ("antes"). Si otra sesión la cambió entretanto, el cambio se omite y se informa.
- Las funciones reciben `almacen` (por defecto el libro de trabajo) para poder probarlas con una copia temporal.
"""
from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from utils import dedupe, libro_codigos
from utils import schema as S
from utils import variables as V
from utils.storage import Libro, LocalStorage, ahora, get_storage
from utils.validation import a_texto, normalizar, validar_fila

REGISTRO = "(registro completo)"      # valor de `campo` en las entradas de alta/baja de una noticia
MAX_CELDA = 32000                     # límite de Excel: 32 767 caracteres por celda


# ============================================================================ tipos
@dataclass
class Cambio:
    id_evento: str
    campo: str
    antes: str          # valor que la persona vio (para detectar conflictos)
    despues: str
    revierte_a: str = ""


@dataclass
class Resultado:
    lote_id: str
    aplicados: list[dict] = field(default_factory=list)    # {id_cambio, id_evento, campo, antes, despues}
    omitidos: list[dict] = field(default_factory=list)     # {id_evento, campo, motivo}
    avisos: list[str] = field(default_factory=list)
    ids_creados: list[str] = field(default_factory=list)
    ids_eliminados: list[str] = field(default_factory=list)

    @property
    def n_aplicados(self) -> int:
        return len(self.aplicados) + len(self.ids_creados) + len(self.ids_eliminados)

    @property
    def n_noticias(self) -> int:
        return len({a["id_evento"] for a in self.aplicados} | set(self.ids_creados) | set(self.ids_eliminados))

    @property
    def ok(self) -> bool:
        return not self.omitidos

    def resumen(self) -> str:
        partes = []
        if self.aplicados:
            partes.append(f"{len(self.aplicados)} cambio(s) en {len({a['id_evento'] for a in self.aplicados})} noticia(s)")
        if self.ids_creados:
            partes.append(f"{len(self.ids_creados)} noticia(s) agregada(s)")
        if self.ids_eliminados:
            partes.append(f"{len(self.ids_eliminados)} noticia(s) retirada(s)")
        if not partes:
            partes.append("Sin cambios")
        if self.omitidos:
            partes.append(f"{len(self.omitidos)} omitido(s)")
        return "; ".join(partes)


class _NadaQueGuardar(Exception):
    """Aborta la transacción sin guardar (no hubo cambios reales)."""


class ErrorOperacion(Exception):
    """Error de uso (p. ej. falta el nombre del editor): el mensaje se muestra tal cual."""


# ============================================================================ utilidades
def _almacen(almacen: LocalStorage | None) -> LocalStorage:
    return almacen or get_storage()


def nuevo_lote(prefijo: str = "L") -> str:
    return f"{prefijo}{datetime.now():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:4]}"


def _usuario(usuario: str | None) -> str:
    u = (usuario or "").strip()
    if not u:
        raise ErrorOperacion("Falta el nombre de quien edita. Indícalo en el inicio de sesión o en el panel lateral.")
    return u[:80]


def _snapshot(datos: dict[str, str]) -> str:
    """JSON compacto de los campos no vacíos de un registro (para poder restaurarlo)."""
    limpio = {k: v for k, v in datos.items() if v not in ("", None)}
    s = json.dumps(limpio, ensure_ascii=False, separators=(",", ":"))
    if len(s) > MAX_CELDA:
        for larga in ("contenido_completo", "preview_contenido", "descripcion_catalogo"):
            limpio.pop(larga, None)
            s = json.dumps({**limpio, "_truncado": True}, ensure_ascii=False, separators=(",", ":"))
            if len(s) <= MAX_CELDA:
                break
    return s


class _Sesion:
    """Contexto de una operación: transacción abierta + datos comunes del registro."""

    def __init__(self, libro: Libro, usuario: str, accion: str, lote_id: str):
        self.libro = libro
        self.usuario = usuario
        self.accion = accion
        self.ts = ahora()
        self.res = Resultado(lote_id=lote_id)
        self._n = libro.max_numero(S.HOJA_HISTORIAL, "id_cambio")
        self.tocados: set[str] = set()

    def registrar(self, ide: str, campo: str, antes: str, despues: str,
                  accion: str | None = None, revierte_a: str = "") -> str:
        self._n += 1
        idc = f"CH{self._n:06d}"
        self.libro.agregar_registro(S.HOJA_HISTORIAL, {
            "id_cambio": idc, "fecha_hora": self.ts, "usuario": self.usuario, "id_evento": ide,
            "campo": campo, "valor_antes": antes, "valor_despues": despues,
            "accion": accion or self.accion, "lote_id": self.res.lote_id, "revierte_a": revierte_a,
        })
        return idc

    def sellar(self) -> None:
        for ide in self.tocados:
            if self.libro.existe(ide):
                self.libro.set_valor(ide, "editado_por", self.usuario)
                self.libro.set_valor(ide, "fecha_edicion", self.ts)


@contextmanager
def _transaccion(almacen: LocalStorage, usuario: str, accion: str, lote_id: str | None, respaldo: str = ""):
    """Transacción + sesión de registro. `respaldo`: etiqueta para guardar antes una copia de seguridad."""
    if respaldo:
        almacen.respaldar(respaldo)
    with almacen.transaccion() as libro:
        yield _Sesion(libro, usuario, accion, lote_id or nuevo_lote())


# ============================================================================ cambios de celdas
def _aplicar(ses: _Sesion, cambios: list[Cambio], verificar_antes: bool, forzar_no_editables: bool) -> None:
    libro = ses.libro
    for cb in cambios:
        c = S.CAMPO.get(cb.campo)
        if c is None:
            ses.res.omitidos.append({"id_evento": cb.id_evento, "campo": cb.campo, "motivo": "Campo desconocido."})
            continue
        if not c.editable and not forzar_no_editables:
            ses.res.omitidos.append({"id_evento": cb.id_evento, "campo": cb.campo,
                                     "motivo": f"«{c.label}» no se edita a mano."})
            continue
        if not libro.existe(cb.id_evento):
            ses.res.omitidos.append({"id_evento": cb.id_evento, "campo": cb.campo,
                                     "motivo": "La noticia ya no existe."})
            continue
        despues, avisos = normalizar(cb.despues, c)
        despues = V.canonizar(c, despues)
        fuera = V.valores_invalidos(c, despues)
        if fuera:
            ses.res.omitidos.append({"id_evento": cb.id_evento, "campo": cb.campo, "motivo": (
                f"«{', '.join(fuera)}» no es una opción de «{c.label}» (opciones: {', '.join(c.opciones)}).")})
            continue
        ses.res.avisos.extend(f"{cb.id_evento} · {c.label}: {a}" for a in avisos)
        actual = libro.valor(cb.id_evento, cb.campo)
        if verificar_antes and actual != a_texto(cb.antes, c.tipo):
            ses.res.omitidos.append({
                "id_evento": cb.id_evento, "campo": cb.campo,
                "motivo": f"Otra persona cambió «{c.label}» mientras editabas (ahora dice «{actual[:60]}»).",
            })
            continue
        if actual == despues:
            continue
        if c.obligatorio and despues == "":
            ses.res.omitidos.append({"id_evento": cb.id_evento, "campo": cb.campo,
                                     "motivo": f"«{c.label}» es obligatorio y no puede quedar vacío."})
            continue
        libro.set_valor(cb.id_evento, cb.campo, despues)
        idc = ses.registrar(cb.id_evento, cb.campo, actual, despues, revierte_a=cb.revierte_a,
                            accion=S.ACC_REVERTIR if cb.revierte_a else None)
        ses.res.aplicados.append({"id_cambio": idc, "id_evento": cb.id_evento, "campo": cb.campo,
                                  "antes": actual, "despues": despues})
        ses.tocados.add(cb.id_evento)


def aplicar_cambios(cambios: list[Cambio], usuario: str, accion: str = S.ACC_EDITAR,
                    lote_id: str | None = None, almacen: LocalStorage | None = None,
                    verificar_antes: bool = True, forzar_no_editables: bool = False,
                    respaldo: str = "") -> Resultado:
    """Aplica cambios de celdas y los registra en el historial (una sola transacción)."""
    usuario = _usuario(usuario)
    almacen = _almacen(almacen)
    res = Resultado(lote_id=lote_id or nuevo_lote())
    try:
        with _transaccion(almacen, usuario, accion, res.lote_id, respaldo) as ses:
            _aplicar(ses, cambios, verificar_antes, forzar_no_editables)
            res = ses.res
            if not res.aplicados:
                raise _NadaQueGuardar
            ses.sellar()
    except _NadaQueGuardar:
        pass
    return res


# ============================================================================ altas
def _agregar(ses: _Sesion, filas: list[dict], origen: str) -> None:
    libro = ses.libro
    indice = dedupe.Indice(libro.fila(i) for i in libro.ids())
    for i, bruta in enumerate(filas, start=1):
        fila, errores, avisos = validar_fila(bruta, requerir_obligatorios=True)
        etiqueta = (fila.get("titulo") or f"fila {i}")[:60]
        if errores:
            ses.res.omitidos.append({"id_evento": "", "campo": etiqueta, "motivo": " ".join(errores)})
            continue
        if fila.get("fuente") not in S.FUENTES:
            ses.res.avisos.append(f"{etiqueta}: la fuente «{fila.get('fuente')}» no es una de las habituales.")
        seguras = [c for c in indice.buscar(fila) if c.segura]
        if seguras:
            ses.res.omitidos.append({
                "id_evento": seguras[0].id_evento, "campo": etiqueta,
                "motivo": f"Ya existe ({seguras[0].motivo.lower()}): {seguras[0].id_evento}.",
            })
            continue
        ses.res.avisos.extend(f"{etiqueta}: {a}" for a in avisos)
        for k in list(fila):
            c = S.CAMPO.get(k)
            if c is not None:
                fila[k] = V.canonizar(c, fila[k])
            fuera = V.valores_invalidos(c, fila[k]) if c is not None else []
            if fuera:
                ses.res.avisos.append(f"{etiqueta} · {c.label}: «{', '.join(fuera)}» no es una opción válida; quedó vacío.")
                fila[k] = ""
        ide = libro.siguiente_id()
        fila.update({
            "id_evento": ide, "origen": origen, "cargado_por": ses.usuario, "fecha_carga": ses.ts,
        })
        if not fila.get("es_duplicado_secundario"):
            fila["es_duplicado_secundario"] = "False"
        libro.agregar_fila(fila)
        indice = dedupe.Indice(libro.fila(i2) for i2 in libro.ids())   # el siguiente de la tanda ve a este
        ses.registrar(ide, REGISTRO, "", _snapshot(fila))
        ses.res.ids_creados.append(ide)


def agregar_filas(filas: list[dict], usuario: str, accion: str = S.ACC_CREAR, origen: str = "manual",
                  lote_id: str | None = None, almacen: LocalStorage | None = None,
                  respaldo: str = "") -> Resultado:
    """Agrega noticias nuevas. Omite las que ya existen (duplicado seguro) o no son válidas."""
    usuario = _usuario(usuario)
    almacen = _almacen(almacen)
    res = Resultado(lote_id=lote_id or nuevo_lote())
    try:
        with _transaccion(almacen, usuario, accion, res.lote_id, respaldo) as ses:
            _agregar(ses, filas, origen)
            res = ses.res
            if not res.ids_creados:
                raise _NadaQueGuardar
    except _NadaQueGuardar:
        pass
    return res


# ============================================================================ variables propias
def _fila_de_variable(libro: Libro, clave: str) -> tuple[int, dict]:
    for n, f in libro.registros(S.HOJA_VARIABLES):
        if f.get("clave") == clave:
            return n, f
    raise ErrorOperacion("La variable no existe.")


def _cerrar_cambio_de_definicion(libro: Libro) -> None:
    """Tras cambiar una definición: vuelve a registrar las variables y regenera el libro de códigos."""
    libro.sincronizar_variables()
    libro_codigos.regenerar(libro.wb)


def listar_variables(almacen: LocalStorage | None = None) -> list[V.Variable]:
    return _almacen(almacen).leer_variables()


def crear_variable(etiqueta: str, tipo: str, opciones, descripcion: str, usuario: str,
                   almacen: LocalStorage | None = None) -> V.Variable:
    """Crea una variable analítica propia (hoja Variables + columna var_* en Base_Datos)."""
    usuario = _usuario(usuario)
    try:
        with _almacen(almacen).transaccion() as libro:
            existentes = libro.variables()
            et, clave, ops = V.validar_nueva(etiqueta, tipo, opciones, existentes)
            v = V.Variable(clave, et, tipo, ops, " ".join((descripcion or "").split())[:300], True,
                           max((x.orden for x in existentes), default=-1) + 1)
            libro.asegurar_columna(clave)
            libro.agregar_registro(S.HOJA_VARIABLES, V.a_fila(v, usuario, ahora()))
            _cerrar_cambio_de_definicion(libro)
    except V.ErrorVariable as e:
        raise ErrorOperacion(str(e)) from e
    return v


def actualizar_variable(clave: str, almacen: LocalStorage | None = None, etiqueta: str | None = None,
                        descripcion: str | None = None, activa: bool | None = None) -> None:
    """Cambia el nombre visible, la descripción o el estado (activa/inactiva) de una variable. El tipo no cambia."""
    try:
        with _almacen(almacen).transaccion() as libro:
            n, fila = _fila_de_variable(libro, clave)
            if etiqueta is not None:
                et = V.limpiar_etiqueta(etiqueta)
                otros = [v for v in libro.variables() if v.clave != clave]
                nombres = {V.sin_tildes(v.etiqueta).lower() for v in otros} | {V.sin_tildes(c.label).lower() for c in S.CAMPOS_BASE}
                if not et or len(et) > V.MAX_LARGO_NOMBRE:
                    raise V.ErrorVariable("El nombre está vacío o es demasiado largo.")
                if V.sin_tildes(et).lower() in nombres:
                    raise V.ErrorVariable(f"Ya existe un campo o variable llamado «{et}».")
                libro.set_registro(S.HOJA_VARIABLES, n, "etiqueta", et)
            if descripcion is not None:
                libro.set_registro(S.HOJA_VARIABLES, n, "descripcion", " ".join(descripcion.split())[:300])
            if activa is not None:
                libro.set_registro(S.HOJA_VARIABLES, n, "activa", "True" if activa else "False")
            _cerrar_cambio_de_definicion(libro)
    except V.ErrorVariable as e:
        raise ErrorOperacion(str(e)) from e


def uso_variables(almacen: LocalStorage | None = None) -> dict[str, dict]:
    """{clave: {"con_dato": n.º de noticias con valor, "por_opcion": {opción: n}}} de cada variable propia."""
    almacen = _almacen(almacen)
    base = almacen.leer_base_texto()
    uso: dict[str, dict] = {}
    for v in almacen.leer_variables():
        col = base[v.clave] if v.clave in base.columns else pd.Series([], dtype=object)
        por_opcion: dict[str, int] = {o: 0 for o in v.opciones_efectivas}
        for valor in col:
            for parte in (S.dividir_etiquetas(valor) if v.es_de_opciones else []):
                por_opcion[parte] = por_opcion.get(parte, 0) + 1
        uso[v.clave] = {"con_dato": int((col.astype(str).str.strip() != "").sum()), "por_opcion": por_opcion}
    return uso


def _variable_de_opciones(libro: Libro, clave: str) -> tuple[int, V.Variable]:
    n, fila = _fila_de_variable(libro, clave)
    v = V.desde_filas([fila])[0]
    if not v.lleva_opciones:
        raise ErrorOperacion("Esta variable no tiene lista de opciones.")
    return n, v


def agregar_opcion(clave: str, opcion: str, almacen: LocalStorage | None = None) -> None:
    try:
        with _almacen(almacen).transaccion() as libro:
            n, v = _variable_de_opciones(libro, clave)
            nuevas = V.normalizar_opciones(list(v.opciones) + [opcion], v.tipo)
            libro.set_registro(S.HOJA_VARIABLES, n, "opciones", S.unir_etiquetas(nuevas))
            _cerrar_cambio_de_definicion(libro)
    except V.ErrorVariable as e:
        raise ErrorOperacion(str(e)) from e


def quitar_opcion(clave: str, opcion: str, almacen: LocalStorage | None = None) -> None:
    """Quita una opción. No se permite si alguna noticia la usa (hay que cambiarla o renombrarla primero)."""
    with _almacen(almacen).transaccion() as libro:
        n, v = _variable_de_opciones(libro, clave)
        if opcion not in v.opciones:
            raise ErrorOperacion("Esa opción no existe.")
        if len(v.opciones) <= 2:
            raise ErrorOperacion("Una variable de opciones necesita al menos 2 opciones.")
        usan = sum(1 for ide in libro.ids() if opcion in S.dividir_etiquetas(libro.valor(ide, clave)))
        if usan:
            raise ErrorOperacion(f"«{opcion}» está en uso en {usan} noticia(s). Cámbiala en esas noticias o usa «Renombrar».")
        libro.set_registro(S.HOJA_VARIABLES, n, "opciones", S.unir_etiquetas(o for o in v.opciones if o != opcion))
        _cerrar_cambio_de_definicion(libro)


def renombrar_opcion(clave: str, viejo: str, nuevo: str, usuario: str, almacen: LocalStorage | None = None) -> Resultado:
    """Renombra una opción en la definición y en todas las noticias que la tienen (un solo lote, deshacible)."""
    usuario = _usuario(usuario)
    almacen = _almacen(almacen)
    res = Resultado(lote_id=nuevo_lote("C"))
    try:
        with _transaccion(almacen, usuario, S.ACC_CATEGORIA, res.lote_id, "antes_de_renombrar_opcion") as ses:
            libro = ses.libro
            n, v = _variable_de_opciones(libro, clave)
            if viejo not in v.opciones:
                raise ErrorOperacion("Esa opción no existe.")
            nuevas = V.normalizar_opciones([nuevo if o == viejo else o for o in v.opciones], v.tipo)
            nuevo_limpio = nuevas[list(v.opciones).index(viejo)]
            libro.set_registro(S.HOJA_VARIABLES, n, "opciones", S.unir_etiquetas(nuevas))
            # primero se actualiza la definición (así el valor nuevo ya es una opción válida) y luego las noticias
            _cerrar_cambio_de_definicion(libro)
            cambios = []
            for ide in libro.ids():
                actual = libro.valor(ide, clave)
                if viejo in S.dividir_etiquetas(actual):
                    cambios.append(Cambio(ide, clave, actual, _con_etiqueta(actual, viejo, nuevo_limpio)))
            _aplicar(ses, cambios, verificar_antes=True, forzar_no_editables=False)
            ses.sellar()
            res = ses.res
    except V.ErrorVariable as e:
        raise ErrorOperacion(str(e)) from e
    return res


# ============================================================================ libro de códigos
def regenerar_libro_codigos(almacen: LocalStorage | None = None) -> None:
    """Reescribe la hoja Libro_de_Codigos desde el registro de campos, con recuentos calculados de los datos."""
    from utils import libro_codigos

    with _almacen(almacen).transaccion() as libro:
        libro_codigos.regenerar(libro.wb)


# ============================================================================ sincronización con la web
def aplicar_sincronizacion(nuevas: list[dict], cambios: list[Cambio], usuario: str,
                           almacen: LocalStorage | None = None, lote_id: str | None = None) -> Resultado:
    """Agrega las noticias nuevas y aplica los cambios elegidos (IDs de WordPress, URLs, contenido
    actualizado) en UNA transacción y UN lote: se puede deshacer completa desde el historial.
    Antes se guarda un respaldo automático."""
    usuario = _usuario(usuario)
    almacen = _almacen(almacen)
    res = Resultado(lote_id=lote_id or nuevo_lote("S"))
    try:
        with _transaccion(almacen, usuario, S.ACC_SINCRONIZAR, res.lote_id, "antes_de_sincronizar") as ses:
            _agregar(ses, nuevas, origen="scraping")
            _aplicar(ses, cambios, verificar_antes=True, forzar_no_editables=True)
            res = ses.res
            if res.n_aplicados == 0:
                raise _NadaQueGuardar
            ses.sellar()
    except _NadaQueGuardar:
        pass
    return res


# ============================================================================ historial (lectura)
def historial_df(almacen: LocalStorage | None = None, id_evento: str | None = None) -> pd.DataFrame:
    df = _almacen(almacen).leer_hoja_texto(S.HOJA_HISTORIAL)
    if id_evento:
        df = df[df["id_evento"] == id_evento]
    return df.sort_values("id_cambio", ascending=False).reset_index(drop=True)


def _entradas(almacen: LocalStorage) -> list[dict]:
    df = almacen.leer_hoja_texto(S.HOJA_HISTORIAL)
    return df.sort_values("id_cambio").to_dict("records") if len(df) else []


# ============================================================================ revertir un cambio
def revertir_cambio(id_cambio: str, usuario: str, almacen: LocalStorage | None = None,
                    forzar: bool = False) -> Resultado:
    """Devuelve una celda al valor que tenía antes de ese cambio (agrega una entrada `revertir`)."""
    usuario = _usuario(usuario)
    almacen = _almacen(almacen)
    ent = next((e for e in _entradas(almacen) if e["id_cambio"] == id_cambio), None)
    if ent is None:
        raise ErrorOperacion(f"No existe el cambio {id_cambio}.")
    if ent["campo"] == REGISTRO:
        raise ErrorOperacion("El alta o baja de una noticia completa se deshace desde «Deshacer por lote».")
    cb = Cambio(ent["id_evento"], ent["campo"], antes=ent["valor_despues"], despues=ent["valor_antes"],
                revierte_a=id_cambio)
    return aplicar_cambios([cb], usuario, accion=S.ACC_REVERTIR, almacen=almacen,
                           verificar_antes=not forzar, forzar_no_editables=True)


# ============================================================================ restaurar a una fecha
def plan_restauracion(id_evento: str, hasta: str, almacen: LocalStorage | None = None) -> list[dict]:
    """Qué campos cambiarían al llevar la noticia a su estado en `hasta` (texto 'AAAA-MM-DD HH:MM:SS').

    Para cada campo modificado después de esa fecha, el valor de entonces es el `valor_antes` de
    su primer cambio posterior.
    """
    almacen = _almacen(almacen)
    hasta = hasta.replace("T", " ")
    base = almacen.leer_base_texto()
    fila = base[base["id_evento"] == id_evento]
    if fila.empty:
        raise ErrorOperacion("La noticia no existe.")
    actual = fila.iloc[0].to_dict()
    posteriores = [e for e in _entradas(almacen) if e["id_evento"] == id_evento and e["fecha_hora"].replace("T", " ") > hasta]
    if any(e["campo"] == REGISTRO and e["valor_antes"] == "" for e in posteriores):
        raise ErrorOperacion("La noticia se creó después de esa fecha: no hay un estado anterior que restaurar.")
    objetivo: dict[str, str] = {}
    for e in posteriores:
        if e["campo"] != REGISTRO and e["campo"] not in objetivo:
            objetivo[e["campo"]] = e["valor_antes"]
    return [
        {"campo": k, "actual": actual.get(k, ""), "objetivo": v}
        for k, v in objetivo.items() if actual.get(k, "") != v
    ]


def restaurar_noticia(id_evento: str, hasta: str, usuario: str, almacen: LocalStorage | None = None) -> Resultado:
    usuario = _usuario(usuario)
    almacen = _almacen(almacen)
    plan = plan_restauracion(id_evento, hasta, almacen)
    cambios = [Cambio(id_evento, p["campo"], antes=p["actual"], despues=p["objetivo"]) for p in plan]
    return aplicar_cambios(cambios, usuario, accion=S.ACC_REVERTIR, almacen=almacen,
                           verificar_antes=True, forzar_no_editables=True)


# ============================================================================ lotes
def lotes_df(almacen: LocalStorage | None = None) -> pd.DataFrame:
    """Resumen por lote: fecha, quién, acción, cuántos cambios/noticias y si ya fue revertido."""
    ent = _almacen(almacen).leer_hoja_texto(S.HOJA_HISTORIAL)
    cols = ["lote_id", "fecha_hora", "usuario", "accion", "n_cambios", "n_noticias", "revertido"]
    if ent.empty:
        return pd.DataFrame(columns=cols)
    revertidas = set(ent.loc[ent["revierte_a"] != "", "revierte_a"])
    filas = []
    for lote, g in ent.groupby("lote_id", sort=False):
        ids = set(g["id_cambio"])
        filas.append({
            "lote_id": lote, "fecha_hora": g["fecha_hora"].min(), "usuario": g["usuario"].iloc[0],
            "accion": ", ".join(sorted({S.ACCION_NOMBRE.get(a, a) for a in g["accion"]})),
            "n_cambios": len(g), "n_noticias": g["id_evento"].nunique(),
            "revertido": bool(ids) and ids <= revertidas,
        })
    return pd.DataFrame(filas, columns=cols).sort_values("fecha_hora", ascending=False).reset_index(drop=True)


def _planificar_lote(lote_id: str, entradas: list[dict], valor, existe) -> list[dict]:
    """Inverso de cada entrada del lote (de la más nueva a la más antigua), con conflictos."""
    del_lote = [e for e in entradas if e["lote_id"] == lote_id]
    ya = {e["revierte_a"] for e in entradas if e["revierte_a"]}
    otras_por_id: dict[str, int] = {}
    for e in entradas:
        if e["lote_id"] != lote_id:
            otras_por_id[e["id_evento"]] = otras_por_id.get(e["id_evento"], 0) + 1
    simulado: dict[tuple[str, str], str] = {}
    plan = []
    for e in sorted(del_lote, key=lambda x: x["id_cambio"], reverse=True):
        if e["id_cambio"] in ya:
            continue
        ide, campo = e["id_evento"], e["campo"]
        item = {"id_cambio": e["id_cambio"], "id_evento": ide, "campo": campo, "conflicto": ""}
        if campo == REGISTRO:
            if e["valor_antes"] == "":          # alta -> el inverso retira la noticia
                item.update(tipo="eliminar", actual="(existe)", objetivo="(retirar)", snapshot=e["valor_despues"])
                if not existe(ide):
                    item["conflicto"] = "La noticia ya no existe."
                elif otras_por_id.get(ide):
                    item["conflicto"] = "La noticia tiene cambios posteriores de otros lotes."
            else:                               # baja -> el inverso la vuelve a crear
                item.update(tipo="recrear", actual="(retirada)", objetivo="(restaurar)", snapshot=e["valor_antes"])
                if existe(ide):
                    item["conflicto"] = "La noticia ya existe."
        else:
            actual = simulado.get((ide, campo), valor(ide, campo) if existe(ide) else "")
            item.update(tipo="campo", actual=actual, objetivo=e["valor_antes"])
            if not existe(ide):
                item["conflicto"] = "La noticia ya no existe."
            elif actual != e["valor_despues"]:
                item["conflicto"] = "El valor cambió después de este lote."
            else:
                simulado[(ide, campo)] = e["valor_antes"]
        plan.append(item)
    return plan


def plan_lote(lote_id: str, almacen: LocalStorage | None = None) -> list[dict]:
    """Vista previa (solo lectura) de lo que haría «Deshacer este lote»."""
    almacen = _almacen(almacen)
    base = almacen.leer_base_texto().set_index("id_evento", drop=False)
    ids = set(base.index)

    def valor(ide, campo):
        return str(base.at[ide, campo]) if ide in ids and campo in base.columns else ""

    return _planificar_lote(lote_id, _entradas(almacen), valor, lambda ide: ide in ids)


def revertir_lote(lote_id: str, usuario: str, almacen: LocalStorage | None = None) -> Resultado:
    """Deshace un lote completo. Los elementos con conflicto se omiten y se informan."""
    usuario = _usuario(usuario)
    almacen = _almacen(almacen)
    nuevo = nuevo_lote("R")
    res = Resultado(lote_id=nuevo)
    try:
        with _transaccion(almacen, usuario, S.ACC_REVERTIR, nuevo, "antes_de_deshacer_lote") as ses:
            libro = ses.libro
            ent_df = libro.registros(S.HOJA_HISTORIAL)
            entradas = [f for _, f in ent_df]
            plan = _planificar_lote(lote_id, entradas, libro.valor, libro.existe)
            for it in plan:
                ide, campo = it["id_evento"], it["campo"]
                if it["conflicto"]:
                    ses.res.omitidos.append({"id_evento": ide, "campo": campo if campo != REGISTRO else "(noticia completa)",
                                             "motivo": it["conflicto"]})
                    continue
                if it["tipo"] == "campo":
                    libro.set_valor(ide, campo, it["objetivo"])
                    idc = ses.registrar(ide, campo, it["actual"], it["objetivo"], revierte_a=it["id_cambio"])
                    ses.res.aplicados.append({"id_cambio": idc, "id_evento": ide, "campo": campo,
                                              "antes": it["actual"], "despues": it["objetivo"]})
                    ses.tocados.add(ide)
                elif it["tipo"] == "eliminar":
                    instantanea = _snapshot(libro.fila(ide))
                    libro.eliminar_fila(ide)
                    ses.registrar(ide, REGISTRO, instantanea, "", revierte_a=it["id_cambio"])
                    ses.res.ids_eliminados.append(ide)
                elif it["tipo"] == "recrear":
                    datos = json.loads(it["snapshot"])
                    datos.pop("_truncado", None)
                    datos["id_evento"] = ide
                    libro.agregar_fila(datos)
                    ses.registrar(ide, REGISTRO, "", it["snapshot"], revierte_a=it["id_cambio"])
                    ses.res.ids_creados.append(ide)
            res = ses.res
            if res.n_aplicados == 0:
                raise _NadaQueGuardar
            ses.sellar()
    except _NadaQueGuardar:
        pass
    return res


# ============================================================================ notas (bitácora)
def agregar_nota(id_evento: str, texto: str, usuario: str, almacen: LocalStorage | None = None) -> str:
    usuario = _usuario(usuario)
    texto = (texto or "").strip()
    if not texto:
        raise ErrorOperacion("La nota está vacía.")
    almacen = _almacen(almacen)
    with almacen.transaccion() as libro:
        if not libro.existe(id_evento):
            raise ErrorOperacion("La noticia ya no existe.")
        idn = f"N{libro.max_numero(S.HOJA_NOTAS, 'id_nota') + 1:06d}"
        libro.agregar_registro(S.HOJA_NOTAS, {
            "id_nota": idn, "fecha_hora": ahora(), "usuario": usuario,
            "id_evento": id_evento, "texto": texto[:MAX_CELDA],
        })
    return idn


def notas_df(almacen: LocalStorage | None = None, id_evento: str | None = None) -> pd.DataFrame:
    df = _almacen(almacen).leer_hoja_texto(S.HOJA_NOTAS)
    if id_evento:
        df = df[df["id_evento"] == id_evento]
    return df.sort_values("id_nota", ascending=False).reset_index(drop=True)


# ============================================================================ categorías
def categorias_df(almacen: LocalStorage | None = None, solo_activas: bool = False) -> pd.DataFrame:
    df = _almacen(almacen).leer_hoja_texto(S.HOJA_CATEGORIAS)
    if solo_activas and len(df):
        df = df[df["activa"].str.lower() != "false"]
    return df.reset_index(drop=True)


def catalogo_desde_df(df: pd.DataFrame) -> dict[str, list[str]]:
    """{dimension: [nombres activos, ordenados]} a partir de la hoja Categorias."""
    if len(df):
        df = df[df["activa"].str.lower() != "false"]
    return {dim: sorted(df.loc[df["dimension"] == dim, "nombre"], key=str.casefold) for dim in S.DIMENSIONES_CATALOGO}


def catalogo_activo(almacen: LocalStorage | None = None) -> dict[str, list[str]]:
    return catalogo_desde_df(categorias_df(almacen))


def uso_categorias(almacen: LocalStorage | None = None) -> dict[tuple[str, str], int]:
    """{(dimension, nombre): n.º de noticias que la usan}."""
    base = _almacen(almacen).leer_base_texto()
    uso: dict[tuple[str, str], int] = {}
    for dim in S.DIMENSIONES_CATALOGO:
        for v in base[dim]:
            for p in S.dividir_etiquetas(v):
                uso[(dim, p)] = uso.get((dim, p), 0) + 1
    return uso


def crear_categoria(dimension: str, nombre: str, descripcion: str, usuario: str,
                    almacen: LocalStorage | None = None) -> None:
    usuario = _usuario(usuario)
    nombre = " ".join((nombre or "").split())
    if dimension not in S.DIMENSIONES_CATALOGO:
        raise ErrorOperacion("Dimensión no válida.")
    if not nombre or ";" in nombre:
        raise ErrorOperacion("El nombre no puede estar vacío ni contener «;».")
    with _almacen(almacen).transaccion() as libro:
        for _, f in libro.registros(S.HOJA_CATEGORIAS):
            if f["dimension"] == dimension and f["nombre"].casefold() == nombre.casefold():
                raise ErrorOperacion(f"La categoría «{f['nombre']}» ya existe.")
        libro.agregar_registro(S.HOJA_CATEGORIAS, {
            "dimension": dimension, "nombre": nombre, "descripcion": descripcion.strip(),
            "activa": "True", "creada_por": usuario, "fecha_hora": ahora(),
        })


def actualizar_categoria(dimension: str, nombre: str, almacen: LocalStorage | None = None,
                         descripcion: str | None = None, activa: bool | None = None) -> None:
    with _almacen(almacen).transaccion() as libro:
        for n, f in libro.registros(S.HOJA_CATEGORIAS):
            if f["dimension"] == dimension and f["nombre"] == nombre:
                if descripcion is not None:
                    libro.set_registro(S.HOJA_CATEGORIAS, n, "descripcion", descripcion.strip())
                if activa is not None:
                    libro.set_registro(S.HOJA_CATEGORIAS, n, "activa", "True" if activa else "False")
                return
        raise ErrorOperacion("La categoría no existe.")


def _con_etiqueta(valor: str, quitar: str | None, poner: str | None) -> str:
    partes = [p for p in S.dividir_etiquetas(valor) if p != quitar]
    if poner and poner not in partes:
        partes.append(poner)
    return S.unir_etiquetas(partes)


def renombrar_categoria(dimension: str, viejo: str, nuevo: str, usuario: str,
                        almacen: LocalStorage | None = None) -> Resultado:
    """Renombra una categoría en el catálogo y en todas las noticias que la usan (un solo lote)."""
    usuario = _usuario(usuario)
    nuevo = " ".join((nuevo or "").split())
    if dimension not in S.DIMENSIONES_CATALOGO or not nuevo or ";" in nuevo:
        raise ErrorOperacion("Nombre o dimensión no válidos.")
    almacen = _almacen(almacen)
    res = Resultado(lote_id=nuevo_lote("C"))
    with _transaccion(almacen, usuario, S.ACC_CATEGORIA, res.lote_id, "antes_de_renombrar_categoria") as ses:
        libro = ses.libro
        filas = libro.registros(S.HOJA_CATEGORIAS)
        if any(f["dimension"] == dimension and f["nombre"].casefold() == nuevo.casefold() and f["nombre"] != viejo
               for _, f in filas):
            raise ErrorOperacion(f"Ya existe una categoría llamada «{nuevo}».")
        destino = next((n for n, f in filas if f["dimension"] == dimension and f["nombre"] == viejo), None)
        if destino is None:
            raise ErrorOperacion("La categoría no existe.")
        libro.set_registro(S.HOJA_CATEGORIAS, destino, "nombre", nuevo)
        cambios = []
        for ide in libro.ids():
            actual = libro.valor(ide, dimension)
            if viejo in S.dividir_etiquetas(actual):
                cambios.append(Cambio(ide, dimension, actual, _con_etiqueta(actual, viejo, nuevo)))
        _aplicar(ses, cambios, verificar_antes=True, forzar_no_editables=False)
        ses.sellar()
        res = ses.res
    return res


def asignar_categoria(dimension: str, nombre: str, ids: list[str], usuario: str, accion: str = "agregar",
                      almacen: LocalStorage | None = None) -> Resultado:
    """Agrega o quita una categoría a muchas noticias a la vez (un lote, deshacible)."""
    usuario = _usuario(usuario)
    almacen = _almacen(almacen)
    base = almacen.leer_base_texto().set_index("id_evento")          # (al leer, registra las variables propias)
    campo = S.CAMPO.get(dimension)
    if dimension not in S.DIMENSIONES_CATALOGO and not (campo is not None and campo.variable):
        raise ErrorOperacion("Dimensión no válida.")
    cambios = []
    for ide in ids:
        if ide not in base.index:
            continue
        actual = str(base.at[ide, dimension])
        if campo is not None and campo.variable and campo.tipo == S.OPCION:          # opción única / sí-no
            nuevo = nombre if accion == "agregar" else ("" if actual == nombre else actual)
        else:                                                                         # etiquetas (varias a la vez)
            nuevo = _con_etiqueta(actual, nombre if accion == "quitar" else None, nombre if accion == "agregar" else None)
        cambios.append(Cambio(ide, dimension, actual, nuevo))
    return aplicar_cambios(cambios, usuario, accion=S.ACC_CATEGORIA, almacen=almacen,
                           respaldo="antes_de_asignar_categoria")


# ============================================================================ duplicados
def decisiones_duplicados(almacen: LocalStorage | None = None) -> pd.DataFrame:
    return _almacen(almacen).leer_hoja_texto(S.HOJA_DUPLICADOS)


def registrar_decision_duplicado(id_a: str, id_b: str, decision: str, usuario: str,
                                 secundaria: str | None = None, almacen: LocalStorage | None = None) -> Resultado:
    """decision: 'duplicado' (marca `secundaria` como duplicado secundario) o 'distintas'."""
    if decision not in ("duplicado", "distintas"):
        raise ErrorOperacion("Decisión no válida.")
    usuario = _usuario(usuario)
    almacen = _almacen(almacen)
    res = Resultado(lote_id=nuevo_lote("D"))
    with _transaccion(almacen, usuario, S.ACC_EDITAR, res.lote_id) as ses:
        libro = ses.libro
        libro.agregar_registro(S.HOJA_DUPLICADOS, {
            "id_a": id_a, "id_b": id_b, "decision": decision, "usuario": usuario, "fecha_hora": ses.ts,
        })
        if decision == "duplicado":
            if secundaria not in (id_a, id_b):
                raise ErrorOperacion("Indica cuál de las dos es la secundaria.")
            _aplicar(ses, [Cambio(secundaria, "es_duplicado_secundario", libro.valor(secundaria, "es_duplicado_secundario"), "True")],
                     verificar_antes=False, forzar_no_editables=False)
            ses.sellar()
        res = ses.res
    return res


# ============================================================================ exportaciones
def registrar_exportacion(usuario: str, contexto: str, formato: str, modo_historias: str, ids: list[str],
                          columnas: list[str], filtros: str = "", almacen: LocalStorage | None = None) -> str:
    usuario = _usuario(usuario)
    with _almacen(almacen).transaccion() as libro:
        ide = f"X{libro.max_numero(S.HOJA_EXPORTACIONES, 'id_exportacion') + 1:06d}"
        libro.agregar_registro(S.HOJA_EXPORTACIONES, {
            "id_exportacion": ide, "fecha_hora": ahora(), "usuario": usuario, "contexto": contexto.strip()[:500],
            "formato": formato, "modo_historias": modo_historias,
            "ids": ",".join(ids)[:MAX_CELDA], "columnas": ",".join(columnas)[:MAX_CELDA], "filtros": filtros[:2000],
        })
    return ide


def exportaciones_df(almacen: LocalStorage | None = None) -> pd.DataFrame:
    df = _almacen(almacen).leer_hoja_texto(S.HOJA_EXPORTACIONES)
    return df.sort_values("id_exportacion", ascending=False).reset_index(drop=True)


# ============================================================================ equipo (nombres de quienes editan)
MIN_NOMBRE = 2


def limpiar_nombre(nombre: str | None) -> str:
    """Nombre sin espacios sobrantes y de largo acotado: «  Ana   María » -> «Ana María»."""
    return " ".join(str(nombre or "").split())[:80]


def _clave_nombre(nombre: str) -> str:
    """Forma comparable de un nombre: sin tildes, mayúsculas ni espacios de más («ana maría» == «Ana María»)."""
    return V.sin_tildes(limpiar_nombre(nombre)).casefold()


def nombres_desde_hojas(registrados: pd.DataFrame, historial: pd.DataFrame) -> list[str]:
    """Lista ordenada de nombres a partir de las hojas Editores e Historial (sin repetir una misma persona)."""
    vistos: dict[str, str] = {}
    for n in list(registrados["nombre"]) + list(historial["usuario"]):
        n = limpiar_nombre(n)
        if n:
            vistos.setdefault(_clave_nombre(n), n)
    return sorted(vistos.values(), key=str.casefold)


def editores(almacen: LocalStorage | None = None) -> list[str]:
    """Nombres de quienes editan, en orden alfabético: los registrados + quienes ya figuran en el historial."""
    almacen = _almacen(almacen)
    return nombres_desde_hojas(almacen.leer_hoja_texto(S.HOJA_EDITORES), almacen.leer_hoja_texto(S.HOJA_HISTORIAL))


def registrar_editor(nombre: str, almacen: LocalStorage | None = None) -> str:
    """Anota un nombre en la lista del equipo y devuelve la forma registrada.

    Si ya existe (aunque se escriba con otras mayúsculas o sin tildes) se devuelve el existente: así cada
    persona figura una sola vez y el historial queda consistente.
    """
    nombre = limpiar_nombre(nombre)
    if len(nombre) < MIN_NOMBRE:
        raise ErrorOperacion("Escribe tu nombre (al menos 2 letras).")
    almacen = _almacen(almacen)
    existentes = {_clave_nombre(n): n for n in editores(almacen)}
    if _clave_nombre(nombre) in existentes:
        return existentes[_clave_nombre(nombre)]
    with almacen.transaccion() as libro:
        libro.agregar_registro(S.HOJA_EDITORES, {"nombre": nombre, "fecha_hora": ahora()})
    return nombre


def quitar_editor(nombre: str, almacen: LocalStorage | None = None) -> str:
    """Quita un nombre de la lista (por ejemplo, uno mal escrito). El historial no se modifica."""
    almacen = _almacen(almacen)
    clave = _clave_nombre(nombre)
    with almacen.transaccion() as libro:
        ws = libro.hoja(S.HOJA_EDITORES)
        filas = [r for r in range(2, ws.max_row + 1) if _clave_nombre(ws.cell(row=r, column=1).value or "") == clave]
        if not filas:
            raise ErrorOperacion("Ese nombre no está en la lista registrada (puede que solo figure en el historial).")
        for r in reversed(filas):
            ws.delete_rows(r)
    return f"«{limpiar_nombre(nombre)}» se quitó de la lista. Sus cambios anteriores siguen en el historial."


def equipo_df(almacen: LocalStorage | None = None) -> pd.DataFrame:
    """Nombre, fecha de registro y último cambio de cada persona (para Administración)."""
    almacen = _almacen(almacen)
    reg = {_clave_nombre(r["nombre"]): r["fecha_hora"] for r in almacen.leer_hoja_texto(S.HOJA_EDITORES).to_dict("records")}
    h = almacen.leer_hoja_texto(S.HOJA_HISTORIAL)
    ultimo: dict[str, str] = {}
    cambios: dict[str, int] = {}
    for r in h.to_dict("records"):
        k = _clave_nombre(r["usuario"])
        cambios[k] = cambios.get(k, 0) + 1
        ultimo[k] = max(ultimo.get(k, ""), r["fecha_hora"])
    filas = [{"Nombre": n, "Registrado": reg.get(_clave_nombre(n), ""), "Último cambio": ultimo.get(_clave_nombre(n), ""),
              "Cambios": cambios.get(_clave_nombre(n), 0)} for n in editores(almacen)]
    return pd.DataFrame(filas, columns=["Nombre", "Registrado", "Último cambio", "Cambios"])
