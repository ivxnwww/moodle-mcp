# moodle-mcp

Servidor [MCP](https://modelcontextprotocol.io) que conecta Claude con tu cuenta de estudiante en Moodle. Con él le puedes preguntar a Claude por tus cursos, entregas pendientes, calificaciones y avisos, pedirle que descargue materiales, que publique en foros o que suba tus tareas.

Funciona con cualquier Moodle que tenga habilitada la app móvil, porque usa la misma API oficial que ella.

## Cómo se usa

Le hablas a Claude como a cualquier persona. **No necesitas saber IDs ni nombres de funciones**: Claude busca solo el curso, el foro o la tarea de la que hablas.

Algunos ejemplos:

- *"¿Qué tengo pendiente esta semana?"*
- *"¿Cómo voy en Estadística? Dame mis calificaciones por actividad."*
- *"¿Ya entregué el reporte 3 de Marketing? ¿El profe dejó comentarios?"*
- *"Descarga todo el material de Analítica Predictiva."*
- *"¿Qué avisos ha publicado el profesor de Ética esta semana?"*
- *"Resúmeme las instrucciones de la Entrega Unidad III."*
- *"Publica en el foro de dudas de Finanzas un post con el asunto 'Duda sobre VPN' preguntando cómo se elige la tasa de descuento."*
- *"Sube `C:\Users\yo\Documents\reporte.pdf` a la tarea Reporte de lectura 4."*

Por ejemplo, cuando le pides publicar en un foro, Claude:

1. Busca el curso entre tus cursos.
2. Busca el foro por su nombre y revisa si puedes publicar en él.
3. Redacta el asunto y el mensaje a partir de lo que le pediste.
4. **Te muestra el texto exacto y espera tu aprobación.**
5. Solo entonces lo publica.

> [!WARNING]
> Publicar en foros, responder y subir entregas son acciones que ven tus profesores y compañeros. Claude siempre te pide confirmación antes de hacerlas, pero lee bien lo que apruebas. Una entrega nueva **reemplaza** los archivos que ya hubieras subido a esa tarea.

## Instalación

Necesitas:

- **Python 3.10 o superior**
- **Claude Code o Claude Desktop**
- Tu **usuario y contraseña** de Moodle, y la dirección de tu Moodle (p. ej. `https://mi.cugdl.udg.mx`)

En los pasos se usa `https://mi.cugdl.udg.mx` (Moodle de CUGDL, UdeG) como ejemplo. Si tu escuela es otra, cámbiala por la dirección de tu Moodle.

### Windows

Todos los comandos son para **PowerShell** (búscalo en el menú Inicio).

**1. Instala Python.** Descárgalo de [python.org](https://www.python.org/downloads/) y, en el instalador, marca **"Add python.exe to PATH"**. Comprueba que quedó instalado:

```powershell
py --version
```

**2. Descarga el proyecto** en tu carpeta de usuario:

```powershell
cd $HOME
git clone https://github.com/ivxnwww/moodle-mcp.git
cd moodle-mcp
```

Si no tienes git, en GitHub ve a **Code → Download ZIP**, descomprímelo en tu carpeta de usuario y cambia el nombre de la carpeta `moodle-mcp-main` a `moodle-mcp`.

**3. Instala las dependencias:**

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**4. Consigue tu token de Moodle y guárdalo.** Cambia la dirección, el usuario y la contraseña:

```powershell
$r = Invoke-RestMethod -Method Post -Uri "https://mi.cugdl.udg.mx/login/token.php" -Body @{
  username = "TU_USUARIO"; password = "TU_CONTRASEÑA"; service = "moodle_mobile_app"
}
$r
```

Si en la respuesta aparece un `token`, guárdalo:

```powershell
$r.token | Set-Content -NoNewline "$HOME\.moodle_token"
```

Si en cambio aparece un `error`, revisa [Problemas comunes](#problemas-comunes).

**5. Prueba que funciona:**

```powershell
$env:MOODLE_URL = "https://mi.cugdl.udg.mx"
.venv\Scripts\python.exe -c "import server; print(server.info_usuario())"
```

Debe mostrar tu nombre y el de tu escuela.

**6. Conéctalo con Claude.**

- **Claude Code:**

  ```powershell
  claude mcp add --scope user moodle -e MOODLE_URL=https://mi.cugdl.udg.mx -- "$HOME\moodle-mcp\.venv\Scripts\python.exe" "$HOME\moodle-mcp\server.py"
  ```

- **Claude Desktop:** abre **Configuración → Desarrollador → Editar configuración** (el archivo es `%APPDATA%\Claude\claude_desktop_config.json`) y agrega esto. Cambia `TU_USUARIO_DE_WINDOWS` y usa `/` en las rutas:

  ```json
  {
    "mcpServers": {
      "moodle": {
        "command": "C:/Users/TU_USUARIO_DE_WINDOWS/moodle-mcp/.venv/Scripts/python.exe",
        "args": ["C:/Users/TU_USUARIO_DE_WINDOWS/moodle-mcp/server.py"],
        "env": { "MOODLE_URL": "https://mi.cugdl.udg.mx" }
      }
    }
  }
  ```

**7. Reinicia Claude** y pregúntale *"¿qué tengo pendiente esta semana?"*.

### macOS

Todos los comandos son para la app **Terminal**.

**1. Instala Python.** Comprueba qué versión tienes:

```sh
python3 --version
```

Si dice 3.9 o menos, o no lo encuentra, instala la versión más reciente desde [python.org](https://www.python.org/downloads/) o con Homebrew (`brew install python`).

**2. Descarga el proyecto** en tu carpeta de usuario:

```sh
cd ~
git clone https://github.com/ivxnwww/moodle-mcp.git
cd moodle-mcp
```

Si macOS te pide instalar las herramientas de desarrollo para usar `git`, acepta. También puedes ir a **Code → Download ZIP** en GitHub, descomprimirlo en tu carpeta de usuario y cambiar el nombre de la carpeta `moodle-mcp-main` a `moodle-mcp`.

**3. Instala las dependencias:**

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

**4. Consigue tu token de Moodle.** Cambia la dirección, el usuario y la contraseña:

```sh
curl -s -X POST https://mi.cugdl.udg.mx/login/token.php \
  --data-urlencode "username=TU_USUARIO" \
  --data-urlencode "password=TU_CONTRASEÑA" \
  --data-urlencode "service=moodle_mobile_app"
```

Si la respuesta trae un `"token"`, copia el valor (sin comillas) y guárdalo:

```sh
echo "PEGA_AQUI_TU_TOKEN" > ~/.moodle_token
chmod 600 ~/.moodle_token
```

Si en cambio aparece un `"error"`, revisa [Problemas comunes](#problemas-comunes).

**5. Prueba que funciona:**

```sh
MOODLE_URL=https://mi.cugdl.udg.mx .venv/bin/python -c "import server; print(server.info_usuario())"
```

Debe mostrar tu nombre y el de tu escuela.

**6. Conéctalo con Claude.**

- **Claude Code:**

  ```sh
  claude mcp add --scope user moodle -e MOODLE_URL=https://mi.cugdl.udg.mx -- "$HOME/moodle-mcp/.venv/bin/python" "$HOME/moodle-mcp/server.py"
  ```

- **Claude Desktop:** abre **Configuración → Desarrollador → Editar configuración** (el archivo es `~/Library/Application Support/Claude/claude_desktop_config.json`) y agrega esto. Cambia `TU_USUARIO_DE_MAC` (lo ves con `whoami`):

  ```json
  {
    "mcpServers": {
      "moodle": {
        "command": "/Users/TU_USUARIO_DE_MAC/moodle-mcp/.venv/bin/python",
        "args": ["/Users/TU_USUARIO_DE_MAC/moodle-mcp/server.py"],
        "env": { "MOODLE_URL": "https://mi.cugdl.udg.mx" }
      }
    }
  }
  ```

**7. Reinicia Claude** y pregúntale *"¿qué tengo pendiente esta semana?"*.

> [!CAUTION]
> El token da acceso completo a tu cuenta de Moodle. No lo compartas ni lo subas a ningún repositorio. Si crees que alguien lo vio, cambia tu contraseña de Moodle y genera uno nuevo.

## Problemas comunes

| Mensaje | Qué significa | Qué hacer |
|---|---|---|
| `invalidlogin` | Usuario o contraseña incorrectos | Revisa que sean los mismos con los que entras a Moodle |
| `enablewsdescription` o `servicenotavailable` | Tu escuela no tiene habilitada la app móvil | No hay solución desde tu lado; pregunta a soporte de tu escuela |
| `Falta MOODLE_URL` | No configuraste la dirección de tu Moodle | Agrega `MOODLE_URL` en el paso 6 |
| `No hay token de Moodle` | No existe `~/.moodle_token` | Repite el paso 4 |
| `invalidtoken` | El token expiró o se revocó | Repite el paso 4 para sacar uno nuevo |
| Claude no ve las herramientas | Claude no ha recargado la configuración | Cierra y abre Claude por completo |

**Si entras a Moodle con Google, Microsoft u otro inicio de sesión único**, el paso 4 no funciona porque no tienes contraseña de Moodle. Busca tu token en Moodle, en **Preferencias → Claves de seguridad**, si tu escuela lo permite.

## Configuración

| Variable | Obligatoria | Qué es |
|---|---|---|
| `MOODLE_URL` | Sí | Dirección de tu Moodle, p. ej. `https://mi.cugdl.udg.mx` |
| `MOODLE_TOKEN` | No | Token; si no está, se lee de `MOODLE_TOKEN_FILE` |
| `MOODLE_TOKEN_FILE` | No | Archivo con el token (por defecto `~/.moodle_token`) |
| `MOODLE_DOWNLOAD_DIR` | No | Carpeta de descargas (por defecto `~/Downloads/Moodle`) |

## Herramientas

Referencia técnica de lo que Claude puede usar. No necesitas escribir estos nombres; Claude los elige según lo que le pidas.

| Herramienta | Qué hace |
|---|---|
| `info_usuario` | Datos de la cuenta conectada y versión de Moodle |
| `mis_cursos` | Cursos inscritos con ID y progreso |
| `pendientes(dias)` | Actividades que vencen en los próximos días |
| `contenido_curso(curso_id)` | Secciones, actividades y archivos de un curso |
| `tareas(curso_id?)` | Tareas con fechas e instrucciones |
| `estado_tarea(tarea_id)` | Si se entregó, archivos enviados, calificación y comentarios |
| `calificaciones(curso_id?)` | Resumen por curso o detalle por actividad |
| `avisos(curso_id)` | Últimas discusiones de los foros del curso |
| `descargar_archivo(fileurl)` | Descarga un archivo |
| `descargar_materiales_curso(curso_id)` | Descarga todo el material de un curso, por sección |
| `foros(curso_id)` | Foros del curso, con ID y si puedes publicar |
| `leer_discusion(discusion_id)` | Mensajes de una discusión, con su `post_id` |
| `publicar_en_foro(foro_id, asunto, mensaje, archivos?)` | **Publica** una discusión nueva |
| `responder_en_foro(post_id, mensaje, asunto?, archivos?)` | **Publica** una respuesta |
| `subir_entrega(tarea_id, archivos?, texto?, enviar_para_calificar?)` | **Entrega** una tarea (reemplaza los archivos previos) |
| `llamar_api(funcion, parametros)` | Llama cualquier función de la API de Moodle |

Las herramientas en negritas hacen cambios visibles para otros.

## Notas

- Lo que puedes ver y hacer depende de los permisos que tu escuela dé a la app móvil. Si una función está desactivada, Moodle responde con un error y Claude te lo dirá.
- Si el servidor de Moodle no responde, se reintenta hasta tres veces antes de fallar.
- No es un proyecto oficial de Moodle. Úsalo de acuerdo con las reglas de tu institución.

## Licencia

[MIT](LICENSE)
