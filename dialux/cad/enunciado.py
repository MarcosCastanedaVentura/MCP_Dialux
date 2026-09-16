"""Los datos del ejercicio, leídos de los textos que la profesora escribe dentro del plano.

Solo se convierte a número lo que se reconoce sin ambigüedad. Todo lo demás se devuelve como nota
con el texto original: es preferible que el modelo lea "Incluir las ventanas a la altura que se
quiera" a que este código adivine qué significa.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass
class Texto:
    x: float
    y: float
    altura: float
    contenido: str


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar ("Baños" y "banos" son lo mismo)."""
    sin_tildes = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sin_tildes if not unicodedata.combining(c)).lower().strip()


def _numero(texto: str) -> float:
    return float(texto.replace(",", "."))


NUM = r"(\d+(?:[.,]\d+)?)"

# (clave, patrón). El patrón se aplica sobre el texto normalizado de UNA línea.
PARAMETROS = [
    ("altura_sala_m", rf"altura de (?:la )?sala:?\s*{NUM}\s*m"),
    ("espesor_pared_m", rf"espesor de (?:la )?pared:?\s*{NUM}\s*m"),
    ("altura_plano_trabajo_m", rf"altura (?:del )?plano (?:de )?trabajo:?\s*{NUM}"),
    ("zona_marginal_m", rf"zona marginal:?\s*{NUM}"),
    ("factor_mantenimiento", rf"factor de mantenimiento:?\s*{NUM}"),
]

# "34.2 Oficina (escritura…)": la referencia de la tabla de la UNE-EN 12464-1 va delante del uso.
USO_CON_REFERENCIA = re.compile(r"^(\d+(?:\.\d+){1,2})\s+(.+)$")
# "…cumpla la normativa de la zona frente al ascensor: 9.4": la referencia va al final.
REFERENCIA_AL_FINAL = re.compile(r"normativa de (?:la |el )?(.+?):\s*(\d+(?:\.\d+){1,2})\s*$", re.I)


def lineas(textos: list[Texto]) -> list[str]:
    return [linea.strip() for t in textos for linea in t.contenido.splitlines() if linea.strip()]


def interpretar(textos: list[Texto]) -> dict:
    """Parámetros reconocidos, uso con su referencia de la norma y notas sin interpretar."""
    datos: dict = {}
    notas: list[str] = []
    for linea in lineas(textos):
        plana = normalizar(linea)
        reconocida = False

        for clave, patron in PARAMETROS:
            if m := re.search(patron, plana):
                datos[clave] = _numero(m.group(1))
                reconocida = True
        if "espesor de pared" in plana and "variable" in plana:
            datos["espesor_pared_m"] = "variable"

        if m := USO_CON_REFERENCIA.match(linea):
            datos["referencia_norma"] = m.group(1)
            datos["uso"] = m.group(2).strip()
            reconocida = True
        elif m := REFERENCIA_AL_FINAL.search(linea):
            datos["referencia_norma"] = m.group(2)
            datos.setdefault("uso", m.group(1).strip())
            notas.append(linea)
            reconocida = True
        elif plana.startswith("sala para"):
            datos.setdefault("uso", linea)
            reconocida = True

        if "no iluminar" in plana:
            datos["no_iluminar"] = True

        # Aunque se reconozca un número, una línea con más contenido se guarda también como nota
        # ("Altura de sala 3 m / espesor de pared: variable").
        if not reconocida or "/" in linea:
            notas.append(linea)

    if notas:
        datos["notas"] = list(dict.fromkeys(notas))
    return datos


def bloques(textos: list[Texto]) -> list[list[Texto]]:
    """Agrupa líneas sueltas en párrafos: centradas en la misma vertical y una debajo de otra.

    En el examen de junio los datos de los baños están fuera del plano, en cuatro TEXT separados
    bajo "Sobre los baños", a 0,8 m uno de otro con letra de 0,3 m.
    """
    pendientes = sorted(textos, key=lambda t: -t.y)
    grupos: list[list[Texto]] = []
    for t in pendientes:
        for grupo in grupos:
            ultimo = grupo[-1]
            if abs(ultimo.x - t.x) <= 1.5 and 0 < ultimo.y - t.y <= 3.5 * max(ultimo.altura, t.altura):
                grupo.append(t)
                break
        else:
            grupos.append([t])
    return grupos


def destinatario(bloque: list[Texto]) -> str | None:
    """"Sobre los baños" -> "banos": el bloque habla de la sala cuyo nombre lleva esa palabra."""
    m = re.match(r"sobre (?:el|la|los|las)\s+(.+)$", normalizar(bloque[0].contenido))
    return m.group(1) if m else None
