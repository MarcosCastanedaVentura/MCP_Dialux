"""leer_plano: de un DWG/DXF de clase a las salas con sus medidas y los datos del enunciado."""

from __future__ import annotations

from pathlib import Path

import ezdxf
from shapely import Point, Polygon
from shapely.affinity import scale as escalar

from . import enunciado as en
from .convertir import a_dxf
from .geometria import aberturas, caras, huecos, salas_y_plantas, tramos

# $INSUNITS de AutoCAD -> metros por unidad de dibujo.
UNIDADES = {4: 0.001, 5: 0.01, 6: 1.0}

# Las cotas del plano se escriben con dos decimales: 9,44 cubre de 9,435 a 9,445.
TOLERANCIA_COTA = 0.006  # m

# Una pared que queda a menos de esto del borde exterior de la planta es fachada. Es medio grueso
# de muro: los muros más gruesos de los exámenes son de 0,59 m.
MARGEN_FACHADA = 0.35  # m

# En fachada, un hueco más estrecho que esto es la puerta de entrada y no una ventana. Medido en
# los exámenes y en el plano de ejemplo: las puertas van de 0,9 a 1,5 m y las ventanas de 1,98 a
# 2,08 m. Hacia dentro del edificio no se usa: ahí todo hueco es un paso entre salas.
ANCHO_MAX_PUERTA = 1.6  # m

DATOS_PARA_CALCULAR = {
    "altura_sala_m": "altura de la sala",
    "altura_plano_trabajo_m": "altura del plano de trabajo",
    "zona_marginal_m": "zona marginal",
    "factor_mantenimiento": "factor de mantenimiento",
    "referencia_norma": "tipo de actividad según la UNE-EN 12464-1",
}


def _textos(msp, factor: float) -> list[en.Texto]:
    salida = []
    for e in msp.query("TEXT MTEXT"):
        if e.dxftype() == "TEXT":
            punto, contenido, altura = e.get_placement()[1], e.dxf.text, e.dxf.height
        else:
            punto, contenido, altura = e.dxf.insert, e.plain_text(), e.dxf.char_height
        if contenido.strip():
            salida.append(en.Texto(punto.x * factor, punto.y * factor, altura * factor, contenido))
    return salida


def _r(valor: float) -> float:
    return round(valor, 3)


def _medidas(poligono: Polygon) -> tuple[float, float]:
    x0, y0, x1, y1 = poligono.bounds
    return x1 - x0, y1 - y0


def leer_plano(ruta: str | Path) -> dict:
    dxf = a_dxf(ruta)
    doc = ezdxf.readfile(dxf)
    msp = doc.modelspace()
    avisos: list[str] = []

    codigo_unidades = doc.header.get("$INSUNITS", 0)
    factor = UNIDADES.get(codigo_unidades)
    if factor is None:
        factor = 1.0
        avisos.append(f"El plano no declara unidades conocidas ($INSUNITS={codigo_unidades}): "
                      "se suponen metros. Comprueba que las medidas cuadran con las cotas.")

    dibujo = tramos(msp)
    poligonos = [escalar(p, factor, factor, origin=(0, 0)) for p in caras(dibujo)]
    cierres = [escalar(c, factor, factor, origin=(0, 0)) for c in huecos(dibujo)]
    salas, plantas = salas_y_plantas(poligonos)
    textos = _textos(msp, factor)

    # Cada texto va a la sala que lo contiene; los de fuera se agrupan en párrafos.
    textos_de: dict[int, list[en.Texto]] = {i: [] for i in range(len(salas))}
    sueltos = []
    for t in textos:
        dentro = next((i for i, s in enumerate(salas) if s.contains(Point(t.x, t.y))), None)
        (textos_de[dentro] if dentro is not None else sueltos).append(t)

    datos_sala = {i: en.interpretar(ts) for i, ts in textos_de.items()}
    nombre = {i: d.get("uso") or (en.lineas(textos_de[i]) or [f"Sala {i + 1}"])[0]
              for i, d in datos_sala.items()}

    generales: dict[int, list[en.Texto]] = {j: [] for j in range(len(plantas))}
    for bloque in en.bloques(sueltos):
        if objetivo := en.destinatario(bloque):
            raiz = objetivo[:4]
            elegida = next((i for i in nombre if raiz in en.normalizar(nombre[i])), None)
            if elegida is not None:
                extra = en.interpretar(bloque[1:])
                datos_sala[elegida] = {**extra, **datos_sala[elegida]}
                continue
        punto = Point(bloque[0].x, bloque[0].y)
        cercana = min(range(len(plantas)), key=lambda j: plantas[j].distance(punto))
        generales[cercana].extend(bloque)

    resultado_plantas = []
    for j, contorno in enumerate(plantas):
        x0, y0 = contorno.bounds[:2]
        propios = generales[j]
        nombre_planta = next((t.contenido.strip() for t in propios if "planta" in en.normalizar(t.contenido)),
                             f"Planta {j + 1}")
        comun = en.interpretar([t for t in propios if "planta" not in en.normalizar(t.contenido)])
        ancho, largo = _medidas(contorno)

        lista_salas = []
        for i, sala in enumerate(salas):
            if not contorno.contains(sala.representative_point()):
                continue
            datos = dict(datos_sala[i])
            heredados = [k for k in DATOS_PARA_CALCULAR if k in comun and k not in datos
                         and k != "referencia_norma"]
            for k in heredados:
                datos[k] = comun[k]

            w, h = _medidas(sala)
            huecos_sala = _aberturas(sala, cierres, contorno, x0, y0, textos)
            entrada = {
                "nombre": nombre[i],
                **{k: v for k, v in datos.items() if k != "notas"},
                "area_m2": round(sala.area, 2),
                "ancho_x_m": _r(w),
                "largo_y_m": _r(h),
                # Sobre el contorno exterior: la columna de Archivos no la hace menos rectangular.
                "rectangular": abs(Polygon(sala.exterior).area - w * h) < 0.01,
                "contorno_m": [(_r(x - x0), _r(y - y0)) for x, y in list(sala.exterior.coords)[:-1]],
                "obstaculos": [
                    {"ancho_x_m": _r(_medidas(Polygon(o))[0]), "largo_y_m": _r(_medidas(Polygon(o))[1]),
                     "centro_m": (_r(Polygon(o).centroid.x - x0), _r(Polygon(o).centroid.y - y0))}
                    for o in sala.interiors
                ],
                **({"aberturas": huecos_sala} if huecos_sala else {}),
            }
            if heredados:
                entrada["datos_del_enunciado_general"] = heredados
            if datos.get("notas"):
                entrada["notas"] = datos["notas"]
            if not datos.get("no_iluminar"):
                faltan = [txt for k, txt in DATOS_PARA_CALCULAR.items() if k not in datos]
                if faltan:
                    entrada["faltan"] = faltan
            lista_salas.append(entrada)

        resultado_plantas.append({
            "nombre": nombre_planta,
            "exterior_ancho_x_m": _r(ancho),
            "exterior_largo_y_m": _r(largo),
            "salas": sorted(lista_salas, key=lambda s: -s["area_m2"]),
            **({"notas": comun["notas"]} if comun.get("notas") else {}),
        })

    return {
        "fichero": Path(ruta).name,
        "plantas": resultado_plantas,
        "cotas": _comprobar_cotas(msp, factor, resultado_plantas),
        "avisos": avisos,
    }


def _aberturas(sala, cierres, contorno_planta, x0: float, y0: float,
               textos: list[en.Texto]) -> list[dict]:
    """Puertas y ventanas de una sala, sacadas de los huecos que quedaron en sus muros.

    Qué es cada una no lo dice el plano, así que se deduce: un hueco en una pared que da al
    exterior del edificio es una ventana, salvo que sea estrecho, que entonces es la puerta de
    entrada; hacia dentro, todo hueco es un paso entre salas. Si hay un texto al lado que dice
    "ventana" o "puerta", manda el texto.
    """
    borde = contorno_planta.exterior
    salida = []
    for hueco in aberturas(sala, cierres):
        x, y = hueco["centro"]
        punto = Point(x, y)
        etiqueta = next((en.normalizar(t.contenido) for t in textos
                         if punto.distance(Point(t.x, t.y)) < 2.0
                         and ("ventana" in en.normalizar(t.contenido)
                              or "puerta" in en.normalizar(t.contenido))), "")
        if "ventana" in etiqueta:
            tipo = "ventana"
        elif "puerta" in etiqueta:
            tipo = "puerta"
        elif borde.distance(punto) <= MARGEN_FACHADA:
            tipo = "puerta" if hueco["ancho_m"] <= ANCHO_MAX_PUERTA else "ventana"
        else:
            tipo = "puerta"
        salida.append({"tipo": tipo, "pared": hueco["pared"], "ancho_m": hueco["ancho_m"],
                       "centro_m": (_r(x - x0), _r(y - y0)),
                       "en_fachada": borde.distance(punto) <= MARGEN_FACHADA})
    return salida


def _comprobar_cotas(msp, factor: float, plantas: list[dict]) -> dict:
    """Cada cota del plano, y qué medida reconstruida la explica.

    Es la comprobación de que las salas salieron bien: si ninguna medida cuadra con una cota,
    algo del contorno está mal y no hay que fiarse de las superficies.
    """
    medidas = []
    for p in plantas:
        medidas += [(p["exterior_ancho_x_m"], f"{p['nombre']}: ancho exterior"),
                    (p["exterior_largo_y_m"], f"{p['nombre']}: largo exterior")]
        for s in p["salas"]:
            medidas += [(s["ancho_x_m"], f"{p['nombre']} / {s['nombre']}: ancho"),
                        (s["largo_y_m"], f"{p['nombre']} / {s['nombre']}: largo")]

    lista = []
    for cota in msp.query("DIMENSION"):
        try:
            valor = cota.get_measurement() * factor
        except Exception:
            continue
        explica = [q for v, q in medidas if abs(v - valor) <= TOLERANCIA_COTA]
        lista.append({"cota_m": round(valor, 2), "coincide_con": explica})
    cuadran = sum(1 for c in lista if c["coincide_con"])
    return {"cuadran": f"{cuadran} de {len(lista)}", "detalle": lista}
