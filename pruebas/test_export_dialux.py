"""Leer el DWG que exporta DIALux evo y compararlo con el STF que generó el MCP.

El fichero de prueba se exportó desde evo 14 a partir del STF del plano de ejemplo, así que el
edificio es el mismo: la comparación tiene que dar todas las salas iguales. No entra en git (es
material local), y sin él estas pruebas se saltan.
"""

from pathlib import Path

import pytest

from dialux.construir import plano_a_stf
from dialux.export_dialux import leer
from dialux.leer_stf import comparar

RAIZ = Path(__file__).resolve().parents[1]
EXPORTADO = RAIZ / "material" / "exportados" / "prueba-export.dwg"
PLANO = RAIZ / "ejemplos" / "plano-ejemplo.dxf"

if not EXPORTADO.is_file():
    pytest.skip(f"falta {EXPORTADO.name} en material/exportados/", allow_module_level=True)


def test_se_leen_las_salas_del_proyecto_exportado():
    salas = {s["nombre"]: s for s in leer(EXPORTADO)["salas"]}
    assert len(salas) == 4
    oficina = next(s for n, s in salas.items() if n.startswith("Oficina"))
    assert (oficina["ancho_x_m"], oficina["largo_y_m"]) == (8.8, 7.8)
    assert oficina["plano_trabajo_m"] == 0.85
    # La envolvente exterior se exporta con el forjado (3,2 m); la sala mide 3.
    assert oficina["altura_m"] == 3.0
    # La columna viaja como bloque, con su tamaño real.
    (columna,) = oficina["objetos"]
    assert (columna["ancho_x_m"], columna["largo_y_m"], columna["alto_m"]) == (0.6, 0.6, 3.0)


def test_un_dwg_que_no_es_de_dialux_lo_dice():
    with pytest.raises(ValueError, match="DIALux evo"):
        leer(PLANO)


def test_el_edificio_exportado_coincide_con_el_generado(tmp_path):
    generado = plano_a_stf(PLANO, carpeta_destino=tmp_path)["ruta_stf"]
    resultado = comparar(generado, EXPORTADO)
    assert len(resultado["iguales"]) == 4
    assert not resultado["con_diferencias"]
    assert not resultado["solo_en_a"] and not resultado["solo_en_b"]
    # El DWG exportado no guarda ni el factor de mantenimiento ni las luminarias: eso no es una
    # diferencia entre los edificios, y no debe contarse como tal.
    assert resultado["sin_comparar"] == ["factor de mantenimiento", "número de luminarias"]
