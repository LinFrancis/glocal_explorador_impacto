# -*- coding: utf-8 -*-
import pytest
import requests

from utils import geocoding


class Resp:
    def __init__(self, datos, status=200, roto=False):
        self._d, self.status_code, self._roto = datos, status, roto

    def json(self):
        if self._roto:
            raise ValueError("x")
        return self._d


class Sesion:
    def __init__(self, tabla):
        self.tabla, self.consultas = tabla, []

    def get(self, url, params=None, headers=None, timeout=None):
        self.consultas.append(params["q"])
        assert headers["User-Agent"].startswith("ImpactoGlocalGestor") and params["accept-language"] == "es"
        r = self.tabla.get(params["q"])
        if isinstance(r, Exception):
            raise r
        if isinstance(r, Resp):
            return r
        return Resp([] if r is None else [r])


def hit(lat, lon, pais="Chile", nombre="x"):
    return {"lat": str(lat), "lon": str(lon), "display_name": nombre, "address": {"country": pais}}


@pytest.fixture(autouse=True)
def limpio(monkeypatch):
    geocoding._cache.clear()
    monkeypatch.setattr(geocoding, "INTERVALO", 0)


def test_lugar_completo():
    s = Sesion({"Chonchi, Chiloé, Chile": hit(-42.623976, -73.772442, "Chile")})
    r = geocoding.geocodificar_lugar("Chonchi, Chiloé, Chile", s)
    assert (r.lat, r.lon, r.pais, r.precision) == ("-42.623976", "-73.772442", "Chile", "completo") and r.encontrado


def test_simplifica_quitando_segmentos_iniciales():
    s = Sesion({"Barrio Yungay, Santiago, Chile": None, "Santiago, Chile": hit(-33.45, -70.66)})
    r = geocoding.geocodificar_lugar("Barrio Yungay, Santiago, Chile", s)
    assert r.precision == "simplificado(-1)" and r.lat == "-33.450000"
    assert s.consultas == ["Barrio Yungay, Santiago, Chile", "Santiago, Chile"]
    s2 = Sesion({"A, B, C, D": None, "B, C, D": None, "C, D": hit(1, 2, "Perú")})
    assert geocoding.geocodificar_lugar("A, B, C, D", s2).precision == "simplificado(-2)"


def test_no_encontrado_es_sin_dato_y_no_reduce_a_solo_el_pais():
    s = Sesion({})
    r = geocoding.geocodificar_lugar("Lugar inventado, Chile", s)
    assert r.precision == "sin_dato" and not r.encontrado
    assert s.consultas == ["Lugar inventado, Chile", "Chile"]
    assert geocoding.geocodificar_lugar("Sitioso", Sesion({})).precision == "sin_dato"   # un solo segmento: una consulta


@pytest.mark.parametrize("texto", ["Online (sin país específico)", "Iberoamérica (modalidad online)", "No especificado", "Virtual"])
def test_online_no_consulta_la_red(texto):
    s = Sesion({})
    r = geocoding.geocodificar_lugar(texto, s)
    assert r.precision == "online" and not r.encontrado and s.consultas == []


def test_cache_evita_repetir_consultas():
    s = Sesion({"Temuco, Chile": hit(-38.7, -72.6)})
    geocoding.geocodificar_lugar("Temuco, Chile", s)
    geocoding.geocodificar_lugar("temuco,  chile", s)
    assert s.consultas == ["Temuco, Chile"]


def test_completar_respeta_lo_que_ya_tiene_y_alinea_listas():
    s = Sesion({"Osorno, Los Lagos, Chile": hit(-40.57, -73.13), "Atlantida, Mundo": None})
    r = geocoding.completar("Chonchi, Chile; Osorno, Los Lagos, Chile; Atlantida, Mundo; Online (modalidad online)",
                            lat="-42.6", lon="-73.7", pais="Chile", precision="corregido_manual", sesion=s)
    assert s.consultas == ["Osorno, Los Lagos, Chile", "Atlantida, Mundo", "Mundo"]
    assert r.valores["sitios_lat"] == "-42.6;-40.570000;;"
    assert r.valores["sitios_precision_geocodificacion"] == "corregido_manual;completo;sin_dato;online"
    assert r.valores["sitios_pais"] == "Chile;Chile;;"
    assert (r.n_nuevos, r.n_fallidos) == (1, 1) and len(r.sitios) == 4
    # las listas siempre tienen un elemento por lugar
    assert all(len(v.split(";")) == 4 for v in r.valores.values())


def test_completar_todo_regeocodifica():
    s = Sesion({"Temuco, Chile": hit(-38.7, -72.6)})
    r = geocoding.completar("Temuco, Chile", lat="1", lon="2", precision="completo", sesion=s, solo_faltantes=False)
    assert r.valores["sitios_lat"] == "-38.700000" and s.consultas == ["Temuco, Chile"]


def test_progreso_y_lista_vacia():
    msgs = []
    geocoding.completar("Temuco, Chile", sesion=Sesion({"Temuco, Chile": hit(1, 2)}), progreso=msgs.append)
    assert msgs and "Temuco" in msgs[0]
    assert geocoding.completar("", sesion=Sesion({})).valores == {"sitios_lat": "", "sitios_lon": "", "sitios_pais": "",
                                                                 "sitios_precision_geocodificacion": ""}


@pytest.mark.parametrize("respuesta,texto", [
    (requests.exceptions.ConnectTimeout(), "tardó demasiado"),
    (requests.exceptions.ConnectionError(), "No hay conexión"),
    (Resp([], 429), "límite de uso"),
    (Resp([], 403), "límite de uso"),
    (Resp([], 500), r"error \(500\)"),
    (Resp(None, 200, roto=True), "no se pudo interpretar"),
])
def test_errores_del_servicio_en_espanol(respuesta, texto):
    with pytest.raises(geocoding.ErrorGeocodificacion, match=texto):
        geocoding.geocodificar_lugar("Temuco, Chile", Sesion({"Temuco, Chile": respuesta}))


def test_respeta_el_intervalo_entre_consultas(monkeypatch):
    monkeypatch.setattr(geocoding, "INTERVALO", 0.2)
    s = Sesion({"A, Chile": hit(1, 2), "B, Chile": hit(3, 4)})
    t0 = geocoding.time.monotonic()
    geocoding.geocodificar_lugar("A, Chile", s)
    geocoding.geocodificar_lugar("B, Chile", s)
    assert geocoding.time.monotonic() - t0 >= 0.2


@pytest.mark.vivo
def test_en_vivo_nominatim_valparaiso():
    r = geocoding.geocodificar_lugar("Valparaíso, Chile")
    assert r.encontrado and r.pais == "Chile" and -34 < float(r.lat) < -32
