"""El reparto de luminarias en retícula y cómo se escribe en el STF.

Lo que se comprueba aquí es geometría, no luminotecnia: que la retícula sea la más cuadrada que
cabe, que las de los bordes queden a media separación del muro y que en una sala que no es
rectangular no se quede ninguna fuera. **Cuántas luminarias hacen falta no lo decide el código**
(hace falta la fotometría), así que el número se le pasa.
"""

from pathlib import Path

import pytest
from shapely import Point, Polygon

from dialux.luminarias import reparto, reticula
from dialux.construir import plano_a_stf
from dialux.leer_stf import leer
from dialux.stf import Estancia, Luminaria, TipoLuminaria, escribir, rectangulo

ELE = [(0, 0), (6, 0), (6, 4), (3, 4), (3, 6), (0, 6)]


def test_la_reticula_sale_lo_mas_cuadrada_posible():
    assert reparto(5, 4, 6) == (3, 2)        # 1,67 × 2,00 m, no 2,50 × 1,33
    assert reparto(4, 5, 6) == (2, 3)        # la misma sala girada, la retícula también
    assert reparto(4, 4, 4) == (2, 2)
    assert reparto(4, 4, 1) == (1, 1)


def test_entre_dos_reticulas_parecidas_gana_la_que_no_sobran_luminarias():
    # 10 × 4 m con 12: 6 × 2 las coloca justas; 5 × 3 dejaría tres de más.
    assert reparto(10, 4, 12) == (6, 2)


def test_un_numero_que_no_forma_reticula_sube_al_siguiente_y_se_avisa():
    assert reparto(5, 4, 7) == (3, 3)
    salida = reticula(rectangulo(5, 4), 7, altura_montaje_m=3.0)
    assert salida["pedidas"] == 7 and salida["colocadas"] == 9
    # El aviso tiene que decir el número nuevo: con 9 luminarias el cálculo hecho para 7 ya no vale.
    assert any("3 × 3 = 9" in a and "9" in a for a in salida["avisos"])


def test_las_de_los_bordes_quedan_a_media_separacion_del_muro():
    salida = reticula(rectangulo(6, 4), 6, altura_montaje_m=3.0, plano_trabajo_m=0.85)
    assert (salida["separacion_x_m"], salida["separacion_y_m"]) == (2.0, 2.0)
    assert salida["distancia_a_pared_x_m"] == 1.0
    assert salida["posiciones_m"][0] == (1.0, 1.0, 3.0)
    assert salida["posiciones_m"][-1] == (5.0, 3.0, 3.0)
    # La altura útil es del plano de trabajo a la luminaria, y es con lo que se compara la
    # separación cuando se tenga la curva de la luminaria.
    assert salida["altura_util_m"] == 2.15
    assert salida["separacion_entre_altura_util"] == round(2.0 / 2.15, 2)


def test_en_una_sala_en_ele_no_se_queda_ninguna_fuera():
    salida = reticula(ELE, 9, altura_montaje_m=3.0)
    sala = Polygon(ELE)
    assert all(sala.contains(Point(x, y)) for x, y, _ in salida["posiciones_m"])
    assert salida["colocadas"] == 7 and any("no es rectangular" in a for a in salida["avisos"])


def test_se_avisa_si_los_bordes_caen_en_la_zona_marginal():
    # Sala pequeña con muchos empotrados: 5 × 4 en 4 × 3 m deja los bordes a 0,38 m del muro,
    # dentro de la banda de 0,5 m del enunciado.
    salida = reticula(rectangulo(4, 3), 20, altura_montaje_m=3.0, zona_marginal_m=0.5)
    assert any("zona marginal" in a for a in salida["avisos"])
    # Con 12 caen a 0,5 m justos, que ya no es dentro: no se avisa de lo que no pasa.
    assert not any("zona marginal" in a
                   for a in reticula(rectangulo(4, 3), 12, altura_montaje_m=3.0,
                                     zona_marginal_m=0.5)["avisos"])


def test_no_se_colocan_por_debajo_del_plano_de_trabajo():
    with pytest.raises(ValueError, match="plano de trabajo"):
        reticula(rectangulo(5, 4), 4, altura_montaje_m=0.8, plano_trabajo_m=0.85)


def test_el_stf_lleva_las_luminarias_y_su_seccion_de_tipo(tmp_path):
    """La especificación pide una sección por tipo de luminaria, aunque DIALux la ignore al leer."""
    tipo = TipoLuminaria("Panel 600x600", fabricante="Endo Lighting", referencia="ERD7616S",
                         flujo_lm=4000, potencia_w=35)
    sala = Estancia("Sala", rectangulo(5, 4), altura_m=3, plano_trabajo_m=0.85,
                    luminarias=[Luminaria(tipo, p)
                                for p in reticula(rectangulo(5, 4), 4,
                                                  altura_montaje_m=3.0)["posiciones_m"]])
    ruta = escribir([sala], tmp_path / "salida")
    texto = ruta.read_text(encoding="latin-1")
    assert "NrLums=4" in texto and "NrStruct=0" in texto
    assert "Lum1=LUMINAIRE.L1" in texto and "Lum1.Pos=1.25 1 3" in texto
    assert "Lum1.Rot=0 0 0" in texto
    assert "[LUMINAIRE.L1]" in texto and "Manufacturer=Endo Lighting" in texto
    assert "OrderNr=ERD7616S" in texto and "Name=Panel 600x600" in texto
    assert "Flux=4000" in texto and "Load=35" in texto
    # Y se vuelven a leer con su posición, para comprobarlo sin abrir DIALux.
    sala_leida, = leer(ruta)["salas"]
    assert sala_leida["luminarias"] == 4
    assert sala_leida["luminarias_colocadas"][0]["posicion_m"] == [1.25, 1.0, 3.0]


def test_el_plano_de_ejemplo_con_luminarias(tmp_path):
    plano = Path(__file__).resolve().parents[1] / "ejemplos" / "plano-ejemplo.dxf"
    salida = plano_a_stf(plano, carpeta_destino=tmp_path, luminarias={"Oficina": 12})
    salas = {e["nombre"]: e for p in salida["plantas"] for e in p["estancias"]}
    oficina = next(s for n, s in salas.items() if "Oficina" in n)
    assert oficina["luminarias"]["colocadas"] == 12
    assert oficina["luminarias"]["altura_montaje_m"] == 3.0  # el techo de la sala
    # Solo la oficina: a las demás no se les ha dicho ningún número.
    assert sum("luminarias" in s for s in salas.values()) == 1
    assert any("marcadores" in a for a in salida["avisos"])
