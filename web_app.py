"""Dependency-free browser interface for StudyFlow."""
from datetime import date
from html import escape
import json
import os
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

import analyzer
import database


def _html_page(body: str, title: str = "StudyFlow") -> str:
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="StudyFlow: gestión y análisis académico">
<title>{escape(title)}</title>
<style>
:root{{--bg:#f4f6fb;--card:#fff;--text:#182230;--muted:#667085;--line:#e4e7ec;--accent:#182230;--good:#067647;--soft:#f8fafc}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:1120px;margin:0 auto;padding:28px 18px 48px}}
header{{display:flex;justify-content:space-between;gap:20px;align-items:end;margin-bottom:22px}}
h1,h2,p{{margin-top:0}}h1{{margin-bottom:4px;font-size:32px}}h2{{margin-bottom:14px;font-size:20px}}
.muted{{color:var(--muted)}}
.grid{{display:grid;grid-template-columns:repeat(12,1fr);gap:16px}}
.card{{grid-column:span 4;background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px;box-shadow:0 2px 8px rgba(16,24,40,.04)}}
.card.wide{{grid-column:span 12}}
.card.half{{grid-column:span 6}}
.metric{{font-size:30px;font-weight:750;margin:8px 0 2px}}
.metric-label{{font-size:14px;color:var(--muted)}}
form{{display:grid;gap:6px}}
label{{font-weight:650;font-size:14px;margin-top:4px}}
input,select,button{{width:100%;padding:10px 12px;border:1px solid #d0d5dd;border-radius:9px;font:inherit;background:#fff}}
button{{margin-top:8px;background:var(--accent);color:#fff;border-color:var(--accent);cursor:pointer;font-weight:650}}
button:disabled,input:disabled,select:disabled{{opacity:.55;cursor:not-allowed}}
.notice{{padding:12px 14px;border-radius:10px;margin-bottom:16px;background:#ecfdf3;border:1px solid #abefc6;color:var(--good)}}
.error{{padding:12px 14px;border-radius:10px;margin-bottom:16px;background:#fef3f2;border:1px solid #fecdca;color:#b42318}}
.table-wrap{{overflow:auto}}
table{{width:100%;border-collapse:collapse;min-width:640px}}
th,td{{padding:11px 10px;text-align:left;border-bottom:1px solid #eaecf0;white-space:nowrap}}
th{{font-size:13px;color:var(--muted);font-weight:700}}
.badge{{display:inline-block;padding:4px 8px;border-radius:999px;background:var(--soft);font-size:12px;font-weight:650}}
.empty{{color:var(--muted);padding:8px 0}}
.footer{{margin-top:18px;font-size:13px;color:var(--muted);text-align:center}}
@media(max-width:850px){{.card,.card.half{{grid-column:span 12}}header{{align-items:start;flex-direction:column}}}}
</style>
</head>
<body><main>{body}<div class="footer">StudyFlow · Gestión y análisis académico</div></main></body>
</html>"""


def _load_report() -> dict:
    return analyzer.build_average_report(
        database.list_subjects(database_path=database.DATABASE_PATH),
        database.list_exams(database_path=database.DATABASE_PATH),
        database.list_evaluations(database_path=database.DATABASE_PATH),
    )


def _render_dashboard(message: str = "", error: str = "") -> str:
    subjects = database.list_subjects(database_path=database.DATABASE_PATH)
    exams = database.list_exams(database_path=database.DATABASE_PATH)
    evaluations = database.list_evaluations(database_path=database.DATABASE_PATH)
    report = analyzer.build_average_report(subjects, exams, evaluations)

    subject_names = {subject.id: subject.name for subject in subjects}
    exam_map = {exam.id: exam for exam in exams}

    options = "".join(
        f'<option value="{exam.id}">'
        f'{escape(subject_names.get(exam.subject_id, "Materia"))} — {escape(exam.name)}'
        f'</option>'
        for exam in exams
    )
    disabled = " disabled" if not exams else ""

    notice = f'<div class="notice">{escape(message)}</div>' if message else ""
    failure = f'<div class="error">{escape(error)}</div>' if error else ""

    form = f"""<section class="card half"><h2>Registrar nota</h2>
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
{"<p class='empty'>Primero crea un examen para poder registrar una nota.</p>" if not exams else ""}
</section>"""

    summary = f"""<section class="card half"><h2>Promedio actual</h2>
<div class="metric">{report["general_average"]:g}/100</div>
<div class="metric-label">Calculado con el resultado más reciente de cada examen.</div>
<hr style="border:0;border-top:1px solid #eaecf0;margin:18px 0">
<p><strong>{report["evaluated_exams"]}</strong> exámenes con nota</p>
<p><strong>{report["total_evaluations"]}</strong> evaluaciones almacenadas</p>
</section>"""

    subject_rows = "".join(
        "<tr>"
        f"<td>{escape(row['subject_name'])}</td>"
        f"<td><strong>{row['average']:g}</strong></td>"
        f"<td>{row['target_grade']:g}</td>"
        f"<td>{row['evaluation_count']}</td>"
        f"<td><span class='badge'>{'Meta alcanzada' if row['evaluation_count'] and row['average'] >= row['target_grade'] else 'En progreso'}</span></td>"
        "</tr>"
        for row in report["subjects"]
    )
    subject_table = (
        "<div class='table-wrap'><table><thead><tr>"
        "<th>Materia</th><th>Promedio</th><th>Meta</th><th>Notas</th><th>Estado</th>"
        f"</tr></thead><tbody>{subject_rows}</tbody></table></div>"
        if subject_rows
        else '<p class="empty">Todavía no hay materias registradas.</p>'
    )

    eval_rows = "".join(
        "<tr>"
        f"<td>{escape(subject_names.get(exam_map[ev.exam_id].subject_id, 'Materia'))}</td>"
        f"<td>{escape(exam_map[ev.exam_id].name)}</td>"
        f"<td>{ev.grade:g}</td>"
        f"<td>{ev.date.isoformat()}</td>"
        f"<td>{escape(ev.evaluation_type)}</td>"
        "</tr>"
        for ev in evaluations
        if ev.exam_id in exam_map
    )
    eval_table = (
        "<div class='table-wrap'><table><thead><tr><th>Materia</th><th>Examen</th>"
        "<th>Nota</th><th>Fecha</th><th>Tipo</th></tr></thead><tbody>"
        f"{eval_rows}</tbody></table></div>"
        if eval_rows
        else '<p class="empty">Todavía no hay notas registradas.</p>'
    )

    body = (
        "<header><div><h1>StudyFlow</h1><div class='muted'>Gestión y análisis académico</div></div>"
        "<div class='badge'>Punto 7 · Promedios</div></header>"
        + notice + failure
        + '<div class="grid">' + form + summary
        + '<section class="card wide"><h2>Promedios por materia</h2>' + subject_table + "</section>"
        + '<section class="card wide"><h2>Evaluaciones registradas</h2>' + eval_table + "</section>"
        + "</div>"
    )
    return _html_page(body)


def application(environ, start_response):
    """WSGI entry point for browser requests."""
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET").upper()

    if path == "/health":
        try:
            database.initialize_database(database.DATABASE_PATH)
            payload = json.dumps({"status": "ok"}).encode("utf-8")
            status = "200 OK"
        except database.DatabaseError as exc:
            payload = json.dumps({"status": "error", "detail": str(exc)}).encode("utf-8")
            status = "500 Internal Server Error"
        start_response(
            status,
            [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(payload))),
            ],
        )
        return [payload]

    if path == "/api/averages":
        try:
            payload = json.dumps(_load_report(), ensure_ascii=False).encode("utf-8")
            status = "200 OK"
        except database.DatabaseError as exc:
            payload = json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8")
            status = "500 Internal Server Error"
        start_response(
            status,
            [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(payload))),
            ],
        )
        return [payload]

    if path not in {"/", "/evaluations"}:
        body = _html_page(
            "<section class='card wide'><h2>404</h2><p>Página no encontrada.</p></section>",
            "404",
        ).encode("utf-8")
        start_response(
            "404 Not Found",
            [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(body)))],
        )
        return [body]

    if method == "GET":
        body = _render_dashboard().encode("utf-8")
        start_response(
            "200 OK",
            [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(body)))],
        )
        return [body]

    if method == "POST" and path == "/evaluations":
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
            if length > 10000:
                raise ValueError("El formulario es demasiado grande.")
            payload = environ["wsgi.input"].read(length).decode("utf-8")
            form = parse_qs(payload, keep_blank_values=True)
            exam_id = int(form.get("exam_id", [""])[0])
            grade = float(form.get("grade", [""])[0])
            evaluation_date = date.fromisoformat(form.get("date", [""])[0])
            evaluation_type = form.get("type", [""])[0]

            evaluation = database.create_evaluation(
                exam_id, grade, evaluation_date, evaluation_type, database.DATABASE_PATH
            )
            body = _render_dashboard(
                message=f"Nota guardada correctamente: {evaluation.grade:g}/100"
            ).encode("utf-8")
        except (ValueError, KeyError, TypeError, database.DatabaseError) as exc:
            body = _render_dashboard(
                error=f"No se pudo guardar la evaluación: {exc}"
            ).encode("utf-8")

        start_response(
            "200 OK",
            [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(body)))],
        )
        return [body]

    body = _html_page(
        "<section class='card wide'><h2>Método no permitido</h2></section>", "405"
    ).encode("utf-8")
    start_response(
        "405 Method Not Allowed",
        [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(body)))],
    )
    return [body]


def run() -> None:
    """Run the local web server, honoring Render's PORT variable."""
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    print(f"StudyFlow web server running at http://{host}:{port}")
    with make_server(host, port, application) as server:
        server.serve_forever()




if __name__ == "__main__":
    run()
