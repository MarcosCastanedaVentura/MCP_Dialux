"""Leer el DWG que exporta DIALux evo, para poder comparar un proyecto hecho a mano.

DIALux evo no exporta STF, pero sí exporta el plano a DWG (Exportar → Exportar en un archivo
nuevo). Eso permite cerrar el círculo: Marcos monta el ejercicio a mano, lo exporta, y se compara
con el edificio que generó el MCP.

Hay **dos variantes** de esa exportación, y no traen lo mismo. Las dos se leen aquí.

**Variante 3D** (vista el 24/9/2026 con evo 14, `material/exportados/prueba-export.dwg`): mallas
con z de verdad, en capas sin prefijo de planta.

- `DLX_CALC`: una malla por sala a la altura del plano de trabajo. **De aquí sale el contorno**,
  que es más fiable que los muros porque ya es la superficie útil de la sala.
- `DLX_DESC`: el nombre de cada sala, como texto colocado dentro de ella.
- `DLX_CONT`: los muros, en 3D. Se usan solo para la altura.
- `DLX_OBJ`: los objetos, como bloques. Una columna es uno.

**Variante 2D** (vista el 3/10/2026 con el trabajo de clase de Marcos): todo son segmentos de dos
puntos con z = 0, así que **no hay alturas ni plano de trabajo**. En cambio trae tres cosas que la
3D no, y que son justo las que hacían falta para corregir un trabajo entero:

- **La planta va en el nombre de la capa**: `DLX_FL0_CONT`, `DLX_FL1_CALC`… Lo que el STF no sabe
  decir al entrar, el DWG lo dice al salir.
- **Las luminarias**: una capa `DLX_FL<planta>_LUM <indice>` con el símbolo de cada una (dos
  cuadrados concéntricos) y otra `..._LUMKEY_IDX` con el índice como texto. El centro se saca del
  símbolo: el texto va desplazado a la esquina.
- **Las tablas de resultados de DIALux**, como entidades `ACAD_TABLE`: la lista de luminarias (con
  flujo, factor de degradación y potencia) y los resultados por sala (mínima, máxima, media y
  uniformidades).

El contorno de las salas se saca de los muros (`CONT`) y no de la superficie de cálculo, porque la
de cálculo va metida hacia dentro medio paso de la retícula de puntos (0,19 m en el trabajo de
clase) y entonces las superficies no cuadrarían con las del STF. Comprobación de que es la cara
buena: con el área de los muros, la potencia específica sale 7,67 W/m², que es exactamente la que
escribe DIALux en el nombre de la sala.

Ojo con las unidades: el fichero declara pulgadas ($INSUNITS=1) aunque se exporte en metros, así
que aquí se ignora la declaración y se toman metros, que es lo que ofrece el cuadro de exportación.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import ezdxf
from shapely import LineString, MultiPolygon, Point, Polygon, polygonize, unary_union

from .cad.convertir import a_dxf
from .cad.geometria import _anchura_media, caras

# Anchura media mínima de una cara para que pueda ser una sala. Es más baja que la del lector de
# planos (0,7 m) porque aquí las salas las manda el rótulo de DIALux y esto solo sirve para que un
# rótulo pegado a un muro no se quede con el grueso del muro: los de este DWG miden 0,15 m de
# anchura media y el cuarto más pequeño del trabajo de clase, 0,66 m.
ANCHURA_MIN_CUARTO = 0.25  # m

CAPA_SALAS = "DLX_CALC"
CAPA_NOMBRES = "DLX_DESC"
CAPA_MUROS = "DLX_CONT"
CAPA_OBJETOS = "DLX_OBJ"

# Variante 2D: las mismas capas, pero con la planta por delante.
PLANTA = re.compile(r"^DLX_FL(\d+)_(CALC|CONT|DESC|OBJ)$", re.IGNORECASE)
CAPA_LUMINARIAS = re.compile(r"^DLX_FL(\d+)_LUM\s*(\d+)$", re.IGNORECASE)

# "Aula 1 (7.67 W/m²)" -> el nombre y la potencia específica que DIALux ya ha calculado. Las salas
# sin luminarias llevan "(/)".
NOMBRE_CON_POTENCIA = re.compile(r"^(.*?)\s*\(([\d.,]+)\s*W/m²\)\s*$")
NOMBRE_SIN_CALCULAR = re.compile(r"^(.*?)\s*\(/\)\s*$")
# Dos piezas de dibujo cuyos centros estén más cerca que esto son el mismo símbolo de luminaria.
# Un panel de 60×60 lleva dos cuadrados concéntricos; la luminaria más apretada del trabajo de
# clase está a 2,09 m de la siguiente, así que hay margen de sobra.
TOLERANCIA_SIMBOLO = 0.1  # m

# "Plano útil (Aula 1)" -> de qué sala son esos resultados.
SALA_DEL_RESULTADO = re.compile(r"\((.+)\)\s*$")


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


def _leer_3d(fichero: Path, doc, msp) -> dict:
    """La variante 3D: una malla por sala, con alturas de verdad."""
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
            "escrito_por": "DIALux evo (exportación a DWG)", "variante": "3D", "salas": salas}


# --- Variante 2D: plantas, luminarias y las tablas de resultados de DIALux -------------------

def _segmentos(msp, capa: str) -> list[LineString]:
    """Los tramos de una capa de la variante 2D: polilíneas de dos puntos, todas con z = 0."""
    salida = []
    for linea in msp.query(f"POLYLINE[layer=='{capa}']"):
        puntos = [(round(v.dxf.location.x, 4), round(v.dxf.location.y, 4))
                  for v in linea.vertices]
        if len(puntos) == 2 and puntos[0] != puntos[1]:
            salida.append(LineString(puntos))
    return salida


def _poligonos(lineas: list[LineString]) -> list[Polygon]:
    """Las caras cerradas de unos tramos, SIN cerrar huecos.

    Para las luminarias no se puede usar `caras()` del lector de planos: ahí se unen los tramos
    alineados separados menos de 2,5 m, que es justo la separación entre luminarias, y en vez de
    20 símbolos salían cientos de caras inventadas entre ellos.
    """
    red = unary_union(lineas)
    return [p for p in polygonize(list(getattr(red, "geoms", [red]))).geoms if p.area > 1e-6]


def _clave(cabecera: str) -> str:
    """La cabecera de una columna, sin tildes, puntos ni mayúsculas, para reconocerla.

    Los puntos se quitan sin dejar espacio: "Mín./medio" es "min/medio". Dejando el espacio
    ("min / medio") no se reconocían dos columnas, el número de columnas salía mal y las filas se
    leían corridas: la media de una sala caía en la casilla de otra.
    """
    tabla = str.maketrans("áéíóúÁÉÍÓÚüñ", "aeiouAEIOUun")
    return " ".join(cabecera.translate(tabla).lower().replace(".", "").split())


COLUMNAS_LUMINARIA = {
    "indice": "indice", "fabricante": "fabricante", "nombre del articulo": "articulo",
    "numero de articulo": "numero_articulo", "lampara": "lampara",
    "flujo luminoso": "flujo_lm", "factor de degradacion": "factor_degradacion",
    "potencia de conexion": "potencia_w", "cantidad": "cantidad",
}
COLUMNAS_RESULTADO = {
    "nombre": "superficie", "parametros": "parametro", "min": "e_min_lx", "max": "e_max_lx",
    "media": "e_media_lx", "min/medio": "u0", "min/max": "e_min_entre_max",
}
NUMERICAS = {"flujo_lm", "factor_degradacion", "potencia_w", "cantidad", "e_min_lx", "e_max_lx",
             "e_media_lx", "u0", "e_min_entre_max"}


def _valor(texto: str) -> float | str | None:
    """"318 lx" -> 318.0, "0.80" -> 0.8, "-" -> None. Vale con coma o con punto decimal."""
    limpio = texto.replace("lx", "").replace("lm", "").replace("W", "").strip()
    if limpio in ("-", "–", ""):
        return None
    try:
        numero = float(limpio.replace(",", "."))
    except ValueError:
        return texto.strip()
    return int(numero) if numero.is_integer() else numero


def _filas(tabla) -> list[dict]:
    """Las filas de una tabla de DIALux, ya con nombres de columna reconocibles.

    Las celdas vienen como MTEXT en orden de lectura. El número de columnas no se da por sabido:
    se cuenta hasta la primera celda que vale "1", que es la primera fila de datos. Así la lectura
    no se rompe si una versión de DIALux añade o quita una columna.
    """
    celdas = [e.plain_text().strip() for e in tabla.virtual_entities() if e.dxftype() == "MTEXT"]
    celdas = [c for c in celdas if c]
    if "1" not in celdas:
        return []
    corte = celdas.index("1")
    previas = [_clave(c) for c in celdas[:corte]]

    # La fila de cabeceras es la tirada de celdas justo anterior a la primera fila de datos. Se
    # recorre hacia atrás hasta encontrar algo que no es una cabecera: así el título que lleva la
    # lista de luminarias ("Lista de luminarias (Edificación 1)") no se cuenta como columna, y una
    # columna nueva de otra versión de DIALux sí se cuenta, aunque luego no se sepa qué es.
    conocidas = set(COLUMNAS_LUMINARIA) | set(COLUMNAS_RESULTADO) | {"#"}
    inicio = len(previas)
    while inicio and (previas[inicio - 1] in conocidas
                      or ("(" not in previas[inicio - 1] and len(previas[inicio - 1]) < 25)):
        inicio -= 1
    cabeceras = previas[inicio:]
    diccionario = COLUMNAS_LUMINARIA if "fabricante" in cabeceras else COLUMNAS_RESULTADO
    columnas = len(cabeceras)
    if not columnas:
        return []
    datos = celdas[corte:]
    filas = []
    for inicio in range(0, len(datos) - columnas + 1, columnas):
        fila = {}
        for cabecera, celda in zip(cabeceras, datos[inicio:inicio + columnas]):
            nombre = diccionario.get(cabecera)
            if nombre is None:
                continue
            fila[nombre] = _valor(celda) if nombre in NUMERICAS else celda
        if fila:
            filas.append(fila)
    return filas


def _tablas(msp) -> tuple[list[dict], dict[str, dict]]:
    """(lista de luminarias del proyecto, resultados por sala) de las tablas del DWG."""
    luminarias: list[dict] = []
    resultados: dict[str, dict] = {}
    for tabla in msp.query("ACAD_TABLE"):
        for fila in _filas(tabla):
            if "fabricante" in fila:
                if fila not in luminarias:
                    luminarias.append(fila)
            elif superficie := fila.pop("superficie", None):
                # "Plano útil (Aula 1)" -> Aula 1. Las tablas se repiten por edificio y por
                # planta; la sala es la misma, así que la primera que aparezca vale.
                if m := SALA_DEL_RESULTADO.search(superficie):
                    resultados.setdefault(m.group(1), {"superficie": superficie, **fila})
    return luminarias, resultados


def _luminarias_2d(msp, planta: str) -> list[dict]:
    """Las luminarias de una planta: centro y tamaño de cada símbolo, con su índice de tipo.

    Cada luminaria son dos cuadrados concéntricos (el aparato y su interior), así que se agrupan
    por centro y se queda el grande. El texto del índice NO sirve de posición: va desplazado a la
    esquina del símbolo (medido el 3/10/2026: +0,30 m en x y en y para un panel de 60×60).
    """
    puestas: list[dict] = []
    for capa in msp.doc.layers:
        coincide = CAPA_LUMINARIAS.match(capa.dxf.name)
        if not coincide or coincide.group(1) != planta:
            continue
        # Los dos cuadrados de una luminaria no comparten el centro al milímetro (uno sale en
        # 7,315 y el otro en 7,3149), así que no se pueden agrupar redondeando: se agrupa por
        # cercanía y de cada grupo se queda el cuadrado grande, que es el aparato.
        grupos: list[list[Polygon]] = []
        for pieza in _poligonos(_segmentos(msp, capa.dxf.name)):
            centro = pieza.centroid
            grupo = next((g for g in grupos
                          if g[0].centroid.distance(centro) < TOLERANCIA_SIMBOLO), None)
            (grupo.append(pieza) if grupo else grupos.append([pieza]))
        for grupo in grupos:
            # El tamaño es la caja de todo el grupo. No vale coger la pieza de más área: al
            # poligonizar dos cuadrados concéntricos, el de fuera queda como un anillo y mide
            # menos que el cuadro de dentro.
            cajas = [p.bounds for p in grupo]
            x0, y0 = min(c[0] for c in cajas), min(c[1] for c in cajas)
            x1, y1 = max(c[2] for c in cajas), max(c[3] for c in cajas)
            puestas.append({"tipo": f"Luminaria {coincide.group(2)}",
                            "posicion_m": [round((x0 + x1) / 2, 3), round((y0 + y1) / 2, 3)],
                            "tamano_m": [round(x1 - x0, 3), round(y1 - y0, 3)]})
        puestas.sort(key=lambda l: (l["posicion_m"][1], l["posicion_m"][0]))
    return puestas


def _nombre_2d(texto: str) -> tuple[str, float | None]:
    """El nombre de la sala y su potencia específica, si DIALux la ha escrito detrás."""
    if m := NOMBRE_CON_POTENCIA.match(texto):
        return m.group(1).strip(), float(m.group(2).replace(",", "."))
    if m := NOMBRE_SIN_CALCULAR.match(texto):
        return m.group(1).strip(), None
    return texto.strip(), None


def _salas_2d(msp, planta: str) -> list[tuple[Polygon, str, float | None]]:
    """Las salas de una planta, con su nombre. El contorno sale de los muros.

    Las caras estrechas se descartan con el mismo criterio que en un plano de clase (una sala mide
    más de `ANCHURA_MIN_SALA` de ancho medio): eso quita los gruesos de muro y el anillo de la
    envolvente. Medido el 3/10/2026 en el trabajo de clase: quedan 13 caras para 13 nombres.
    """
    poligonos = [c for c in caras(_segmentos(msp, f"DLX_FL{planta}_CONT"))
                 if c.area > 0.5 and _anchura_media(c) >= ANCHURA_MIN_CUARTO]
    # La envolvente del edificio también se cierra como cara, y es ancha, así que el filtro de
    # anchura no la quita: se reconoce porque dentro de ella hay otras caras.
    poligonos = [c for c in poligonos
                 if not any(c is not d and Polygon(c.exterior).contains(d.representative_point())
                            for d in poligonos)]
    etiquetas = [(t.get_placement()[1], t.dxf.text)
                 for t in msp.query(f"TEXT[layer=='DLX_FL{planta}_DESC']")]

    # **Las salas las manda el rótulo**: DIALux escribe uno por sala con su nombre, y una cara sin
    # rótulo no es una sala (en el trabajo de clase, los muros de la planta 2 son el peto de la
    # cubierta). Cada rótulo se queda con la cara más pequeña que lo contiene —si cae dentro de
    # dos, la buena es la de dentro— y si cae sobre un muro, con la más cercana que quede libre.
    salida: list[tuple[Polygon, str, float | None]] = []
    usadas: set[int] = set()
    sueltos = []
    for punto, texto in etiquetas:
        dentro = [i for i, s in enumerate(poligonos)
                  if i not in usadas and s.contains(Point(punto.x, punto.y))]
        if dentro:
            i = min(dentro, key=lambda j: poligonos[j].area)
            usadas.add(i)
            salida.append((poligonos[i], *_nombre_2d(texto)))
        else:
            sueltos.append((punto, texto))
    for punto, texto in sueltos:
        libres = [i for i in range(len(poligonos)) if i not in usadas]
        if not libres:
            continue
        i = min(libres, key=lambda j: poligonos[j].distance(Point(punto.x, punto.y)))
        usadas.add(i)
        salida.append((poligonos[i], *_nombre_2d(texto)))
    return salida


def _leer_2d(fichero: Path, doc, msp, plantas: list[str]) -> dict:
    """La variante 2D: plantas, luminarias y resultados, pero sin alturas."""
    tipos, resultados = _tablas(msp)
    salas = []
    for planta in plantas:
        luminarias = _luminarias_2d(msp, planta)
        for poligono, nombre, potencia in _salas_2d(msp, planta):
            x0, y0, x1, y1 = poligono.bounds
            dentro = [l for l in luminarias
                      if poligono.contains(Point(*l["posicion_m"]))]
            sala = {
                "nombre": nombre,
                "planta": f"Planta {planta}",
                # En 2D todo está a z = 0: la altura y el plano de trabajo no se pueden saber.
                "altura_m": None,
                "plano_trabajo_m": None,
                "vertices": len(poligono.exterior.coords) - 1,
                "contorno_m": [(round(x, 3), round(y, 3))
                               for x, y in poligono.exterior.coords[:-1]],
                "area_m2": round(poligono.area, 2),
                "ancho_x_m": round(x1 - x0, 3),
                "largo_y_m": round(y1 - y0, 3),
                "luminarias": len(dentro),
            }
            if dentro:
                sala["luminarias_colocadas"] = dentro
            if potencia is not None:
                sala["potencia_especifica_w_m2"] = potencia
            if nombre in resultados:
                sala["resultados"] = resultados[nombre]
            salas.append(sala)

    avisos = ["Esta exportación es la 2D: todo está a z = 0, así que NO trae la altura de las "
              "salas ni el plano de trabajo. Para comparar alturas hace falta exportar en 3D."]
    if not tipos:
        avisos.append("No se han entendido las tablas de resultados del DWG. Se leen por el "
                      "nombre de sus columnas en castellano; si DIALux está en otro idioma, hay "
                      "que añadir esas cabeceras en export_dialux.py.")
    return {"fichero": fichero.name, "proyecto": fichero.stem,
            "escrito_por": "DIALux evo (exportación a DWG)", "variante": "2D (sin alturas)",
            "plantas": [f"Planta {p}" for p in plantas],
            **({"luminarias_del_proyecto": tipos} if tipos else {}),
            "salas": salas, "avisos": avisos}


def leer(ruta: str | Path) -> dict:
    """Las salas de un proyecto exportado por DIALux evo, con el mismo formato que `leer_stf`.

    Acepta las dos variantes de exportación y dice en `variante` cuál ha leído.
    """
    fichero = Path(ruta).expanduser()
    doc = ezdxf.readfile(a_dxf(fichero))
    msp = doc.modelspace()

    plantas = sorted({m.group(1) for capa in doc.layers
                      if (m := PLANTA.match(capa.dxf.name) or CAPA_LUMINARIAS.match(capa.dxf.name))},
                     key=int)
    if msp.query(f"POLYLINE[layer=='{CAPA_SALAS}']"):
        return _leer_3d(fichero, doc, msp)
    if plantas:
        return _leer_2d(fichero, doc, msp, plantas)
    raise ValueError(
        f"{fichero.name} no parece un DWG exportado por DIALux evo: no tiene ni la capa "
        f"{CAPA_SALAS} (exportación 3D) ni capas DLX_FL<planta>_… (exportación 2D). Al exportar "
        "hay que dejar marcada 'Puntos y superficies de cálculo'.")
