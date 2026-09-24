"""Leer un fichero STF y contar qué hay dentro, y comparar dos entre sí.

Sirve para dos cosas: mirar lo que se ha generado sin abrir DIALux, y comparar el edificio del
MCP con otro fichero, por ejemplo uno exportado por otro programa.

**Límite que conviene tener claro:** DIALux evo no exporta STF, así que un proyecto montado a
mano en evo no se puede convertir a este formato para compararlo. La comparación vale entre
ficheros STF: dos versiones generadas, o uno del MCP contra uno de un CAD que sí exporte.

El formato es texto plano con secciones `[TAG]` y líneas `clave=valor`, y las claves no
distinguen mayúsculas (lo dice la especificación, y los ficheros de otros programas lo aprovechan).
"""

from __future__ import annotations

import re
from pathlib import Path

from shapely import Polygon

TOLERANCIA = 0.01  # m. Por debajo de un centímetro, dos medidas son la misma.

CABECERA = re.compile(r"^\[(.+)\]\s*$")


def _secciones(texto: str) -> dict[str, dict[str, str]]:
    salida: dict[str, dict[str, str]] = {}
    actual: dict[str, str] = {}
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        if m := CABECERA.match(linea):
            actual = salida.setdefault(m.group(1).upper(), {})
        elif "=" in linea:
            clave, valor = linea.split("=", 1)
            actual[clave.strip().upper()] = valor.strip()
    return salida


def _numero(texto: str | None) -> float | None:
    try:
        valor = float(texto)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return int(valor) if valor.is_integer() else valor


def _puntos(seccion: dict[str, str]) -> list[tuple[float, float]]:
    cuantos = int(_numero(seccion.get("NRPOINTS")) or 0)
    puntos = []
    for i in range(1, cuantos + 1):
        partes = (seccion.get(f"POINT{i}") or "").split()
        if len(partes) >= 2:
            puntos.append((float(partes[0]), float(partes[1])))
    return puntos


def _muebles(seccion: dict[str, str]) -> list[dict]:
    cuantos = int(_numero(seccion.get("NRFURNS")) or 0)
    muebles = []
    for i in range(1, cuantos + 1):
        nombre = seccion.get(f"FURN{i}")
        if not nombre:
            continue
        tamano = (seccion.get(f"FURN{i}.SIZE") or "").split()
        posicion = (seccion.get(f"FURN{i}.POS") or "").split()
        tipo = {"win": "ventana", "door": "puerta", "skylight": "claraboya"}.get(
            nombre.lower(), "objeto")
        muebles.append({
            "tipo": tipo,
            "nombre": nombre,
            "posicion_m": [float(v) for v in posicion[:3]] if len(posicion) >= 3 else None,
            "tamano_m": [float(v) for v in tamano[:3]] if len(tamano) >= 3 else None,
        })
    return muebles


def leer(ruta: str | Path) -> dict:
    """Todo lo que dice un fichero STF, sala por sala."""
    fichero = Path(ruta).expanduser()
    if not fichero.is_file():
        raise FileNotFoundError(f"No existe el fichero: {fichero}")
    secciones = _secciones(fichero.read_text(encoding="latin-1", errors="replace"))
    proyecto = secciones.get("PROJECT", {})

    salas = []
    for i in range(1, int(_numero(proyecto.get("NRROOMS")) or 0) + 1):
        etiqueta = (proyecto.get(f"ROOM{i}") or "").upper()
        seccion = secciones.get(etiqueta)
        if not seccion:
            continue
        puntos = _puntos(seccion)
        poligono = Polygon(puntos) if len(puntos) >= 3 else None
        muebles = _muebles(seccion)
        sala = {
            "nombre": seccion.get("NAME") or etiqueta,
            "altura_m": _numero(seccion.get("HEIGHT")),
            "plano_trabajo_m": _numero(seccion.get("WORKINGPLANE")),
            "factor_mantenimiento": _numero(seccion.get("MF")),
            "vertices": len(puntos),
            "contorno_m": [(round(x, 3), round(y, 3)) for x, y in puntos],
            "luminarias": int(_numero(seccion.get("NRLUMS")) or 0),
        }
        if poligono is not None:
            x0, y0, x1, y1 = poligono.bounds
            sala |= {"area_m2": round(poligono.area, 2),
                     "ancho_x_m": round(x1 - x0, 3), "largo_y_m": round(y1 - y0, 3)}
        for clave, etiqueta_stf in (("reflectancia_techo", "R_CEILING"),
                                    ("reflectancia_suelo", "R_FLOOR"),
                                    ("reflectancia_paredes", "R_WALL1")):
            if (valor := _numero(seccion.get(etiqueta_stf))) is not None:
                sala[clave] = valor
        if muebles:
            sala["muebles"] = muebles
        salas.append(sala)

    return {
        "fichero": fichero.name,
        "proyecto": proyecto.get("NAME"),
        "escrito_por": secciones.get("VERSION", {}).get("PROGNAME"),
        "version_stf": secciones.get("VERSION", {}).get("STFF"),
        "salas": salas,
    }


CAMPOS = [("altura_m", "altura"), ("plano_trabajo_m", "plano de trabajo"),
          ("factor_mantenimiento", "factor de mantenimiento"), ("area_m2", "superficie"),
          ("ancho_x_m", "ancho"), ("largo_y_m", "largo"),
          ("reflectancia_techo", "reflectancia del techo"),
          ("reflectancia_suelo", "reflectancia del suelo"),
          ("reflectancia_paredes", "reflectancia de las paredes"),
          ("luminarias", "número de luminarias")]


def _emparejar(salas_a: list[dict], salas_b: list[dict]) -> list[tuple[dict | None, dict | None]]:
    """Empareja salas por nombre; las que no casen, por superficie parecida."""
    pendientes_b = list(salas_b)
    parejas: list[tuple[dict | None, dict | None]] = []
    for sala in salas_a:
        pareja = next((s for s in pendientes_b if s["nombre"] == sala["nombre"]), None)
        if pareja is None:
            pareja = next((s for s in pendientes_b
                           if abs(s.get("area_m2", -1) - sala.get("area_m2", -2)) < TOLERANCIA),
                          None)
        if pareja is not None:
            pendientes_b.remove(pareja)
        parejas.append((sala, pareja))
    parejas += [(None, s) for s in pendientes_b]
    return parejas


def comparar(ruta_a: str | Path, ruta_b: str | Path) -> dict:
    """Qué se diferencia entre dos ficheros STF, sala por sala."""
    a, b = leer(ruta_a), leer(ruta_b)
    diferencias, iguales, solo_a, solo_b = [], [], [], []

    for sala_a, sala_b in _emparejar(a["salas"], b["salas"]):
        if sala_b is None:
            solo_a.append(sala_a["nombre"])
            continue
        if sala_a is None:
            solo_b.append(sala_b["nombre"])
            continue
        propias = []
        for clave, titulo in CAMPOS:
            va, vb = sala_a.get(clave), sala_b.get(clave)
            if va is None and vb is None:
                continue
            if va is None or vb is None or abs(va - vb) > TOLERANCIA:
                propias.append({"que": titulo, "en_a": va, "en_b": vb})
        muebles_a = len(sala_a.get("muebles", []))
        muebles_b = len(sala_b.get("muebles", []))
        if muebles_a != muebles_b:
            propias.append({"que": "número de muebles (huecos y columnas)",
                            "en_a": muebles_a, "en_b": muebles_b})
        nombre = sala_a["nombre"]
        if sala_b["nombre"] != nombre:
            propias.append({"que": "nombre", "en_a": nombre, "en_b": sala_b["nombre"]})
        (diferencias.append({"sala": nombre, "diferencias": propias}) if propias
         else iguales.append(nombre))

    return {
        "a": {"fichero": a["fichero"], "salas": len(a["salas"])},
        "b": {"fichero": b["fichero"], "salas": len(b["salas"])},
        "iguales": iguales,
        "con_diferencias": diferencias,
        "solo_en_a": solo_a,
        "solo_en_b": solo_b,
        "resumen": (f"{len(iguales)} sala(s) iguales, {len(diferencias)} con diferencias, "
                    f"{len(solo_a)} solo en el primero y {len(solo_b)} solo en el segundo."),
    }
