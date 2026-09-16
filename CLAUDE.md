# MCP_Dialux — corrector de ejercicios de DIALux evo

Servidor MCP (Python, SDK `mcp` 2.x con `MCPServer`) que resuelve **entero** un ejercicio de iluminación de clase a
partir del plano DWG y las luminarias que da el enunciado, para que Marcos compare con su propia
solución.

**Para qué es:** uso personal en clase. Marcos hace el ejercicio por su cuenta en DIALux y después
se lo pasa al MCP para verificar que lo tiene bien. No es un producto para vender.

De ahí salen las prioridades: **que acierte y que explique por qué**, no que sea bonito ni que
escale. Una solución del MCP que esté mal y parezca bien es peor que no tener MCP, porque Marcos se
"corregiría" hacia el error.

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
   - El entorno **no se copia**: se recrea en cada máquina desde `requirements.txt`. Como la carpeta
     se comparte con la VM, el de Windows se llama `.venv-windows`; con el mismo nombre, cada
     sistema rompería el entorno del otro.
   - Lo que solo tiene sentido en Windows (automatizar la ventana de DIALux) va aislado en su
     propio módulo y se importa solo en Windows, para que el resto arranque en el Mac.

3. **No inventar datos de norma ni de luminarias.** Los valores exigidos por la UNE-EN 12464-1
   (Em, UGRL, U₀, Ra por tipo de tarea) salen de la copia de la norma de Marcos, leídos de su PDF, y
   se enseña de qué fila salen para que se pueda revisar. Los datos fotométricos salen del fichero de la luminaria (LDT/ULD/
   IES), nunca de memoria. Si falta un dato, se pide; no se supone.

---

## 2. CÓMO SE TRABAJA AQUÍ

- **Probar con los exámenes reales** de `material/examenes/`, no con planos inventados. Los planos
  de clase son de la profesora (AutoCAD 2023/2024) y son los que hay que saber leer.
- **Verificar antes de construir** lo que no se sabe seguro. En concreto, qué formatos de
  intercambio importa de verdad la versión de DIALux evo de Marcos (STF es del DIALux clásico 4.x;
  no está comprobado que evo lo acepte). Se prueba un fichero de ejemplo en la VM antes de escribir
  el generador.
- **Decir lo que no funciona** y lo que está sin verificar. Marcos es estudiante de Ingeniería
  Alimentaria, no programador: explicar el porqué en términos de iluminación y de uso, no solo de
  código.
- **Git:** rama antes de commitear, nunca directo a `main`.

---

## 3. LO QUE SE SABE DEL MATERIAL (16/9/2026)

- Los tres DWG son formato **AC1032** (AutoCAD 2018 en adelante), comprimidos. `ezdxf` no lee DWG:
  hay que convertirlos a DXF antes con ODA File Converter (instalado en el Mac el 16/9/2026).
  **En macOS `ezdxf` no lo encuentra solo**: hay que darle la ruta
  `/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter` con
  `ezdxf.options.set("odafc-addon", "unix_exec_path", …)`. Lo hace `convertir.py`. En Windows lo
  busca en `Program Files\ODA\ODAFileConverter*`: **sin probar todavía en la VM**.
- **El enunciado va DENTRO del plano**, como texto: altura de sala, espesor de pared, altura del
  plano de trabajo, zona marginal, factor de mantenimiento, reflectancias y tipo de actividad. Es
  la fuente de datos del ejercicio; no hay que pedírselo aparte a Marcos.
- En el examen de junio cada zona lleva un código delante del uso ("34.2 Oficina…", "10.7 Sala para
  atención médica", "9.4" zona frente al ascensor). **Confirmado:** es `tabla.fila` de la
  UNE-EN 12464-1:2022 (34.7 = tabla 34 Oficinas, fila Archivos).
- **La norma es la copia de Marcos** (`material/norma/AlumbradoInterior-2022.pdf`), con licencia
  de la UPM por AENORmás para uso interno. Los valores exigidos (Em, U₀, Ra, RUGL…) se leen de
  ese PDF al usarlos; **no se transcriben a un fichero del repo** ni se publican.
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
- La máquina virtual es **VMware Fusion con Windows 11 ARM** (Mac con chip Apple). Consecuencias:
  - ODA File Converter solo sale para Windows x64: en ARM corre emulado. Sin probar.
  - Si alguna librería no trae versión para Windows ARM (`shapely` es la candidata), instalar el
    Python **x64** de python.org, que Windows 11 ARM también emula.
  - El proyecto se comparte con Windows por carpeta compartida, no copiándolo. La carpeta
    compartida necesita VMware Tools instalado en Windows (pendiente a 16/9/2026).

---

## 4. ESTRUCTURA

```
server.py            el servidor MCP: solo declara herramientas
dialux/cad/
  convertir.py       DWG -> DXF con ODA, Mac y Windows (caché en cache/dxf por hash)
  geometria.py       reconstruir salas: cerrar huecos, poligonizar, separar muros de salas
  enunciado.py       leer los datos del ejercicio de los textos del plano
  plano.py           leer_plano: junta todo y comprueba contra las cotas
pruebas/             pytest contra los exámenes reales (se saltan si no está material/)
material/            exámenes, norma y fichas de luminarias — NO entra en git
```

Pruebas: `.venv/bin/python -m pytest -q pruebas`. Cada número de `geometria.py` lleva al lado la
medición con los exámenes que lo justifica; si se cambia, se vuelve a medir.

Las fichas de luminarias de `material/luminarias/` son las hojas de datos PDF de
luminaires.dialux.com (flujo, potencia, montaje, medidas). **No traen la fotometría** (LDT/ULD),
que hará falta para calcular.
