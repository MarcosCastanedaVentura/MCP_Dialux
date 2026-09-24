"""Del plano del examen al edificio en STF, listo para importar en DIALux evo.

Junta lo que ya hay: `leer_plano` saca las salas con sus medidas y los datos del enunciado, y
`stf.escribir` los convierte en el fichero que importa DIALux.

Dos decisiones:

- **Un solo fichero, con las plantas una al lado de otra.** Tres hechos medidos en evo 14, el 20
  y el 21/9/2026: importar un segundo STF **no añade, sustituye** lo que hubiera en el proyecto;
  el STF **no guarda a qué nivel está cada sala** (probados Z, Z0, Base, BaseHeight, Level,
  Elevation, FloorHeight y Offset: las nueve salas del sondeo salieron en el suelo); y dejadas en
  su sitio real las plantas se solapan. Separándolas en X entran todas de una importación, se
  pueden seleccionar por separado y Marcos las sube a su planta dentro de DIALux.
- **Lo que el STF no lleva, se dice con números.** La zona marginal y las columnas no se han
  conseguido escribir en el STF (no hay ejemplo real del que copiar el nombre de esos campos, ver
  `stf.py`), y Marcos prefiere ponerlas a mano en DIALux antes que cambiar de versión. Así que
  salen en `a_mano`, con el valor y la posición ya calculados: la herramienta no puede meterlas,
  pero sí evitar que haya que volver al plano a buscarlas.
- **Los nombres son los del plano, salvo que se pidan genéricos.** Con `nombres_genericos` las
  salas salen como "Local 1", "Local 2"…, que es como las nombra DIALux al crearlas a mano, y el
  proyecto lleva el nombre que se le pase. El edificio y la planta no se pueden nombrar desde el
  fichero: los pone DIALux y se cambian con doble clic.
- **Lo que el plano no dice, se pide.** Si falta la altura de una sala no se escribe el fichero:
  se devuelve qué falta y para qué salas. Un edificio con una altura inventada parece correcto y
  es justo lo que no puede pasar (ver el invariante 3).
"""

from __future__ import annotations

import math
from pathlib import Path

from . import stf
from .cad.plano import leer_plano

RAIZ = Path(__file__).resolve().parents[1]
CARPETA = RAIZ / "salida"

# Hueco mínimo entre plantas dentro del mismo fichero: suficiente para verlas separadas y para
# seleccionar una entera sin pillar la de al lado. El desplazamiento final se redondea hacia
# arriba a un múltiplo de PASO, porque Marcos tiene que restarlo a mano en DIALux para llevar
# cada planta a su sitio: restar 30 es fácil y restar 28,365 es una fuente de erratas.
SEPARACION = 5.0  # m
PASO = 10.0  # m

# Alturas de puertas y ventanas: el plano no las dice nunca (el examen de enero llega a decir
# "incluir las ventanas a la altura que se quiera"), así que son valores de obra corrientes y se
# avisa de que se han usado. Se pueden cambiar al llamar.
ALTO_PUERTA = 2.1        # m
ALFEIZAR_VENTANA = 1.0   # m del suelo al borde de abajo
ALTO_VENTANA = 1.5       # m

# Con `nombres_genericos`, las salas se numeran como las nombra DIALux evo al crearlas a mano.
NOMBRE_GENERICO = "Local {n}"


def _altura(sala: dict, altura_m: float | None, alturas: dict[str, float] | None) -> float | None:
    if alturas:
        for nombre, valor in alturas.items():
            if nombre.lower() in sala["nombre"].lower():
                return valor
    return sala.get("altura_sala_m") or altura_m


def _aberturas(sala: dict, alto_puerta: float, alfeizar: float, alto_ventana: float,
               altura_sala: float) -> list[stf.Abertura]:
    salida = []
    for hueco in sala.get("aberturas", []):
        if hueco["tipo"] == "ventana":
            alto = min(alto_ventana, altura_sala - alfeizar - 0.1)
            salida.append(stf.Abertura("ventana", tuple(hueco["centro_m"]), hueco["ancho_m"],
                                       round(alto, 3), alfeizar))
        else:
            salida.append(stf.Abertura("puerta", tuple(hueco["centro_m"]), hueco["ancho_m"],
                                       min(alto_puerta, altura_sala - 0.1)))
    return salida


def plano_a_stf(ruta_plano: str | Path, altura_m: float | None = None,
                alturas: dict[str, float] | None = None,
                carpeta_destino: str | Path | None = None,
                nombres_genericos: bool = False,
                nombre_proyecto: str | None = None,
                alto_puerta_m: float = ALTO_PUERTA,
                alfeizar_ventana_m: float = ALFEIZAR_VENTANA,
                alto_ventana_m: float = ALTO_VENTANA) -> dict:
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
    numero = 1
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
            if nombres_genericos:
                nombre = NOMBRE_GENERICO.format(n=numero)
                numero += 1
            elif len(plano["plantas"]) > 1:
                # Todas llevan la planta detrás, no solo las repetidas como el ascensor: al
                # duplicar la planta en DIALux hay que borrar las salas de las otras, y con el
                # nombre delante se sabe cuáles sin ir mirándolas una a una.
                nombre = f"{nombre} [{planta['nombre'].split()[0].lower()}]"
            huecos = _aberturas(sala, alto_puerta_m, alfeizar_ventana_m, alto_ventana_m, altura)
            for hueco in huecos:
                x, y = hueco.centro_m
                hueco.centro_m = (x + desplazamiento, y)
            estancias.append(stf.Estancia(
                nombre=nombre,
                contorno=[(x + desplazamiento, y) for x, y in sala["contorno_m"]],
                altura_m=altura,
                plano_trabajo_m=plano_trabajo,
                factor_mantenimiento=sala.get("factor_mantenimiento"),
                aberturas=huecos,
            ))

        plantas.append({"nombre": planta["nombre"], "estancias": estancias,
                        "desplazada_x_m": round(desplazamiento, 3),
                        "a_mano": _a_mano(planta, alto_puerta_m, alfeizar_ventana_m,
                                          alto_ventana_m)})
        siguiente = desplazamiento + planta["exterior_ancho_x_m"] + SEPARACION
        desplazamiento = PASO * math.ceil(siguiente / PASO)

    if faltan:
        return {"fichero": plano["fichero"], "escrito": False, "faltan": sorted(set(faltan)),
                "avisos": avisos,
                "como_seguir": "Pásame esos datos (por ejemplo altura_m=3) y lo vuelvo a generar."}

    puertas = sum(1 for p in plantas for e in p["estancias"] for h in e.aberturas
                  if h.tipo == "puerta")
    ventanas = sum(1 for p in plantas for e in p["estancias"] for h in e.aberturas
                   if h.tipo == "ventana")
    if puertas or ventanas:
        avisos.append(
            f"Del plano salen {puertas} puerta(s) y {ventanas} ventana(s), y van escritas en el "
            "fichero, pero **DIALux evo no las importa** (comprobado el 22/9/2026: el formato las "
            "admite y evo las ignora). Están en 'a_mano' con su posición y su tamaño para ponerlas "
            f"en DIALux. Las alturas no las da el plano: puertas de {alto_puerta_m} m y ventanas "
            f"de {alto_ventana_m} m a {alfeizar_ventana_m} m del suelo.")

    if len(plantas) > 1:
        avisos.append(
            f"El edificio tiene {len(plantas)} plantas y van todas en el mismo fichero, una al "
            f"lado de otra con {SEPARACION:g} m de separación, porque el STF no guarda a qué "
            "nivel está cada sala. Cada planta dice cuánto se ha desplazado en 'desplazada_x_m'; "
            "colócalas en DIALux como quieras.")

    todas = [e for planta in plantas for e in planta["estancias"]]
    ruta = stf.escribir(todas, carpeta / base,
                        proyecto=nombre_proyecto or Path(ruta_plano).stem)
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
            **({"para_dejarlo_en_un_solo_edificio": [
                "El STF no sabe de plantas: al importar, todas las salas entran en la misma, una "
                "al lado de otra. Las de cada planta están juntas, a la distancia que dice "
                "'desplazada_x_m'.",
                "1. Importa el fichero y renombra la planta con el nombre de la primera.",
                "2. Crea en el mismo edificio una planta nueva por cada una de las demás.",
                "3. Selecciona las salas de una planta (son las desplazadas a la derecha), "
                "córtalas y pégalas en su planta nueva.",
                "4. Colócalas en el mismo sitio que la primera, restando su 'desplazada_x_m' a la "
                "coordenada X.",
            ]} if len(escritos) > 1 else {}),
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


def _a_mano(planta: dict, alto_puerta: float, alfeizar: float, alto_ventana: float) -> list[dict]:
    """Lo que hay que teclear en DIALux después de importar, sala por sala y con los números.

    Aquí va todo lo que el importador de evo no coge: la zona marginal, las columnas y los huecos
    de puertas y ventanas.
    """
    pendiente = []
    for sala in planta["salas"]:
        tareas = {}
        if sala.get("aberturas"):
            tareas["huecos"] = [
                {"tipo": h["tipo"], "centro_m": h["centro_m"], "ancho_m": h["ancho_m"],
                 "alto_m": alto_ventana if h["tipo"] == "ventana" else alto_puerta,
                 "alfeizar_m": alfeizar if h["tipo"] == "ventana" else 0.0,
                 "en_fachada": h["en_fachada"]}
                for h in sala["aberturas"]]
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
