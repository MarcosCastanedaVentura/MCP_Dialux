"""Del examen al STF, con los planos reales de clase."""

from pathlib import Path

import pytest

from dialux.construir import plano_a_stf

EXAMENES = Path(__file__).resolve().parents[1] / "material" / "examenes"


def _plano(nombre: str):
    ruta = EXAMENES / nombre
    if not ruta.is_file():
        pytest.skip(f"falta {ruta.name} en material/examenes/")
    return ruta


def test_sin_la_altura_no_se_escribe_nada(tmp_path):
    # El examen de junio no dice la altura en ningún texto: inventarla es el invariante 3.
    salida = plano_a_stf(_plano("ExamenFinal-Junio-Dialux-26.dwg"), carpeta_destino=tmp_path)
    assert salida["escrito"] is False
    assert len(salida["faltan"]) == 7
    assert not list(tmp_path.glob("*.stf"))


def test_junio_da_un_stf_por_planta(tmp_path):
    salida = plano_a_stf(_plano("ExamenFinal-Junio-Dialux-26.dwg"), altura_m=3,
                         carpeta_destino=tmp_path)
    assert salida["escrito"] and salida["cotas"] == "6 de 6"
    assert [p["planta"] for p in salida["plantas"]] == ["SEGUNDA PLANTA", "TERCERA PLANTA"]
    assert len(salida["plantas"][0]["estancias"]) == 5
    assert len(list(tmp_path.glob("*.stf"))) == 2

    # Las columnas todavía no se escriben: hay que decirlo, no callarlo.
    assert any("columna" in a for a in salida["avisos"])

    oficina = salida["plantas"][1]["estancias"][0]
    assert oficina["nombre"].startswith("Oficina") and oficina["plano_trabajo_m"] == 0.85


def test_el_parcial_usa_la_altura_del_enunciado(tmp_path):
    salida = plano_a_stf(_plano("Examen-parcial.dwg"), carpeta_destino=tmp_path)
    (sala,) = salida["plantas"][0]["estancias"]
    assert sala["altura_m"] == 5.0 and sala["plano_trabajo_m"] == 0.8


def test_altura_distinta_para_una_sala(tmp_path):
    salida = plano_a_stf(_plano("ExamenFinal-Junio-Dialux-26.dwg"), altura_m=3,
                         alturas={"Archivos": 4.5}, carpeta_destino=tmp_path)
    alturas = {e["nombre"]: e["altura_m"] for e in salida["plantas"][0]["estancias"]}
    assert alturas["Archivos"] == 4.5 and alturas["Baños"] == 3
