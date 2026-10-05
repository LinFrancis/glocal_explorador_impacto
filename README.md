# Impacto Glocal

Plataforma interna de **gestión de información sobre impacto social** de
[Glocalminds](https://glocalminds.com) y [Fundación Glocal](https://fundacionglocal.org). Permite recolectar
noticias de ambos sitios, cargar y editar información, llevar un historial reversible de cambios, medir qué tan
completa está cada noticia, explorar el catálogo (mapas, evolución, cruces, cuencas) y exportar de forma selectiva.

Todo en español. Protegida con usuario y contraseña compartidos.

## Ejecutar

```bash
pip install -r requirements.txt
streamlit run Inicio.py
```

Entras en dos pasos: usuario `Impacto` con la contraseña del equipo y, después, **tu nombre**. La primera vez lo escribes y queda
registrado en la lista del equipo; las próximas veces solo lo eliges de la lista (así el historial usa siempre el mismo nombre
para cada persona). Se puede cambiar en «Editando como» (menú lateral). La primera carga tarda unos segundos.

> Si ves errores como «módulo … no tiene el atributo …» tras actualizar el código, reinicia el servidor (`Ctrl+C` y volver a
> ejecutar). `Inicio.py` ya vuelve a importar solo los módulos cuando detecta que los archivos cambiaron.

### Claves (producción)

Los valores por defecto son para desarrollo. En uso real fíjalos en `.streamlit/secrets.toml` (no se sube a git) o en los
secretos de Streamlit Cloud. La base de datos es una **hoja de Google** (ver [`docs/GUIA_GOOGLE_SHEETS.md`](docs/GUIA_GOOGLE_SHEETS.md)):

```toml
[oauth]                 # acceso compartido a la plataforma (también vale [auth] con usuario / clave)
username = "impacto"
password = "..."

[auth]
clave_admin = "..."     # se pide para acciones destructivas (restablecer, deshacer lotes, renombrar categorías...)

[gsheets]               # la base de datos: hoja de Google + cuenta de servicio
spreadsheet = "https://docs.google.com/spreadsheets/d/<ID>/edit"
type = "service_account"
client_email = "...@....iam.gserviceaccount.com"
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
# ...y el resto de campos del JSON de la cuenta de servicio (project_id, private_key_id, client_id, token_uri…)
```

Sin la sección `[gsheets]` se usa un archivo local (`data/catalogo_gestion.xlsx`), solo para desarrollo y pruebas.

## Módulos

| Sección | Página | Qué hace |
|---|---|---|
| Plataforma | **Inicio** | Estado de la base, bandeja de trabajo (noticias con menos información), aviso de última sincronización, actividad reciente y panorama analítico. Incluye un desplegable de **Ayuda** con todo lo que se puede hacer. |
| | **Explorador Glocal** | Búsqueda y filtros (incluye nivel de completitud y variables propias), selección de noticias y exportación a Excel, Word o CSV con las columnas que elijas. Mapa, evolución, cruces, análisis de variables propias y cuencas. |
| Gestión | **Fichas de noticia** | Editar datos, **carpeta del proyecto** (Drive u otro enlace) y otros enlaces, clasificación y variables propias (con noticias parecidas ya analizadas), bitácora de notas, historial con reversión, coordenadas y actualización desde la web. |
| | **Tabla de datos** | La base completa como planilla editable; los cambios se guardan explícitamente. Las columnas de categorías **se eligen de su lista del libro de códigos** (no se escriben) y lo que no respeta el libro no se puede guardar. |
| | **Cargar información** | Formulario o importación de Excel/CSV, con validación por tipo y detección de duplicados. |
| | **Sincronizar con la web** | Busca noticias nuevas en ambos sitios (manual) y las compara con la base. Trabaja siempre sobre la base real; cada sincronización es un lote que se puede deshacer. |
| | **Historial de cambios** | Quién cambió qué y cuándo; deshacer lotes completos; repetir exportaciones. |
| Administración | **Administración** | Categorías, **variables analíticas propias**, asignación en lote, bitácora general, calidad de datos, duplicados, respaldo y **equipo** (nombres). |
| Referencia | Marco teórico · Glosario | Definiciones y fuentes de las dimensiones del catálogo, **variables propias del equipo** y libro de códigos completo. |

### Variables analíticas propias

En *Administración → Variables analíticas* el equipo crea nuevas categorías de análisis: nombre, **tipo** (opción única, varias
opciones, sí/no, número, fecha, texto, texto largo, enlace) y **opciones de respuesta**. Ejemplo: «tamaño_proyecto» con *pequeño,
mediana, grande*. Cada variable pasa a ser una columna más (`var_tamano_proyecto`): se asigna en la ficha, en la tabla y en lote,
sirve de filtro y de gráfico en el Explorador (distribución y cruces), se exporta e importa, y queda registrada en el **Marco
teórico** y en la hoja `Libro_de_Codigos`. Las listas de opciones son cerradas: se pueden agregar, renombrar (se propaga a las
noticias) o quitar opciones sin uso. Las variables no cuentan para el indicador de completitud.

### Carpeta del proyecto

Cada noticia tiene un campo `carpeta_proyecto` (enlace a la carpeta de Google Drive u otro lugar con los archivos finales y la
documentación) y `documentos_proyecto` (otros enlaces, uno por línea). La ficha muestra un botón «Abrir carpeta del proyecto».

## Cómo se guardan los datos

Los datos viven en una **hoja de cálculo de Google**, con una pestaña por tabla: `Base_Datos`, `Libro_de_Codigos`, `Historial`,
`Notas`, `Categorias`, `Variables`, `Duplicados`, `Exportaciones` y `Editores` (la lista del equipo). La primera vez, una hoja vacía se
llena sola con el Excel original (`data/experiencia_glocal_…xlsx`, que **no se modifica nunca**). Guía de configuración:
[`docs/GUIA_GOOGLE_SHEETS.md`](docs/GUIA_GOOGLE_SHEETS.md). La implementación está en `utils/sheets.py`; el archivo local
(`utils/storage.py`) tiene la misma interfaz y se usa en desarrollo y en las pruebas.

- Toda escritura pasa por `utils/repo.py`: una transacción que relee la hoja vigente, comprueba que nadie más haya cambiado la
  celda, sube solo las filas modificadas y deja una entrada en `Historial` (quién, qué, cuándo, antes → después).
- Antes de importar, sincronizar o aplicar correcciones en lote se guarda un respaldo automático (una pestaña `RESPALDO_…`; se
  conservan los últimos 5). «Descargar copia (.xlsx)» entrega todo el libro.
- Revertir **agrega** entradas, nunca borra: se puede deshacer un cambio, un lote o restaurar una noticia a una fecha.
- La pestaña `Libro_de_Codigos` se genera desde el registro de campos (`utils/schema.py`) con recuentos calculados de los datos, e
  incluye las variables propias. La tabla de datos usa sus opciones para validar lo que se edita.

### Criterios de datos

- **Obligatorios:** `titulo`, `url_noticia`, `fuente`. El resto es opcional.
- **Duplicados**, por prioridad: ID de WordPress + fuente → URL normalizada → slug + fuente (estos tres se omiten solos) → mismo
  título (solo aviso: puede ser otro evento).
- **Completitud:** 14 campos clave (6 de contenido web + 8 de análisis). *Completa* ≥ 80 %, *Parcial* 50–79 %, *Básica* < 50 %.
  «No aplica» cuenta como completo; «No especificado» y vacío, no.
- **Validación:** por tipo y no invasiva (avisos); solo bloquean los obligatorios vacíos y los duplicados seguros.

## Estructura

```
Inicio.py                  # entrada: login + navegación
app_pages/                 # páginas (ficha, tabla, carga, sincronizar, historial, administracion, explorador...)
sections/                  # bloques del Inicio y del Explorador (resultados, exportar, mapa, evolución, cruces, variables, cuencas),
                           # la ayuda de Inicio (ayuda.py) y el libro de códigos del Marco teórico (libro.py)
utils/
  schema.py                # registro único de campos (tipos, obligatorios, opciones, vistas) + variables propias en ejecución
  variables.py             # definición, tipos y opciones de las variables analíticas propias
  storage.py  sheets.py    # almacén local (desarrollo) y almacén en Google Sheets
  repo.py                  # operaciones con historial sobre cualquiera de los dos
  validation.py            # conversión y validación por tipo
  dedupe.py  completitud.py  similares.py  calidad.py
  scraper.py  geocoding.py  importar.py  export.py  libro_codigos.py
  auth.py                  # login y clave de administración
  data.py  filters.py  components.py  style.py  formularios.py  edicion.py  seleccion.py  vistas.py  ui.py
data/                      # Excel original (semilla) + referencia de cuencas
images/                    # logos
docs/                      # guía de Google Sheets
tests/                     # pruebas automáticas
```

## Pruebas

```bash
pip install -r requirements-dev.txt
python -m pytest                 # todas (≈ 15 min: simulan cada página)
python -m pytest -m vivo -s      # además, las que consultan los sitios reales (solo lectura)
```

Las pruebas trabajan siempre sobre copias temporales del Excel: nunca tocan tus datos. En GitHub corren solas en cada push
(`.github/workflows/tests.yml`).
