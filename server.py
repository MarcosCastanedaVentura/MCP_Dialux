"""Servidor MCP de MCP_Dialux. Claude Desktop lo arranca solo con la configuración del README."""

import sys
from pathlib import Path

# Claude Desktop arranca el proceso desde otra carpeta: sin esto no encuentra el paquete `dialux`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402

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


if __name__ == "__main__":
    mcp.run()
