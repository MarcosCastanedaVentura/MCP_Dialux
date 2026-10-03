"""Corregir un trabajo de DIALux contra la UNE-EN 12464-1, sala por sala.

Es lo que da sentido al proyecto: Marcos monta el ejercicio en DIALux, lo exporta a DWG y aquí se
contrasta lo que ha salido con lo que la norma exige para cada local. Lo que se compara sale de
las **tablas de resultados que DIALux escribe dentro del DWG** (iluminancia mínima, máxima, media
y uniformidad), no de ningún cálculo propio, así que corregir no depende de tener la fotometría.

Dos cosas que este módulo NO hace, a propósito:

- **No elige la fila de la norma.** El local lo decide Marcos: el mismo nombre de sala puede ser
  varias filas, y una fila mal elegida da una corrección mal hecha que parece bien. Si no se le
  pasa la referencia, se buscan candidatas por el nombre y se le preguntan.
- **No decide entre Ēm requerido y Ēm modificado.** La norma da los dos y en clase no está
  decidido cuál se usa, así que se dicen los dos y cuál se cumple. Con `usar` se puede forzar uno.

Lo que no se puede comprobar con esto, y se dice en cada sala: Ra, RUGL (deslumbramiento) y las
iluminancias de paredes, techo y zona circundante. DIALux las calcula, pero no las escribe en las
tablas de la exportación a DWG; para eso hay que mirar su informe.
"""

from __future__ import annotations

from pathlib import Path

from . import norma
from .export_dialux import leer

# Margen al comparar: las tablas del DWG vienen redondeadas (596 lx, 0.53), así que exigir el
# valor exacto sería inventar precisión. Un 1 % no cambia ningún veredicto de verdad.
MARGEN = 0.01


def _referencia(nombre: str, referencias: dict[str, str] | None) -> str | None:
    if not referencias:
        return None
    for clave, valor in referencias.items():
        if clave.lower() in nombre.lower() or nombre.lower() in clave.lower():
            return valor
    return None


def _candidatas(nombre: str) -> list[dict]:
    """Filas de la norma que podrían ser esa sala, buscando por su nombre.

    Se quitan los números del nombre antes de buscar: DIALux numera las salas ("Aula 1", "Baño
    2") y `buscar` pide que aparezcan todas las palabras, así que con el número no encontraba
    nada. Son candidatas para preguntar, nunca una elección.
    """
    palabras = [p for p in nombre.split() if not p.strip(".,").isdigit()]
    return norma.buscar(" ".join(palabras)) if palabras else []


def _flujo(sala: dict, tipos: list[dict]) -> tuple[float | None, float | None]:
    """(flujo de una luminaria, factor de degradación) del tipo que hay en esa sala."""
    puestas = sala.get("luminarias_colocadas") or []
    if not puestas or not tipos:
        return None, None
    indice = puestas[0]["tipo"].split()[-1]
    tipo = next((t for t in tipos if str(t.get("indice")) == indice), tipos[0])
    return tipo.get("flujo_lm"), tipo.get("factor_degradacion")


def _cumple(medido: float | None, exigido: float | None) -> bool | None:
    if medido is None or exigido is None:
        return None
    return medido >= exigido * (1 - MARGEN)


def corregir(ruta: str | Path, referencias: dict[str, str] | None = None,
             usar: str | None = None) -> dict:
    """Compara los resultados de un trabajo exportado de DIALux con lo que exige la norma.

    `referencias`: la fila de la norma de cada sala, por nombre, p. ej. {"Aula 1": "44.1"}.
    `usar`: "requerido" o "modificado" para quedarse con uno de los dos Ēm; por defecto, los dos.
    """
    if Path(ruta).suffix.lower() == ".stf":
        raise ValueError(
            "Un STF no se puede corregir: no lleva resultados, solo el edificio. Para corregir "
            "hace falta el cálculo de DIALux: ábrelo, calcula y exporta a DWG (Exportar → "
            "Exportar en un archivo nuevo), que ahí van las tablas de resultados.")
    proyecto = leer(ruta)
    tipos = proyecto.get("luminarias_del_proyecto", [])
    salas, sin_referencia, sin_calcular = [], [], []

    for sala in proyecto["salas"]:
        resultados = sala.get("resultados") or {}
        em = resultados.get("e_media_lx")
        nombre = sala["nombre"]

        # Una sala sin luminarias no se corrige aunque DIALux le dé una iluminancia: los 0,37 lx
        # del pasillo del trabajo de clase son luz que se cuela del aula de al lado, no alumbrado.
        if not resultados or not em or not sala["luminarias"]:
            sin_calcular.append({
                "sala": nombre, "planta": sala.get("planta"),
                "luminarias": sala["luminarias"],
                "por_que": ("no tiene luminarias" if not sala["luminarias"]
                            else "DIALux no da iluminancia: está sin calcular"),
                **({"e_media_lx": em, "ojo": "esa iluminancia es luz que entra de otra sala"}
                   if em and not sala["luminarias"] else {}),
            })
            continue

        referencia = _referencia(nombre, referencias)
        if referencia is None:
            candidatas = _candidatas(nombre)
            sin_referencia.append({
                "sala": nombre, "planta": sala.get("planta"),
                "medido": {"e_media_lx": em, "u0": resultados.get("u0")},
                "candidatas": [{"referencia": c["referencia"], "tipo_de_area": c["tipo_de_area"]}
                               for c in candidatas[:6]],
                "que_hace_falta": "Dime de qué fila de la norma es esta sala y la corrijo. No la "
                                  "elijo yo: el nombre de la sala no dice la actividad.",
            })
            continue

        exigido = norma.requisitos(referencia)
        if "error" in exigido:
            sin_referencia.append({"sala": nombre, "referencia": referencia,
                                   "que_hace_falta": exigido["error"]})
            continue

        em_requerido = exigido.get("Em_requerido_lx")
        em_modificado = exigido.get("Em_modificado_lx")
        objetivos = {"requerido": em_requerido, "modificado": em_modificado}
        if usar in ("requerido", "modificado"):
            objetivos = {usar: objetivos[usar]}

        bien, mal = [], []
        falla_modificado = False
        for cual, valor in objetivos.items():
            if (pasa := _cumple(em, valor)) is None:
                continue
            frase = f"Ēm {cual}: {em:g} lx de {valor:g} lx"
            (bien if pasa else mal).append(frase)
            falla_modificado = falla_modificado or (not pasa and cual == "modificado")
        if (pasa := _cumple(resultados.get("u0"), exigido.get("Uo"))) is not None:
            frase = f"U0: {resultados['u0']:g} de {exigido['Uo']:g}"
            (bien if pasa else mal).append(frase)

        # Fallar solo el Ēm modificado no es suspender: la norma da los dos valores y en clase no
        # está decidido cuál se usa (ver CLAUDE.md), así que se dice y se deja la decisión.
        graves = [f for f in mal if "modificado" not in f]
        if graves:
            veredicto = "NO cumple: " + "; ".join(graves)
        elif falla_modificado:
            veredicto = ("Cumple el Ēm requerido, pero no el modificado. Cuál de los dos piden en "
                         "clase está sin decidir: si es el modificado, no llega.")
        else:
            veredicto = "Cumple lo que se puede comprobar aquí"

        salas.append({
            "sala": nombre,
            "planta": sala.get("planta"),
            "referencia": referencia,
            "tipo_de_area": exigido.get("tipo_de_area"),
            "area_m2": sala.get("area_m2"),
            "luminarias": sala["luminarias"],
            "medido": {k: v for k, v in {
                "e_media_lx": em, "e_min_lx": resultados.get("e_min_lx"),
                "e_max_lx": resultados.get("e_max_lx"), "u0": resultados.get("u0"),
                "potencia_especifica_w_m2": sala.get("potencia_especifica_w_m2"),
            }.items() if v is not None},
            "exigido": {k: v for k, v in {
                "Em_requerido_lx": em_requerido, "Em_modificado_lx": em_modificado,
                "Uo": exigido.get("Uo"), "Ra": exigido.get("Ra"), "RUGL": exigido.get("RUGL"),
            }.items() if v is not None},
            "cumple": bien,
            "no_cumple": mal,
            "sin_comprobar": ["Ra", "RUGL (deslumbramiento)", "Ēm de paredes, techo y zona "
                              "circundante"],
            "veredicto": veredicto,
            "fuente": exigido.get("fuente"),
            **({"rendimiento_del_local_implicito": _rendimiento(sala, em, tipos)}
               if _rendimiento(sala, em, tipos) else {}),
        })

    return {
        "fichero": proyecto["fichero"],
        "variante": proyecto.get("variante"),
        **({"plantas": proyecto["plantas"]} if proyecto.get("plantas") else {}),
        **({"luminarias_del_proyecto": tipos} if tipos else {}),
        "corregidas": salas,
        **({"sin_referencia_de_norma": sin_referencia} if sin_referencia else {}),
        **({"sin_calcular": sin_calcular} if sin_calcular else {}),
        "no_se_comprueba_aqui": "Ra, RUGL y las iluminancias de paredes, techo y zona "
                                "circundante: DIALux las calcula pero no las escribe en las "
                                "tablas del DWG. Para esas, su informe.",
        "resumen": (f"{sum(1 for s in salas if not s['veredicto'].startswith('NO'))} sala(s) "
                    f"cumplen, {sum(1 for s in salas if s['veredicto'].startswith('NO'))} no, "
                    f"{len(sin_referencia)} sin fila de la norma y "
                    f"{len(sin_calcular)} sin calcular en DIALux."),
    }


def _rendimiento(sala: dict, em: float, tipos: list[dict]) -> float | None:
    """El rendimiento del local que se deduce del propio resultado de DIALux.

    De Ēm = n·Φ·FM·η / S sale η. No es un dato de catálogo: es lo que ha salido en ESTA sala con
    ESTA luminaria, y sirve para comprobar el orden de magnitud de un cálculo por el método de los
    lúmenes mientras no haya fotometría (.ldt o .ies).
    """
    flujo, degradacion = _flujo(sala, tipos)
    cuantas, area = sala.get("luminarias"), sala.get("area_m2")
    if not (flujo and degradacion and cuantas and area):
        return None
    return round(em * area / (cuantas * flujo * degradacion), 3)
