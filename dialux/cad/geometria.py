"""Reconstruir las salas de un plano en el que ninguna sala está dibujada como polígono.

Los planos de clase dibujan cada muro como líneas sueltas (cara interior, cara exterior y
remates), con huecos en puertas y aberturas. El proceso es:

1. Juntar todos los tramos rectos del dibujo, sin mirar la capa.
2. Cerrar los huecos: dos tramos sobre la misma recta separados menos de `HUECO_MAX` son un muro
   con una puerta, y se une el hueco.
3. Poligonizar: cada cara cerrada del dibujo es una sala, un grueso de muro o un detalle.
4. Quedarse con las caras anchas; las estrechas son muros.
"""

from __future__ import annotations

import math
from collections import defaultdict

from ezdxf.layouts import Modelspace
from ezdxf.path import make_path
from shapely import LineString, Polygon, polygonize, unary_union

# No se filtra por capa: en el examen de junio los remates de muro de los huecos de puerta están
# en la capa "Texto", y quitar esa capa dejaba el pasillo unido a las salas.
TIPOS_DIBUJO = {"LINE", "LWPOLYLINE", "POLYLINE", "ARC"}

TOLERANCIA = 0.005  # m. Dos puntos a menos de 5 mm son el mismo punto (redondeos de AutoCAD).

# Hueco más ancho que se cierra. Medido el 16/9/2026 en los tres exámenes: el mayor es la abertura
# del pasillo de la segunda planta de junio (2,17 m), seguido de las ventanas del parcial y de
# enero (2,08 m). Si se sube demasiado, se unirían muros que no forman pared entre sí.
HUECO_MAX = 2.5  # m

# Anchura media de una cara (2·área/perímetro) por debajo de la cual es grueso de muro y no sala.
# El muro más grueso de los exámenes es el de 0,59 m del final de enero (da ~0,55); el espacio
# útil más estrecho, el ascensor de junio de 1,5 m de lado (da ~0,85).
ANCHURA_MIN_SALA = 0.7  # m

# Un hueco dentro de una sala más delgado que esto no es un obstáculo, es un dibujo: la hoja de la
# puerta abierta de Archivos (junio) mide 6 cm y salía como un agujero de la sala. La columna más
# pequeña de los exámenes mide 0,66 × 0,63 m (anchura media 0,32).
GROSOR_MIN_OBSTACULO = 0.15  # m


def tramos(msp: Modelspace) -> list[LineString]:
    """Todos los tramos rectos del dibujo. Los arcos (giro de puertas) se aproximan con cuerdas."""
    salida = []
    for entidad in msp:
        if entidad.dxftype() not in TIPOS_DIBUJO:
            continue
        try:
            puntos = [(round(v.x, 3), round(v.y, 3)) for v in make_path(entidad).flattening(0.01)]
        except Exception:
            continue
        for a, b in zip(puntos, puntos[1:]):
            if math.dist(a, b) > TOLERANCIA:
                salida.append(LineString([a, b]))
    return salida


def _recta(tramo: LineString) -> tuple[tuple[float, float], float, tuple[float, float]]:
    """(dirección unitaria canónica, distancia de la recta al origen, punto de paso)."""
    (x1, y1), (x2, y2) = tramo.coords
    dx, dy = x2 - x1, y2 - y1
    largo = math.hypot(dx, dy)
    ux, uy = dx / largo, dy / largo
    if ux < -1e-9 or (abs(ux) < 1e-9 and uy < 0):
        ux, uy = -ux, -uy
    return (ux, uy), -uy * x1 + ux * y1, (x1, y1)


def huecos(lista: list[LineString], hueco_max: float = HUECO_MAX) -> list[LineString]:
    """Tramos que cierran los huecos entre tramos alineados sobre una misma recta."""
    grupos: dict[tuple[int, int, int], list[tuple[float, float]]] = defaultdict(list)
    rectas: dict[tuple[int, int, int], tuple[tuple[float, float], float]] = {}
    for tramo in lista:
        (ux, uy), offset, _ = _recta(tramo)
        clave = (round(math.degrees(math.atan2(uy, ux)) * 2), round(offset / TOLERANCIA), 0)
        (xa, ya), (xb, yb) = tramo.coords
        ta, tb = ux * xa + uy * ya, ux * xb + uy * yb
        grupos[clave].append((min(ta, tb), max(ta, tb)))
        rectas[clave] = ((ux, uy), offset)

    cierres = []
    for clave, intervalos in grupos.items():
        (ux, uy), offset = rectas[clave]
        intervalos.sort()
        fin = intervalos[0][1]
        for inicio, final in intervalos[1:]:
            separacion = inicio - fin
            if TOLERANCIA < separacion <= hueco_max:
                # punto de la recta = t·u + offset·n, con n = (-uy, ux)
                a = (fin * ux - offset * uy, fin * uy + offset * ux)
                b = (inicio * ux - offset * uy, inicio * uy + offset * ux)
                cierres.append(LineString([a, b]))
            fin = max(fin, final)
    return cierres


def aberturas(sala: Polygon, cierres: list[LineString]) -> list[dict]:
    """Los huecos de puerta y ventana de una sala: los tramos cerrados que caen sobre su pared.

    Cada uno se devuelve con el centro del hueco y su anchura. La pared es la que va del punto
    <n> al <n>+1 del contorno, que es la numeración que usa el propio STF para las reflectancias.
    """
    encontradas = []
    contorno = list(sala.exterior.coords)[:-1]
    for i, (a, b) in enumerate(zip(contorno, contorno[1:] + contorno[:1]), start=1):
        pared = LineString([a, b])
        for cierre in cierres:
            comun = pared.intersection(cierre.buffer(TOLERANCIA, cap_style="flat"))
            if comun.is_empty or comun.geom_type != "LineString" or comun.length < 0.2:
                continue
            centro = comun.interpolate(0.5, normalized=True)
            encontradas.append({"pared": i, "centro": (centro.x, centro.y),
                                "ancho_m": round(comun.length, 3)})
    return encontradas


def caras(lista: list[LineString]) -> list[Polygon]:
    red = unary_union(lista + huecos(lista))
    return [p for p in polygonize(list(getattr(red, "geoms", [red]))).geoms if p.area > 1e-6]


def salas_y_plantas(poligonos: list[Polygon]) -> tuple[list[Polygon], list[Polygon]]:
    """(salas, contorno exterior de cada planta). Una planta es un bloque de caras que se tocan."""
    salas = [_sin_dibujos_dentro(p) for p in poligonos if _anchura_media(p) >= ANCHURA_MIN_SALA]
    bloque = unary_union(poligonos)
    plantas = [Polygon(g.exterior) for g in getattr(bloque, "geoms", [bloque])]
    return salas, plantas


def _anchura_media(poligono: Polygon) -> float:
    """2·área/perímetro: en un rectángulo alargado es casi su grosor, en uno cuadrado su medio lado."""
    return 2 * poligono.area / poligono.exterior.length


def _sin_dibujos_dentro(sala: Polygon) -> Polygon:
    obstaculos = [h for h in sala.interiors if _anchura_media(Polygon(h)) >= GROSOR_MIN_OBSTACULO]
    # Cerrar huecos y cortar tramos deja vértices en mitad de las paredes rectas: el parcial salía
    # con 8 vértices para un rectángulo, y a DIALux hay que darle las esquinas de verdad.
    return Polygon(sala.exterior, obstaculos).simplify(TOLERANCIA / 5, preserve_topology=True)
