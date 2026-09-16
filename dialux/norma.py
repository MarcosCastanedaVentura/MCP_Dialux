"""Requisitos de la UNE-EN 12464-1:2022 leídos de la copia de la norma de Marcos.

Los valores no se escriben a mano en ningún sitio: se leen del PDF (licencia de la UPM, uso
interno) y se guardan en `cache/norma/`, que no entra en git. Cada fila devuelve la tabla y la
página de donde sale, para poder comprobarla contra el papel.

Las columnas no están en la misma posición en todas las tablas, así que se localizan en la
cabecera de cada tabla (Ēm "requerido"/"modificado", Uo, Ra, RUGL y los tres "lx" de Ēm,z,
Ēm,pared y Ēm,techo), y cada celda va a la columna más cercana.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pdfplumber

from dialux.cad.enunciado import normalizar

RAIZ = Path(__file__).resolve().parents[1]
CARPETA_NORMA = RAIZ / "material" / "norma"
CACHE = RAIZ / "cache" / "norma"

COLUMNAS = ["Em_requerido_lx", "Em_modificado_lx", "Uo", "Ra", "RUGL",
            "Em_z_lx", "Em_pared_lx", "Em_techo_lx"]

TITULO_TABLA = re.compile(r"^Tabla (\d+) – (.+?)\s*$")
REFERENCIA = re.compile(r"^(\d+(?:\.\d+){1,2})$")
# "1 000" y también "1000": la tabla 13 escribe los miles sin espacio y se perdían tres filas.
VALOR = re.compile(r"^(\d{1,3}(?: ?\d{3})?|\d+,\d+|–|-)$")
# Pies de página y notas de la tabla: cortan la fila en curso para que no se peguen a sus requisitos.
RUIDO = ("Este documento ha sido adquirido", "autorización previa", "Requerido: valor",
         "Modificado: considera", "UNE-EN 12464-1:2022")


def _pdf(ruta: str | Path | None) -> Path:
    if ruta:
        return Path(ruta).expanduser()
    encontrados = sorted(CARPETA_NORMA.glob("*.pdf"))
    if not encontrados:
        raise FileNotFoundError(
            f"No hay ningún PDF de la norma en {CARPETA_NORMA}. Copia ahí la UNE-EN 12464-1.")
    return encontrados[0]


def _lineas(pagina) -> list[list[dict]]:
    """Celdas de la página agrupadas en renglones. `keep_blank_chars` junta "1 000" en una celda;
    la tolerancia de 1,5 pt no llega a unir dos columnas (el hueco menor medido es de ~15 pt)."""
    celdas = pagina.extract_words(keep_blank_chars=True, x_tolerance=1.5)
    renglones: list[list[dict]] = []
    for c in sorted(celdas, key=lambda c: (round(c["top"]), c["x0"])):
        c["text"] = c["text"].strip()
        if not c["text"]:
            continue
        if renglones and abs(renglones[-1][0]["top"] - c["top"]) < 3:
            renglones[-1].append(c)
        else:
            renglones.append([c])
    return [sorted(r, key=lambda c: c["x0"]) for r in renglones]


def _anclas(cabecera: list[dict]) -> dict[str, float] | None:
    """Centro horizontal de cada columna de valores, sacado de la cabecera de UNA tabla.

    Por tabla y no por página: la página 44 tiene las tablas 14 y 15 con las columnas desplazadas
    ~6 pt, y con las anclas de la página salían 11 filas con columnas corridas o vacías.
    """
    centro = lambda *cs: (min(c["x0"] for c in cs) + max(c["x1"] for c in cs)) / 2  # noqa: E731

    def par(primera: str, segunda: str) -> list[float]:
        # Uo, Ra y RUGL se escriben con el subíndice en otro renglón, pegado a la letra.
        return [centro(a, b) for a in cabecera for b in cabecera
                if a["text"] == primera and b["text"] == segunda
                and abs(b["x0"] - a["x1"]) < 2 and abs(a["top"] - b["top"]) < 6]

    req = [centro(c) for c in cabecera if c["text"].startswith("requerido")]
    mod = [centro(c) for c in cabecera if c["text"].startswith("modificado")]
    uo, ra, rugl = par("U", "o"), par("R", "a"), par("R", "UGL")
    if not (req and mod and uo and ra and rugl):
        return None
    anclas = {"Em_requerido_lx": req[0], "Em_modificado_lx": mod[0], "Uo": min(uo),
              "Ra": ra[0], "RUGL": rugl[0]}
    lx = sorted(centro(c) for c in cabecera if c["text"] == "lx" and centro(c) > anclas["RUGL"])
    if len(lx) != 3:
        return None
    anclas.update(Em_z_lx=lx[0], Em_pared_lx=lx[1], Em_techo_lx=lx[2])
    return anclas


def _numero(texto: str) -> float | None:
    if texto in ("–", "-"):
        return None
    valor = float(texto.replace(" ", "").replace(",", "."))
    return int(valor) if valor.is_integer() else valor


def _leer(pdf: Path) -> dict:
    filas: dict[str, dict] = {}
    tabla = None
    with pdfplumber.open(pdf) as documento:
        for n, pagina in enumerate(documento.pages, start=1):
            anclas = None
            cabecera: list[dict] = []
            actual = None
            for renglon in _lineas(pagina):
                texto = " ".join(c["text"] for c in renglon)
                if m := TITULO_TABLA.match(texto):
                    tabla = {"numero": m.group(1), "titulo": f"Tabla {m.group(1)} – {m.group(2)}"}
                    anclas, cabecera, actual = None, [], None
                    continue
                if any(r in texto for r in RUIDO):
                    actual = None
                    continue
                if tabla is None:
                    continue

                primera = renglon[0]
                ref = REFERENCIA.match(primera["text"])
                es_fila = bool(ref and ref.group(1).split(".")[0] == tabla["numero"])
                if not es_fila and actual is None:
                    cabecera.extend(renglon)
                    continue
                if es_fila and cabecera:
                    anclas, cabecera = _anclas(cabecera), []
                if anclas is None:
                    actual = None
                    continue
                if es_fila and primera["x1"] < anclas["Em_requerido_lx"]:
                    actual = {"referencia": ref.group(1), "tabla": tabla["titulo"], "pagina_pdf": n,
                              "tipo_de_area": [], "requisitos_especificos": [], "valores": {}}
                    filas.setdefault(ref.group(1), actual)
                    renglon = renglon[1:]
                elif actual is None:
                    continue

                inicio_valores = anclas["Em_requerido_lx"] - 30
                fin_valores = anclas["Em_techo_lx"] + 20
                for celda in renglon:
                    medio = (celda["x0"] + celda["x1"]) / 2
                    if medio < inicio_valores:
                        actual["tipo_de_area"].append(celda["text"])
                    elif medio > fin_valores:
                        actual["requisitos_especificos"].append(celda["text"])
                    elif VALOR.match(celda["text"]):
                        columna = min(COLUMNAS, key=lambda k: abs(anclas[k] - medio))
                        actual["valores"].setdefault(columna, _numero(celda["text"]))

    salida = {}
    for ref, f in filas.items():
        fila = {"referencia": ref, "tabla": f["tabla"], "pagina_pdf": f["pagina_pdf"],
                "tipo_de_area": " ".join(f["tipo_de_area"])}
        subfilas = [r for r in filas if r.startswith(ref + ".")]
        if not f["valores"] and subfilas:
            fila["error"] = f"Es un título de grupo sin valores: usa una de sus filas ({', '.join(subfilas)})."
        elif set(f["valores"]) != set(COLUMNAS):
            # Mejor no dar la fila que dar una columna corrida: un Ra de otra casilla no se nota.
            fila["error"] = ("No se han podido leer todas las columnas de esta fila (en la norma "
                             "hay filas con casillas vacías); consúltala en el PDF.")
        else:
            fila.update(f["valores"])
        if f["requisitos_especificos"]:
            fila["requisitos_especificos"] = " ".join(f["requisitos_especificos"])
        salida[ref] = fila
    return salida


def tabla_norma(ruta_pdf: str | Path | None = None) -> dict:
    """Todas las filas de la norma. La primera vez lee el PDF (unos segundos); luego, de la caché."""
    pdf = _pdf(ruta_pdf)
    huella = hashlib.sha256(pdf.read_bytes()).hexdigest()[:16]
    cache = CACHE / f"{huella}.json"
    if cache.is_file():
        return json.loads(cache.read_text(encoding="utf-8"))
    filas = _leer(pdf)
    CACHE.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(filas, ensure_ascii=False, indent=1), encoding="utf-8")
    return filas


def requisitos(referencia: str, ruta_pdf: str | Path | None = None) -> dict:
    filas = tabla_norma(ruta_pdf)
    ref = referencia.strip().replace(",", ".")
    if ref not in filas:
        return {"referencia": ref, "error": f"La referencia {ref} no aparece en las tablas de la norma."}
    return {**filas[ref], "fuente": f"UNE-EN 12464-1:2022, {filas[ref]['tabla']}, fila {ref}, "
                                    f"página {filas[ref]['pagina_pdf']} del PDF"}


def buscar(texto: str, ruta_pdf: str | Path | None = None) -> list[dict]:
    """Filas cuyo tipo de área o tabla contienen todas las palabras buscadas (sin tildes)."""
    palabras = normalizar(texto).split()
    return [{"referencia": f["referencia"], "tabla": f["tabla"], "tipo_de_area": f["tipo_de_area"]}
            for f in tabla_norma(ruta_pdf).values()
            if all(p in normalizar(f"{f['tipo_de_area']} {f['tabla']}") for p in palabras)]
