# La base de datos en Google Sheets

La plataforma guarda **toda** la base (noticias, libro de códigos, historial, notas, categorías, variables, duplicados,
exportaciones y equipo) en una hoja de cálculo de Google, una pestaña por tabla. Cada cambio que se hace en la plataforma
actualiza solo las filas modificadas. Sin configuración se usa un archivo local (`data/catalogo_gestion.xlsx`), pensado solo
para desarrollo y pruebas.

## 1. Preparar la hoja y la cuenta de servicio

1. En [Google Sheets](https://sheets.google.com) crea una hoja **vacía** (por ejemplo, «Impacto Glocal – Base de datos»).
2. En Google Cloud, en el proyecto de la cuenta de servicio, habilita **Google Sheets API** (y, recomendado, **Google Drive API**:
   permite detectar al instante las ediciones hechas a mano en la hoja; sin ella la plataforma refresca cada 30 segundos).
3. **Comparte la hoja con el correo de la cuenta de servicio** (`client_email` del JSON, termina en `iam.gserviceaccount.com`)
   con permiso de **Editor**.
4. Copia la dirección de la hoja (`https://docs.google.com/spreadsheets/d/<ID>/edit`).

## 2. Secretos

En local: `.streamlit/secrets.toml` (está en `.gitignore`; no se sube a GitHub). En Streamlit Community Cloud:
*App → Settings → Secrets*. El formato es **TOML**: `clave = "valor"` (no `"clave": "valor"` como en el JSON).

```toml
[oauth]                       # usuario y contraseña compartidos de acceso a la plataforma
username = "impacto"
password = "glocal"

[auth]
clave_admin = "una-clave-distinta"    # se pide para acciones delicadas (restablecer, deshacer lotes…)

[gsheets]
spreadsheet = "https://docs.google.com/spreadsheets/d/XXXXXXXXXXXXXXXX/edit"
type = "service_account"
project_id = "impactoglocal"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "plataforma-...@impactoglocal.iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/..."
universe_domain = "googleapis.com"
```

La `private_key` va en **una sola línea**, con los saltos como `\n` (tal cual aparece en el JSON que descarga Google).

> **Seguridad.** La clave privada da acceso a la hoja. No la pegues en chats, correos ni repositorios. Si se expuso, en Google Cloud
> (*IAM → Cuentas de servicio → Claves*) elimina esa clave, crea una nueva y reemplázala en los secretos.

## 3. Primera ejecución

Al abrir la plataforma por primera vez con la hoja vacía, se llena sola: usa `data/catalogo_gestion.xlsx` si existe en ese equipo y,
si no, el Excel original (`data/experiencia_glocal_…xlsx`). Crea todas las pestañas necesarias y quita la «Hoja 1» por defecto.
Si algo falla (hoja no compartida, API sin habilitar, dirección incorrecta) la plataforma lo explica en pantalla.

Para comprobar que está conectada: en **Tabla de datos** aparece el botón «Abrir en Google Sheets» y el texto «la base está en una
hoja de cálculo de Google».

## 4. Cómo funciona

- **Lecturas:** la plataforma guarda una copia en memoria y solo vuelve a descargar la hoja cuando cambia (consulta la fecha de
  modificación como máximo cada 8 segundos), para no agotar la cuota de la API de Google.
- **Escrituras:** cada operación relee la hoja vigente, comprueba que nadie haya cambiado antes la celda que vas a modificar (si
  alguien lo hizo, el cambio se omite y se avisa) y sube solo las filas modificadas. Todo cambio queda en la pestaña `Historial`.
- **Respaldos:** antes de importar, sincronizar o aplicar cambios en lote se guarda una pestaña `RESPALDO_AAAAMMDD_HHMMSS` con la
  copia de `Base_Datos` (se conservan las últimas 5). Además, «Descargar copia (.xlsx)» entrega todo el libro.
- **Editar a mano en Google Sheets:** se puede (se ve al refrescar), pero conviene hacerlo desde la plataforma para que quede en el
  historial. No cambies los encabezados de la primera fila ni el orden de las pestañas. Los valores deben seguir el libro de códigos.
- **Límites:** una celda admite hasta 32 000 caracteres (los textos más largos se recortan); la hoja de Google, 10 millones de
  celdas. Con el volumen actual (≈ 275 noticias × 60 columnas) hay holgura de sobra.
- **Cuotas de la API:** 60 lecturas por minuto por usuario. Si se supera, la plataforma reintenta sola y, si no basta, pide esperar
  un minuto.

## 5. Volver al archivo local

Quita (o comenta) la sección `[gsheets]` de los secretos: la plataforma vuelve a usar `data/catalogo_gestion.xlsx`. Para llevarte el
contenido actual de la hoja, descarga la copia («Descargar copia (.xlsx)» en Tabla de datos o en Administración → Respaldo) y
reemplaza ese archivo con ella.
