# -*- coding: utf-8 -*-
"""La plataforma debe estar 100 % en español: nada de textos de interfaz en inglés ni formatos de fecha en inglés."""
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVOS = [p for d in ("sections", "app_pages", "utils") for p in (RAIZ / d).glob("*.py")] + [RAIZ / "Inicio.py"]

PROHIBIDO = [
    (r"Heatmap", "usa «Mapa de calor»"), (r"Top \d+", "usa «Las N principales»"), (r"Presiona Play", "usa «Reproducir»"),
    (r"strftime\([^)]*%[bB]", "strftime con meses (%b/%B) sale en inglés: usa data.fecha_corta_es"),
    (r"\"Slug\"", "usa «Identificador web (slug)»"), (r"\"Link\"", "usa «Enlace»"), (r"Preparedness and planning", "traducir la lista CR2"),
    (r"label=\"(Save|Cancel|Submit|Delete|Login|Logout)\b", "botón en inglés"),
]


@pytest.mark.parametrize("patron,motivo", PROHIBIDO)
def test_sin_textos_en_ingles(patron, motivo):
    malos = []
    for p in ARCHIVOS:
        for n, linea in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
            if linea.lstrip().startswith("#"):
                continue
            if re.search(patron, linea):
                malos.append(f"{p.relative_to(RAIZ)}:{n}: {linea.strip()[:80]}")
    assert not malos, f"{motivo}\n" + "\n".join(malos)


def test_fecha_corta_en_espanol():
    import pandas as pd

    from utils.data import fecha_corta_es
    assert fecha_corta_es(pd.Timestamp("2026-07-12")) == "12 jul 2026" and fecha_corta_es(pd.Timestamp("2025-01-03")) == "3 ene 2025"
    assert fecha_corta_es(None) == "s/f" and fecha_corta_es(pd.NaT) == "s/f"
