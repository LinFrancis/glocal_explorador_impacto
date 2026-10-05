# -*- coding: utf-8 -*-
"""Registro único de campos de la base de datos (Base_Datos).

Una sola definición por columna: etiqueta, tipo, grupo, obligatoriedad, si el usuario puede
editarla y de dónde salen sus opciones. De aquí se alimentan la tabla editable, la ficha, el
formulario de carga, la importación de archivos, la exportación, la completitud y el libro de
códigos. No importa Streamlit, así que se puede usar (y probar) sin levantar la app.

El registro tiene una parte fija (`CAMPOS_BASE`) y una parte dinámica: las **variables propias** que el
equipo define en Administración (nombre, tipo y opciones de respuesta). Se guardan en la hoja `Variables`
y se suman al registro con `registrar_variables()`; desde afuera, `CAMPOS`, `CAMPO`, `COLUMNAS` y `VISTAS`
siempre reflejan las dos partes juntas.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass

# ------------------------------------------------------------------------------ constantes
FUENTES = ("glocalminds.com", "fundacionglocal.org")
SEPARADOR_ETIQUETAS = "; "          # forma canónica al guardar; al leer se acepta ';' con o sin espacio
SEPARADOR_ENLACES = " | "
VALORES_VACIOS = {"", "no especificado", "sin dato", "nan", "none"}   # para completitud/exportación
VALORES_NO_ETIQUETA = {"", "no aplica", "no especificado", "sin dato"}  # no cuentan como categoría

ORIGENES = ("historico", "scraping", "manual", "archivo")

# Variantes del mismo método de facilitación, escritas distinto por distintos lotes de
# codificación. Clave en minúsculas -> forma canónica. Se aplica al LEER (vista de lectura y
# recuentos del libro de códigos); la hoja guardada conserva el texto original.
ALIAS_METODOLOGIA = {
    "otra: café pro-acción": "Otra: Café ProAcción",
    "otra: café proacción": "Otra: Café ProAcción",
    "otra: café pro acción": "Otra: Café ProAcción",
    "otra: diseño de acción sabia": "Otra: Diseño para la Acción Sabia",
    "otra: tres horizontes": "Otra: Marco de los Tres Horizontes",
}

# Completitud: umbrales en % (ver utils/completitud.py)
UMBRAL_COMPLETA = 80
UMBRAL_PARCIAL = 50
# Aviso de última sincronización (días)
DIAS_ALERTA_SINCRONIZACION = 14

# Tipos de dato
TEXTO = "texto"
TEXTO_LARGO = "texto_largo"
URL = "url"
IMAGEN_URL = "imagen_url"
LISTA_URL = "lista_url"
FECHA = "fecha"
FECHA_TEXTO = "fecha_texto"
ENTERO = "entero"
NUMERO = "numero"
BOOLEANO = "booleano"
OPCION = "opcion"
ETIQUETAS = "etiquetas"
LISTA_NUMEROS = "lista_numeros"
LISTA_TEXTO = "lista_texto"

TIPO_NOMBRE = {
    TEXTO: "Texto", TEXTO_LARGO: "Texto largo", URL: "URL", IMAGEN_URL: "URL de imagen",
    LISTA_URL: "Lista de URLs", FECHA: "Fecha", FECHA_TEXTO: "Fecha (texto libre)",
    ENTERO: "Número entero", NUMERO: "Número", BOOLEANO: "Sí/No", OPCION: "Opción única",
    ETIQUETAS: "Etiquetas (separadas por ;)", LISTA_NUMEROS: "Números (separados por ;)",
    LISTA_TEXTO: "Lista de textos (separados por ;)",
}

# Grupos (orden de aparición en formularios y fichas)
G_IDENT = "Identificación"
G_CONTENIDO = "Contenido"
G_PROYECTO = "Carpeta y documentos"
G_CLASIF = "Clasificación"
G_ACTORES = "Actores y beneficiarios"
G_UBICACION = "Ubicación"
G_VARIABLES = "Variables propias"
G_WEB = "Metadatos de la web"
G_CONTROL = "Control y auditoría"
GRUPOS = (G_IDENT, G_CONTENIDO, G_PROYECTO, G_CLASIF, G_ACTORES, G_UBICACION, G_VARIABLES, G_WEB, G_CONTROL)

# Origen de las opciones de un campo de opción/etiquetas
OPC_DATOS = "datos"                       # valores únicos presentes en la base
OPC_CAT_CATEGORIAS = "catalogo:categorias"
OPC_CAT_MACRO = "catalogo:categoria_macro"
OPC_ATRIBUTOS = "const:atributos"
OPC_SUBATRIBUTOS = "const:subatributos"
OPC_GCAA_EJE = "const:eje_gcaa"

CLAVE_CONTENIDO = "contenido"
CLAVE_ANALISIS = "analisis"


@dataclass(frozen=True)
class Campo:
    key: str                      # nombre de la columna en Base_Datos
    label: str                    # etiqueta visible (español)
    tipo: str
    grupo: str
    obligatorio: bool = False
    recomendado: bool = False     # aviso (no bloqueo) si falta
    editable: bool = True         # editable por el usuario en tabla/ficha
    clave: str | None = None      # None | "contenido" | "analisis": cuenta para la completitud
    opciones: object = None       # tupla fija | OPC_* | None
    ayuda: str = ""
    variable: bool = False        # True: variable propia definida por el equipo (hoja Variables)
    activo: bool = True           # una variable desactivada se conserva pero no se ofrece en formularios ni filtros


def _c(key, label, tipo, grupo, **kw) -> Campo:
    return Campo(key, label, tipo, grupo, **kw)


# Orden = orden de columnas de la hoja Base_Datos (49 originales) + columnas nuevas de la plataforma al final.
CAMPOS_BASE: tuple[Campo, ...] = (
    _c("id_evento", "ID", TEXTO, G_IDENT, editable=False, ayuda="Se genera automáticamente (EV0001, EV0002…)."),
    _c("titulo", "Título", TEXTO, G_IDENT, obligatorio=True, clave=CLAVE_CONTENIDO),
    _c("Fundación Glocal?", "Fundación Glocal (ejecutora)", OPCION, G_IDENT, opciones=OPC_DATOS,
       ayuda="'Fundación Glocal' si la ejecutó la Fundación; '0' en otro caso."),
    _c("Consultora", "Consultora ejecutora", OPCION, G_IDENT, opciones=OPC_DATOS,
       ayuda="Personalidad jurídica de la consultora (EIRL, SpA, Ltda) o '0'."),
    _c("slug", "Identificador web (slug)", TEXTO, G_WEB, editable=False),
    _c("url_noticia", "Enlace", URL, G_IDENT, obligatorio=True, clave=CLAVE_CONTENIDO),
    _c("preview_contenido", "Vista previa del contenido", TEXTO_LARGO, G_CONTENIDO),
    _c("contenido_completo", "Texto completo", TEXTO_LARGO, G_CONTENIDO, clave=CLAVE_CONTENIDO),
    _c("fecha_publicacion", "Fecha de publicación (texto)", FECHA_TEXTO, G_CONTENIDO),
    _c("autor", "Autor", TEXTO, G_WEB),
    _c("imagen_principal_url", "Imagen principal", IMAGEN_URL, G_CONTENIDO, clave=CLAVE_CONTENIDO),
    _c("imagen_alt", "Texto alternativo de la imagen", TEXTO, G_WEB),
    _c("meta_description", "Meta descripción", TEXTO, G_WEB),
    _c("og_title", "Título Open Graph", TEXTO, G_WEB),
    _c("og_description", "Descripción Open Graph", TEXTO, G_WEB),
    _c("og_image", "Imagen Open Graph", IMAGEN_URL, G_WEB),
    _c("og_type", "Tipo Open Graph", TEXTO, G_WEB),
    _c("og_url", "URL Open Graph", URL, G_WEB),
    _c("enlaces_externos", "Enlaces externos", LISTA_URL, G_WEB),
    _c("num_enlaces_externos", "N.º de enlaces externos", ENTERO, G_WEB, editable=False),
    _c("menciones_instagram", "Menciones de Instagram", TEXTO, G_WEB),
    _c("num_menciones_instagram", "N.º de menciones de Instagram", ENTERO, G_WEB, editable=False),
    _c("timestamp_extraccion", "Fecha de extracción", FECHA, G_WEB, editable=False),
    _c("titulo_catalogo", "Título en el catálogo", TEXTO, G_CONTENIDO),
    _c("descripcion_catalogo", "Resumen", TEXTO_LARGO, G_CONTENIDO, clave=CLAVE_CONTENIDO),
    _c("fecha_catalogo", "Fecha en el catálogo (texto)", FECHA_TEXTO, G_CONTENIDO),
    _c("categorias", "Categorías temáticas", ETIQUETAS, G_CLASIF, clave=CLAVE_ANALISIS, opciones=OPC_CAT_CATEGORIAS),
    _c("categoria_macro", "Categoría macro", ETIQUETAS, G_CLASIF, clave=CLAVE_ANALISIS, opciones=OPC_CAT_MACRO),
    _c("metodologia", "Metodología de facilitación", ETIQUETAS, G_CLASIF, clave=CLAVE_ANALISIS, opciones=OPC_DATOS),
    _c("actores", "Actores", ETIQUETAS, G_ACTORES, opciones=OPC_DATOS),
    _c("lugar", "Lugar", ETIQUETAS, G_UBICACION, clave=CLAVE_ANALISIS,
       ayuda="Un elemento por sitio, separados por ';'. Las coordenadas se alinean con esta lista."),
    _c("eje_gcaa", "Eje GCAA", ETIQUETAS, G_CLASIF, clave=CLAVE_ANALISIS, opciones=OPC_GCAA_EJE),
    _c("objetivo_gcaa", "Objetivo GCAA", ETIQUETAS, G_CLASIF, opciones=OPC_DATOS),
    _c("atributos_resiliencia", "Atributo de resiliencia", ETIQUETAS, G_CLASIF, clave=CLAVE_ANALISIS, opciones=OPC_ATRIBUTOS),
    _c("subatributos_resiliencia", "Sub-atributo de resiliencia", ETIQUETAS, G_CLASIF, opciones=OPC_SUBATRIBUTOS),
    _c("beneficiarios_directos", "Beneficiarios directos", ETIQUETAS, G_ACTORES, clave=CLAVE_ANALISIS, opciones=OPC_DATOS),
    _c("beneficiarios_indirectos", "Beneficiarios indirectos", ETIQUETAS, G_ACTORES, opciones=OPC_DATOS),
    _c("enfoque_genero", "Enfoque de género", TEXTO, G_CLASIF,
       ayuda="'No' o 'Sí: <descripción>'."),
    _c("fecha_publicacion_web", "Fecha de publicación", FECHA, G_CONTENIDO, recomendado=True, clave=CLAVE_CONTENIDO),
    _c("fecha_modificacion_web", "Fecha de modificación en la web", FECHA, G_WEB, editable=False),
    _c("actores_normalizados", "Actores institucionales", ETIQUETAS, G_ACTORES, clave=CLAVE_ANALISIS, opciones=OPC_DATOS),
    _c("sitios_lat", "Latitudes", LISTA_NUMEROS, G_UBICACION),
    _c("sitios_lon", "Longitudes", LISTA_NUMEROS, G_UBICACION),
    _c("sitios_pais", "Países", LISTA_TEXTO, G_UBICACION),
    _c("sitios_cuenca_nombre", "Cuencas hidrográficas", LISTA_TEXTO, G_UBICACION),
    _c("sitios_precision_geocodificacion", "Precisión de la geocodificación", LISTA_TEXTO, G_UBICACION),
    _c("fuente", "Fuente", OPCION, G_IDENT, obligatorio=True, opciones=FUENTES),
    _c("es_duplicado_secundario", "Duplicado secundario", BOOLEANO, G_CONTROL,
       ayuda="Marca el mismo evento publicado en ambos sitios; se excluye de los conteos."),
    _c("tipo_informacion", "Tipo de información", OPCION, G_CLASIF, opciones=OPC_DATOS),
    # ---- columnas nuevas de la plataforma de gestión
    _c("wp_id", "ID en WordPress", ENTERO, G_CONTROL, editable=False),
    _c("origen", "Origen del registro", OPCION, G_CONTROL, editable=False, opciones=ORIGENES),
    _c("cargado_por", "Cargado por", TEXTO, G_CONTROL, editable=False),
    _c("fecha_carga", "Fecha de carga", FECHA, G_CONTROL, editable=False),
    _c("editado_por", "Editado por", TEXTO, G_CONTROL, editable=False),
    _c("fecha_edicion", "Fecha de edición", FECHA, G_CONTROL, editable=False),
    # ---- carpeta y documentos del proyecto
    _c("carpeta_proyecto", "Carpeta del proyecto", URL, G_PROYECTO,
       ayuda="Enlace a la carpeta del proyecto (Google Drive u otro lugar con sus archivos)."),
    _c("documentos_proyecto", "Otros enlaces del proyecto", LISTA_URL, G_PROYECTO,
       ayuda="Archivos finales, documentación, informes… Un enlace por línea."),
)

# Columnas que la plataforma llena sola (no se importan ni se editan a mano).
COLUMNAS_SISTEMA = ("wp_id", "origen", "cargado_por", "fecha_carga", "editado_por", "fecha_edicion")
# Todas las columnas que la migración agrega al final de Base_Datos si faltan.
COLUMNAS_NUEVAS = COLUMNAS_SISTEMA + ("carpeta_proyecto", "documentos_proyecto")
COLUMNAS_AUDITORIA = ("cargado_por", "fecha_carga", "editado_por", "fecha_edicion")

OBLIGATORIOS = tuple(c.key for c in CAMPOS_BASE if c.obligatorio)

# Campos clave de la completitud (mismo peso). Ver utils/completitud.py. Las variables propias NO cuentan.
CLAVE_CONTENIDO_CAMPOS = tuple(c.key for c in CAMPOS_BASE if c.clave == CLAVE_CONTENIDO)
CLAVE_ANALISIS_CAMPOS = tuple(c.key for c in CAMPOS_BASE if c.clave == CLAVE_ANALISIS)

# Columnas derivadas/internas que nunca deben salir en una exportación.
COLUMNAS_INTERNAS = (
    "item", "_palabras_busqueda", "enlaces_externos_lista", "fecha_parsed", "tiene_fecha",
    "enfoque_genero_binario", "anio", "pais", "completitud",
)


def campo(key: str) -> Campo:
    return _estado()["CAMPO"][key]


def etiqueta(key: str) -> str:
    c = _estado()["CAMPO"].get(key)
    return c.label if c else key


def campos_de_grupo(grupo: str) -> list[Campo]:
    return [c for c in _estado()["CAMPOS"] if c.grupo == grupo]


def variables_activas() -> list[Campo]:
    """Variables propias que se ofrecen en formularios, filtros y tablas (las desactivadas se omiten)."""
    return [c for c in _estado()["CAMPOS"] if c.variable and c.activo]


# ------------------------------------------------------------------------------ vistas de tabla
VISTA_ESENCIALES = (
    "id_evento", "titulo", "fuente", "fecha_publicacion_web", "tipo_informacion",
    "categoria_macro", "categorias", "lugar", "url_noticia",
)
VISTA_ANALISIS = VISTA_ESENCIALES[:2] + (
    "categoria_macro", "categorias", "metodologia", "actores_normalizados", "eje_gcaa", "objetivo_gcaa",
    "atributos_resiliencia", "subatributos_resiliencia", "beneficiarios_directos",
    "beneficiarios_indirectos", "enfoque_genero", "lugar", "tipo_informacion",
)
VISTA_PROYECTO = ("id_evento", "titulo", "carpeta_proyecto", "documentos_proyecto")   # + variables propias

# Formatos del libro de códigos para campos de texto con estructura: columna -> (expresión regular, explicación).
PATRONES_CODIGO = {
    "enfoque_genero": (r"^(No|Sí: .+)$", "Debe ser «No» o «Sí: descripción breve»."),
}
# Códigos que el libro de códigos admite además de las opciones ("7 atributos + 'No aplica'").
CODIGOS_ESPECIALES = ("No aplica", "No especificado")

# ------------------------------------------------------------------------------ hojas auxiliares
HOJA_BASE = "Base_Datos"
HOJA_LIBRO = "Libro_de_Codigos"
HOJA_HISTORIAL = "Historial"
HOJA_NOTAS = "Notas"
HOJA_CATEGORIAS = "Categorias"
HOJA_DUPLICADOS = "Duplicados"
HOJA_EXPORTACIONES = "Exportaciones"
HOJA_VARIABLES = "Variables"
HOJA_EDITORES = "Editores"

HOJAS_AUX = {
    HOJA_HISTORIAL: ("id_cambio", "fecha_hora", "usuario", "id_evento", "campo", "valor_antes",
                     "valor_despues", "accion", "lote_id", "revierte_a"),
    HOJA_NOTAS: ("id_nota", "fecha_hora", "usuario", "id_evento", "texto"),
    HOJA_CATEGORIAS: ("dimension", "nombre", "descripcion", "activa", "creada_por", "fecha_hora"),
    HOJA_DUPLICADOS: ("id_a", "id_b", "decision", "usuario", "fecha_hora"),
    HOJA_EXPORTACIONES: ("id_exportacion", "fecha_hora", "usuario", "contexto", "formato",
                         "modo_historias", "ids", "columnas", "filtros"),
    HOJA_VARIABLES: ("clave", "etiqueta", "tipo", "opciones", "descripcion", "activa", "orden",
                     "creada_por", "fecha_hora"),
    HOJA_EDITORES: ("nombre", "fecha_hora"),
}

# Acciones registradas en el historial
ACC_CREAR = "crear"
ACC_EDITAR = "editar"
ACC_SINCRONIZAR = "sincronizar"
ACC_CARGA = "carga"
ACC_CATEGORIA = "categoria"
ACC_REVERTIR = "revertir"
ACCIONES = (ACC_CREAR, ACC_EDITAR, ACC_SINCRONIZAR, ACC_CARGA, ACC_CATEGORIA, ACC_REVERTIR)
ACCION_NOMBRE = {
    ACC_CREAR: "Creada", ACC_EDITAR: "Edición", ACC_SINCRONIZAR: "Sincronización",
    ACC_CARGA: "Carga", ACC_CATEGORIA: "Categoría", ACC_REVERTIR: "Reversión",
}

# Dimensiones gestionadas desde el catálogo de categorías
DIMENSIONES_CATALOGO = {
    "categoria_macro": "Categoría macro",
    "categorias": "Categoría temática",
}


# ------------------------------------------------------------------------------ opciones
def dividir_etiquetas(texto) -> list[str]:
    """'a; b;c' -> ['a', 'b', 'c'] (sin vacíos ni repetidos, conserva el orden)."""
    if texto is None:
        return []
    partes = [p.strip() for p in str(texto).split(";")]
    return list(dict.fromkeys(p for p in partes if p))


def unir_etiquetas(partes) -> str:
    return SEPARADOR_ETIQUETAS.join(dict.fromkeys(p.strip() for p in partes if p and str(p).strip()))


def opciones_de(key: str, valores_columna=None, catalogo: dict[str, list[str]] | None = None) -> list[str]:
    """Opciones sugeridas para un campo.

    valores_columna: iterable con los valores actuales de la columna (para OPC_DATOS).
    catalogo: {dimension: [nombres activos]} (para los campos gestionados por catálogo).
    """
    c = _estado()["CAMPO"][key]
    op = c.opciones
    if op is None:
        return []
    if isinstance(op, tuple):
        return list(op)
    if op.startswith("catalogo:"):
        dim = op.split(":", 1)[1]
        return sorted((catalogo or {}).get(dim, []), key=str.casefold)
    if op.startswith("const:"):
        from utils import data as _data  # import perezoso: data.py depende de Streamlit
        if op == OPC_ATRIBUTOS:
            return list(_data.RESILIENCE_TAXONOMY.keys())
        if op == OPC_SUBATRIBUTOS:
            return [s for subs in _data.RESILIENCE_TAXONOMY.values() for s in subs]
        if op == OPC_GCAA_EJE:
            return [e for e in _data.GCAA_EJE_ORDER if e.lower() not in VALORES_NO_ETIQUETA]
    # OPC_DATOS
    vistos: dict[str, None] = {}
    for v in (valores_columna if valores_columna is not None else []):
        if c.tipo == ETIQUETAS:
            for p in dividir_etiquetas(v):
                if p.lower() not in VALORES_NO_ETIQUETA:
                    vistos[p] = None
        else:
            s = str(v).strip() if v is not None else ""
            if s and s.lower() not in ("nan", "none"):
                vistos[s] = None
    return sorted(vistos, key=str.casefold)


# ------------------------------------------------------------------------------ registro dinámico
_variables: tuple[Campo, ...] = ()
_cache: dict | None = None
_candado = threading.Lock()


def registrar_variables(campos) -> bool:
    """Reemplaza las variables propias del registro. True si cambió algo. Es idempotente y barato."""
    global _variables, _cache
    nuevas = tuple(campos)
    with _candado:
        if nuevas == _variables:
            return False
        _variables, _cache = nuevas, None
        return True


def _estado() -> dict:
    """CAMPOS / CAMPO / COLUMNAS / VISTAS con las variables propias incluidas (se reconstruye tras registrar)."""
    global _cache
    c = _cache
    if c is None:
        with _candado:
            campos = CAMPOS_BASE + _variables
            columnas = tuple(x.key for x in campos)
            propias = tuple(x.key for x in _variables if x.activo)
            c = {
                "CAMPOS": campos,
                "CAMPO": {x.key: x for x in campos},
                "COLUMNAS": columnas,
                "VISTAS": {
                    "Esenciales": VISTA_ESENCIALES,
                    "Análisis": VISTA_ANALISIS,
                    "Proyecto y variables": VISTA_PROYECTO + propias,
                    "Todo": columnas,
                },
            }
            _cache = c
    return c


def __getattr__(nombre: str):
    """`schema.CAMPOS`, `.CAMPO`, `.COLUMNAS` y `.VISTAS` se calculan al pedirlos (incluyen las variables propias)."""
    if nombre in ("CAMPOS", "CAMPO", "COLUMNAS", "VISTAS"):
        return _estado()[nombre]
    raise AttributeError(f"module {__name__!r} has no attribute {nombre!r}")
