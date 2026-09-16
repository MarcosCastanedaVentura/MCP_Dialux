"""leer_plano contra los tres exámenes reales de clase.

Los valores esperados salen de mirar cada plano dibujado y de sus propias cotas, no de lo que
devolvía el código. Los exámenes no están en git (son de la profesora): sin ellos, se saltan.
"""

from pathlib import Path

import pytest

from dialux.cad.plano import leer_plano

EXAMENES = Path(__file__).resolve().parents[1] / "material" / "examenes"


def _plano(nombre: str) -> dict:
    ruta = EXAMENES / nombre
    if not ruta.is_file():
        pytest.skip(f"falta {ruta.name} en material/examenes/")
    return leer_plano(ruta)


def _sala(plano: dict, planta: int, empieza: str) -> dict:
    return next(s for s in plano["plantas"][planta]["salas"] if s["nombre"].startswith(empieza))


def test_parcial_una_sala_rectangular_con_datos_del_enunciado():
    plano = _plano("Examen-parcial.dwg")
    assert plano["cotas"]["cuadran"] == "4 de 4"
    assert len(plano["plantas"]) == 1
    (sala,) = plano["plantas"][0]["salas"]
    assert (sala["ancho_x_m"], sala["largo_y_m"], sala["area_m2"]) == (5.0, 4.0, 20.0)
    assert sala["rectangular"] and len(sala["contorno_m"]) == 4
    assert sala["altura_sala_m"] == 5.0
    assert sala["altura_plano_trabajo_m"] == 0.8
    assert sala["zona_marginal_m"] == 0.5
    # El plano no dice qué local es ni el factor de mantenimiento: no se inventan.
    assert "referencia_norma" not in sala and "factor_mantenimiento" not in sala
    assert "tipo de actividad según la UNE-EN 12464-1" in sala["faltan"]


def test_enero_muro_de_grosor_variable_no_confunde_la_sala():
    plano = _plano("Examen-finalEnero.dwg")
    assert plano["cotas"]["cuadran"] == "4 de 4"
    (sala,) = plano["plantas"][0]["salas"]
    assert (round(sala["ancho_x_m"], 2), round(sala["largo_y_m"], 2)) == (8.65, 5.88)
    assert sala["altura_sala_m"] == 3.0 and sala["altura_plano_trabajo_m"] == 0.75
    assert sala["espesor_pared_m"] == "variable"
    assert sala["uso"].startswith("Sala para actividad sanitaria")


def test_junio_dos_plantas_y_cada_texto_en_su_sala():
    plano = _plano("ExamenFinal-Junio-Dialux-26.dwg")
    assert plano["cotas"]["cuadran"] == "6 de 6"
    assert [p["nombre"] for p in plano["plantas"]] == ["SEGUNDA PLANTA", "TERCERA PLANTA"]
    assert len(plano["plantas"][0]["salas"]) == 5
    assert len(plano["plantas"][1]["salas"]) == 2

    # Los textos de Archivos y de la sala médica están intercalados en el fichero: se asignan
    # por dónde están colocados, no por su orden (se confundieron una vez al leerlos en orden).
    archivos = _sala(plano, 0, "Archivos")
    assert (archivos["referencia_norma"], archivos["altura_plano_trabajo_m"],
            archivos["factor_mantenimiento"], archivos["zona_marginal_m"]) == ("34.7", 0.0, 0.85, 0.2)
    medica = _sala(plano, 0, "Sala para atención médica")
    assert (medica["referencia_norma"], medica["altura_plano_trabajo_m"],
            medica["factor_mantenimiento"]) == ("10.7", 0.85, 0.8)

    # Los datos de los baños están fuera del plano, bajo "Sobre los baños".
    banos = _sala(plano, 0, "Baños")
    assert (banos["referencia_norma"], banos["zona_marginal_m"], banos["factor_mantenimiento"]) == ("10.4", 0.1, 0.8)
    assert (banos["ancho_x_m"], banos["largo_y_m"]) == (3.0, 2.084)

    pasillo = _sala(plano, 0, "zona frente al ascensor")
    assert pasillo["referencia_norma"] == "9.4" and pasillo["ancho_x_m"] == 18.131

    ascensor = _sala(plano, 0, "Ascensor")
    assert ascensor["no_iluminar"] and "faltan" not in ascensor

    # La columna es un obstáculo; la hoja de la puerta abierta de Archivos (6 cm) no.
    assert archivos["rectangular"] and len(archivos["obstaculos"]) == 1

    oficina = _sala(plano, 1, "Oficina")
    assert (oficina["referencia_norma"], oficina["factor_mantenimiento"], oficina["zona_marginal_m"]) == ("34.2", 0.7, 0.3)
    assert not oficina["rectangular"]  # le falta la esquina del ascensor
    assert len(oficina["contorno_m"]) == 6 and len(oficina["obstaculos"]) == 1

    # Ningún texto dice la altura de las salas de junio: se avisa en vez de suponerla.
    assert "altura de la sala" in oficina["faltan"]
