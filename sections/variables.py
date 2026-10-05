# -*- coding: utf-8 -*-
"""Análisis de las variables propias (categorías analíticas creadas por el equipo) sobre las noticias filtradas.

Para cada variable muestra su distribución según el tipo (opciones, número, fecha, texto) y permite
cruzarla con otra variable o dimensión del catálogo. Respeta los filtros activos del Explorador.
"""
import pandas as pd
import plotly.express as px
import streamlit as st

from utils import schema as S
from utils.style import COLOR_PRIMARY, style_fig
from utils.variables import SIN_DATO

# Dimensiones del catálogo con las que se puede cruzar una variable (columna, etiqueta).
DIMENSIONES_CRUCE = (
    ("categoria_macro", "Categoría macro"), ("categorias", "Categoría temática"), ("eje_gcaa", "Eje GCAA"),
    ("metodologia", "Metodología"), ("atributos_resiliencia", "Atributo de resiliencia"),
    ("beneficiarios_directos", "Beneficiarios directos"), ("fuente", "Fuente"),
    ("tipo_informacion", "Tipo de información"), ("anio", "Año de publicación"),
)


def _valores(df: pd.DataFrame, col: str, multiple: bool) -> pd.DataFrame:
    """Una fila por (noticia, valor); vacío = «(sin dato)». `multiple`: la celda guarda varios valores con «;»."""
    if col == "anio":
        etiquetas = df[col].map(lambda v: str(int(v)) if pd.notna(v) else "")
    else:
        etiquetas = df[col].fillna("").astype(str)
    filas = []
    for ide, celda in zip(df["id_evento"], etiquetas):
        partes = S.dividir_etiquetas(celda) if (multiple or col != "anio") else ([celda] if celda else [])
        for p in (partes or [SIN_DATO]):
            filas.append((ide, p))
    return pd.DataFrame(filas, columns=["id_evento", "valor"])


def _es_multiple(col: str) -> bool:
    c = S.CAMPO.get(col)
    return col in ("categorias", "categoria_macro", "eje_gcaa", "metodologia", "atributos_resiliencia", "beneficiarios_directos") or (
        c is not None and c.tipo == S.ETIQUETAS)


def _orden(valores, campo) -> list[str]:
    """Orden de las opciones definido por la variable, con «(sin dato)» al final; lo demás por frecuencia."""
    base = list(campo.opciones) if campo is not None and isinstance(campo.opciones, tuple) else []
    extra = [v for v in valores if v not in base and v != SIN_DATO]
    return [v for v in base if v in set(valores)] + sorted(extra) + ([SIN_DATO] if SIN_DATO in set(valores) else [])


def _distribucion(df: pd.DataFrame, campo: S.Campo, key: str) -> None:
    n = len(df)
    con_dato = int((df[campo.key].fillna("").astype(str).str.strip() != "").sum())
    m1, m2 = st.columns(2)
    m1.metric("Noticias con dato", f"{con_dato} de {n}")
    m2.metric("Cobertura", f"{con_dato / n:.0%}" if n else "—")

    if isinstance(campo.opciones, tuple):                                 # opción única / múltiple / Sí-No
        largo = _valores(df, campo.key, campo.tipo == S.ETIQUETAS)
        cuenta = largo["valor"].value_counts()
        orden = _orden(list(cuenta.index), campo)
        datos = pd.DataFrame({"Opción": orden, "Noticias": [int(cuenta.get(o, 0)) for o in orden]})
        datos["% de las noticias"] = (datos["Noticias"] / n * 100).round(1) if n else 0
        fig = px.bar(datos, x="Noticias", y="Opción", orientation="h", text="Noticias", color_discrete_sequence=[COLOR_PRIMARY])
        fig.update_yaxes(categoryorder="array", categoryarray=orden[::-1], title=None)
        style_fig(fig, height=max(240, 60 + 38 * len(datos)), title=f"Noticias por «{campo.label}»", showlegend=False)
        st.plotly_chart(fig, width="stretch", key=f"{key}_dist")
        st.dataframe(datos, hide_index=True)
        if campo.tipo == S.ETIQUETAS:
            st.caption("Es de opciones múltiples: una noticia puede estar en varias, por eso los porcentajes pueden sumar más de 100 %.")
    elif campo.tipo == S.NUMERO:
        nums = pd.to_numeric(df[campo.key].astype(str).str.replace(",", "."), errors="coerce").dropna()
        if nums.empty:
            st.info("Todavía no hay valores numéricos para esta variable.", icon=":material/info:")
            return
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Mínimo", f"{nums.min():g}")
        r2.metric("Mediana", f"{nums.median():g}")
        r3.metric("Promedio", f"{nums.mean():.2f}".rstrip("0").rstrip("."))
        r4.metric("Máximo", f"{nums.max():g}")
        st.caption(f"Suma: {nums.sum():g}")
        if len(nums) >= 2:
            fig = px.histogram(nums.to_frame("valor"), x="valor", nbins=min(20, max(5, len(nums) // 2)), color_discrete_sequence=[COLOR_PRIMARY])
            style_fig(fig, height=300, title=f"Distribución de «{campo.label}»", showlegend=False)
            fig.update_xaxes(title=campo.label)
            fig.update_yaxes(title="Noticias")
            st.plotly_chart(fig, width="stretch", key=f"{key}_hist")
    elif campo.tipo == S.FECHA:
        fechas = pd.to_datetime(df[campo.key].replace("", pd.NA), errors="coerce").dropna()
        if fechas.empty:
            st.info("Todavía no hay fechas para esta variable.", icon=":material/info:")
            return
        por_anio = fechas.dt.year.value_counts().sort_index().rename_axis("Año").reset_index(name="Noticias")
        fig = px.bar(por_anio, x="Año", y="Noticias", color_discrete_sequence=[COLOR_PRIMARY])
        style_fig(fig, height=300, title=f"«{campo.label}» por año", showlegend=False)
        fig.update_xaxes(type="category")
        st.plotly_chart(fig, width="stretch", key=f"{key}_fechas")
    else:                                                                   # texto / enlace
        valores = df[campo.key].fillna("").astype(str).str.strip()
        valores = valores[valores != ""].value_counts().head(20)
        if valores.empty:
            st.info("Todavía no hay valores para esta variable.", icon=":material/info:")
        else:
            st.dataframe(valores.rename_axis("Valor").reset_index(name="Noticias"), hide_index=True)


def _cruce(df: pd.DataFrame, campo: S.Campo, otra: str, etiqueta_otra: str, key: str) -> None:
    b = _valores(df, otra, _es_multiple(otra)).rename(columns={"valor": "otra"})
    if campo.tipo == S.NUMERO:                                              # número × categoría: resumen por grupo
        nums = pd.to_numeric(df[campo.key].astype(str).str.replace(",", "."), errors="coerce").rename("numero")
        m = pd.concat([df["id_evento"], nums], axis=1).dropna().merge(b, on="id_evento")
        if m.empty:
            st.info("No hay datos numéricos para cruzar.", icon=":material/info:")
            return
        resumen = m.groupby("otra")["numero"].agg(Noticias="count", Promedio="mean", Mediana="median", Suma="sum").round(2).reset_index()
        resumen = resumen.rename(columns={"otra": etiqueta_otra}).sort_values("Promedio", ascending=False)
        fig = px.bar(resumen, x="Promedio", y=etiqueta_otra, orientation="h", color_discrete_sequence=[COLOR_PRIMARY])
        style_fig(fig, height=max(260, 60 + 34 * len(resumen)), title=f"Promedio de «{campo.label}» según {etiqueta_otra.lower()}", showlegend=False)
        st.plotly_chart(fig, width="stretch", key=f"{key}_cruce_num")
        st.dataframe(resumen, hide_index=True)
        return
    a = _valores(df, campo.key, campo.tipo == S.ETIQUETAS).rename(columns={"valor": "variable"})
    m = a.merge(b, on="id_evento")
    tabla = pd.crosstab(m["variable"], m["otra"])
    if tabla.empty:
        st.info("No hay datos para cruzar.", icon=":material/info:")
        return
    filas = _orden(list(tabla.index), campo)
    columnas = _orden(list(tabla.columns), S.CAMPO.get(otra))
    tabla = tabla.reindex(index=filas, columns=columnas, fill_value=0)
    fig = px.imshow(tabla.values, x=list(tabla.columns), y=list(tabla.index), text_auto=True, aspect="auto",
                    color_continuous_scale="Teal", labels={"x": etiqueta_otra, "y": campo.label, "color": "Noticias"})
    fig.update_layout(coloraxis_showscale=False)
    style_fig(fig, height=max(300, 90 + 44 * len(tabla)), title=f"«{campo.label}» × {etiqueta_otra}", showlegend=False)
    st.plotly_chart(fig, width="stretch", key=f"{key}_cruce")
    tabla_df = tabla.rename_axis(index=campo.label, columns=None).reset_index()
    st.dataframe(tabla_df, hide_index=True)
    st.download_button("Descargar tabla (CSV)", data=lambda: tabla_df.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"{campo.key}_x_{otra}.csv", mime="text/csv", icon=":material/download:",
                       on_click="ignore", key=f"{key}_csv")
    st.caption("Cuenta noticias; si alguna de las dos es de opciones múltiples, una noticia puede aparecer en varias celdas.")


def render(df: pd.DataFrame, criterios=None) -> None:
    propias = [c for c in S.variables_activas() if c.key in df.columns]
    if not propias:
        st.info("Todavía no hay variables propias. Crea una en Administración → Variables analíticas "
                "(por ejemplo «Tamaño del proyecto» con las opciones Pequeño, Mediano y Grande) y asígnala a las noticias.",
                icon=":material/tune:")
        return
    st.caption(f"Análisis sobre las **{len(df)} noticia(s)** de los filtros activos (sin duplicados entre sitios).")
    c1, c2 = st.columns(2)
    clave = c1.selectbox("Variable a analizar", [c.key for c in propias], format_func=S.etiqueta, key="var_an_clave")
    campo = S.CAMPO[clave]
    if campo.ayuda:
        st.caption(campo.ayuda)
    opciones_cruce = [(k, e) for k, e in DIMENSIONES_CRUCE if k in df.columns] + [
        (c.key, c.label) for c in propias if c.key != clave and isinstance(c.opciones, tuple)]
    otra = c2.selectbox("Cruzar con (opcional)", ["(ninguna)"] + [k for k, _ in opciones_cruce],
                        format_func=lambda k: "(ninguna)" if k == "(ninguna)" else dict(opciones_cruce)[k], key="var_an_cruce")
    if len(df) == 0:
        st.info("Ningún resultado con los filtros actuales.")
        return
    if otra == "(ninguna)":
        _distribucion(df, campo, f"van_{clave}")
    else:
        _cruce(df, campo, otra, dict(opciones_cruce)[otra], f"van_{clave}_{otra}")
