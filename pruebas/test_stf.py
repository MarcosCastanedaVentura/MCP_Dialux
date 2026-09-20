"""El STF que se le da a DIALux evo.

Lo que se comprueba aquí sale de importar los ficheros de verdad en evo 14 (ver
material/pruebas_stf/): el formato no tiene especificación pública, así que cada regla de este
módulo es una prueba hecha en la máquina virtual.
"""

import pytest

from dialux.stf import Estancia, escribir, rectangulo


def _contenido(tmp_path, estancias, **extra) -> str:
    ruta = escribir(estancias, tmp_path / "salida", **extra)
    assert ruta.suffix == ".stf"
    return ruta.read_text(encoding="latin-1")


def test_una_sala_lleva_medidas_altura_y_plano_de_trabajo(tmp_path):
    texto = _contenido(tmp_path, [Estancia("Sala", rectangulo(5, 4), altura_m=3,
                                           plano_trabajo_m=0.8)], proyecto="Parcial")
    assert "[ROOM.R1]" in texto and "Name=Sala" in texto
    assert "Height=3" in texto and "WorkingPlane=0.8" in texto
    assert "NrPoints=4" in texto and "Point2=5 0" in texto
    assert "Name=Parcial" in texto
    # DIALux evo sobre Windows: el fichero va con finales de línea de Windows.
    assert texto.startswith("[VERSION]\r\n")


def test_vertice_donde_acaba_la_pared_del_vecino(tmp_path):
    """Sin ese vértice, evo 14 cruzaba el pasillo con una diagonal (medido el 20/9/2026)."""
    pasillo = Estancia("Pasillo", rectangulo(12, 2, 0, 6), altura_m=3, plano_trabajo_m=0.0)
    escribir([Estancia("Oficina", rectangulo(8, 6), altura_m=3),
              Estancia("Aseos", rectangulo(4, 6, 8, 0), altura_m=3),
              pasillo], tmp_path / "salida")
    assert pasillo.contorno == [(0, 6), (8, 6), (12, 6), (12, 8), (0, 8)]


def test_una_sala_aislada_no_gana_vertices(tmp_path):
    sola = Estancia("Sala", rectangulo(5, 4), altura_m=3)
    escribir([sola], tmp_path / "salida")
    assert len(sola.contorno) == 4


def test_forma_en_ele_se_respeta(tmp_path):
    ele = [(0, 0), (6, 0), (6, 4), (3, 4), (3, 6), (0, 6)]
    texto = _contenido(tmp_path, [Estancia("Sala en L", list(ele), altura_m=3)])
    assert "NrPoints=6" in texto
    assert "Point4=3 4" in texto


def test_reflectancias_y_mantenimiento_solo_si_se_dan(tmp_path):
    texto = _contenido(tmp_path, [Estancia("Sala", rectangulo(5, 4), altura_m=3)])
    assert "R_Ceiling" not in texto and "MaintenanceFactor" not in texto
    texto = _contenido(tmp_path, [Estancia("Sala", rectangulo(5, 4), altura_m=3,
                                           reflectancia_techo=0.7, factor_mantenimiento=0.8)])
    assert "R_Ceiling=0.7" in texto and "MaintenanceFactor=0.8" in texto


def test_no_se_escribe_un_edificio_imposible(tmp_path):
    with pytest.raises(ValueError, match="plano de trabajo"):
        escribir([Estancia("Sala", rectangulo(5, 4), altura_m=3, plano_trabajo_m=3.5)],
                 tmp_path / "salida")
    with pytest.raises(ValueError, match="3 puntos"):
        escribir([Estancia("Sala", [(0, 0), (1, 1)], altura_m=3)], tmp_path / "salida")
    with pytest.raises(ValueError, match="ninguna estancia"):
        escribir([], tmp_path / "salida")
