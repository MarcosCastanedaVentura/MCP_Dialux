"""Leer el DWG que exporta DIALux evo, para poder comparar un proyecto hecho a mano.

DIALux evo no exporta STF, pero sí exporta el plano a DWG (Exportar → Exportar en un archivo
nuevo). Eso permite cerrar el círculo: Marcos monta el ejercicio a mano, lo exporta, y se compara
con el edificio que generó el MCP.

El fichero viene en 3D y repartido en capas, que es lo que lo hace legible (visto el 24/9/2026
con evo 14):

- `DLX_CALC`: una malla por sala a la altura del plano de trabajo. **De aquí sale el contorno**,
  que es más fiable que los muros porque ya es la superficie útil de la sala.
- `DLX_DESC`: el nombre de cada sala, como texto colocado dentro de ella.
- `DLX_CONT`: los muros, en 3D. Se usan solo para la altura.
- `DLX_OBJ`: los objetos, como bloques. Una columna es uno.

Ojo con las unidades: el fichero declara pulgadas ($INSUNITS=1) aunque se exporte en metros, así
que aquí se ignora la declaración y se toman metros, que es lo que ofrece el cuadro de exportación.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import ezdxf
from shapely import MultiPolygon, Point, Polygon, unary_union

from .cad.convertir import a_dxf

CAPA_SALAS = "DLX_CALC"
CAPA_NOMBRES = "DLX_DESC"
CAPA_MUROS = "DLX_CONT"
CAPA_OBJETOS = "DLX_OBJ"


def _caras(malla) -> list[Polygon]:
    """Los triángulos de una malla, en planta.

    Se piden como entidades 3DFACE (`virtual_entities`) en vez de recorrer la malla a mano: es la
    forma que funciona con las mallas que escribe DIALux.
    """
    salida = []
    for cara in malla.virtual_entities():
        if cara.dxftype() != "3DFACE":
            continue
        puntos = [(cara[i].x, cara[i].y) for i in range(4)]
        poligono = Polygon(dict.fromkeys(puntos))
        if poligono.is_valid and poligono.area > 1e-6:
            salida.append(poligono)
    return salida


def _altura(msp, sala: Polygon) -> float | None:
    """La altura de la sala, sacada de los muros que la tocan.

    Se coge la altura que más se repite, no la mayor: DIALux exporta la envolvente exterior con
    el forjado incluido, así que ese muro mide 3,2 donde la sala mide 3,0 (medido el 24/9/2026 en
    el ejemplo: cuatro muros a 3,0 y uno a 3,2). En un proyecto de una sola sala no hay tabiques
    con los que comparar y la altura puede salir con el grueso del forjado de más.
    """
    alturas = []
    for muro in msp.query(f"POLYLINE[layer=='{CAPA_MUROS}']"):
        puntos = [v.dxf.location for v in muro.vertices]
        if not puntos:
            continue
        alto = max(p.z for p in puntos)
        if alto <= 0:
            continue
        xs = [p.x for p in puntos]
        ys = [p.y for p in puntos]
        caja = Polygon([(min(xs), min(ys)), (max(xs), min(ys)),
                        (max(xs), max(ys)), (min(xs), max(ys))])
        if caja.area > 1e-9 and caja.intersects(sala):
            alturas.append(round(alto, 3))
    if not alturas:
        return None
    repeticiones = Counter(alturas)
    veces = max(repeticiones.values())
    return min(a for a, n in repeticiones.items() if n == veces)


def _objetos(msp, doc) -> list[dict]:
    objetos = []
    for insercion in msp.query(f"INSERT[layer=='{CAPA_OBJETOS}']"):
        bloque = doc.blocks.get(insercion.dxf.name)
        puntos = [v.dxf.location for pieza in bloque if pieza.dxftype() == "POLYLINE"
                  for v in pieza.vertices]
        if not puntos:
            continue
        x, y, z = insercion.dxf.insert
        anchos = (max(p.x for p in puntos) - min(p.x for p in puntos),
                  max(p.y for p in puntos) - min(p.y for p in puntos),
                  max(p.z for p in puntos) - min(p.z for p in puntos))
        objetos.append({"centro_m": (round(x, 3), round(y, 3)),
                        "ancho_x_m": round(anchos[0] * insercion.dxf.xscale, 3),
                        "largo_y_m": round(anchos[1] * insercion.dxf.yscale, 3),
                        "alto_m": round(anchos[2] * insercion.dxf.zscale, 3),
                        "base_z_m": round(z, 3)})
    return objetos


def leer(ruta: str | Path) -> dict:
    """Las salas de un proyecto exportado por DIALux evo, con el mismo formato que `leer_stf`."""
    fichero = Path(ruta).expanduser()
    doc = ezdxf.readfile(a_dxf(fichero))
    msp = doc.modelspace()

    mallas = msp.query(f"POLYLINE[layer=='{CAPA_SALAS}']")
    if not mallas:
        raise ValueError(
            f"{fichero.name} no parece un DWG exportado por DIALux evo: no tiene la capa "
            f"{CAPA_SALAS}. Al exportar hay que dejar marcada 'Puntos y superficies de cálculo'.")

    nombres = [(t.get_placement()[1], t.dxf.text) for t in msp.query(f"TEXT[layer=='{CAPA_NOMBRES}']")]
    objetos = _objetos(msp, doc)

    salas = []
    for i, malla in enumerate(mallas, start=1):
        caras = _caras(malla)
        if not caras:
            continue
        superficie = unary_union(caras)
        if isinstance(superficie, MultiPolygon):
            superficie = max(superficie.geoms, key=lambda p: p.area)
        superficie = superficie.simplify(0.001)
        alturas_z = [v.dxf.location.z for v in malla.vertices if v.dxf.location.z]
        x0, y0, x1, y1 = superficie.bounds
        nombre = next((texto for punto, texto in nombres
                       if superficie.contains(Point(punto.x, punto.y))), f"Sala {i}")
        salas.append({
            "nombre": nombre,
            "altura_m": _altura(msp, superficie),
            "plano_trabajo_m": round(min(alturas_z), 3) if alturas_z else None,
            "vertices": len(superficie.exterior.coords) - 1,
            "contorno_m": [(round(x, 3), round(y, 3)) for x, y in superficie.exterior.coords[:-1]],
            "area_m2": round(superficie.area, 2),
            "ancho_x_m": round(x1 - x0, 3),
            "largo_y_m": round(y1 - y0, 3),
            "objetos": [o for o in objetos if superficie.contains(Point(*o["centro_m"]))],
        })

    return {"fichero": fichero.name, "proyecto": fichero.stem,
            "escrito_por": "DIALux evo (exportación a DWG)", "salas": salas}
