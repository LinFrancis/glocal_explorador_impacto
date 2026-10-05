# -*- coding: utf-8 -*-
"""Ayuda de la plataforma: todo lo que se puede hacer, módulo por módulo, para quien entra por primera vez.

Va en Inicio dentro de un desplegable cerrado. Es texto fijo: si se agrega o cambia un módulo, hay que
actualizarlo aquí.
"""
import streamlit as st

PRIMEROS_PASOS = """
**Qué es esta plataforma.** Es la base de información sobre impacto social de Glocal Minds y Fundación Glocal
(noticias y proyectos de glocalminds.com y fundacionglocal.org). Sirve para **explorarla, completarla, mantenerla
al día con la web y exportarla**, con un registro de quién cambió qué y cuándo.

**Entrar.**
1. Escribe el usuario y la contraseña compartidos del equipo y pulsa **Continuar**.
2. Elige tu nombre en la lista. **La primera vez** escríbelo en «¿Primera vez?» y queda registrado; las próximas veces
   solo lo eliges de la lista. Así el historial siempre usa el mismo nombre para cada persona.
3. Puedes cambiar de nombre o agregar uno en **«Editando como»** (menú lateral). Para salir, **Cerrar sesión**.

**Moverte.** El menú lateral agrupa los módulos: *Plataforma* (Inicio y Explorador), *Gestión* (fichas, tabla, carga,
sincronización e historial), *Administración* y *Referencia* (marco teórico y glosario).

**Este panel de Inicio** muestra cuántas noticias hay, qué tan completas están, cuándo fue la última sincronización con la web,
la **bandeja de trabajo** (las 10 noticias con menos información, con un botón para abrir su ficha), la actividad reciente
y el panorama analítico del catálogo.

**Qué tan completa está una noticia.** Se mide con 14 campos clave (6 de contenido web y 8 de análisis). **Completa**: 80 % o más;
**Parcial**: 50 a 79 %; **Básica**: menos de 50 %. Las variables propias no cuentan para este indicador.

**Nada se borra.** Cada cambio queda en el historial con quién, qué, cuándo y el valor antes y después, y casi todo se puede
deshacer (un cambio, una noticia a una fecha, o una carga/sincronización completa).
"""

EXPLORAR = """
**Explorador Glocal — buscar y filtrar.** En el panel lateral combinas todos los criterios que quieras (dentro de un filtro
se une con «o»; entre filtros distintos, con «y»): texto en título o contenido (con nivel de coincidencia ajustable para tolerar
tildes o errores de tipeo), fuente, tipo de información, personalidad jurídica, nivel de completitud, año, categorías,
metodología, actores, ejes y objetivos GCAA, atributos de resiliencia, beneficiarios, enfoque de género y **tus variables propias**.
«Limpiar filtros» los quita todos. Los filtros se conservan al cambiar de página.

**Secciones del Explorador** (todas respetan los filtros):
- **Resultados:** planilla y catálogo de lectura. Puedes leer cada noticia completa y abrir su ficha para editarla.
- **Mapa:** dónde ocurrieron las experiencias.
- **Evolución en el tiempo:** cuántas experiencias por año y por dimensión.
- **Cruces y correlaciones:** cruza dos dimensiones (mapa de calor y tabla).
- **Variables propias:** distribución de cada variable que creó el equipo y su cruce con otras dimensiones.
- **Cuencas:** experiencias por cuenca hidrográfica de Chile.

**Seleccionar y exportar.** Marca noticias una por una, «esta página», «todas las filtradas» o las filas marcadas en la planilla.
Luego exporta a **Excel, Word o CSV**:
- *Qué noticias:* solo tu selección, todas las filtradas o toda la base.
- *Qué información:* completa, o solo las columnas que elijas (agrupadas por tema, con atajos como «Postulación» o «Mínimo»).
- El **Word** puede llevar portada y encabezado con los logos de ambas organizaciones.
- Cada exportación queda anotada y se puede volver a descargar desde **Historial → Exportaciones**.
"""

EDITAR = """
**Fichas de noticia — editar una noticia.** Elige la noticia (con buscador). Arriba ves quién la editó por última vez y su
**completitud** (con la lista de lo que falta). Tiene cinco pestañas:
- **Datos:** título, enlace, fecha, resúmenes, texto, lugar, etc. Incluye la **carpeta del proyecto** (enlace a Google Drive u
  otro lugar con los archivos finales y la documentación) y otros enlaces del proyecto. Puedes **actualizar esa noticia desde la web**
  y **geocodificar** el lugar para que aparezca en el mapa.
- **Clasificación:** categorías macro y temáticas, metodología, actores, ejes y objetivos GCAA, resiliencia, beneficiarios, enfoque
  de género y tus **variables propias**. Hay **noticias parecidas ya analizadas**, con un botón para copiar su clasificación como
  punto de partida (nada se guarda hasta que confirmes).
- **Bitácora:** notas con autor y fecha.
- **Historial:** cada cambio de esa noticia; puedes **revertir un cambio** o **restaurar la noticia a una fecha**.
- **Vista de lectura:** cómo se ve la noticia ya publicada.

**Tabla de datos — editar como planilla.** Toda la base en una grilla, con vistas de columnas (esenciales, análisis, proyecto y
variables, todo). Editas con doble clic y **los cambios no se guardan hasta pulsar «Guardar cambios»**, que antes muestra qué cambia.
Las columnas de categorías **se eligen de su lista, tomada del libro de códigos** (no se escriben): pasa el cursor sobre el nombre de
la columna para ver su significado y sus opciones. Lo que no respeta el libro de códigos no se puede guardar. También puedes
descargar una copia del archivo.

**Historial de cambios.** Tres pestañas: **Cambios** (quién, qué, cuándo, antes y después, con filtros), **Lotes** (cada carga,
sincronización o asignación masiva se puede **deshacer completa**) y **Exportaciones** (volver a descargar una exportación anterior).
"""

CARGAR = """
**Cargar información.**
- **Formulario:** agrega una noticia a mano. Solo son obligatorios el título, el enlace y la fuente; el resto es opcional.
  Avisa si se parece a una noticia que ya existe.
- **Subir archivo:** sube un Excel o CSV. La plataforma reconoce las columnas, te muestra una vista previa con avisos y duplicados,
  e importa solo las filas válidas. Hay una **plantilla** para descargar.

**Sincronizar con la web.** Busca noticias nuevas en glocalminds.com y fundacionglocal.org **solo cuando tú lo pides**, y las compara con
la base: *Nuevas*, *URL cambió*, *Cambiaron en la web* y *Solo en la base*. Eliges qué aplicar y nada se guarda hasta confirmar.
Si no hay diferencias dice **«✓ Todo actualizado»**. Si un sitio no responde, se explica y no se toca nada.
Las noticias nuevas entran con la información de la web; luego se completan con su análisis.
"""

ADMINISTRAR = """
**Administración** (nueve pestañas):
- **Categorías macro y temática:** crea, describe, renombra o desactiva las categorías del catálogo.
- **Variables analíticas:** crea **tus propias categorías de análisis**: les pones nombre, **tipo de variable** (opción única,
  varias opciones, sí/no, número, fecha, texto, enlace…) y **opciones de respuesta**. Por ejemplo, «Tamaño del proyecto» con las
  opciones *Pequeño, Mediano, Grande*. Después puedes agregar, renombrar o quitar opciones y desactivar la variable. Una variable
  nueva se comporta como una columna más: aparece en la ficha y en la tabla, sirve de filtro y de gráfico en el Explorador, se
  exporta y se importa, y **queda registrada en el Marco teórico y en el libro de códigos**.
- **Asignar a noticias:** filtra, marca y asigna o quita una categoría o variable a muchas noticias a la vez.
- **Bitácora general:** todas las notas de todas las noticias.
- **Calidad de datos:** detecta fechas dudosas, metodologías escritas de varias formas, países sin normalizar, enlaces mal formados,
  valores fuera de las opciones y lugares sin coordenadas (que puedes buscar en lote).
- **Duplicados:** compara lado a lado posibles noticias repetidas y decide si son la misma o no.
- **Sincronización:** estado de la última sincronización y origen de las noticias.
- **Respaldo:** descargar el archivo de trabajo, ver los respaldos automáticos, regenerar el libro de códigos y restablecer desde el
  Excel original.
- **Equipo:** la lista de nombres de quienes editan (agregar o quitar un nombre mal escrito).

**Referencia.** El **Marco teórico** explica cada dimensión, lista las **variables propias del equipo** con sus opciones y muestra el
**libro de códigos** completo. El **Glosario** define cada categoría.
"""

CLAVES = """
**Dos claves.** La **clave de acceso** (usuario y contraseña) la conoce todo el equipo y abre la plataforma. La **clave de administración**
se pide solo para acciones delicadas: restablecer desde el Excel original, deshacer un lote, restaurar una noticia a una fecha, renombrar o
desactivar categorías y variables, aplicar correcciones masivas y quitar nombres del equipo. Pídela a quien administra la plataforma.

**Dónde viven los datos.** En una **hoja de cálculo de Google** con las pestañas de datos, libro de códigos, historial, notas,
categorías, variables, duplicados, exportaciones y equipo (en Tabla de datos hay un botón para abrirla). El Excel original no se modifica
nunca. Antes de importar, sincronizar o aplicar cambios en lote se guarda un **respaldo automático** (una pestaña `RESPALDO_…`; se conservan
los últimos 5). Puedes mirar la hoja directamente, pero edita desde la plataforma: así cada cambio queda en el historial.

**Si algo no sale como esperabas:** revisa el **Historial de cambios** (casi todo se puede deshacer) y, si hace falta, el respaldo desde
Administración.
"""


def render() -> None:
    with st.expander(":material/help: Ayuda: qué puedes hacer en la plataforma", expanded=False):
        st.caption("Guía rápida de todos los módulos, pensada para quien entra por primera vez.")
        t1, t2, t3, t4, t5, t6 = st.tabs([
            "Primeros pasos", "Explorar y exportar", "Editar información", "Cargar y sincronizar", "Administrar y referencia",
            "Claves y datos"])
        with t1:
            st.markdown(PRIMEROS_PASOS)
        with t2:
            st.markdown(EXPLORAR)
        with t3:
            st.markdown(EDITAR)
        with t4:
            st.markdown(CARGAR)
        with t5:
            st.markdown(ADMINISTRAR)
        with t6:
            st.markdown(CLAVES)
