"""Servidor MCP de MCP_Dialux. Claude Desktop lo arranca solo con la configuración del README."""

import sys
from pathlib import Path

# Claude Desktop arranca el proceso desde otra carpeta: sin esto no encuentra el paquete `dialux`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from dialux import norma as _norma  # noqa: E402
from dialux.construir import plano_a_stf as _plano_a_stf  # noqa: E402
from dialux.cad.plano import leer_plano as _leer_plano  # noqa: E402

mcp = MCPServer(
    "MCP_Dialux",
    instructions=(
        "Herramientas para resolver ejercicios de iluminación de DIALux evo de clase. "
        "Nunca inventes un dato que el plano no da (altura de sala, factor de mantenimiento, "
        "tipo de actividad): si aparece en 'faltan', pregúntaselo al alumno."
    ),
)


@mcp.tool()
def leer_plano(ruta: str) -> dict:
    """Lee un plano de clase (.dwg o .dxf) y devuelve sus plantas y salas.

    Para cada sala: nombre y uso, referencia de la tabla de la UNE-EN 12464-1 si el plano la da
    (p. ej. "34.2"), medidas y superficie, contorno en metros con origen en la esquina de la
    planta, obstáculos (columnas), y los datos del enunciado escritos en el plano: altura de sala,
    altura del plano de trabajo, zona marginal y factor de mantenimiento. 'faltan' lista lo que el
    plano no dice. 'cotas' indica si las medidas reconstruidas cuadran con las cotas del dibujo;
    si alguna no cuadra, avisa al alumno antes de usar las superficies.

    ruta: ruta absoluta al fichero en esta máquina.
    """
    return _leer_plano(ruta)


@mcp.tool()
def construir_edificio(ruta_plano: str, altura_m: float | None = None,
                       alturas: dict[str, float] | None = None,
                       nombres_genericos: bool = False,
                       nombre_proyecto: str | None = None) -> dict:
    """Construye el edificio del plano y escribe un fichero STF por planta para DIALux evo.

    Cada sala entra con su contorno real, su nombre, su altura y su plano de trabajo. El alumno
    lo importa con Archivo → Importar → Archivo STF… y compara con su propia solución.

    ruta_plano: ruta al .dwg o .dxf del ejercicio.
    altura_m: altura de las salas cuando el plano no la dice. Pregúntasela al alumno; no la
      supongas. Si falta, la herramienta no escribe nada y devuelve 'faltan'.
    alturas: altura distinta para salas concretas, por nombre, p. ej. {"Oficina": 3.5}.
    nombres_genericos: si es True, las salas se llaman "Local 1", "Local 2"…, como las nombra
      DIALux al crearlas a mano, en vez de con el uso que pone el plano.
    nombre_proyecto: el nombre del proyecto dentro del fichero; por defecto, el del plano.

    Cuéntale SIEMPRE lo que venga en 'a_mano': son la zona marginal y las columnas, que el STF no
    lleva y hay que poner en DIALux después de importar. Van con el valor y la posición ya
    calculados; enséñaselos sala por sala para que solo tenga que teclearlos.

    Lee también 'avisos', y comprueba 'cotas': si las cotas del plano no cuadran, avísale antes
    de que use el edificio.
    """
    return _plano_a_stf(ruta_plano, altura_m=altura_m, alturas=alturas,
                        nombres_genericos=nombres_genericos, nombre_proyecto=nombre_proyecto)


@mcp.tool()
def requisitos_norma(referencia: str) -> dict:
    """Lo que exige la UNE-EN 12464-1:2022 para una referencia de tabla, p. ej. "34.7".

    Se lee de la copia de la norma del alumno (PDF en material/norma/). Devuelve el tipo de área,
    Ēm requerido y Ēm modificado (lx), Uo, Ra, RUGL, Ēm,z, Ēm,pared y Ēm,techo, los requisitos
    específicos y 'fuente' con la tabla, la fila y la página del PDF: cítala siempre, para que el
    alumno pueda comprobarlo. Un valor None es una casilla con "–" en la norma (no se exige).

    Ēm requerido es el mínimo; Ēm modificado aplica los modificadores de contexto del apartado
    5.3.3. No elijas uno por tu cuenta: si el enunciado no dice cuál, pregunta al alumno.
    Si hay 'error', no rellenes los valores de memoria: dile que consulte la página del PDF.
    """
    return _norma.requisitos(referencia)


@mcp.tool()
def buscar_en_norma(texto: str) -> list[dict]:
    """Busca en las tablas de la UNE-EN 12464-1:2022 las filas cuyo tipo de área o tabla contienen
    todas las palabras dadas (sin distinguir tildes ni mayúsculas), p. ej. "enfermeria" o "oficinas".

    Sirve para encontrar la referencia cuando el enunciado describe el local sin dar el número.
    Si hay varias candidatas, enséñaselas al alumno y que elija él: no decidas la fila.
    """
    return _norma.buscar(texto)


if __name__ == "__main__":
    mcp.run()
