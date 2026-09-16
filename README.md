# MCP_Dialux

Servidor MCP que resuelve ejercicios de iluminación de DIALux evo de clase, para comprobar la
solución propia.

Herramientas disponibles:

| Herramienta | Qué hace |
|---|---|
| `leer_plano` | DWG/DXF → plantas, salas, medidas, columnas y los datos del enunciado escritos en el plano, comprobados contra las cotas |
| `requisitos_norma` | Referencia de tabla ("34.7") → Ēm, Uo, Ra, RUGL… de la UNE-EN 12464-1:2022, con tabla, fila y página |
| `buscar_en_norma` | Texto ("enfermería") → filas de la norma que encajan |

## Requisitos

- Python 3.12 o superior
- [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter), para leer DWG
- El PDF de la UNE-EN 12464-1:2022 en `material/norma/` (no está en el repositorio)

## Instalar

### En el Mac

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q pruebas
```

### En Windows (máquina virtual)

La carpeta del proyecto está en el Mac y Windows la ve como la unidad de red `Z:` (compartida
por SMB desde el Mac, en `\\192.168.110.1\MCP_Dialux`, la red interna de VMware, que no cambia al
cambiar de wifi).

El entorno de Python **no va en `Z:`**: instalar librerías sobre una unidad de red es lento y
puede fallar. Va en el disco de Windows, y el código se lee de `Z:`.

```powershell
py -m venv $HOME\.venvs\mcp_dialux
~\.venvs\mcp_dialux\Scripts\pip install -r Z:\requirements.txt
cd Z:\
~\.venvs\mcp_dialux\Scripts\python -m pytest -q pruebas
```

## Conectar con Claude Desktop

Abre Claude Desktop → *Ajustes → Desarrollador → Editar configuración* y añade el servidor a
`claude_desktop_config.json`. Después, cierra Claude Desktop del todo y vuelve a abrirlo.

**Mac** (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "dialux": {
      "command": "/Users/marcos/Desktop/Proyectos/MCP_Dialux/.venv/bin/python",
      "args": ["/Users/marcos/Desktop/Proyectos/MCP_Dialux/server.py"]
    }
  }
}
```

**Windows** (`%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "dialux": {
      "command": "C:\\Users\\marco\\.venvs\\mcp_dialux\\Scripts\\python.exe",
      "args": ["Z:\\server.py"]
    }
  }
}
```

Si ODA File Converter no está en su sitio habitual, añade al servidor
`"env": {"ODA_FILE_CONVERTER": "ruta al ejecutable"}`.
