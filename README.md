# Explorador Impacto Glocal

Plataforma de visualización del catálogo histórico de experiencias de facilitación de
[Glocalminds](https://glocalminds.com) y de [Fundación Glocal](https://fundacionglocal.org),
mapeadas contra marcos internacionales de acción climática (Global Climate Action Agenda,
UNFCCC) y resiliencia (CR2 - Centro de Ciencia del Clima y Resiliencia).

Es un **explorador**: los criterios de búsqueda que se definen en "Explorador Avanzado"
(incluyendo fuente y personalidad jurídica ejecutora — Fundación Glocal vs. consultora)
gobiernan todas las demás vistas (Mapa, Evolución en el Tiempo, Cruces y Correlaciones,
Cuencas, Inicio). Sin filtros, se ve el catálogo completo.

## Contenido

- **Inicio** — panorama general con indicadores clave (respeta los filtros del Explorador).
- **Marco Teórico y Fuentes** — qué significa cada dimensión del catálogo y de dónde viene.
- **Explorador Avanzado** — define los criterios de búsqueda (filtros combinables por las 12
  dimensiones del catálogo + fuente + entidad ejecutora) y permite hojear los resultados como
  un catálogo, leyendo cada experiencia completa, o exportarlos a Word/Excel/CSV.
- **Mapa** — vistas por país, ciudad/localidad y coordenadas específicas.
- **Evolución en el Tiempo** — series históricas y animaciones dinámicas por categoría y por zona geográfica.
- **Cruces y Correlaciones** — heatmaps, diagrama de flujo (Sankey), vacíos de cobertura y gráfico radial de atributos/sub-atributos de resiliencia (CR2).
- **Cuencas Hidrográficas** — vinculación territorial a la jerarquía de cuencas de Chile (BNA/DGA).
- **Glosario** — definiciones de todas las categorías y términos clave.

## Ejecutar localmente

```bash
pip install -r requirements.txt
streamlit run Inicio.py
```

## Estructura

```
Inicio.py                  # página principal
pages/                     # resto de páginas (numeradas para fijar el orden del menú)
utils/
  data.py                  # carga y transformación de datos (Excel -> DataFrames)
  filters.py               # criterios de búsqueda compartidos entre todas las páginas
  components.py            # componentes reutilizables (ficha de experiencia, badges)
  export.py                # exportadores a Word/Excel
  style.py                 # sistema de diseño: tipografía, paleta, tema de gráficos
data/                      # catálogo fuente (Excel) + referencia de cuencas de Chile
.streamlit/config.toml     # tema visual (Montserrat + paleta)
```

## Fuente de datos

El archivo Excel en `data/` contiene el catálogo completo en la hoja `Base_Datos` (una fila por
experiencia, con la columna `fuente` indicando si viene de glocalminds.com o
fundacionglocal.org, y `Fundación Glocal?`/`Consultora` indicando la personalidad jurídica
ejecutora), más la hoja `Libro_de_Codigos` con la definición y procedencia de cada columna.
