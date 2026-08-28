# Explorador Impacto Glocal

Plataforma de visualización del catálogo histórico de experiencias de facilitación de
[Glocalminds](https://glocalminds.com), mapeadas contra marcos internacionales de acción
climática (Global Climate Action Agenda, UNFCCC) y resiliencia (CR2 - Centro de Ciencia del
Clima y Resiliencia).

## Contenido

- **Inicio** — panorama general con indicadores clave.
- **Marco Teórico y Fuentes** — qué significa cada dimensión del catálogo y de dónde viene.
- **Explorador Avanzado** — búsqueda con filtros combinables por las 12 dimensiones del catálogo.
- **Mapa** — vistas por país, ciudad/localidad y coordenadas específicas.
- **Evolución en el Tiempo** — series históricas y animaciones dinámicas por categoría y por zona geográfica.
- **Cruces y Correlaciones** — heatmaps, diagrama de flujo (Sankey), vacíos de cobertura y gráfico radial de atributos/sub-atributos de resiliencia (CR2).
- **Cuencas Hidrográficas** — vinculación territorial a la jerarquía de cuencas de Chile (BNA/DGA).
- **Línea de Tiempo** — cronología navegable, experiencia por experiencia.
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
  style.py                 # sistema de diseño: tipografía, paleta, tema de gráficos
data/                      # catálogo fuente (Excel)
.streamlit/config.toml     # tema visual (Montserrat + paleta)
```

## Fuente de datos

El archivo Excel en `data/` contiene el catálogo completo, con hojas para el catálogo
principal (`Noticias`), fuentes teóricas (`Fuentes_Reales`), y datos territoriales
(`Cuencas`, `Subcuencas`, `Subsubcuencas`, `Mapa_Ubicaciones`).
