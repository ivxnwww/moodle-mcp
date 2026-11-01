# moodle-mcp

Servidor [MCP](https://modelcontextprotocol.io) que conecta Claude (u otro cliente MCP) con tu cuenta de estudiante en cualquier Moodle. Con él puedes preguntar por tus cursos, entregas pendientes, calificaciones y avisos, descargar materiales, participar en foros y subir tareas, todo desde el chat.

Usa la API oficial de Web Services de Moodle, la misma que usa la app móvil, así que funciona en cualquier sitio que tenga la app móvil habilitada.

## Herramientas

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

> [!WARNING]
> Las herramientas en negritas hacen cambios que ven tus profesores y compañeros. El servidor le indica al modelo que te muestre lo que va a enviar y te pida confirmación antes de usarlas, pero revisa siempre lo que apruebas.

## Requisitos

- Python 3.10 o superior
- Una cuenta en un Moodle que tenga habilitada la app móvil (servicio `moodle_mobile_app`)

## Instalación

```sh
git clone https://github.com/ivxnwww/moodle-mcp.git
cd moodle-mcp
python -m venv .venv
```

Activa el entorno e instala las dependencias:

```sh
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Configuración

### 1. Consigue tu token

Cambia la URL por la de tu Moodle y pon tu usuario y contraseña:

```sh
curl -s -X POST https://moodle.tu-escuela.edu/login/token.php \
  --data-urlencode "username=TU_USUARIO" \
  --data-urlencode "password=TU_CONTRASEÑA" \
  --data-urlencode "service=moodle_mobile_app"
```

La respuesta trae un campo `token`. Guárdalo en `~/.moodle_token` (un archivo con solo el token) o pásalo en la variable `MOODLE_TOKEN`.

> [!CAUTION]
> El token da acceso completo a tu cuenta. No lo subas a ningún repositorio ni lo compartas.

Si tu escuela entra con inicio de sesión único (SSO, Google, Microsoft), este método no funciona. En ese caso puedes sacar el token desde la app móvil o pedirlo en **Preferencias → Claves de seguridad** dentro de Moodle, si tu sitio lo permite.

### 2. Variables de entorno

| Variable | Obligatoria | Qué es |
|---|---|---|
| `MOODLE_URL` | Sí | Dirección de tu Moodle, p. ej. `https://moodle.tu-escuela.edu` |
| `MOODLE_TOKEN` | No | Token; si no está, se lee de `MOODLE_TOKEN_FILE` |
| `MOODLE_TOKEN_FILE` | No | Archivo con el token (por defecto `~/.moodle_token`) |
| `MOODLE_DOWNLOAD_DIR` | No | Carpeta de descargas (por defecto `~/Downloads/Moodle`) |

## Uso con Claude

### Claude Code

Usa las rutas completas de tu instalación:

```sh
claude mcp add --scope user moodle \
  -e MOODLE_URL=https://moodle.tu-escuela.edu \
  -- /ruta/a/moodle-mcp/.venv/bin/python /ruta/a/moodle-mcp/server.py
```

En Windows, el intérprete está en `.venv\Scripts\python.exe`.

### Claude Desktop

Agrega esto a `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "moodle": {
      "command": "/ruta/a/moodle-mcp/.venv/bin/python",
      "args": ["/ruta/a/moodle-mcp/server.py"],
      "env": { "MOODLE_URL": "https://moodle.tu-escuela.edu" }
    }
  }
}
```

Después reinicia Claude y prueba con algo como *"¿qué tareas tengo pendientes esta semana?"*.

## Notas

- Lo que puedes ver y hacer depende de los permisos que tu escuela dé a la app móvil. Si una función está desactivada, Moodle responde con un error y el servidor lo muestra tal cual.
- Si el servidor de Moodle no responde, se reintenta hasta tres veces antes de fallar.
- No es un proyecto oficial de Moodle. Úsalo de acuerdo con las reglas de tu institución.

## Licencia

[MIT](LICENSE)
