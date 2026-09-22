"""Dibuja `plano-ejemplo.dxf`: un plano de mentira con el estilo de los de clase.

Existe para que cualquiera pueda probar la herramienta sin tener los planos de la asignatura, que
no se publican. Imita lo que hace difícil leerlos de verdad: los muros son parejas de líneas
sueltas, con huecos en las puertas y en la ventana, el enunciado va escrito dentro del dibujo y
hay una columna en medio de una sala.

    python ejemplos/generar_plano_ejemplo.py
"""

from pathlib import Path

import ezdxf

GROSOR = 0.2  # m de grosor de los muros
DESTINO = Path(__file__).resolve().parent / "plano-ejemplo.dxf"

# Recinto exterior de 16 x 10 (medidas interiores), partido en cuatro estancias.
#   +--------------------------+
#   |        Pasillo (2 m)     |
#   +---------------+----+-----+
#   |    Oficina    |Arch|Aseos|
#   +---------------+----+-----+
ANCHO, LARGO = 16.0, 10.0
PASILLO = 2.0            # fondo del pasillo, arriba
CORTE_1, CORTE_2 = 9.0, 12.5   # tabiques verticales de la fila de abajo


def pared(msp, x1, y1, x2, y2, huecos=()):
    """Un muro como dos líneas paralelas, con los huecos de puertas y ventanas sin dibujar."""
    vertical = x1 == x2
    largo = (y2 - y1) if vertical else (x2 - x1)
    tramos, desde = [], 0.0
    for inicio, fin in sorted(huecos):
        tramos.append((desde, inicio))
        desde = fin
    tramos.append((desde, largo))

    for lado in (-GROSOR / 2, GROSOR / 2):
        for a, b in tramos:
            if b - a < 0.01:
                continue
            if vertical:
                msp.add_line((x1 + lado, y1 + a), (x1 + lado, y1 + b))
            else:
                msp.add_line((x1 + a, y1 + lado), (x1 + b, y1 + lado))
    # Remates: la cara del muro se cierra a los lados de cada hueco.
    for corte in [t for tramo in tramos for t in tramo][1:-1]:
        if vertical:
            msp.add_line((x1 - GROSOR / 2, y1 + corte), (x1 + GROSOR / 2, y1 + corte))
        else:
            msp.add_line((x1 + corte, y1 - GROSOR / 2), (x1 + corte, y1 + GROSOR / 2))


def main() -> Path:
    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 6  # metros
    msp = doc.modelspace()

    # Fachada, con la puerta de entrada abajo y una ventana a la izquierda.
    pared(msp, 0, 0, ANCHO, 0, huecos=[(7.0, 8.2)])
    pared(msp, 0, LARGO, ANCHO, LARGO)
    pared(msp, 0, 0, 0, LARGO, huecos=[(3.0, 5.0)])  # ventana de 2 m
    pared(msp, ANCHO, 0, ANCHO, LARGO)

    # Tabique del pasillo, con tres puertas.
    y = LARGO - PASILLO
    pared(msp, 0, y, ANCHO, y, huecos=[(4.0, 5.0), (10.0, 11.0), (13.5, 14.5)])
    # Tabiques entre las tres salas de abajo.
    pared(msp, CORTE_1, 0, CORTE_1, y)
    pared(msp, CORTE_2, 0, CORTE_2, y)

    # Una columna en la oficina.
    msp.add_lwpolyline([(4.0, 3.0), (4.6, 3.0), (4.6, 3.6), (4.0, 3.6)], close=True)
    msp.add_text("Columna", height=0.25).set_placement((4.3, 3.8), align=ezdxf.enums.TextEntityAlignment.CENTER)

    # El enunciado, escrito dentro del plano como hacen en clase.
    msp.add_mtext(
        "Cotas en metros\n"
        "Altura de sala 3 m / espesor de pared: 0,2 m\n"
        "Altura del plano de trabajo: 0,85 m\n"
        "Zona marginal: 0,5 m\n"
        "Factor de mantenimiento: 0,8\n"
        "Reflectancias: dejarlas por defecto",
        dxfattribs={"char_height": 0.3},
    ).set_location((0.5, -1.5))

    # El uso de cada sala, con su referencia de la UNE-EN 12464-1.
    for x, y_texto, texto in [
        (4.5, 5.0, "34.2 Oficina (escritura, escritura a máquina...)"),
        (10.75, 5.0, "34.7 Archivos"),
        (14.25, 5.0, "10.4 Baños"),
        (8.0, 9.0, "9.1 Áreas de circulación y pasillos"),
    ]:
        msp.add_text(texto, height=0.3).set_placement(
            (x, y_texto), align=ezdxf.enums.TextEntityAlignment.CENTER)

    # Cotas entre caras interiores de los muros: son la comprobación de que las salas se han
    # reconstruido bien, así que tienen que medir lo mismo que las salas.
    m = GROSOR / 2
    # Sin estos ajustes el estilo por defecto escribe "880" donde el plano mide 8,80 m.
    estilo = {"dimlfac": 1, "dimdec": 2, "dimtxt": 0.28, "dimasz": 0.25, "dimexe": 0.1,
              "dimexo": 0.1, "dimgap": 0.08}
    msp.add_linear_dim(base=(0, -1.0), p1=(m, m), p2=(ANCHO - m, m), override=estilo).render()
    msp.add_linear_dim(base=(-1.0, 0), p1=(m, m), p2=(m, LARGO - PASILLO - m), angle=90,
                       override=estilo).render()
    msp.add_linear_dim(base=(0, LARGO + 1.0), p1=(m, LARGO - m), p2=(CORTE_1 - m, LARGO - m),
                       override=estilo).render()

    doc.saveas(DESTINO)
    return DESTINO


if __name__ == "__main__":
    print(main())
