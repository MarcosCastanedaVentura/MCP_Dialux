"""La exportación 2D de DIALux evo, con el trabajo de clase de Marcos.

Es el único fichero que tiene plantas, luminarias y tablas de resultados a la vez, así que cada
número de aquí está medido sobre él. Sin el material (no entra en git), se salta.
"""

from pathlib import Path

import pytest

from dialux.export_dialux import leer
from dialux.leer_stf import comparar
from dialux.luminarias import reticula
from dialux.stf import Estancia, Luminaria, TipoLuminaria, escribir

TRABAJO = Path(__file__).resolve().parents[1] / "material" / "exportados" / "trabajo2-clase-2d.dwg"

if not TRABAJO.is_file():
    pytest.skip(f"falta {TRABAJO.name} en material/exportados/", allow_module_level=True)


@pytest.fixture(scope="module")
def trabajo() -> dict:
    return leer(TRABAJO)


def test_se_reconoce_la_variante_y_las_plantas(trabajo):
    assert trabajo["variante"] == "2D (sin alturas)"
    assert trabajo["plantas"] == ["Planta 0", "Planta 1", "Planta 2"]
    # La planta 2 son los muros de la cubierta: no tiene ninguna sala con nombre.
    assert {s["planta"] for s in trabajo["salas"]} == {"Planta 0", "Planta 1"}


def test_cada_rotulo_de_dialux_es_una_sala(trabajo):
    """13 salas en la planta baja y 2 en la primera, que son los rótulos que escribe DIALux."""
    assert len(trabajo["salas"]) == 15
    nombres = [s["nombre"] for s in trabajo["salas"]]
    assert nombres.count("Aula 1") == 1 and "Cafetería" in nombres
    # El nombre se queda sin la potencia que DIALux le pone detrás: "Aula 1 (7.67 W/m²)".
    aula = next(s for s in trabajo["salas"] if s["nombre"] == "Aula 1")
    assert aula["potencia_especifica_w_m2"] == 7.67
    # Y esa potencia cuadra con la superficie leída: 20 luminarias de 35 W sobre 91,23 m².
    assert round(20 * 35 / aula["area_m2"], 2) == 7.67


def test_las_salas_pequenas_van_a_su_cara_y_no_a_la_de_al_lado(trabajo):
    """Los cuartos de menos de 1 m² existen: el filtro de anchura no se los puede comer."""
    bano = next(s for s in trabajo["salas"] if s["nombre"] == "Baño 1")
    assert bano["area_m2"] == 0.95


def test_la_superficie_de_calculo_y_lo_que_se_mete_del_muro(trabajo):
    """Ese margen NO es la zona marginal: cambia con el tamaño de la sala (medio paso de retícula)."""
    aula = next(s for s in trabajo["salas"] if s["nombre"] == "Aula 1")
    assert aula["superficie_calculo_m2"] == 83.24  # frente a 91,23 m² de sala
    assert aula["margen_calculo_m"] == 0.195
    cuarto = next(s for s in trabajo["salas"] if s["nombre"] == "Local 12")
    assert cuarto["margen_calculo_m"] == 0.075


def test_no_hay_alturas_y_se_avisa(trabajo):
    assert all(s["altura_m"] is None for s in trabajo["salas"])
    assert any("NO trae la altura" in a for a in trabajo["avisos"])


def test_las_luminarias_salen_con_su_sitio_y_su_tamano(trabajo):
    aula = next(s for s in trabajo["salas"] if s["nombre"] == "Aula 1")
    assert aula["luminarias"] == 20
    puestas = aula["luminarias_colocadas"]
    # Panel de 60×60: el símbolo son dos cuadrados y el aparato es el de fuera.
    assert puestas[0]["tamano_m"] == [0.595, 0.595]
    # La retícula de verdad: 4 columnas y 5 filas.
    assert len({p["posicion_m"][0] for p in puestas}) == 4
    assert len({p["posicion_m"][1] for p in puestas}) == 5
    # Y ninguna fuera de la sala.
    assert all(s["luminarias"] == len(s.get("luminarias_colocadas", []))
               for s in trabajo["salas"])


def test_la_lista_de_luminarias_de_las_tablas_del_dwg(trabajo):
    (tipo,) = trabajo["luminarias_del_proyecto"]
    assert tipo["fabricante"] == "Exaktor"
    assert tipo["flujo_lm"] == 4095 and tipo["potencia_w"] == 35
    assert tipo["factor_degradacion"] == 0.8 and tipo["cantidad"] == 20


def test_los_resultados_de_dialux_van_a_su_sala(trabajo):
    """Las columnas con tilde ("Mín./medio") se reconocen: si no, las filas salen corridas."""
    aula = next(s for s in trabajo["salas"] if s["nombre"] == "Aula 1")
    assert aula["resultados"]["e_media_lx"] == 596
    assert aula["resultados"]["e_min_lx"] == 318
    assert aula["resultados"]["u0"] == 0.53
    # Una sala sin luminarias sale a 0 lx, no sin resultados.
    local = next(s for s in trabajo["salas"] if s["nombre"] == "Local 5")
    assert local["resultados"]["e_media_lx"] == 0


def test_la_reticula_del_mcp_es_la_misma_que_puso_marcos(tmp_path, trabajo):
    """La prueba de verdad de `luminarias.py`: su aula, hecha a mano en DIALux, contra el MCP."""
    aula = next(s for s in trabajo["salas"] if s["nombre"] == "Aula 1")
    contorno = [tuple(p) for p in aula["contorno_m"]]
    reparto = reticula(contorno, 20, altura_montaje_m=3.0, plano_trabajo_m=0.85)
    assert reparto["reticula"] == "4 × 5"
    mio = escribir([Estancia("Aula 1", contorno, altura_m=3.0, plano_trabajo_m=0.85,
                             luminarias=[Luminaria(TipoLuminaria("MOLNPRO 60x60"), p)
                                         for p in reparto["posiciones_m"]])],
                   tmp_path / "aula")
    resultado = comparar(mio, TRABAJO)
    (luminarias,) = resultado["luminarias"]
    assert luminarias == {"sala": "Aula 1", "en_a": 20, "en_b": 20,
                          "en_el_mismo_sitio": 20, "desviacion_maxima_m": 0.0}
    assert resultado["iguales"] == ["Aula 1"]
