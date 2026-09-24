"""requisitos de la norma contra la copia de Marcos de la UNE-EN 12464-1:2022.

Solo se comprueban las filas que usan los exámenes, y sus valores se han mirado en la tabla del PDF.
Medido el 16/9/2026: 303 de 303 filas coinciden con una lectura independiente hecha con
pdftotext; 5 filas no se dan porque en la norma son títulos de grupo o tienen casillas vacías.
Sin el PDF en material/norma/, se saltan.
"""

from pathlib import Path

import pytest

from dialux import norma

if not list((Path(__file__).resolve().parents[1] / "material" / "norma").glob("*.pdf")):
    pytest.skip("falta el PDF de la norma en material/norma/", allow_module_level=True)

COLUMNAS = norma.COLUMNAS


def _valores(ref: str) -> list:
    fila = norma.requisitos(ref)
    assert "error" not in fila, fila
    return [fila[k] for k in COLUMNAS]


@pytest.mark.parametrize("ref, esperado", [
    ("9.4", [200, 300, 0.4, 40, 25, 75, 75, 50]),
    ("10.4", [200, 300, 0.4, 80, 25, 75, 75, 50]),
    ("10.6", [500, 750, 0.6, 80, 19, 150, 150, 100]),
    ("10.7", [500, 1000, 0.6, 90, 19, 150, 150, 100]),
    ("34.2", [500, 1000, 0.6, 80, 19, 150, 150, 100]),
    ("34.7", [200, 300, 0.4, 80, 25, 75, 75, 50]),
])
def test_filas_de_los_examenes(ref, esperado):
    assert _valores(ref) == esperado


def test_dos_tablas_en_la_misma_pagina_no_se_corren_las_columnas():
    # Página 44: tablas 14 y 15 con las columnas desplazadas; 14.1 no tiene Ēm,techo ("–").
    assert _valores("14.1") == [200, 300, 0.4, 80, 25, 50, 50, None]
    assert _valores("15.2") == [500, 750, 0.7, 80, 22, 150, 150, 75]


def test_miles_sin_espacio():
    assert _valores("13.3")[1] == 1000


def test_titulo_de_grupo_dice_que_subfila_usar():
    assert "19.2.1" in norma.requisitos("19.2")["error"]


def test_referencia_inexistente_no_se_inventa():
    assert "error" in norma.requisitos("99.9")


def test_la_fuente_dice_tabla_fila_y_pagina():
    assert norma.requisitos("34.7")["fuente"].endswith("fila 34.7, página 62 del PDF")


def test_buscar_sin_tildes():
    assert [f["referencia"] for f in norma.buscar("enfermeria")] == ["10.6"]
