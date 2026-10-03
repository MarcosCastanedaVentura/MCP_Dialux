# Estado del proyecto

Última actualización: **3/10/2026**. Rama actual: `feat/luminarias`.
Publicado en https://github.com/MarcosCastanedaVentura/MCP_Dialux (público, MIT).

**Pruebas: 49 pasan** (lanzadas hoy, 3/10/2026, `.venv/bin/python -m pytest -q pruebas`; tardan
menos de un segundo y no tocan la red ni ninguna API de pago). No hay nada en rojo ni ningún apaño
provisional en el código.

---

## Qué hace hoy

| Herramienta MCP | Estado |
|---|---|
| `leer_plano` | Funciona. Salas, medidas, columnas, huecos y los datos del enunciado escritos en el plano, comprobados contra las cotas |
| `construir_edificio` | Funciona. Un STF por ejercicio, con salas, altura, plano de trabajo, factor de mantenimiento, columnas y huecos |
| `requisitos_norma` / `buscar_en_norma` | Funcionan. UNE-EN 12464-1:2022 leída del PDF de Marcos, citando tabla, fila y página |
| `leer_stf` | Funciona. Qué contiene un STF sin abrir DIALux |
| `comparar_edificios` | Funciona. Compara dos edificios; cada uno puede ser `.stf` o el `.dwg` que exporta DIALux evo |
| `reticula_luminarias` | Funciona en el Mac. Reparte N luminarias en una sala: retícula, separación, distancia al muro y posiciones. **Sin probar en DIALux todavía** |

Comprobado importando en **DIALux evo 14** (máquina virtual): entran las salas con su contorno,
altura y plano de trabajo, las formas en L, el factor de mantenimiento y **las columnas** (24/9).

---

## Lo que falta: las luminarias

Son dos cosas distintas y solo está hecha la primera:

1. **Colocarlas** — HECHO el 3/10/2026 (`dialux/luminarias.py`). Se le dice cuántas van en cada
   sala y las reparte en la retícula más cuadrada que las contenga, con la luminaria en el centro
   de cada casilla (los bordes a media separación del muro). Si el número no forma retícula (7),
   sube al siguiente que sí y lo avisa, porque entonces hay más luz de la calculada. En una sala
   en L quita las posiciones que caen fuera y avisa de que el reparto ya no es regular. Van al
   STF una a una (`Lum<n>.Pos`), no como campo `Type=FIELD`: en un campo la especificación deja
   el reparto a DIALux y no se puede recortar. **Falta probar la importación en evo 14**: está
   generado `salida/plano-ejemplo.stf` con 12 luminarias en la oficina y 6 en archivos.
2. **Decidir cuántas** — el cálculo luminotécnico. **Bloqueado**, ver abajo.

### Bloqueado, hace falta que Marcos lo consiga

1. **La fotometría de las tres luminarias del parcial** (`.ldt` o `.ies`). Las fichas que hay en
   `material/luminarias/` son PDF y **no traen la curva de distribución**: sin ella no se puede
   calcular cuántas hacen falta. Caminos: "Enviar a DIALux" desde `luminaires.dialux.com` en la
   VM, o la web del fabricante (la primera es Endo Lighting, modelo `ERD7616S`).
2. **Ēm requerido o Ēm modificado**: la norma da los dos (Archivos, 200 lx o 300 lx) y de eso
   depende el número de luminarias. Marcos tiene que decir cuál usan en clase.
3. **Sin verificar**: si el DWG que exporta DIALux **trae las luminarias**. El proyecto que se
   exportó no tenía ninguna, así que no se sabe. Prueba: meter una luminaria en el ejemplo,
   exportar a `Z:\salida\prueba-export-con-luminaria.dwg` y mirar en qué capa aparece.

---

## Lo que se queda a mano en DIALux (y por qué)

No es del programa, es de lo que deja hacer el formato o el importador de evo. Todo comprobado
importando ficheros, y lo primero confirmado por el soporte de DIAL con la especificación oficial:

- **Subir cada planta a su nivel.** El STF no guarda el nivel de una sala. El fichero sale con las
  plantas separadas en X (múltiplo de 10 m, que la herramienta dice) y con la planta en el nombre
  de cada sala; en DIALux: duplicar planta, borrar las salas de las otras y restar el
  desplazamiento.
- **La zona marginal.** No existe en el formato. Sale en `a_mano` con el valor del enunciado.
- **Las puertas y ventanas.** Se escriben en el STF (correctas para DIALux 4) pero **evo las
  ignora**; salen en `a_mano` con posición, ancho, alto y alféizar.
- **Renombrar el edificio y la planta**, que DIALux llama "STF Building" y "STF Storey". El nombre
  del proyecto y los de las salas sí salen del fichero.

---

## Decisiones tomadas (no volver a discutirlas sin motivo nuevo)

- **Un ejercicio es un edificio**, y sus plantas son plantas del mismo edificio. Regla de Marcos.
- **Un solo fichero STF por ejercicio**, con las plantas separadas en el plano: importar un
  segundo STF *sustituye* el proyecto, y dos salas superpuestas se pierden.
- **Nada de automatizar la interfaz de DIALux**: es frágil y evo dibuja su propia interfaz, así
  que habría que ir por coordenadas de pantalla. Lo que ahorraría son dos minutos por ejercicio.
- **Nada de instalar DIALux 4** para aprovechar lo que evo no importa. Decisión de Marcos.
- **IFC descartado**: es de pago en evo, al importar y al exportar.
- **La norma se lee del PDF de Marcos**, no se copia al repositorio (licencia UPM). Única
  excepción: las filas que usan los exámenes, en `pruebas/test_norma.py`.
- **La especificación de STF no se sube**: el PDF que mandó DIAL va marcado como confidencial.
- **Los planos de clase no se publican**: son de la profesora. Por eso el repositorio trae
  `ejemplos/plano-ejemplo.dxf`, generado por `ejemplos/generar_plano_ejemplo.py`.
- **Rama por bloque de trabajo y fusión a `main`**. El historial se reescribió el 24/9 para que
  quedara así; los commits conservan sus mensajes y fechas (16–24/9).

---

## Siguientes pasos, por orden

1. **Importar `salida/plano-ejemplo.stf` en evo 14** y mirar tres cosas: si las luminarias
   aparecen, en qué sitio, y como qué (se espera un marcador sin fotometría, porque la
   especificación dice que evo ignora los datos de la luminaria al importar). De ahí sale si hay
   que cambiar algo o si vale como está.
2. **Conseguir la fotometría** y decidir requerido/modificado, para pasar de colocar a calcular
   cuántas.
3. **Comprobar si el DWG exportado trae luminarias**, para poder comparar las del alumno con las
   calculadas.
4. **Cuando haya fotometría**: cálculo del número de luminarias por el método de los lúmenes,
   contraste con lo que exige la norma, y comprobar la separación contra el criterio de la
   luminaria (ahora solo se devuelve la relación separación / altura útil, sin juzgarla).

### Recordatorio al terminar algo en el Mac

El código llega solo a Windows por la carpeta compartida `Z:`, pero hay que **reiniciar Claude
Desktop en Windows** si se tocó `server.py` o un módulo que use, y reinstalar el entorno si cambió
`requirements.txt`.
