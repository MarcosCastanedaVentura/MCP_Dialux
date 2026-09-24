"""Leer un STF y comparar dos, sobre el fichero del plano de ejemplo."""

from pathlib import Path

import pytest

from dialux.construir import plano_a_stf
from dialux.leer_stf import comparar, leer

PLANO = Path(__file__).resolve().parents[1] / "ejemplos" / "plano-ejemplo.dxf"


@pytest.fixture
def generado(tmp_path):
    return plano_a_stf(PLANO, carpeta_destino=tmp_path)["ruta_stf"]


def test_se_lee_lo_que_se_acaba_de_escribir(generado):
    leido = leer(generado)
    assert leido["version_stf"] == "1.0.5" and leido["escrito_por"] == "MCP_Dialux"
    assert len(leido["salas"]) == 4

    oficina = next(s for s in leido["salas"] if s["nombre"].startswith("Oficina"))
    assert (oficina["ancho_x_m"], oficina["largo_y_m"]) == (8.8, 7.8)
    assert oficina["altura_m"] == 3 and oficina["plano_trabajo_m"] == 0.85
    assert oficina["factor_mantenimiento"] == 0.8
    # Los muebles se traducen a castellano: win -> ventana, door -> puerta.
    tipos = [m["tipo"] for m in oficina["muebles"]]
    assert tipos.count("puerta") == 2 and tipos.count("ventana") == 1
    assert next(m for m in oficina["muebles"] if m["nombre"] == "columna")["tipo"] == "objeto"


def test_las_claves_no_distinguen_mayusculas(tmp_path, generado):
    # La especificación dice que no distinguen, y otros programas escriben en mayúsculas.
    copia = tmp_path / "gritando.stf"
    copia.write_text(Path(generado).read_text(encoding="latin-1").upper(), encoding="latin-1")
    assert len(leer(copia)["salas"]) == 4


def test_comparar_el_mismo_fichero_no_da_diferencias(generado):
    resultado = comparar(generado, generado)
    assert len(resultado["iguales"]) == 4 and not resultado["con_diferencias"]


def test_comparar_encuentra_la_sala_que_cambia(tmp_path, generado):
    otro = plano_a_stf(PLANO, alturas={"Archivos": 4.0},
                       carpeta_destino=tmp_path / "otro")["ruta_stf"]
    resultado = comparar(generado, otro)
    (cambia,) = resultado["con_diferencias"]
    assert cambia["sala"] == "Archivos"
    assert cambia["diferencias"] == [{"que": "altura", "en_a": 3, "en_b": 4}]
    assert len(resultado["iguales"]) == 3


def test_una_sala_de_menos_se_ve(tmp_path, generado):
    recortado = tmp_path / "recortado.stf"
    texto = Path(generado).read_text(encoding="latin-1")
    recortado.write_text(texto.replace("NrRooms=4", "NrRooms=3"), encoding="latin-1")
    resultado = comparar(generado, recortado)
    assert len(resultado["solo_en_a"]) == 1 and not resultado["solo_en_b"]
