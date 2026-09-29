"""Dependency-free browser interface for StudyFlow.

The exported WSGI application can be served locally with Python's standard
library and can also be connected to a Python web host.
"""
from datetime import date
from html import escape
import json
import os
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

import database


def _html_page(body: str, title: str = "StudyFlow") -> str:
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
body{{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;max-width:1050px;margin:0 auto;padding:24px;background:#f6f7fb;color:#172033}}
header{{margin-bottom:22px}}h1{{margin:0 0 4px}}.muted{{color:#667085}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}}
.card{{background:#fff;border:1px solid #e4e7ec;border-radius:14px;padding:18px;box-shadow:0 1px 2px rgba(0,0,0,.04);margin-bottom:16px}}
label{{display:block;font-weight:600;margin:10px 0 4px}}input,select,button{{width:100%;box-sizing:border-box;padding:10px;border:1px solid #d0d5dd;border-radius:8px;font:inherit}}
button{{margin-top:12px;cursor:pointer;background:#172033;color:#fff}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;text-align:left;border-bottom:1px solid #eaecf0}}
.ok{{padding:10px;background:#ecfdf3;border:1px solid #abefc6;border-radius:8px;margin-bottom:16px}}.error{{padding:10px;background:#fef3f2;border:1px solid #fecdca;border-radius:8px;margin-bottom:16px}}
@media(max-width:600px){{body{{padding:14px}}th,td{{font-size:14px}}}}
</style>
</head>
<body>
<header><h1>StudyFlow</h1><div class="muted">Gestión y análisis académico</div></header>
{body}
</body>
</html>"""


def _render_dashboard(message: str = "", error: str = "") -> str:
    db_path = database.DATABASE_PATH
    subjects = database.list_subjects(database_path=db_path)
    exams = database.list_exams(database_path=db_path)
    evaluations = database.list_evaluations(database_path=db_path)

    subject_names = {subject.id: subject.name for subject in subjects}
    exam_map = {exam.id: exam for exam in exams}

    options = "".join(
        f'<option value="{exam.id}">'
        f'{escape(subject_names.get(exam.subject_id, "Materia"))} — '
        f'{escape(exam.name)}'
        f"</option>"
        for exam in exams
    )

    rows = "".join(
        "<tr>"
        f"<td>{escape(subject_names.get(exam_map[ev.exam_id].subject_id, 'Materia'))}</td>"
        f"<td>{escape(exam_map.get(ev.exam_id).name if ev.exam_id in exam_map else 'Examen')}</td>"
        f"<td>{ev.grade:g}</td>"
        f"<td>{ev.date.isoformat()}</td>"
        f"<td>{escape(ev.evaluation_type)}</td>"
        "</tr>"
        for ev in evaluations
        if ev.exam_id in exam_map
    )

    notice = f'<div class="ok">{escape(message)}</div>' if message else ""
    failure = f'<div class="error">{escape(error)}</div>' if error else ""
    disabled = " disabled" if not exams else ""

    form = f"""<section class="card"><h2>Registrar nota</h2>
<form method="post" action="/evaluations">
<label for="exam_id">Examen</label>
<select id="exam_id" name="exam_id" required{disabled}>{options}</select>
<label for="grade">Nota (0–100)</label>
<input id="grade" name="grade" type="number" min="0" max="100" step="0.01" required{disabled}>
<label for="date">Fecha</label>
<input id="date" name="date" type="date" value="{date.today().isoformat()}" required{disabled}>
<label for="type">Tipo de evaluación</label>
<input id="type" name="type" placeholder="Examen, quiz, proyecto..." required{disabled}>
<button type="submit"{disabled}>Guardar nota</button>
</form>
{"<p class='muted'>Primero crea un examen para poder registrar una nota.</p>" if not exams else ""}
</section>"""

    summary = f"""<section class="card"><h2>Resumen</h2>
<p><strong>{len(subjects)}</strong> materias</p>
<p><strong>{len(exams)}</strong> exámenes</p>
<p><strong>{len(evaluations)}</strong> evaluaciones registradas</p>
</section>"""

    table = (
        "<table><thead><tr><th>Materia</th><th>Examen</th><th>Nota</th>"
        "<th>Fecha</th><th>Tipo</th></tr></thead><tbody>"
        f"{rows}</tbody></table>"
        if rows
        else '<p class="muted">Todavía no hay notas registradas.</p>'
    )

    body = (
        notice + failure + '<div class="grid">' + form + summary + "</div>"
        + '<section class="card"><h2>Evaluaciones</h2>' + table + "</section>"
    )
    return _html_page(body)


def application(environ, start_response):
    """WSGI entry point for browser requests."""
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET").upper()

    if path == "/health":
        payload = json.dumps({"status": "ok"}).encode("utf-8")
        start_response(
            "200 OK",
            [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(payload))),
            ],
        )
        return [payload]

    if path not in {"/", "/evaluations"}:
        body = _html_page(
            "<div class='card'><h2>404</h2><p>Página no encontrada.</p></div>",
            "404",
        ).encode("utf-8")
        start_response(
            "404 Not Found",
            [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]

    if method == "GET":
        body = _render_dashboard().encode("utf-8")
        start_response(
            "200 OK",
            [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]

    if method == "POST" and path == "/evaluations":
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
            payload = environ["wsgi.input"].read(length).decode("utf-8")
            form = parse_qs(payload)

            exam_id = int(form.get("exam_id", [""])[0])
            grade = float(form.get("grade", [""])[0])
            evaluation_date = date.fromisoformat(form.get("date", [""])[0])
            evaluation_type = form.get("type", [""])[0]

            evaluation = database.create_evaluation(
                exam_id,
                grade,
                evaluation_date,
                evaluation_type,
                database.DATABASE_PATH,
            )
            body = _render_dashboard(
                message=f"Nota guardada correctamente: {evaluation.grade:g}/100"
            ).encode("utf-8")
            status = "200 OK"
        except (
            ValueError,
            KeyError,
            TypeError,
            database.ExamNotFoundError,
            database.DatabaseError,
        ) as exc:
            body = _render_dashboard(
                error=f"No se pudo guardar la evaluación: {exc}"
            ).encode("utf-8")
            status = "200 OK"

        start_response(
            status,
            [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]

    body = _html_page(
        "<div class='card'><h2>Método no permitido</h2></div>", "405"
    ).encode("utf-8")
    start_response(
        "405 Method Not Allowed",
        [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ],
    )
    return [body]


def run() -> None:
    """Run a simple local web server."""
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    print(f"StudyFlow web server running at http://{host}:{port}")
    with make_server(host, port, application) as server:
        server.serve_forever()


if __name__ == "__main__":
    run()
