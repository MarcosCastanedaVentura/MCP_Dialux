"""Servidor MCP de MCP_Dialux. Claude Desktop lo arranca solo con la configuración del README."""

import sys
from pathlib import Path

# Claude Desktop arranca el proceso desde otra carpeta: sin esto no encuentra el paquete `dialux`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from dialux import leer_stf as _stf  # noqa: E402
from dialux import luminarias as _luminarias  # noqa: E402
from dialux import norma as _norma  # noqa: E402
from dialux.corregir import corregir as _corregir  # noqa: E402
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
                       nombre_proyecto: str | None = None,
                       luminarias: int | dict[str, int] | None = None,
                       altura_montaje_m: float | None = None) -> dict:
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
    luminarias: cuántas luminarias se colocan en cada sala, en retícula. Un número para todas, o
      uno por sala por nombre, p. ej. {"Oficina": 12, "Archivos": 6}. **Este número lo da el
      alumno o sale del cálculo: no lo elijas tú.** Si no se pasa, el edificio va sin luminarias.
    altura_montaje_m: a qué altura cuelgan, desde el suelo; por defecto, en el techo.

    Cuéntale SIEMPRE lo que venga en 'a_mano': son la zona marginal y las columnas, que el STF no
    lleva y hay que poner en DIALux después de importar. Van con el valor y la posición ya
    calculados; enséñaselos sala por sala para que solo tenga que teclearlos.

    Lee también 'avisos', y comprueba 'cotas': si las cotas del plano no cuadran, avísale antes
    de que use el edificio.
    """
    return _plano_a_stf(ruta_plano, altura_m=altura_m, alturas=alturas,
                        nombres_genericos=nombres_genericos, nombre_proyecto=nombre_proyecto,
                        luminarias=luminarias, altura_montaje_m=altura_montaje_m)


@mcp.tool()
def reticula_luminarias(ancho_m: float, largo_m: float, cuantas: int, altura_montaje_m: float,
                        plano_trabajo_m: float = 0.0, zona_marginal_m: float = 0.0) -> dict:
    """Cómo quedan `cuantas` luminarias repartidas en una sala rectangular, sin necesitar el plano.

    Devuelve la retícula (filas × columnas), la separación en x y en y, la distancia al muro (que
    es media separación), la posición de cada luminaria y la relación entre la separación y la
    altura útil.

    Dos cosas que hay que contarle al alumno tal cual salen:
    - Si el número pedido no forma retícula (7, por ejemplo), se sube al siguiente que sí, y
      entonces hay más luz de la calculada: aparece en 'avisos'.
    - Si la separación es admisible NO lo dice esta herramienta: depende de la curva de
      distribución de la luminaria. Dale el número de 'separacion_entre_altura_util' y que lo
      compare con el criterio de separación de su luminaria.
    """
    return _luminarias.reticula([(0.0, 0.0), (ancho_m, 0.0), (ancho_m, largo_m), (0.0, largo_m)],
                                cuantas, altura_montaje_m, plano_trabajo_m, zona_marginal_m)


@mcp.tool()
def leer_proyecto(ruta: str) -> dict:
    """Dice qué edificio hay dentro de un fichero, sin abrir DIALux.

    Acepta un .stf (el que genera `construir_edificio`) y también el .dwg que exporta DIALux evo
    (Exportar → Exportar en un archivo nuevo), en sus dos variantes:

    - La exportación **3D** trae alturas de verdad.
    - La exportación **2D** no trae alturas, pero sí **la planta de cada sala**, **las luminarias
      colocadas** y **las tablas de resultados de DIALux** (iluminancia mínima, máxima, media y
      uniformidad de cada sala), además de la lista de luminarias con flujo, factor de
      degradación y potencia. Dice en 'variante' cuál ha leído, y en 'avisos' lo que esa variante
      no puede dar.

    De cada sala: nombre, planta si se sabe, contorno, superficie, medidas, altura, plano de
    trabajo, factor de mantenimiento, reflectancias, muebles (ventanas, puertas y columnas),
    luminarias con su posición y resultados si los hay.
    """
    return _stf._leer_cualquiera(ruta)


@mcp.tool()
def comparar_edificios(ruta_a: str, ruta_b: str) -> dict:
    """Compara dos edificios y dice en qué se diferencian, sala por sala.

    Cada uno puede ser un .stf generado por `construir_edificio` o un .dwg exportado desde
    DIALux evo (Exportar → Exportar en un archivo nuevo, con todas las capas marcadas). Así se
    puede contrastar el edificio del MCP con el que el alumno ha montado a mano.

    Empareja las salas por nombre, y si no coinciden, por superficie. Devuelve las iguales, las
    que cambian y en qué (altura, plano de trabajo, superficie, factor de mantenimiento,
    reflectancias, luminarias, columnas), y las que solo están en uno de los dos.

    Compara también **las luminarias**: 'luminarias' dice, sala por sala, cuántas hay en cada
    edificio y cuántas están en el mismo sitio. Cuéntaselo al alumno aunque coincidan: que
    coincidan es justo lo que se quiere saber.

    Lo que NO se puede comparar así: las puertas y ventanas (el DWG exportado no las trae) ni la
    zona marginal. Y con la exportación 2D tampoco las alturas: eso sale en 'sin_comparar'.
    """
    return _stf.comparar(ruta_a, ruta_b)


@mcp.tool()
def corregir_trabajo(ruta: str, referencias: dict[str, str] | None = None,
                     usar: str | None = None) -> dict:
    """Corrige un trabajo de DIALux contra la UNE-EN 12464-1, sala por sala.

    ruta: el .dwg que el alumno ha exportado de DIALux **después de calcular** (Exportar →
      Exportar en un archivo nuevo). Los resultados salen de las tablas que DIALux escribe dentro
      de ese DWG; un .stf no sirve, porque no lleva resultados.
    referencias: la fila de la norma de cada sala, por nombre, p. ej. {"Aula 1": "44.1"}.
    usar: "requerido" o "modificado" para quedarse con uno de los dos Ēm. Por defecto se dan los
      dos, porque la norma da los dos y en clase no está decidido cuál se usa.

    De cada sala corregida: lo medido (Ēm, mínima, máxima, U0, W/m²), lo exigido, qué cumple y qué
    no, y 'fuente' con la tabla, la fila y la página del PDF: cítala siempre.

    Las salas sin fila de la norma salen en 'sin_referencia_de_norma' con candidatas buscadas por
    el nombre: **pregúntale al alumno cuál es, no la elijas tú**. Y dile lo que hay en
    'no_se_comprueba_aqui' (Ra, RUGL y las iluminancias de paredes y techo), para que no crea que
    un trabajo está entero revisado.
    """
    return _corregir(ruta, referencias=referencias, usar=usar)


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
