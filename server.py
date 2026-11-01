"""Servidor MCP para cualquier Moodle usando la API de Web Services."""

import html
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from mcp.server import MCPServer
from mcp.types import ToolAnnotations

MOODLE_URL = os.environ.get("MOODLE_URL", "").rstrip("/")
TOKEN_FILE = Path(os.environ.get("MOODLE_TOKEN_FILE", Path.home() / ".moodle_token"))
DOWNLOAD_DIR = Path(os.environ.get("MOODLE_DOWNLOAD_DIR", Path.home() / "Downloads" / "Moodle"))

mcp = MCPServer(
    "moodle",
    instructions=(
        "Acceso al Moodle del estudiante. Usa mis_cursos para obtener "
        "los IDs de curso y pendientes para ver entregas próximas. subir_entrega, "
        "publicar_en_foro y responder_en_foro son visibles para profesores y compañeros: "
        "muestra al usuario exactamente qué se enviará y pide su confirmación antes de usarlas."
    ),
)

# Herramientas que publican algo visible para otros en Moodle.
PUBLICA = ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=True)

_userid: int | None = None
logging.getLogger("httpx").setLevel(logging.WARNING)


def _url() -> str:
    if not MOODLE_URL:
        raise RuntimeError("Falta MOODLE_URL, la dirección de tu Moodle (p. ej. https://moodle.tu-escuela.edu).")
    return MOODLE_URL


def _token() -> str:
    token = os.environ.get("MOODLE_TOKEN") or (TOKEN_FILE.read_text().strip() if TOKEN_FILE.exists() else "")
    if not token:
        raise RuntimeError(f"No hay token de Moodle. Define MOODLE_TOKEN o crea {TOKEN_FILE}.")
    return token


def _flatten(params: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Convierte dicts/listas anidados al formato de Moodle: courseids[0]=1, options[0][name]=x."""
    flat: dict[str, Any] = {}
    for key, value in params.items():
        name = f"{prefix}[{key}]" if prefix else str(key)
        if isinstance(value, dict):
            flat.update(_flatten(value, name))
        elif isinstance(value, (list, tuple)):
            flat.update(_flatten(dict(enumerate(value)), name))
        elif isinstance(value, bool):
            flat[name] = int(value)
        elif value is not None:
            flat[name] = value
    return flat


def _call(function: str, **params: Any) -> Any:
    data = {"wstoken": _token(), "moodlewsrestformat": "json", "wsfunction": function, **_flatten(params)}
    # Algunos servidores de Moodle dejan de responder unos segundos; reintenta solo errores de conexión.
    for intento in range(3):
        try:
            resp = httpx.post(f"{_url()}/webservice/rest/server.php", data=data, timeout=httpx.Timeout(60, connect=15))
            break
        except (httpx.ConnectError, httpx.ConnectTimeout):
            if intento == 2:
                raise RuntimeError(f"No se pudo conectar con {MOODLE_URL}; el servidor de Moodle no responde.") from None
            time.sleep(5 * (intento + 1))
    resp.raise_for_status()
    result = resp.json()
    if isinstance(result, dict) and "exception" in result:
        raise RuntimeError(f"Moodle: {result.get('errorcode')}: {result.get('message')}")
    return result


def _me() -> int:
    global _userid
    if _userid is None:
        _userid = _call("core_webservice_get_site_info")["userid"]
    return _userid


def _fecha(ts: int | None) -> str | None:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else None


def _texto(contenido: str | None) -> str:
    """Quita etiquetas HTML para devolver texto legible."""
    if not contenido:
        return ""
    text = re.sub(r"<(br|/p|/li|/div|/h\d)[^>]*>", "\n", contenido, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).replace("\xa0", " ")
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def _nombre_seguro(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip() or "archivo"


def _a_html(texto: str) -> str:
    """Texto plano a HTML con párrafos; si ya trae etiquetas HTML se deja igual."""
    if re.search(r"<(p|br|div|ul|ol|strong|em|h\d)\b", texto, flags=re.I):
        return texto
    parrafos = [p.strip() for p in re.split(r"\n\s*\n", texto) if p.strip()]
    return "".join(f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>" for p in parrafos)


def _subir_borrador(rutas: list[str]) -> int:
    """Sube archivos locales al área de borradores del usuario y devuelve el itemid."""
    itemid = 0
    for ruta in rutas:
        path = Path(ruta).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"No existe el archivo: {path}")
        with open(path, "rb") as f:
            resp = httpx.post(
                f"{_url()}/webservice/upload.php",
                data={"token": _token(), "filearea": "draft", "itemid": itemid},
                files={"file_1": (path.name, f)},
                timeout=600,
            )
        resp.raise_for_status()
        result = resp.json()
        if isinstance(result, dict) and ("error" in result or "exception" in result):
            raise RuntimeError(f"Error al subir {path.name}: {result.get('error') or result.get('message')}")
        itemid = result[0]["itemid"]
    return itemid


def _descargar(fileurl: str, destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    sep = "&" if "?" in fileurl else "?"
    with httpx.stream("GET", f"{fileurl}{sep}token={_token()}", timeout=300, follow_redirects=True) as resp:
        resp.raise_for_status()
        with open(destino, "wb") as f:
            for chunk in resp.iter_bytes():
                f.write(chunk)
    return destino


@mcp.tool()
def info_usuario() -> dict:
    """Datos de la cuenta conectada: nombre, usuario y versión de Moodle."""
    info = _call("core_webservice_get_site_info")
    return {k: info.get(k) for k in ("fullname", "username", "userid", "sitename", "release")}


@mcp.tool()
def mis_cursos() -> list[dict]:
    """Lista los cursos en los que está inscrito el estudiante, con su ID y progreso."""
    cursos = _call("core_enrol_get_users_courses", userid=_me())
    return [
        {
            "id": c["id"],
            "nombre": c["fullname"],
            "nombre_corto": c["shortname"],
            "progreso": c.get("progress"),
            "inicio": _fecha(c.get("startdate")),
            "fin": _fecha(c.get("enddate")),
            "ultimo_acceso": _fecha(c.get("lastaccess")),
        }
        for c in cursos
    ]


@mcp.tool()
def pendientes(dias: int = 30) -> list[dict]:
    """Actividades con fecha de entrega en los próximos `dias` días (tareas, quizzes, foros...)."""
    ahora = int(time.time())
    eventos = _call(
        "core_calendar_get_action_events_by_timesort",
        timesortfrom=ahora - 86400,
        timesortto=ahora + dias * 86400,
        limitnum=50,
    ).get("events", [])
    return [
        {
            "fecha": _fecha(e["timesort"]),
            "curso": (e.get("course") or {}).get("fullname"),
            "curso_id": (e.get("course") or {}).get("id"),
            "actividad": e.get("name"),
            "tipo": e.get("modulename"),
            "instancia_id": e.get("instance"),
            "vencida": e["timesort"] < ahora,
            "url": e.get("url"),
        }
        for e in eventos
    ]


@mcp.tool()
def contenido_curso(curso_id: int) -> list[dict]:
    """Secciones, actividades y archivos de un curso (temas, recursos, enlaces, tareas)."""
    secciones = _call("core_course_get_contents", courseid=curso_id)
    resultado = []
    for s in secciones:
        modulos = []
        for m in s.get("modules", []):
            if not m.get("uservisible", True):
                continue
            modulos.append(
                {
                    "id": m["id"],
                    "nombre": m["name"],
                    "tipo": m["modname"],
                    "instancia_id": m.get("instance"),
                    "descripcion": _texto(m.get("description"))[:500] or None,
                    "url": m.get("url"),
                    "archivos": [
                        {"nombre": c["filename"], "tamano": c.get("filesize"), "fileurl": c["fileurl"]}
                        for c in m.get("contents", [])
                        if c.get("type") == "file"
                    ],
                    "enlace_externo": next(
                        (c["fileurl"] for c in m.get("contents", []) if c.get("type") == "url"), None
                    ),
                }
            )
        resultado.append({"seccion": s["name"], "resumen": _texto(s.get("summary"))[:500] or None, "modulos": modulos})
    return resultado


@mcp.tool()
def tareas(curso_id: int | None = None) -> list[dict]:
    """Tareas (assignments) de un curso o de todos, con fechas, instrucciones y estado de entrega."""
    params = {"courseids": [curso_id]} if curso_id else {}
    cursos = _call("mod_assign_get_assignments", **params).get("courses", [])
    resultado = []
    for c in cursos:
        for a in c.get("assignments", []):
            resultado.append(
                {
                    "tarea_id": a["id"],
                    "curso": c["fullname"],
                    "nombre": a["name"],
                    "abre": _fecha(a.get("allowsubmissionsfromdate")),
                    "vence": _fecha(a.get("duedate")),
                    "cierre": _fecha(a.get("cutoffdate")),
                    "calificacion_max": a.get("grade"),
                    "instrucciones": _texto(a.get("intro"))[:1500],
                    "archivos_adjuntos": [f["filename"] for f in a.get("introattachments", [])],
                }
            )
    return resultado


@mcp.tool()
def estado_tarea(tarea_id: int) -> dict:
    """Estado detallado de una tarea: si ya se entregó, archivos enviados, calificación y comentarios."""
    st = _call("mod_assign_get_submission_status", assignid=tarea_id)
    envio = (st.get("lastattempt") or {}).get("submission") or {}
    archivos = []
    texto_enviado = None
    for plugin in envio.get("plugins", []):
        for area in plugin.get("fileareas", []):
            archivos += [f["filename"] for f in area.get("files", [])]
        for campo in plugin.get("editorfields", []):
            texto_enviado = _texto(campo.get("text")) or texto_enviado
    feedback = st.get("feedback") or {}
    comentarios = [
        _texto(campo.get("text"))
        for plugin in feedback.get("plugins", [])
        for campo in plugin.get("editorfields", [])
        if campo.get("text")
    ]
    return {
        "estado_envio": envio.get("status"),  # new / draft / submitted
        "modificado": _fecha(envio.get("timemodified")),
        "calificado": (st.get("lastattempt") or {}).get("gradingstatus"),
        "archivos_enviados": archivos,
        "texto_enviado": texto_enviado,
        "calificacion": feedback.get("gradefordisplay"),
        "comentarios_profesor": comentarios,
    }


@mcp.tool()
def calificaciones(curso_id: int | None = None) -> list[dict]:
    """Calificaciones. Sin curso_id: resumen por curso. Con curso_id: detalle por actividad."""
    if curso_id is None:
        nombres = {c["id"]: c["fullname"] for c in _call("core_enrol_get_users_courses", userid=_me())}
        grades = _call("gradereport_overview_get_course_grades", userid=_me()).get("grades", [])
        return [
            {"curso_id": g["courseid"], "curso": nombres.get(g["courseid"]), "calificacion": g.get("grade")}
            for g in grades
        ]
    reporte = _call("gradereport_user_get_grade_items", courseid=curso_id, userid=_me())
    items = (reporte.get("usergrades") or [{}])[0].get("gradeitems", [])
    return [
        {
            "actividad": i.get("itemname") or ("Total del curso" if i.get("itemtype") == "course" else i.get("itemtype")),
            "calificacion": _texto(i.get("gradeformatted")),
            "rango": _texto(i.get("rangeformatted")),
            "porcentaje": i.get("percentageformatted"),
            "comentario": _texto(i.get("feedback")) or None,
        }
        for i in items
    ]


@mcp.tool()
def avisos(curso_id: int, limite: int = 10) -> list[dict]:
    """Últimas discusiones de los foros de un curso (avisos del profesor, foros de dudas, etc.)."""
    foros = _call("mod_forum_get_forums_by_courses", courseids=[curso_id])
    resultado = []
    for f in foros:
        discusiones = _call(
            "mod_forum_get_forum_discussions", forumid=f["id"], sortorder=1, perpage=limite
        ).get("discussions", [])
        for d in discusiones:
            resultado.append(
                {
                    "foro": f["name"],
                    "foro_id": f["id"],
                    "discusion_id": d.get("discussion"),
                    "post_id": d.get("id"),
                    "titulo": d.get("name"),
                    "autor": d.get("userfullname"),
                    "fecha": _fecha(d.get("created")),
                    "mensaje": _texto(d.get("message"))[:2000],
                    "respuestas": d.get("numreplies"),
                }
            )
    resultado.sort(key=lambda x: x["fecha"] or "", reverse=True)
    return resultado[:limite]


@mcp.tool()
def descargar_archivo(fileurl: str, nombre: str | None = None, carpeta: str | None = None) -> str:
    """Descarga un archivo de Moodle (usa el `fileurl` de contenido_curso). Devuelve la ruta local."""
    nombre = nombre or Path(fileurl.split("?")[0]).name
    destino = Path(carpeta) if carpeta else DOWNLOAD_DIR
    return str(_descargar(fileurl, destino / _nombre_seguro(nombre)))


@mcp.tool()
def descargar_materiales_curso(curso_id: int, carpeta: str | None = None) -> dict:
    """Descarga todos los archivos de un curso, organizados en carpetas por sección."""
    nombre_curso = next((c["nombre"] for c in mis_cursos() if c["id"] == curso_id), str(curso_id))
    base = Path(carpeta) if carpeta else DOWNLOAD_DIR / _nombre_seguro(nombre_curso)
    descargados, errores = [], []
    for s in contenido_curso(curso_id):
        for m in s["modulos"]:
            for a in m["archivos"]:
                destino = base / _nombre_seguro(s["seccion"]) / _nombre_seguro(a["nombre"])
                try:
                    if not (destino.exists() and destino.stat().st_size == a.get("tamano")):
                        _descargar(a["fileurl"], destino)
                    descargados.append(str(destino))
                except Exception as e:  # sigue con el resto si un archivo falla
                    errores.append(f"{a['nombre']}: {e}")
    return {"carpeta": str(base), "archivos": len(descargados), "errores": errores}


@mcp.tool()
def foros(curso_id: int) -> list[dict]:
    """Foros de un curso con su ID, tipo, fechas y si el estudiante puede abrir discusiones."""
    return [
        {
            "foro_id": f["id"],
            "nombre": f["name"],
            "tipo": f["type"],  # news = avisos, general, eachuser, single, qanda...
            "instrucciones": _texto(f.get("intro"))[:1500],
            "puede_publicar": f.get("cancreatediscussions"),
            "vence": _fecha(f.get("duedate")),
            "cierre": _fecha(f.get("cutoffdate")),
        }
        for f in _call("mod_forum_get_forums_by_courses", courseids=[curso_id])
    ]


@mcp.tool()
def leer_discusion(discusion_id: int) -> list[dict]:
    """Todos los mensajes de una discusión de foro, con su post_id para poder responder."""
    posts = _call("mod_forum_get_discussion_posts", discussionid=discusion_id, sortby="created", sortdirection="ASC")
    return [
        {
            "post_id": p["id"],
            "responde_a": p.get("parentid"),
            "autor": (p.get("author") or {}).get("fullname"),
            "fecha": _fecha(p.get("timecreated")),
            "asunto": p.get("subject"),
            "mensaje": _texto(p.get("message")),
            "adjuntos": [a["filename"] for a in p.get("attachments") or []],
        }
        for p in posts.get("posts", [])
    ]


@mcp.tool(annotations=PUBLICA)
def publicar_en_foro(foro_id: int, asunto: str, mensaje: str, archivos: list[str] | None = None) -> dict:
    """Abre una discusión nueva en un foro. Lo verán el profesor y los compañeros.

    `mensaje` puede ser texto plano (los párrafos se respetan) o HTML. `archivos` son rutas locales
    para adjuntar. Antes de llamar, muestra al usuario el asunto, mensaje y adjuntos y pide confirmación.
    """
    opciones = []
    if archivos:
        opciones.append({"name": "attachmentsid", "value": _subir_borrador(archivos)})
    result = _call("mod_forum_add_discussion", forumid=foro_id, subject=asunto, message=_a_html(mensaje), options=opciones)
    return {"publicado": True, "discusion_id": result.get("discussionid"), "avisos": result.get("warnings") or []}


@mcp.tool(annotations=PUBLICA)
def responder_en_foro(post_id: int, mensaje: str, asunto: str | None = None, archivos: list[str] | None = None) -> dict:
    """Responde a un mensaje de foro (usa el post_id de avisos o leer_discusion). Lo verán otros.

    Antes de llamar, muestra al usuario el mensaje y adjuntos y pide confirmación.
    """
    if not asunto:
        original = _call("mod_forum_get_discussion_post", postid=post_id).get("post", {})
        asunto = original.get("subject", "")
        asunto = asunto if asunto.lower().startswith("re:") else f"Re: {asunto}"
    opciones = []
    if archivos:
        opciones.append({"name": "attachmentsid", "value": _subir_borrador(archivos)})
    result = _call(
        "mod_forum_add_discussion_post", postid=post_id, subject=asunto, message=_a_html(mensaje), options=opciones
    )
    return {"publicado": True, "post_id": result.get("postid"), "avisos": result.get("warnings") or []}


@mcp.tool(annotations=PUBLICA)
def subir_entrega(
    tarea_id: int,
    archivos: list[str] | None = None,
    texto: str | None = None,
    enviar_para_calificar: bool = True,
) -> dict:
    """Sube la entrega de una tarea (usa el tarea_id de tareas o pendientes).

    `archivos` son rutas locales; REEMPLAZAN los archivos que ya estuvieran en la entrega.
    `texto` es para tareas con texto en línea. Si la tarea usa borradores y
    `enviar_para_calificar` es True, además la envía al profesor (ya no se podrá editar).
    Antes de llamar, confirma con el usuario la tarea y los archivos exactos.
    """
    if not archivos and not texto:
        raise ValueError("Indica al menos un archivo o un texto para entregar.")
    plugindata: dict[str, Any] = {}
    if archivos:
        plugindata["files_filemanager"] = _subir_borrador(archivos)
    if texto:
        draft = _call("core_files_get_unused_draft_itemid")["itemid"]
        plugindata["onlinetext_editor"] = {"text": _a_html(texto), "format": 1, "itemid": draft}
    warnings = _call("mod_assign_save_submission", assignmentid=tarea_id, plugindata=plugindata)
    if warnings:
        raise RuntimeError("Moodle rechazó la entrega: " + "; ".join(w.get("message", str(w)) for w in warnings))

    estado = estado_tarea(tarea_id)
    if enviar_para_calificar and estado["estado_envio"] == "draft":
        warnings = _call("mod_assign_submit_for_grading", assignmentid=tarea_id, acceptsubmissionstatement=True)
        if warnings:
            raise RuntimeError("Se guardó como borrador pero no se pudo enviar: " + "; ".join(w.get("message", str(w)) for w in warnings))
        estado = estado_tarea(tarea_id)
    return estado


@mcp.tool()
def llamar_api(funcion: str, parametros: dict[str, Any] | None = None) -> Any:
    """Llama directamente cualquier función de la API de Moodle (p. ej. 'mod_quiz_get_quizzes_by_courses').

    Úsala solo cuando ninguna otra herramienta sirva. Los parámetros se pasan como dict anidado.
    """
    return _call(funcion, **(parametros or {}))


if __name__ == "__main__":
    mcp.run()
