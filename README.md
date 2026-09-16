# MCP_Dialux

Servidor MCP que resuelve ejercicios de iluminación de DIALux evo de clase, para comprobar la
solución propia.

Herramientas disponibles:

| Herramienta | Qué hace |
|---|---|
| `leer_plano` | DWG/DXF → plantas, salas, medidas, columnas y los datos del enunciado escritos en el plano, comprobados contra las cotas |

## Requisitos

- Python 3.12 o superior
- [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter), para leer DWG

## Instalar

### En el Mac

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q pruebas
```

### En Windows (máquina virtual)

La carpeta del proyecto se comparte con el Mac, así que el entorno de Windows va en **otra**
carpeta, `.venv-windows`: si los dos se llamaran `.venv`, cada sistema rompería el del otro.

```powershell
py -m venv .venv-windows
.venv-windows\Scripts\pip install -r requirements.txt
.venv-windows\Scripts\python -m pytest -q pruebas
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

**Windows** (`%APPDATA%\Claude\claude_desktop_config.json`). Cambia `Z:\\MCP_Dialux` por la ruta
donde aparezca la carpeta compartida:

```json
{
  "mcpServers": {
    "dialux": {
      "command": "Z:\\MCP_Dialux\\.venv-windows\\Scripts\\python.exe",
      "args": ["Z:\\MCP_Dialux\\server.py"]
    }
  }
}
```

Si ODA File Converter no está en su sitio habitual, añade al servidor
`"env": {"ODA_FILE_CONVERTER": "ruta al ejecutable"}`.
