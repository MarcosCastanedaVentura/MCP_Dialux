"""Del plano del examen al edificio en STF, listo para importar en DIALux evo.

Junta lo que ya hay: `leer_plano` saca las salas con sus medidas y los datos del enunciado, y
`stf.escribir` los convierte en el fichero que importa DIALux.

Dos decisiones:

- **Un fichero por planta.** STF no tiene el concepto de planta y `leer_plano` da las coordenadas
  de cada planta desde su propia esquina, así que meter dos plantas en el mismo fichero las
  pondría una encima de otra en el mismo suelo. En DIALux se importa cada una por separado.
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
            if sala.get("obstaculos"):
                avisos.append(f"{sala['nombre']}: tiene {len(sala['obstaculos'])} columna(s) que "
                              "el STF todavía no lleva. Hay que ponerlas a mano en DIALux.")
            estancias.append(stf.Estancia(
                nombre=sala["nombre"],
                contorno=[tuple(p) for p in sala["contorno_m"]],
                altura_m=altura,
                plano_trabajo_m=plano_trabajo,
                factor_mantenimiento=sala.get("factor_mantenimiento"),
            ))

        plantas.append({"nombre": planta["nombre"], "estancias": estancias,
                        "salas": [s["nombre"] for s in planta["salas"]]})

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
            "estancias": [{"nombre": e.nombre, "altura_m": e.altura_m,
                           "plano_trabajo_m": e.plano_trabajo_m,
                           "vertices": len(e.contorno)} for e in planta["estancias"]],
        })

    return {"fichero": plano["fichero"], "escrito": True, "plantas": escritos,
            "cotas": plano["cotas"]["cuadran"], "avisos": avisos,
            "como_importar": "En DIALux evo: Archivo → Importar → Archivo STF…, un fichero por "
                             "planta. El edificio y la planta los nombra DIALux ('STF Building'): "
                             "se renombran con doble clic."}
