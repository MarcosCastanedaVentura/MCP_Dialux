"""DWG -> DXF con ODA File Converter, igual en el Mac que en la máquina virtual de Windows.

`ezdxf` solo lee DXF, y los planos de clase llegan en DWG de AutoCAD 2023/2024 (comprimido).
"""

from __future__ import annotations

import hashlib
import os
import platform
from pathlib import Path

import ezdxf
from ezdxf.addons import odafc

RAIZ = Path(__file__).resolve().parents[2]
CACHE_DXF = RAIZ / "cache" / "dxf"


def _buscar_oda() -> Path | None:
    """Dónde está el conversor en esta máquina.

    En macOS `ezdxf` no lo encuentra solo aunque esté instalado (medido el 16/9/2026: dice
    "not installed" con la app en /Applications). En Windows ODA lo instala en una carpeta con
    la versión en el nombre ("ODAFileConverter 27.1.0"), así que la ruta fija de `ezdxf` falla
    en cuanto se actualiza: se busca con comodín.
    """
    propia = os.environ.get("ODA_FILE_CONVERTER")
    if propia and Path(propia).is_file():
        return Path(propia)

    sistema = platform.system()
    if sistema == "Darwin":
        candidatos = [Path("/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter")]
    elif sistema == "Windows":
        candidatos = []
        for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
            if base:
                candidatos += sorted(Path(base, "ODA").glob("ODAFileConverter*/ODAFileConverter.exe"),
                                     reverse=True)
    else:
        candidatos = [Path("/usr/bin/ODAFileConverter")]
    return next((c for c in candidatos if c.is_file()), None)


def _configurar_oda() -> None:
    ruta = _buscar_oda()
    if ruta is None:
        raise RuntimeError(
            "No encuentro ODA File Converter. Instálalo desde "
            "https://www.opendesign.com/guestfiles/oda_file_converter o indica la ruta del "
            "ejecutable en la variable de entorno ODA_FILE_CONVERTER."
        )
    clave = "win_exec_path" if platform.system() == "Windows" else "unix_exec_path"
    ezdxf.options.set("odafc-addon", clave, str(ruta))


def a_dxf(ruta: str | Path) -> Path:
    """Devuelve un DXF legible para el plano dado. Un DXF se devuelve tal cual.

    La conversión se guarda en `cache/dxf/` con el hash del contenido: el mismo plano no se
    vuelve a convertir, y un plano cambiado con el mismo nombre no reutiliza el viejo.
    """
    ruta = Path(ruta).expanduser()
    if not ruta.is_file():
        raise FileNotFoundError(f"No existe el fichero: {ruta}")
    extension = ruta.suffix.lower()
    if extension == ".dxf":
        return ruta
    if extension != ".dwg":
        raise ValueError(f"Solo se leen planos .dwg o .dxf, no '{ruta.suffix}'")

    huella = hashlib.sha256(ruta.read_bytes()).hexdigest()[:16]
    destino = CACHE_DXF / f"{huella}.dxf"
    if destino.is_file():
        return destino

    _configurar_oda()
    CACHE_DXF.mkdir(parents=True, exist_ok=True)
    odafc.convert(ruta, destino, version="R2018", replace=True)
    return destino
