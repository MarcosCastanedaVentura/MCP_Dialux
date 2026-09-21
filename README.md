# MCP_Dialux

**Del plano de un ejercicio de iluminación al edificio construido en DIALux evo, sin dibujarlo a
mano.**

MCP_Dialux es un servidor [MCP](https://modelcontextprotocol.io) que lee el plano DWG de un
ejercicio de luminotecnia —incluido el enunciado que el profesor escribe dentro del propio
plano—, consulta lo que exige la norma UNE-EN 12464-1 para cada tipo de local y genera un fichero
que DIALux evo importa con las estancias ya levantadas.

Se usa hablando con un asistente de IA, sin tocar la línea de comandos:

> **—** Construye el edificio del examen `Examen-junio.dwg`
>
> **—** El plano no dice la altura de las salas. ¿Qué altura tienen?
>
> **—** 3 metros
>
> **—** Listo: 7 salas en 2 plantas, en `salida/Examen-junio.stf`. Las 6 cotas del plano cuadran
> con las medidas reconstruidas. En Archivos hay una columna de 0,66 × 0,63 m en (22,18 ; 6,65)
> que tendrás que poner a mano.

---

## Por qué existe

En clase de iluminación el ejercicio siempre empieza igual: un plano en DWG, un enunciado con los
datos del local y un catálogo de luminarias. Después hay que montarlo en DIALux evo, que es el
programa estándar del sector, y calcular.

Montar el edificio es la parte lenta y la que no enseña nada: dibujar paredes siguiendo un plano
que ya existe. Este proyecto la automatiza, para poder dedicar el tiempo al cálculo y, sobre todo,
para **comparar el edificio generado con el que uno ha hecho a mano** y detectar dónde se ha
equivocado.

## Qué hace

| Herramienta | Entrada | Salida |
|---|---|---|
| `leer_plano` | Un `.dwg` o `.dxf` | Plantas, salas, contornos, superficies, columnas y los datos del enunciado escritos en el plano, comprobados contra las cotas del dibujo |
| `construir_edificio` | Un `.dwg` o `.dxf` | Un fichero `.stf` que DIALux evo importa con las estancias levantadas, más la lista de lo que hay que rematar a mano |
| `requisitos_norma` | Una referencia de tabla, `"34.7"` | Ēm, U₀, Ra, UGR e iluminancias en paredes y techo, citando tabla, fila y página del PDF de la norma |
| `buscar_en_norma` | Un texto, `"enfermería"` | Las filas de la norma que encajan, para encontrar la referencia cuando el enunciado no la da |

### Un ejemplo real

El examen final de junio es un edificio de dos plantas con nueve zonas. De su plano salen, sin
escribir un dato a mano:

- **Las salas**, reconstruidas a partir de muros dibujados como líneas sueltas: oficina en L de
  214 m², archivos, sala de atención médica, baños, pasillo y dos huecos de ascensor.
- **Los datos de cada zona**, que la profesora escribe como texto dentro del plano: altura del
  plano de trabajo, zona marginal, factor de mantenimiento y el tipo de actividad según la norma
  (`34.2 Oficina`, `10.7 Sala para atención médica`…).
- **Las columnas** que hay dentro de dos salas, con su tamaño y su posición.
- **La comprobación**: las 6 cotas del dibujo coinciden con las medidas reconstruidas.

## Cómo funciona

```
 .dwg  ──ODA File Converter──►  .dxf  ──ezdxf──►  geometría + textos
                                                        │
          ┌─────────────────────────────────────────────┤
          ▼                                             ▼
   reconstruir salas                            leer el enunciado
   (shapely)                                    (altura, plano de
          │                                      trabajo, actividad)
          └─────────────────┬───────────────────────────┘
                            ▼
                   comprobar con las cotas
                            │
                            ▼
                    escribir el .stf ──────►  DIALux evo
```

Tres problemas interesantes por el camino:

**1. En el plano no hay ninguna sala.** Los muros son polilíneas abiertas, con la cara interior y
la exterior por separado y huecos en las puertas; las capas no distinguen un muro de una cota. Las
salas se reconstruyen cerrando los huecos entre tramos alineados, poligonizando el dibujo y
quedándose con las caras cuya anchura media supera el grosor de un muro. Un detalle que costó
encontrar: DIALux importa mal una pared que toca a dos salas si no hay un vértice justo donde
acaba la pared del vecino, así que las paredes se parten automáticamente en esos puntos.

**2. El enunciado va dentro del plano, como texto suelto.** Cada texto se asigna a la sala que lo
contiene, y los párrafos que quedan fuera del dibujo se agrupan y se asignan por su encabezado
("Sobre los baños"). Lo que no se reconoce con seguridad no se interpreta: se devuelve tal cual
para que lo lea el asistente.

**3. La norma es un PDF de 114 páginas.** Las tablas de la UNE-EN 12464-1:2022 se leen localizando
las columnas por su cabecera en cada tabla, porque cambian de posición incluso dentro de la misma
página. De 319 filas se leen 314; las 5 restantes son títulos de grupo o filas con casillas vacías
en la propia norma, y se devuelven como "consúltala en el PDF" en vez de rellenarlas. Contrastadas
con una lectura independiente, **coinciden las 303 filas comparables**.

## Ingeniería inversa del formato STF

DIALux evo importa arquitectura en tres formatos: IFC (solo en la versión de pago), DX4 (del
DIALux clásico) y **STF**. STF es el único camino gratuito, y su especificación **no es pública**:
DIAL la envía por correo a quien la pide.

El generador de este proyecto se escribió deduciendo el formato de dos exportadores de código
abierto —[STF-Exporter](https://github.com/kmorin/STF-Exporter) para Revit y
[DIALux_Toolkit](https://github.com/BHoM/DIALux_Toolkit) de BHoM— y validando cada campo
importando ficheros de prueba en DIALux evo 14. Lo que se ha averiguado probando:

| Comprobación | Resultado |
|---|---|
| Contorno, nombre, altura y plano de trabajo | Se importan bien, incluidas las plantas en forma de L |
| Pared que toca a dos salas sin vértice en la unión | La sala entra cruzada por una diagonal. Se corrige partiendo la pared |
| Importar un segundo STF en el mismo proyecto | **Sustituye** el proyecto, no añade. Todo tiene que ir en un fichero |
| Dos salas en el mismo sitio (dos plantas superpuestas) | Se pierden: solo sobrevive una |
| Nivel o planta de cada sala | No existe. Probados ocho nombres de campo, ninguno funciona |
| Columnas y zona marginal | No se han conseguido escribir; se devuelven con sus medidas para ponerlas a mano |

Como el formato no sabe de plantas, las de un mismo edificio se escriben separadas en el plano,
con un desplazamiento redondo que la herramienta indica, y cada sala lleva su planta en el nombre
(`Archivos [segunda]`) para poder repartirlas dentro de DIALux.

## Decisiones de diseño

- **Nunca inventar un dato.** Si el plano no dice la altura de las salas, no se escribe ningún
  fichero: se devuelve qué falta y para qué salas. Un edificio con una altura inventada parece
  correcto, y eso es peor que no tener nada.
- **Los valores de la norma salen del PDF del usuario**, no están copiados en el código, y cada
  respuesta dice de qué tabla, fila y página viene para poder comprobarla en el papel.
- **Lo que la herramienta no puede hacer, lo dice con números.** Las columnas y la zona marginal
  no caben en el STF, así que se devuelven con su valor y su posición ya calculados, para no tener
  que volver al plano.
- **Cada regla del código tiene al lado la medición que la justifica**, con la fecha en la que se
  comprobó.

## Limitaciones

- Las **luminarias** todavía no se colocan: el edificio llega a DIALux vacío. El formato STF las
  admite y es el siguiente paso.
- **Columnas y zona marginal** hay que ponerlas a mano, con los datos que da la herramienta.
- Las plantas de un edificio **se colocan a mano** dentro de DIALux, por lo que se explica arriba.
- Probado con planos de AutoCAD 2023 y 2024 en metros; otros orígenes pueden necesitar ajustes.

## Instalación

Requisitos:

- Python 3.12 o superior
- [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter), gratuito, para
  leer DWG (`ezdxf` solo lee DXF)
- DIALux evo (Windows) para importar el resultado
- Tu copia del PDF de la UNE-EN 12464-1 en `material/norma/`, si quieres las herramientas de norma

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q pruebas
```

En Windows:

```powershell
py -m venv $HOME\.venvs\mcp_dialux
~\.venvs\mcp_dialux\Scripts\pip install -r requirements.txt
~\.venvs\mcp_dialux\Scripts\python -m pytest -q pruebas
```

## Conectar con un cliente MCP

En Claude Desktop: *Ajustes → Desarrollador → Editar configuración*, y añadir el servidor a
`claude_desktop_config.json`. Después, cerrar la aplicación del todo y volver a abrirla.

```json
{
  "mcpServers": {
    "dialux": {
      "command": "/ruta/al/proyecto/.venv/bin/python",
      "args": ["/ruta/al/proyecto/server.py"]
    }
  }
}
```

En Windows, las rutas van con doble barra: `"C:\\Users\\tu-usuario\\.venvs\\mcp_dialux\\Scripts\\python.exe"`.

Si ODA File Converter no está en su carpeta habitual, se le indica con
`"env": {"ODA_FILE_CONVERTER": "ruta al ejecutable"}`.

## Estructura

```
server.py              el servidor MCP: solo declara las herramientas
dialux/
  cad/convertir.py     DWG → DXF con ODA, igual en macOS y en Windows, con caché por hash
  cad/geometria.py     reconstruir las salas del plano
  cad/enunciado.py     leer los datos del ejercicio de los textos del plano
  cad/plano.py         leer_plano: lo junta y lo comprueba contra las cotas
  norma.py             las tablas de la UNE-EN 12464-1, leídas del PDF
  stf.py               escribir el fichero que importa DIALux evo
  construir.py         del plano al edificio
pruebas/               25 pruebas, sobre planos de examen reales
```

Los planos de clase, el PDF de la norma y las fichas de luminarias **no se incluyen** en el
repositorio: son material de la asignatura.

## Pruebas

```bash
.venv/bin/python -m pytest -q pruebas
```

Las pruebas se apoyan en los exámenes reales y se saltan solas si no están. Cada una documenta el
fallo que la hizo necesaria: la diagonal del pasillo, los textos de dos salas que se asignaron al
revés, las filas de la norma con los miles escritos sin espacio.

## Licencia

MIT. Ver [LICENSE](LICENSE).
