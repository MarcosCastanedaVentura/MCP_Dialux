"""El plano de ejemplo del repositorio, que es lo que puede probar cualquiera.

Va en las pruebas porque es lo primero que ejecutará quien se encuentre el proyecto: si se rompe,
la primera impresión es que la herramienta no funciona.
"""

from pathlib import Path

from dialux.cad.plano import leer_plano
from dialux.construir import plano_a_stf

PLANO = Path(__file__).resolve().parents[1] / "ejemplos" / "plano-ejemplo.dxf"


def test_se_leen_las_cuatro_salas_y_cuadran_las_cotas():
    plano = leer_plano(PLANO)
    (planta,) = plano["plantas"]
    salas = {s["referencia_norma"]: s for s in planta["salas"]}
    assert sorted(salas) == ["10.4", "34.2", "34.7", "9.1"]
    assert plano["cotas"]["cuadran"] == "3 de 3"

    oficina = salas["34.2"]
    assert (oficina["ancho_x_m"], oficina["largo_y_m"]) == (8.8, 7.8)
    assert oficina["altura_sala_m"] == 3.0 and oficina["altura_plano_trabajo_m"] == 0.85
    assert len(oficina["obstaculos"]) == 1  # la columna

    # Los huecos de los muros se leen como puertas y ventanas: la de fachada es ventana por ser
    # ancha, la estrecha de fachada es la entrada, y la que da al pasillo es una puerta.
    assert [(a["tipo"], a["ancho_m"]) for a in oficina["aberturas"]] == [
        ("puerta", 1.2), ("ventana", 2.0), ("puerta", 1.0)]


def test_el_ejemplo_genera_su_stf(tmp_path):
    salida = plano_a_stf(PLANO, carpeta_destino=tmp_path)
    assert salida["escrito"] and "faltan" not in salida
    texto = Path(salida["ruta_stf"]).read_text(encoding="latin-1")
    assert "NrRooms=4" in texto and "Height=3" in texto
    assert "Furn1=door" in texto and "Furn2=win" in texto
    assert any("ventana" in a for a in salida["avisos"])
