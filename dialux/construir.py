"""Del plano del examen al edificio en STF, listo para importar en DIALux evo.

Junta lo que ya hay: `leer_plano` saca las salas con sus medidas y los datos del enunciado, y
`stf.escribir` los convierte en el fichero que importa DIALux.

Dos decisiones:

- **Un fichero por planta.** STF no tiene el concepto de planta y `leer_plano` da las coordenadas
  de cada planta desde su propia esquina, así que meter dos plantas en el mismo fichero las
  pondría una encima de otra en el mismo suelo. En DIALux se importa cada una por separado.
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


def _altura(sala: dict, altura_m: float | None, alturas: dict[str, float] | None) -> float | None:
    if alturas:
        for nombre, valor in alturas.items():
            if nombre.lower() in sala["nombre"].lower():
                return valor
    return sala.get("altura_sala_m") or altura_m


def plano_a_stf(ruta_plano: str | Path, altura_m: float | None = None,
                alturas: dict[str, float] | None = None,
                carpeta_destino: str | Path | None = None) -> dict:
    """Construye el edificio del plano y escribe un STF por planta."""
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

    plantas = []
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
            estancias.append(stf.Estancia(
                nombre=sala["nombre"],
                contorno=[tuple(p) for p in sala["contorno_m"]],
                altura_m=altura,
                plano_trabajo_m=plano_trabajo,
                factor_mantenimiento=sala.get("factor_mantenimiento"),
            ))

        plantas.append({"nombre": planta["nombre"], "estancias": estancias,
                        "a_mano": _a_mano(planta)})

    if faltan:
        return {"fichero": plano["fichero"], "escrito": False, "faltan": sorted(set(faltan)),
                "avisos": avisos,
                "como_seguir": "Pásame esos datos (por ejemplo altura_m=3) y lo vuelvo a generar."}

    escritos = []
    for i, planta in enumerate(plantas, start=1):
        if not planta["estancias"]:
            continue
        sufijo = f"-{i}" if len(plantas) > 1 else ""
        ruta = stf.escribir(planta["estancias"], carpeta / f"{base}{sufijo}",
                            proyecto=planta["nombre"])
        escritos.append({
            "planta": planta["nombre"],
            "ruta_stf": str(ruta),
            **({"a_mano": planta["a_mano"]} if planta["a_mano"] else {}),
            "estancias": [{"nombre": e.nombre, "altura_m": e.altura_m,
                           "plano_trabajo_m": e.plano_trabajo_m,
                           "vertices": len(e.contorno)} for e in planta["estancias"]],
        })

    return {"fichero": plano["fichero"], "escrito": True, "plantas": escritos,
            "cotas": plano["cotas"]["cuadran"], "avisos": avisos,
            "como_importar": "En DIALux evo: Archivo → Importar → Archivo STF…, un fichero por "
                             "planta. El edificio y la planta los nombra DIALux ('STF Building'): "
                             "se renombran con doble clic.",
            "que_falta_por_poner": "Lo de 'a_mano' NO va dentro del STF: la zona marginal se pone "
                                   "en la superficie de cálculo de cada sala, y las columnas como "
                                   "objeto en la posición indicada (su centro, en metros desde la "
                                   "esquina de la planta)."}


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
