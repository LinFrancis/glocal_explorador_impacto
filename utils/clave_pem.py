# -*- coding: utf-8 -*-
"""Normaliza la clave privada de la cuenta de servicio, que los editores de secretos suelen alterar."""
import re


def normalizar_clave(clave: str) -> str:
    """Reconstruye la clave PEM aunque venga alterada: saltos de línea escritos como texto («\\n»), espacios o sangrías
    al comienzo de las líneas, comillas sobrantes o líneas unidas. Si no parece una clave PEM, la devuelve igual."""
    texto = str(clave).strip().strip("\"'").replace("\\n", "\n")
    m = re.search(r"-----BEGIN ([A-Z ]+)-----(.*?)-----END \1-----", texto, re.S)
    if not m:
        return texto
    cuerpo = re.sub(r"[^A-Za-z0-9+/=]", "", m.group(2))
    filas = [cuerpo[i:i + 64] for i in range(0, len(cuerpo), 64)]
    return f"-----BEGIN {m.group(1)}-----\n" + "\n".join(filas) + f"\n-----END {m.group(1)}-----\n"
