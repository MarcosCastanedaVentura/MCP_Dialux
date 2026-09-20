"""Del plano del examen al edificio en STF, listo para importar en DIALux evo.

Junta lo que ya hay: `leer_plano` saca las salas con sus medidas y los datos del enunciado, y
`stf.escribir` los convierte en el fichero que importa DIALux.

Dos decisiones:

- **Un solo fichero, con las plantas una al lado de otra.** Dos hechos medidos el 20/9/2026 en
  evo 14 obligan a esto: importar un segundo STF **no añade, sustituye** lo que hubiera en el
  proyecto (así que un fichero por planta = una planta por proyecto), y el STF **no guarda a qué
  nivel está cada sala**, así que si se dejan en su sitio real las plantas se solapan en el
  suelo. Separándolas en X entran todas de una importación y Marcos las coloca en DIALux.
- **Lo que el STF no lleva, se dice con números.** La zona marginal y las columnas no se han
  conseguido escribir en el STF (no hay ejemplo real del que copiar el nombre de esos campos, ver
  `stf.py`), y Marcos prefiere ponerlas a mano en DIALux antes que cambiar de versión. Así que
  salen en `a_mano`, con el valor y la posición ya calculados: la herramienta no puede meterlas,
  pero sí evitar que haya que volver al plano a buscarlas.
- **Lo que el plano no dice, se pide.** Si falta la altura de una sala no se escribe el fichero:
  se devuelve qué falta y para qué salas. Un edificio con una altura inventada parece correcto y
  es justo lo que no puede pasar (ver el invariante 3).
"""

from __future__ import annotations

from pathlib import Path

from . import stf
from .cad.plano import leer_plano

RAIZ = Path(__file__).resolve().parents[1]
CARPETA = RAIZ / "salida"

# Hueco entre plantas dentro del mismo fichero: suficiente para verlas separadas y para
# seleccionar una entera sin pillar la de al lado.
SEPARACION = 5.0  # m


def _altura(sala: dict, altura_m: float | None, alturas: dict[str, float] | None) -> float | None:
    if alturas:
        for nombre, valor in alturas.items():
            if nombre.lower() in sala["nombre"].lower():
                return valor
    return sala.get("altura_sala_m") or altura_m


def plano_a_stf(ruta_plano: str | Path, altura_m: float | None = None,
                alturas: dict[str, float] | None = None,
                carpeta_destino: str | Path | None = None) -> dict:
    """Construye el edificio del plano y escribe UN fichero STF con todas sus plantas."""
    plano = leer_plano(ruta_plano)
    carpeta = Path(carpeta_destino) if carpeta_destino else CARPETA
    base = Path(ruta_plano).stem

    faltan: list[str] = []
    avisos: list[str] = list(plano["avisos"])
    if not plano["cotas"]["detalle"]:
        avisos.append("El plano no trae cotas, así que las medidas no se han podido comprobar "
                      "contra nada. Revísalas en DIALux antes de fiarte.")
    elif plano["cotas"]["cuadran"].split(" de ")[0] == "0":
        avisos.append("Ninguna cota del plano cuadra con las salas reconstruidas: NO uses este "
                      "edificio sin mirarlo, puede estar mal leído.")

    repetidos = _nombres_repetidos(plano["plantas"])
    plantas = []
    desplazamiento = 0.0
    for planta in plano["plantas"]:
        estancias = []
        for sala in planta["salas"]:
            altura = _altura(sala, altura_m, alturas)
            if not altura:
                faltan.append(f"{planta['nombre']} / {sala['nombre']}: altura de la sala")
                continue
            plano_trabajo = sala.get("altura_plano_trabajo_m")
            if plano_trabajo is None:
                plano_trabajo = 0.0
                avisos.append(f"{sala['nombre']}: el plano no da altura del plano de trabajo; "
                              "se deja en el suelo (0 m).")
            nombre = sala["nombre"]
            if nombre in repetidos:
                # "Ascensor" está en las dos plantas: sin esto habría dos salas iguales en la lista.
                nombre = f"{nombre} ({planta['nombre'].lower()})"
            estancias.append(stf.Estancia(
                nombre=nombre,
                contorno=[(x + desplazamiento, y) for x, y in sala["contorno_m"]],
                altura_m=altura,
                plano_trabajo_m=plano_trabajo,
                factor_mantenimiento=sala.get("factor_mantenimiento"),
            ))

        plantas.append({"nombre": planta["nombre"], "estancias": estancias,
                        "desplazada_x_m": round(desplazamiento, 3),
                        "a_mano": _a_mano(planta)})
        desplazamiento += planta["exterior_ancho_x_m"] + SEPARACION

    if faltan:
        return {"fichero": plano["fichero"], "escrito": False, "faltan": sorted(set(faltan)),
                "avisos": avisos,
                "como_seguir": "Pásame esos datos (por ejemplo altura_m=3) y lo vuelvo a generar."}

    if len(plantas) > 1:
        avisos.append(
            f"El edificio tiene {len(plantas)} plantas y van todas en el mismo fichero, una al "
            f"lado de otra con {SEPARACION:g} m de separación, porque el STF no guarda a qué "
            "nivel está cada sala. Cada planta dice cuánto se ha desplazado en 'desplazada_x_m'; "
            "colócalas en DIALux como quieras.")

    todas = [e for planta in plantas for e in planta["estancias"]]
    ruta = stf.escribir(todas, carpeta / base, proyecto=Path(ruta_plano).stem)
    escritos = [{
        "planta": planta["nombre"],
        "desplazada_x_m": planta["desplazada_x_m"],
        **({"a_mano": planta["a_mano"]} if planta["a_mano"] else {}),
        "estancias": [{"nombre": e.nombre, "altura_m": e.altura_m,
                       "plano_trabajo_m": e.plano_trabajo_m,
                       "vertices": len(e.contorno)} for e in planta["estancias"]],
    } for planta in plantas if planta["estancias"]]

    return {"fichero": plano["fichero"], "escrito": True, "ruta_stf": str(ruta),
            "plantas": escritos,
            "cotas": plano["cotas"]["cuadran"], "avisos": avisos,
            "como_importar": "En DIALux evo: Archivo → Importar → Archivo STF…, y se elige ESTE "
                             "único fichero. Importar un segundo STF no añade nada: sustituye lo "
                             "que hubiera en el proyecto. El edificio y la planta los nombra "
                             "DIALux ('STF Building'): se renombran con doble clic.",
            "que_falta_por_poner": "Lo de 'a_mano' NO va dentro del STF: la zona marginal se pone "
                                   "en la superficie de cálculo de cada sala, y las columnas como "
                                   "objeto en la posición indicada (su centro, en metros desde la "
                                   "esquina de la planta)."}


def _nombres_repetidos(plantas: list[dict]) -> set[str]:
    """Nombres de sala que se repiten en varias plantas, como el ascensor del examen de junio."""
    vistos: set[str] = set()
    repetidos: set[str] = set()
    for planta in plantas:
        for sala in planta["salas"]:
            (repetidos if sala["nombre"] in vistos else vistos).add(sala["nombre"])
    return repetidos


def _a_mano(planta: dict) -> list[dict]:
    """Lo que hay que teclear en DIALux después de importar, sala por sala y con los números."""
    pendiente = []
    for sala in planta["salas"]:
        tareas = {}
        if sala.get("zona_marginal_m"):
            tareas["zona_marginal_m"] = sala["zona_marginal_m"]
        if sala.get("obstaculos"):
            tareas["columnas"] = [
                {"centro_m": o["centro_m"], "ancho_x_m": o["ancho_x_m"],
                 "largo_y_m": o["largo_y_m"], "alto_m": "hasta el techo"}
                for o in sala["obstaculos"]]
        if tareas:
            pendiente.append({"sala": sala["nombre"], **tareas})
    return pendiente
