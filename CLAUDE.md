# MCP_Dialux — corrector de ejercicios de DIALux evo

Servidor MCP (Python, SDK `mcp` 2.x con `MCPServer`) que resuelve **entero** un ejercicio de iluminación de clase a
partir del plano DWG y las luminarias que da el enunciado, para que Marcos compare con su propia
solución.

**Para qué es:** uso personal en clase. Marcos hace el ejercicio por su cuenta en DIALux y después
se lo pasa al MCP para verificar que lo tiene bien. No es un producto para vender.

De ahí salen las prioridades: **que acierte y que explique por qué**, no que sea bonito ni que
escale. Una solución del MCP que esté mal y parezca bien es peor que no tener MCP, porque Marcos se
"corregiría" hacia el error.

**El objetivo, fijado el 20/9/2026:** que se le pase el ejercicio de clase o de examen —el plano
con su enunciado dentro— y **devuelva el edificio construido**: estancias con sus medidas y
alturas, y las luminarias colocadas. Marcos lo importa en DIALux, abre su propia solución al lado
y las compara. La cadena es `leer_plano` + `requisitos_norma` -> STF.

---

## 1. LO QUE NO SE TOCA

1. **DIALux evo corre SIEMPRE en Windows, dentro de una máquina virtual.** Marcos desarrolla en un
   Mac (macOS), pero DIALux no existe para Mac y no se va a usar nunca fuera de Windows. Todo lo
   que toque DIALux (importar, lanzar el cálculo, leer lo que genera) se diseña y se prueba pensando
   en Windows. Nunca proponer una solución que necesite DIALux en el Mac.

2. **El código tiene que funcionar igual en Mac y en Windows.** El proyecto se mueve a la máquina
   virtual, así que:
   - Rutas siempre con `pathlib`, nunca con `/` escrito a mano ni rutas absolutas del Mac.
   - Nada que solo exista en macOS (ni `brew`, ni comandos de shell de Unix desde Python).
   - El entorno **no se copia**: se recrea en cada máquina desde `requirements.txt`. El de Windows
     va en el disco de Windows (`%USERPROFILE%\.venvs\mcp_dialux`), nunca dentro de la carpeta
     compartida: sobre una unidad de red la instalación es lenta y falla, y con el mismo nombre
     que el del Mac cada sistema rompería el del otro.
   - Lo que solo tiene sentido en Windows (automatizar la ventana de DIALux) va aislado en su
     propio módulo y se importa solo en Windows, para que el resto arranque en el Mac.

3. **Un ejercicio es UN edificio.** Lo que en el plano son plantas distintas (segunda, tercera…)
   son plantas del mismo edificio, nunca edificios separados. Regla de Marcos del 21/9/2026,
   después de recibir el examen de junio como dos edificios sueltos. Solo se hacen varios
   edificios si él lo pide. El STF no sabe de niveles (ver sección 3), así que mientras no se
   encuentre la forma de decirlo en el fichero, hay que explicarle cómo dejarlo en un edificio
   dentro de DIALux.

4. **No inventar datos de norma ni de luminarias.** Los valores exigidos por la UNE-EN 12464-1
   (Em, UGRL, U₀, Ra por tipo de tarea) salen de la copia de la norma de Marcos, leídos de su PDF, y
   se enseña de qué fila salen para que se pueda revisar. Los datos fotométricos salen del fichero de la luminaria (LDT/ULD/
   IES), nunca de memoria. Si falta un dato, se pide; no se supone.

---

## 2. CÓMO SE TRABAJA AQUÍ

- **Probar con los exámenes reales** de `material/examenes/`, no con planos inventados. Los planos
  de clase son de la profesora (AutoCAD 2023/2024) y son los que hay que saber leer.
- **Verificar antes de construir** lo que no se sabe seguro. Se prueba un fichero de ejemplo en
  la VM antes de dar por bueno un formato o un campo.
- **Decir lo que no funciona** y lo que está sin verificar. Marcos es estudiante de Ingeniería
  Alimentaria, no programador: explicar el porqué en términos de iluminación y de uso, no solo de
  código.
- **Git:** rama antes de commitear, nunca directo a `main`.
- **Al terminar algo en el Mac, dejarlo listo en Windows** (pedido por Marcos el 20/9/2026). El
  código llega solo por la carpeta compartida `Z:`, pero eso no basta. Antes de decir que está
  hecho, decirle a Marcos, y solo lo que aplique:
  1. **Reiniciar Claude Desktop en Windows** si se ha tocado `server.py` o cualquier módulo que
     use: el servidor MCP se arranca al abrir Claude, y hasta entonces sigue el código viejo.
  2. **Reinstalar el entorno de Windows** si ha cambiado `requirements.txt`:
     `%USERPROFILE%\.venvs\mcp_dialux\Scripts\pip install -r Z:\requirements.txt`.
  3. **Pasar las pruebas en Windows** si se ha tocado algo que dependa del sistema (rutas, ODA,
     ficheros): `cd /d Z:\` y `%USERPROFILE%\.venvs\mcp_dialux\Scripts\python -m pytest -q pruebas`.
  4. Decirle **qué pedirle al MCP** para probarlo, con la ruta en `Z:` ya escrita.

---

## 3. LO QUE SE SABE DEL MATERIAL (16/9/2026)

- Los tres DWG son formato **AC1032** (AutoCAD 2018 en adelante), comprimidos. `ezdxf` no lee DWG:
  hay que convertirlos a DXF antes con ODA File Converter (instalado en el Mac el 16/9/2026).
  **En macOS `ezdxf` no lo encuentra solo**: hay que darle la ruta
  `/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter` con
  `ezdxf.options.set("odafc-addon", "unix_exec_path", …)`. Lo hace `convertir.py`. En Windows lo
  busca en `Program Files\ODA\ODAFileConverter*`: **comprobado el 16/9/2026 en la VM**, lo
  encuentra en `C:\Program Files\ODA\ODAFileConverter 27.1.0\` y convierte el parcial desde
  cero (313 471 bytes; en el Mac 313 468, la diferencia es la cabecera).
- **El enunciado va DENTRO del plano**, como texto: altura de sala, espesor de pared, altura del
  plano de trabajo, zona marginal, factor de mantenimiento, reflectancias y tipo de actividad. Es
  la fuente de datos del ejercicio; no hay que pedírselo aparte a Marcos.
- En el examen de junio cada zona lleva un código delante del uso ("34.2 Oficina…", "10.7 Sala para
  atención médica", "9.4" zona frente al ascensor). **Confirmado:** es `tabla.fila` de la
  UNE-EN 12464-1:2022 (34.7 = tabla 34 Oficinas, fila Archivos).
- **La norma es la copia de Marcos** (`material/norma/AlumbradoInterior-2022.pdf`), con licencia
  de la UPM por AENORmás para uso interno. Los valores exigidos (Em, U₀, Ra, RUGL…) se leen de
  ese PDF (`dialux/norma.py`, caché en `cache/norma/`); **no se transcriben a un fichero del
  repo** ni se publican. Única excepción: los valores de las pocas filas que usan los exámenes,
  en `pruebas/test_norma.py`, porque sin ellos la prueba no comprueba nada.
- Lectura de la norma medida el 16/9/2026: 319 filas, **303 de 303 comparables coinciden** con una
  lectura independiente con pdftotext. 5 filas no se dan a propósito: 2 títulos de grupo
  (19.2, 26.11) y 3 con casillas vacías en la propia norma (13.5, 13.8, 37.3). Dos trampas que ya
  costaron filas: columnas en distinta posición en cada tabla, **incluso en la misma página** (se
  localizan por la cabecera de cada tabla), y miles escritos "1 000" o "1000".
- Cada fila tiene Ēm **requerido** (mínimo) y **modificado** (con los modificadores de contexto
  del 5.3.3). Cuál vale en clase no está decidido: pendiente de preguntar a Marcos.
- No todos los enunciados dan la referencia: el parcial no dice el local y enero dice "sala para
  actividad sanitaria (iluminación general)". La fila de la tabla en esos casos **la decide
  Marcos**, no el código. **Decidido por Marcos el 16/9/2026: 10.6 (Enfermería) en los dos.**
- Ningún texto del examen de junio da la altura de las salas: `leer_plano` la lista en `faltan`.
  **Marcos: 3 m** (16/9/2026). El plano sigue sin decirlo, así que la herramienta lo seguirá
  pidiendo; estos datos se pasan al resolver, no se escriben dentro de `leer_plano`.
- **Las capas no dicen qué es un muro**: en junio los remates de los huecos de puerta están en la
  capa "Texto". La geometría se lee sin filtrar por capa.
- Los muros son **polilíneas abiertas**, cara interior y exterior por separado, con huecos en
  puertas y ventanas. No hay ninguna sala dibujada como polígono cerrado: el contorno hay que
  reconstruirlo. Las coordenadas vienen georreferenciadas (x ≈ 438 000, y ≈ 4 477 000): se
  llevan a origen antes de nada.
- Las **cotas** (DIMENSION) dan las medidas reales: sirven para comprobar que el contorno
  reconstruido es el bueno.
- `Lámparas-Examen-2.pdf` **no es un informe de DIALux**: es la hoja del parcial del 28/10/2025
  con tres enlaces a luminarias de `luminaires.dialux.com` entre las que hay que elegir.

- **SDK de MCP 2.x** (`mcp==2.2.0`): `FastMCP` ya no existe con ese nombre, ahora es
  `from mcp.server.mcpserver import MCPServer`. Los ejemplos de internet con
  `mcp.server.fastmcp` son de la versión 1 y no arrancan.
- La versión instalada en la VM es **DIALux evo 14.0**. Su menú Archivo → Importar (visto el
  20/9/2026) ofrece: Plano, **Archivo IFC (marcado PRO, de pago: descartado)**, **Archivo STF**,
  Espacios interiores DX4, Archivo de luminarias, Sistema de luz diurna, muebles, imágenes y
  layout. **La vía para construir el edificio es STF**, y las luminarias se pueden meter aparte
  con "Archivo de luminarias" (ahí entrarán los .ldt cuando los haya).
- **STF comprobado en evo 14 el 20/9/2026**: importa las estancias con su nombre, contorno,
  altura y plano de trabajo, y las formas en L salen bien. Dos cosas medidas:
  - **Donde acaba la pared de una sala vecina tiene que haber un vértice.** Un pasillo cuya pared
    tocaba a dos salas entraba con una diagonal cruzándolo de esquina a esquina; con el vértice
    en la unión, limpio. Lo hace solo `_vertices_de_vecinos` en `stf.py`.
  - Los nombres del **edificio y de la planta los pone DIALux**, no el fichero: con varias
    estancias salen "STF Building" y "STF Storey"; con una sola, el nombre de la estancia. Se
    renombran con doble clic en evo. El nombre del PROYECTO sí sale del fichero.
- **Un solo fichero STF por ejercicio, con las plantas una al lado de otra** (decidido el
  20/9/2026 después de probar las tres opciones en evo 14). Dos hechos medidos:
  - **Importar un segundo STF NO añade: sustituye** lo que hubiera en el proyecto. Con un fichero
    por planta solo se puede tener una planta por proyecto.
  - El STF **no guarda el nivel de cada sala**, así que dos plantas en su sitio real se solapan.
    Comprobado a ciegas y AGOTADO el 21 y el 22/9/2026. **No volver a probar nombres de campo.**
    Descartados: Z, Z0, Base, BaseHeight, Level, Elevation, FloorHeight, Offset, Storey, Floor,
    FloorLevel, Niveau, ZOffset, BaseZ, LowerEdge y Bottom; escribir los puntos del contorno con
    tercera coordenada (`Point1=X Y Z`); y una sección `[STOREY.S1]` aparte a la que la sala hace
    referencia. En los tres casos todas las salas salen al nivel del suelo.
    Marcos pidió la especificación a DIAL por correo el 22/9/2026 y **está esperando respuesta**:
    hasta que llegue, el nivel de planta se pone a mano en DIALux.
  - **Las salas que se solapan se PIERDEN**, no se reparten en edificios como dice la
    documentación de DIAL: probado el 21/9/2026 con las dos plantas de junio en su sitio real,
    y en DIALux solo apareció una sala. Por eso las plantas van separadas.
  Así que `construir.py` desplaza cada planta en X y redondea a múltiplo de 10 (`PASO`), porque
  ese número Marcos lo resta a mano en DIALux; devuelve cuánto en `desplazada_x_m`. Y cada sala
  lleva la planta en el nombre ("Archivos [segunda]") para saber cuáles borrar al duplicar.

  **El método de Marcos para dejarlo en un edificio** (21/9/2026): importar, duplicar la planta,
  borrar de cada copia las salas de las otras plantas y llevar cada planta a su origen restando
  su desplazamiento.
- **Lo que NO se ha conseguido meter en el STF: la zona marginal y las columnas.** Ni el
  exportador de Revit ni el de BHoM las escriben (los dos ponen `NrStruct=0`), así que no hay
  ejemplo real del que copiar los nombres de esos campos. Hay dos ficheros de sondeo con nombres
  candidatos en `material/pruebas_stf/` (pruebaA y pruebaB), sin probar todavía.
  **Decisión de Marcos (20/9/2026): no va a instalar DIALux 4 para sacar la especificación;
  prefiere poner esas dos cosas a mano, que son rápidas.** Por eso `construir_edificio` las
  devuelve en `a_mano` con el valor y la posición calculados. Si algún día aparece el nombre
  bueno del campo, se añade a `stf.py` y se quita de ahí.
- **La especificación oficial de STF (1.0.5) la tiene Marcos desde el 22/9/2026**, enviada por
  el soporte de DIAL a petición suya. Está en `material/STF file format.pdf`, **fuera de git: el
  documento va marcado como confidencial**. No subirlo ni copiar sus tablas al repositorio
  público; usarlo para escribir el código es para lo que lo mandan.
  Lo que aclaró, y que antes estaba deducido de los exportadores de código abierto:
  - El factor de mantenimiento es **`MF`**. `MaintenanceFactor`, que estaba escrito antes, no
    existe: DIALux lo ignoraba y las salas entraban con el 0,8 por defecto.
  - Las reflectancias de pared son **`R_Wall<n>`**, una por tramo (del punto n al n+1), además de
    `R_Ceiling` y `R_Floor`.
  - **No hay nivel de planta ni zona marginal**: una sala es un polígono 2D con suelo y techo
    planos. Deja de ser una sospecha y pasa a ser un límite del formato.
  - **Ventanas y puertas sí se pueden escribir** (`Furn<n>=win` / `door` / `skylight`, con
    posición y tamaño); los muebles corrientes se escriben pero DIALux **no los lee** al
    importar, así que las columnas se quedan a mano.
  - Las luminarias admiten **retícula** (`Type=FIELD` con `Extend` y `NrLums` en x e y), y al
    importar DIALux las sustituye por marcadores que hay que cambiar por luminarias reales.
- La máquina virtual es **VMware Fusion con Windows 11 ARM** (Mac con chip Apple). Consecuencias:
  - Python en Windows es **3.14 ARM64**, y todo `requirements.txt` se instala con él (shapely
    incluido). Las 3 pruebas pasan en la VM (16/9/2026).
  - ODA File Converter solo sale para Windows x64: en ARM corre emulado, y funciona.
  - Las carpetas compartidas de VMware no aparecen en esta VM aunque VMware Tools está instalado.
    **El proyecto se comparte por SMB desde el Mac** (16/9/2026) y en Windows es la unidad `Z:`.
    La dirección es la del Mac en la red NAT de VMware (vmnet8), que no cambia al cambiar de
    wifi; se monta con `net use Z: \\<ip-del-mac>\MCP_Dialux /user:<usuario> /persistent:yes`.
  - El usuario de Windows y el del Mac no se llaman igual: ojo al escribir rutas.

---

## 4. ESTRUCTURA

```
server.py            el servidor MCP: solo declara herramientas
dialux/cad/
  convertir.py       DWG -> DXF con ODA, Mac y Windows (caché en cache/dxf por hash)
  geometria.py       reconstruir salas: cerrar huecos, poligonizar, separar muros de salas
  enunciado.py       leer los datos del ejercicio de los textos del plano
  plano.py           leer_plano: junta todo y comprueba contra las cotas
dialux/norma.py      requisitos_norma y buscar_en_norma: tablas de la UNE-EN 12464-1 desde el PDF
dialux/stf.py        escribir el STF que importa DIALux evo
dialux/construir.py  construir_edificio: del plano del examen al STF, una planta por fichero
salida/              los STF generados — no entra en git
pruebas/             pytest contra los exámenes reales (se saltan si no está material/)
material/            exámenes, norma y fichas de luminarias — NO entra en git
```

Pruebas: `.venv/bin/python -m pytest -q pruebas`. Cada número de `geometria.py` lleva al lado la
medición con los exámenes que lo justifica; si se cambia, se vuelve a medir.

Las fichas de luminarias de `material/luminarias/` son las hojas de datos PDF de
luminaires.dialux.com (flujo, potencia, montaje, medidas). **No traen la fotometría** (LDT/ULD),
que hará falta para calcular.

---

## 5. RECURSOS

- **Texturas para DIALux:** [Architextures](https://architextures.org). Es donde Marcos busca las
  texturas de los materiales (suelos, paredes, techos) para DIALux evo. Si un ejercicio pide un
  acabado concreto, recomendar buscarlo ahí antes que en otra web.
