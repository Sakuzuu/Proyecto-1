"""Dependency-free WSGI web application for StudyFlow."""
from datetime import date, datetime, time
from html import escape
import json
import logging
import os
import re
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

import analyzer
import charts
import database
import planner


LOGGER = logging.getLogger("studyflow.web")


def _page(body, title="StudyFlow"):
    return f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title><style>
body{{margin:0;background:#f4f6fb;color:#182230;font:15px system-ui,sans-serif}}main{{max-width:1100px;margin:auto;padding:24px 16px}}h1{{margin:0}}h2{{margin-bottom:10px}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.card{{background:#fff;border:1px solid #e4e7ec;border-radius:14px;padding:16px}}.wide{{grid-column:1/-1}}.metric{{font-size:30px;font-weight:800}}.muted{{color:#667085}}form{{display:grid;gap:7px}}input,select,textarea,button{{padding:9px;border:1px solid #d0d5dd;border-radius:8px;font:inherit}}button{{background:#182230;color:#fff;cursor:pointer}}table{{width:100%;border-collapse:collapse}}th,td{{padding:8px;text-align:left;border-bottom:1px solid #eaecf0}}th{{color:#667085}}.badge{{display:inline-block;padding:3px 7px;border-radius:999px;background:#f2f4f7;font-size:12px}}.red{{background:#fef3f2;color:#b42318}}.orange{{background:#fffaeb;color:#b54708}}.green{{background:#ecfdf3;color:#067647}}.notice,.error,.warning{{padding:10px 12px;border-radius:8px;margin-bottom:12px}}.notice{{background:#ecfdf3;color:#067647}}.error{{background:#fef3f2;color:#b42318}}.warning{{background:#fffaeb;color:#b54708}}.session{{border:1px solid #e4e7ec;border-radius:10px;padding:10px;margin:8px 0}}.session-time{{font-size:17px;font-weight:800}}.metric-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:12px 0}}.metric-box{{background:#f8fafc;border:1px solid #eaecf0;border-radius:10px;padding:12px}}.metric-small{{font-size:18px;margin-top:4px}}.table-wrap{{overflow-x:auto}}.chart{{display:block;width:100%;height:auto;border:1px solid #eaecf0;border-radius:10px;background:#fff}}@media(max-width:900px){{.metric-grid{{grid-template-columns:1fr 1fr}}}}@media(max-width:800px){{.grid{{grid-template-columns:1fr}}.wide{{grid-column:auto}}}}
</style></head><body><main>{body}<p class="muted">StudyFlow · Planificador académico integrado</p></main></body></html>'''


def _json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _json(start_response, payload, status="200 OK"):
    data = json.dumps(payload, ensure_ascii=False, default=_json_default).encode()
    start_response(status, [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(data)))])
    return [data]


def _html(start_response, body, status="200 OK"):
    data = body.encode("utf-8")
    start_response(status, [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(data)))])
    return [data]


def _error_page(start_response, message, status="500 Internal Server Error", title="Error"):
    safe_message = escape(message)
    return _html(
        start_response,
        _page(
            f'<section class="card error-page"><h2>{escape(title)}</h2><p>{safe_message}</p>'
            '<p class="muted">Puedes volver al inicio e intentarlo nuevamente.</p>'
            '<form method="get" action="/"><button type="submit">Volver al inicio</button></form></section>',
            title,
        ),
        status,
    )


def _operation_error(start_response, message, status="400 Bad Request"):
    try:
        return _html(start_response, _dashboard(error=message), status)
    except Exception:
        LOGGER.exception("No se pudo renderizar el mensaje de error de la operación")
        return _error_page(start_response, message, status, "No se pudo completar la operación")


def _form(environ):
    raw_length = environ.get("CONTENT_LENGTH") or "0"
    try:
        length = int(raw_length)
    except (TypeError, ValueError) as exc:
        raise ValueError("El tamaño del formulario no es válido.") from exc
    if length < 0 or length > 10000:
        raise ValueError("El formulario es demasiado grande.")
    stream = environ.get("wsgi.input")
    if stream is None:
        raise ValueError("No se recibió el contenido del formulario.")
    raw_bytes = stream.read(length)
    try:
        raw = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("El formulario contiene texto no válido.") from exc
    return {k: (v[0] if v else "") for k, v in parse_qs(raw, keep_blank_values=True).items()}


def _text(form, key, label):
    value = form.get(key, "").strip()
    if not value:
        raise ValueError(f"{label} es obligatorio.")
    return value


def _int(form, key, label):
    try:
        return int(_text(form, key, label))
    except ValueError as exc:
        raise ValueError(f"{label} debe ser un entero válido.") from exc


def _float(form, key, label):
    try:
        value = float(_text(form, key, label))
    except ValueError as exc:
        raise ValueError(f"{label} debe ser un número válido.") from exc
    if not (value == value and abs(value) != float("inf")):
        raise ValueError(f"{label} debe ser un número finito.")
    return value


def _date(form, key, label):
    try:
        return date.fromisoformat(_text(form, key, label))
    except ValueError as exc:
        raise ValueError(f"{label} no tiene una fecha válida.") from exc


def _names(subjects):
    return {s.id: s.name for s in subjects}


def _start(raw):
    now = datetime.now().replace(second=0, microsecond=0)
    minimum = planner._round_up_to_five_minutes(now)
    if not raw:
        return minimum
    try:
        requested = time.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("La hora de inicio no es válida.") from exc
    return max(minimum, datetime.combine(now.date(), requested))


def _priority_html(tasks, exams, subjects):
    names = _names(subjects)
    rows = []
    for x in planner.rank_study_items(tasks, exams, date.today()):
        cls = "red" if x["priority"] >= 7.5 else "orange" if x["priority"] >= 5 else "green"
        state = "Vencida" if x["overdue"] else "Planificable"
        kind = "📘 Tarea" if x["kind"] == "task" else "📝 Examen"
        rows.append(f"<tr><td>{kind}</td><td>{escape(names.get(x['subject_id'],'Materia'))}</td><td>{escape(x['title'])}</td><td>{x['deadline']}</td><td><span class='badge {cls}'>{x['priority']:g}/10</span></td><td>{x['remaining_minutes']} min</td><td>{state}</td></tr>")
    if not rows:
        return '<p class="muted">No hay tareas pendientes ni exámenes registrados.</p>'
    return '<table><tr><th>Tipo</th><th>Materia</th><th>Actividad</th><th>Fecha límite</th><th>Prioridad</th><th>Tiempo</th><th>Estado</th></tr>'+''.join(rows)+'</table>'


def _plan_html(plan):
    if not plan:
        return '<p class="muted">No hay sesiones posibles con el tiempo y las fechas disponibles.</p>'
    html = [f"<p><strong>{sum(x.minutes for x in plan)} min</strong> de estudio asignados.</p>"]
    for x in plan:
        html.append(f"<div class='session'><div class='session-time'>{x.start:%H:%M} – {x.end:%H:%M}</div><div><strong>{escape(x.subject_name)}</strong> · {escape(x.title)}</div><div class='muted'>{escape(x.purpose)} · {x.minutes} min · prioridad {x.priority:g}/10 · fecha límite {x.deadline}</div></div>")
    return ''.join(html)


def _performance_summary_html(performance):
    best = performance["best_subject"]
    lowest = performance["lowest_subject"]
    best_html = (
        f"<strong>{escape(best['subject_name'])}</strong><br><span class='muted'>{best['average']:g}/100</span>"
        if best else "<span class='muted'>Sin evaluaciones</span>"
    )
    lowest_html = (
        f"<strong>{escape(lowest['subject_name'])}</strong><br><span class='muted'>{lowest['average']:g}/100</span>"
        if lowest else "<span class='muted'>Sin evaluaciones</span>"
    )
    rows = "".join(
        f"<tr><td>{escape(row['subject_name'])}</td><td><strong>{row['average']:g}</strong></td>"
        f"<td>{row['target_grade']:g}</td><td>{row['evaluation_count']}</td>"
        f"<td><span class='badge {'green' if row['trend_status']=='up' else 'red' if row['trend_status']=='down' else ''}'>{escape(row['trend'])}</span></td></tr>"
        for row in performance["subjects"]
    )
    table = (
        "<table><tr><th>Materia</th><th>Promedio</th><th>Meta</th><th>Evaluaciones</th><th>Tendencia</th></tr>"
        + rows + "</table>"
        if rows else '<p class="muted">Todavía no existen evaluaciones suficientes para comparar materias.</p>'
    )
    trend_class = "green" if performance["overall_trend_status"] == "up" else "red" if performance["overall_trend_status"] == "down" else ""
    return f"""
<section class="card wide">
<h2>📊 Dashboard de rendimiento</h2>
<div class="metric-grid">
<div class="metric-box"><div class="muted">Promedio general</div><div class="metric">{performance['general_average']:g}</div></div>
<div class="metric-box"><div class="muted">Mejor materia</div><div class="metric-small">{best_html}</div></div>
<div class="metric-box"><div class="muted">Menor promedio</div><div class="metric-small">{lowest_html}</div></div>
<div class="metric-box"><div class="muted">Tendencia general</div><div class="metric-small"><span class="badge {trend_class}">{escape(performance['overall_trend'])}</span></div></div>
</div>
<h3>Promedios por materia</h3><div class="table-wrap">{table}</div>
<div style="display:flex;gap:8px;flex-wrap:wrap">
<form method="get" action="/analysis"><button type="submit">Abrir análisis detallado</button></form>
<form method="get" action="/charts"><button type="submit">Ver gráficos</button></form>
</div>
</section>
"""


def _subject_picker(subjects, field_name="subject_id"):
    if not subjects:
        return '<div class="empty-picker">No hay materias guardadas todavía. Usa <strong>Agregar materias</strong> primero.</div>'
    items = []
    for subject in subjects:
        items.append(
            f'<label class="picker-option">'
            f'<input type="radio" name="{escape(field_name)}" value="{subject.id}" required>'
            f'<span><strong>{escape(subject.name)}</strong>'
            f'<small>Meta: {subject.target_grade:g}/100</small></span></label>'
        )
    return '<div class="picker-list">' + ''.join(items) + '</div>'


def _exam_picker(exams, subjects):
    names = _names(subjects)
    if not exams:
        return '<div class="empty-picker">No hay exámenes guardados todavía. Crea un examen primero.</div>'
    items = []
    for exam in exams:
        items.append(
            f'<label class="picker-option">'
            f'<input type="radio" name="exam_id" value="{exam.id}" required>'
            f'<span><strong>{escape(names.get(exam.subject_id, "Materia"))} · {escape(exam.name)}</strong>'
            f'<small>{exam.date} · dificultad {exam.difficulty}/10 · peso {exam.weight:g}%</small></span></label>'
        )
    return '<div class="picker-list">' + ''.join(items) + '</div>'


def _dashboard(message="", error="", plan=None):
    subjects = database.list_subjects(database_path=database.DATABASE_PATH)
    tasks = database.list_tasks(database_path=database.DATABASE_PATH)
    exams = database.list_exams(database_path=database.DATABASE_PATH)
    evaluations = database.list_evaluations(database_path=database.DATABASE_PATH)
    report = analyzer.build_average_report(subjects, exams, evaluations)
    performance = analyzer.build_performance_report(subjects, exams, evaluations)
    names = _names(subjects)
    today = date.today().isoformat()
    notice = (
        (f'<div class="notice">{escape(message)}</div>' if message else '')
        + (f'<div class="error">{escape(error)}</div>' if error else '')
    )
    overdue = sum(
        1 for x in planner.rank_study_items(tasks, exams, date.today()) if x["overdue"]
    )
    if overdue:
        notice += (
            f'<div class="warning">Hay {overdue} elemento(s) vencido(s). '
            'No se programan en el plan.</div>'
        )
    start = planner._round_up_to_five_minutes(datetime.now()).strftime("%H:%M")
    has_subjects = bool(subjects)
    has_exams = bool(exams)

    subject_list = _subject_picker(subjects)
    exam_list = _exam_picker(exams, subjects)

    body = f'''<header><h1>StudyFlow</h1>
<div class="muted">Planificación y análisis académico · <span class="badge">Puntos 8–11</span></div>
</header>{notice}<div class="grid">

<section class="card wide">
<h2>📚 Agregar materias</h2>
<p class="muted">Escribe tus materias, una por línea. Se guardarán en la base de datos y después podrás elegirlas desde las listas visibles de tareas y exámenes.</p>
<form method="post" action="/subjects">
<label for="subjects">Agregar materias</label>
<textarea id="subjects" name="subjects" rows="5" placeholder="Ejemplo:
Cálculo
Programación
Física" required></textarea>
<button type="submit">Guardar materias</button>
</form>
{f'<div class="saved-subjects"><strong>Materias guardadas:</strong> ' + ' · '.join(escape(s.name) for s in subjects) + '</div>' if subjects else '<p class="muted">Todavía no hay materias guardadas.</p>'}
{('<div class="subject-management"><h3>Gestionar materias</h3>' + ''.join(
    f"<div class='session'><strong>{escape(s.name)}</strong>"
    f"<form method='post' action='/subjects/{s.id}/delete' style='display:inline' onsubmit='return confirm(\"¿Eliminar esta materia? Solo será posible si no tiene tareas ni exámenes.\")'>"
    '<button type="submit">Eliminar materia</button></form></div>'
    for s in subjects
) + '</div>') if subjects else ''}
</section>

<section class="card">
<h2>📅 Generador de plan de estudio</h2>
<p class="muted">Introduce tus horas disponibles y StudyFlow distribuye el tiempo entre tareas y exámenes según prioridad, tiempo y fecha límite.</p>
<form method="post" action="/plan">
<label>Horas disponibles hoy</label>
<input name="hours" type="number" min="0.25" max="16" step="0.25" value="3" required>
<label>Hora de inicio</label>
<input name="start_time" type="time" value="{start}" required>
<button type="submit">Generar plan de hoy</button>
</form>
<p class="muted">Máximo 80 min por sesión y 15 min de descanso.</p>
</section>

<section class="card">
<h2>📊 Resumen</h2>
<div class="metric">{report['general_average']:g}/100</div>
<p class="muted">Promedio actual</p>
<p><span class="badge">{len(tasks)} tareas</span> <span class="badge">{len(exams)} exámenes</span> <span class="badge">{len(evaluations)} evaluaciones</span></p>
</section>

{_performance_summary_html(performance)}

<section class="card wide"><h2>🎯 Prioridades de estudio</h2>{_priority_html(tasks, exams, subjects)}</section>

<section class="card wide">
<h2>➕ Registrar tareas y exámenes</h2>
<p class="muted">Ya no usamos menús desplegables. Selecciona una materia directamente de la lista visible.</p>
<div class="grid">
<form method="post" action="/tasks">
<h3>Nueva tarea</h3>
<label>Materia</label>
{subject_list}
<label>Nombre</label>
<input name="name" required>
<label>Descripción</label>
<textarea name="description"></textarea>
<label>Fecha límite</label>
<input name="deadline" type="date" min="{today}" required>
<label>Dificultad (1–10)</label>
<input name="difficulty" type="number" min="1" max="10" value="5" required>
<label>Tiempo estimado (min)</label>
<input name="estimated_minutes" type="number" min="1" value="60" required>
<label>Progreso</label>
<input name="progress" type="number" min="0" max="100" value="0" required>
<label>Estado</label>
<div class="choice-list">
<label><input type="radio" name="status" value="pending" checked required><span>Pendiente</span></label>
<label><input type="radio" name="status" value="in_progress"><span>En progreso</span></label>
<label><input type="radio" name="status" value="completed"><span>Completada</span></label>
</div>
<button type="submit"{"" if has_subjects else " disabled"}>Guardar tarea</button>
{"" if has_subjects else '<p class="muted">Agrega al menos una materia para poder guardar tareas.</p>'}
</form>

<form method="post" action="/exams">
<h3>Nuevo examen</h3>
<label>Materia</label>
{_subject_picker(subjects)}
<label>Nombre</label>
<input name="name" required>
<label>Fecha del examen</label>
<input name="exam_date" type="date" min="{today}" required>
<label>Dificultad (1–10)</label>
<input name="difficulty" type="number" min="1" max="10" value="7" required>
<label>Peso (%)</label>
<input name="weight" type="number" min="0" max="100" step="0.1" value="20" required>
<button type="submit"{"" if has_subjects else " disabled"}>Guardar examen</button>
{"" if has_subjects else '<p class="muted">Agrega al menos una materia para poder guardar exámenes.</p>'}
</form>
</div>
</section>

<section class="card wide">
<h2>📝 Registrar evaluación</h2>
<p class="muted">Selecciona el examen desde la lista visible. Así no dependemos de un menú desplegable.</p>
<form method="post" action="/evaluations">
<label>Examen</label>
{exam_list}
<label>Nota (0–100)</label>
<input name="grade" type="number" min="0" max="100" step="0.01" required{"" if has_exams else " disabled"}>
<label>Fecha</label>
<input name="date" type="date" value="{today}" required{"" if has_exams else " disabled"}>
<label>Tipo de evaluación</label>
<input name="type" required{"" if has_exams else " disabled"}>
<button type="submit"{"" if has_exams else " disabled"}>Guardar evaluación</button>
{"" if has_exams else '<p class="muted">Crea al menos un examen para poder registrar una evaluación.</p>'}
</form>
</section>

<section class="card wide"><h2>✅ Tareas registradas</h2>
{('<p class="muted">No hay tareas registradas.</p>' if not tasks else ''.join(
    f"<div class='session'><strong>{escape(names.get(t.subject_id,'Materia'))}</strong> · {escape(t.name)} · {t.deadline} · {t.progress}% "
    + (f"<form method='post' action='/tasks/{t.id}/complete' style='display:inline'><button type='submit'>Marcar como completada</button></form>"
       if t.status != 'completed' else '✅ Completada')
    + "</div>" for t in tasks))}
</section>

<section class="card wide"><h2>Exámenes registrados</h2>
{('<p class="muted">No hay exámenes registrados.</p>' if not exams else ''.join(
    f"<p><strong>{escape(names.get(e.subject_id,'Materia'))}</strong> · {escape(e.name)} · {e.date} · preparación sugerida: {planner.estimate_exam_minutes(e)} min</p>"
    for e in exams))}
</section>

<section class="card wide"><h2>Evaluaciones registradas</h2>
{('<p class="muted">Todavía no hay notas registradas.</p>' if not evaluations else ''.join(
    f"<p>{escape(names.get(next((e.subject_id for e in exams if e.id==v.exam_id),0),'Materia'))} · {v.grade:g}/100 · {v.date} · {escape(v.evaluation_type)}</p>"
    for v in evaluations))}
</section>'''
    if plan is not None:
        body += f'<section class="card wide"><h2>HOY · Plan generado</h2>{_plan_html(plan)}</section>'
    body += '''<style>
.picker-list{display:grid;gap:8px;margin:4px 0 12px}
.picker-option,.choice-list label{display:flex;align-items:center;gap:10px;border:1px solid #d0d5dd;border-radius:10px;padding:10px;background:#fff;cursor:pointer}
.picker-option:hover,.choice-list label:hover{border-color:#98a2b3;background:#f8fafc}
.picker-option input,.choice-list input{margin:0}
.picker-option span{display:flex;flex-direction:column;gap:2px}
.picker-option small{color:#667085}
.choice-list{display:grid;gap:7px}
.empty-picker{padding:11px 12px;border:1px dashed #d0d5dd;border-radius:10px;color:#667085;background:#f8fafc;margin-bottom:10px}
.saved-subjects{margin-top:10px;padding:10px 12px;border-radius:10px;background:#f8fafc;border:1px solid #eaecf0}
</style>'''
    return _page(body + '</div>')



def _charts_dashboard():
    subjects = database.list_subjects(database_path=database.DATABASE_PATH)
    tasks = database.list_tasks(database_path=database.DATABASE_PATH)
    exams = database.list_exams(database_path=database.DATABASE_PATH)
    evaluations = database.list_evaluations(database_path=database.DATABASE_PATH)
    return _page(
        f'''<header><h1>StudyFlow</h1><div class="muted">Visualizaciones académicas · <span class="badge">Punto 10</span></div></header>
<section class="card wide">
<h2>📈 Gráficos de rendimiento</h2>
<p class="muted">Las visualizaciones se actualizan con tus evaluaciones, materias, exámenes y actividades registradas.</p>
<h3>Evolución de notas</h3>
<img class="chart" src="/charts/grade-evolution.svg" alt="Evolución de notas">
<h3>Promedio por materia</h3>
<img class="chart" src="/charts/subject-averages.svg" alt="Promedio por materia">
<h3>Tiempo de estudio estimado</h3>
<img class="chart" src="/charts/study-time.svg" alt="Tiempo de estudio estimado por materia">
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px">
<form method="get" action="/analysis"><button type="submit">Volver al análisis</button></form>
<form method="get" action="/"><button type="submit">Volver al inicio</button></form>
</div>
</section>'''
    )



def _analysis_dashboard():
    subjects = database.list_subjects(database_path=database.DATABASE_PATH)
    exams = database.list_exams(database_path=database.DATABASE_PATH)
    evaluations = database.list_evaluations(database_path=database.DATABASE_PATH)
    performance = analyzer.build_performance_report(subjects, exams, evaluations)
    return _page(
        f'<header><h1>StudyFlow</h1><div class="muted">Análisis académico detallado · <span class="badge">Punto 9</span></div></header>'
        f'{_performance_summary_html(performance)}'
        f'<form method="get" action="/"><button type="submit">Volver al inicio</button></form>'
    )
def _make_plan(form):
    subjects = database.list_subjects(database_path=database.DATABASE_PATH)
    return planner.generate_study_plan(database.list_tasks(database_path=database.DATABASE_PATH), database.list_exams(database_path=database.DATABASE_PATH), _float(form,'hours','Las horas'), start_datetime=_start(form.get('start_time','')), subject_names=_names(subjects))


def _session_dict(x):
    return {'kind':x.kind,'source_id':x.source_id,'subject_id':x.subject_id,'subject_name':x.subject_name,'title':x.title,'minutes':x.minutes,'priority':x.priority,'deadline':x.deadline.isoformat(),'start':x.start.isoformat(),'end':x.end.isoformat()}


def application(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET").upper()

    if path == "/health" and method == "GET":
        try:
            database.initialize_database(database.DATABASE_PATH)
            return _json(start_response, {"status": "ok"})
        except database.DatabaseError as exc:
            return _json(start_response, {"status": "error", "detail": str(exc)}, "500 Internal Server Error")
        except Exception:
            LOGGER.exception("Error inesperado en /health")
            return _json(start_response, {"status": "error", "detail": "No se pudo comprobar la base de datos."}, "500 Internal Server Error")

    if path == "/api/averages" and method == "GET":
        try:
            return _json(
                start_response,
                analyzer.build_average_report(
                    database.list_subjects(database_path=database.DATABASE_PATH),
                    database.list_exams(database_path=database.DATABASE_PATH),
                    database.list_evaluations(database_path=database.DATABASE_PATH),
                ),
            )
        except database.DatabaseError as exc:
            return _json(start_response, {"error": str(exc)}, "500 Internal Server Error")
        except Exception:
            LOGGER.exception("Error inesperado en /api/averages")
            return _json(start_response, {"error": "No se pudo calcular los promedios."}, "500 Internal Server Error")

    if path == "/api/performance" and method == "GET":
        try:
            subjects = database.list_subjects(database_path=database.DATABASE_PATH)
            exams = database.list_exams(database_path=database.DATABASE_PATH)
            evaluations = database.list_evaluations(database_path=database.DATABASE_PATH)
            return _json(start_response, analyzer.build_performance_report(subjects, exams, evaluations))
        except (ValueError, database.DatabaseError) as exc:
            return _json(start_response, {"error": str(exc)}, "400 Bad Request")
        except Exception:
            LOGGER.exception("Error inesperado en /api/performance")
            return _json(start_response, {"error": "No se pudo generar el informe de rendimiento."}, "500 Internal Server Error")

    if path == "/api/priorities" and method == "GET":
        try:
            subjects = database.list_subjects(database_path=database.DATABASE_PATH)
            items = planner.rank_study_items(
                database.list_tasks(database_path=database.DATABASE_PATH),
                database.list_exams(database_path=database.DATABASE_PATH),
                date.today(),
            )
            names = _names(subjects)
            for item in items:
                item["subject_name"] = names.get(item["subject_id"], "Materia")
            return _json(start_response, {"date": date.today(), "items": items})
        except (ValueError, database.DatabaseError) as exc:
            return _json(start_response, {"error": str(exc)}, "400 Bad Request")
        except Exception:
            LOGGER.exception("Error inesperado en /api/priorities")
            return _json(start_response, {"error": "No se pudieron calcular las prioridades."}, "500 Internal Server Error")

    if path == "/api/study-plan" and method == "GET":
        try:
            q = {
                k: (v[0] if v else "")
                for k, v in parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True).items()
            }
            plan = _make_plan(q)
            return _json(
                start_response,
                {
                    "date": date.today(),
                    "available_hours": _float(q, "hours", "Las horas"),
                    "sessions": [_session_dict(x) for x in plan],
                    "study_minutes": sum(x.minutes for x in plan),
                },
            )
        except (ValueError, database.DatabaseError) as exc:
            return _json(start_response, {"error": str(exc)}, "400 Bad Request")
        except Exception:
            LOGGER.exception("Error inesperado en /api/study-plan")
            return _json(start_response, {"error": "No se pudo generar el plan de estudio."}, "500 Internal Server Error")

    if path == "/charts" and method == "GET":
        try:
            return _html(start_response, _charts_dashboard())
        except (ValueError, database.DatabaseError) as exc:
            LOGGER.exception("Error generando la página de gráficos")
            return _error_page(start_response, str(exc), "500 Internal Server Error", "Error al cargar los gráficos")
        except Exception:
            LOGGER.exception("Error inesperado generando la página de gráficos")
            return _error_page(start_response, "Ocurrió un error interno al cargar los gráficos.", "500 Internal Server Error", "Error interno")

    if path in {"/charts/grade-evolution.svg", "/charts/subject-averages.svg", "/charts/study-time.svg"} and method == "GET":
        try:
            subjects = database.list_subjects(database_path=database.DATABASE_PATH)
            tasks = database.list_tasks(database_path=database.DATABASE_PATH)
            exams = database.list_exams(database_path=database.DATABASE_PATH)
            evaluations = database.list_evaluations(database_path=database.DATABASE_PATH)
            if path.endswith("grade-evolution.svg"):
                svg = charts.plot_grade_evolution(evaluations, exams, subjects)
            elif path.endswith("subject-averages.svg"):
                svg = charts.plot_subject_averages(subjects, exams, evaluations)
            else:
                svg = charts.plot_study_time(tasks, subjects)
            data = svg.encode("utf-8")
            start_response(
                "200 OK",
                [
                    ("Content-Type", "image/svg+xml; charset=utf-8"),
                    ("Content-Length", str(len(data))),
                    ("Cache-Control", "no-store"),
                ],
            )
            return [data]
        except (ValueError, database.DatabaseError) as exc:
            return _json(start_response, {"error": str(exc)}, "400 Bad Request")
        except Exception:
            LOGGER.exception("Error inesperado generando un gráfico")
            return _json(start_response, {"error": "No se pudo generar el gráfico."}, "500 Internal Server Error")

    if path == "/analysis" and method == "GET":
        try:
            return _html(start_response, _analysis_dashboard())
        except (ValueError, database.DatabaseError) as exc:
            return _error_page(start_response, str(exc), "500 Internal Server Error", "Error al cargar el análisis")
        except Exception:
            LOGGER.exception("Error inesperado en /analysis")
            return _error_page(start_response, "Ocurrió un error interno al cargar el análisis.", "500 Internal Server Error", "Error interno")

    if path in {"/", "/evaluations"} and method == "GET":
        try:
            return _html(start_response, _dashboard())
        except (ValueError, database.DatabaseError) as exc:
            return _error_page(start_response, str(exc), "500 Internal Server Error", "Error al cargar StudyFlow")
        except Exception:
            LOGGER.exception("Error inesperado cargando el dashboard")
            return _error_page(start_response, "Ocurrió un error interno. Tus datos no se han eliminado.", "500 Internal Server Error", "Error interno")

    if method == "POST":
        try:
            form = _form(environ)

            if path == "/plan":
                return _html(start_response, _dashboard(plan=_make_plan(form)))

            if path == "/subjects":
                raw = _text(form, "subjects", "Las materias")
                subject_names = [name.strip() for name in re.split(r"[\r\n]+", raw) if name.strip()]
                if not subject_names:
                    raise ValueError("Escribe al menos una materia.")
                if len(subject_names) > 50:
                    raise ValueError("Puedes agregar como máximo 50 materias a la vez.")
                existing = {
                    subject.name.casefold(): subject.name
                    for subject in database.list_subjects(database_path=database.DATABASE_PATH)
                }
                added = []
                repeated = []
                for subject_name in subject_names:
                    key = subject_name.casefold()
                    if key in existing:
                        repeated.append(existing[key])
                        continue
                    created = database.create_subject(subject_name, database_path=database.DATABASE_PATH)
                    existing[key] = created.name
                    added.append(created.name)
                if added and repeated:
                    message = f"Materias guardadas: {', '.join(added)}. Ya existían: {', '.join(repeated)}."
                elif added:
                    message = f"Materias guardadas: {', '.join(added)}."
                else:
                    message = "Todas las materias que escribiste ya estaban guardadas."
                return _html(start_response, _dashboard(message=message))

            if path == "/tasks":
                sid = _int(form, "subject_id", "La materia")
                deadline = _date(form, "deadline", "La fecha límite")
                progress = _int(form, "progress", "El progreso")
                status = _text(form, "status", "El estado")
                if deadline < date.today():
                    raise ValueError("La fecha límite no puede estar antes de hoy.")
                if progress == 100:
                    status = "completed"
                elif status == "completed":
                    raise ValueError("Una tarea completada debe tener 100% de progreso.")
                database.create_task(
                    sid,
                    _text(form, "name", "El nombre"),
                    form.get("description", "").strip(),
                    deadline,
                    _int(form, "difficulty", "La dificultad"),
                    _int(form, "estimated_minutes", "El tiempo estimado"),
                    progress,
                    status,
                    database.DATABASE_PATH,
                )
                return _html(start_response, _dashboard(message="Tarea creada correctamente."))

            if path == "/exams":
                sid = _int(form, "subject_id", "La materia")
                exam_date = _date(form, "exam_date", "La fecha del examen")
                if exam_date < date.today():
                    raise ValueError("La fecha del examen no puede estar antes de hoy.")
                database.create_exam(
                    sid,
                    _text(form, "name", "El nombre"),
                    exam_date,
                    _int(form, "difficulty", "La dificultad"),
                    _float(form, "weight", "El peso"),
                    database.DATABASE_PATH,
                )
                return _html(start_response, _dashboard(message="Examen creado correctamente."))

            if path == "/evaluations":
                ev = database.create_evaluation(
                    _int(form, "exam_id", "El examen"),
                    _float(form, "grade", "La nota"),
                    _date(form, "date", "La fecha"),
                    _text(form, "type", "El tipo de evaluación"),
                    database.DATABASE_PATH,
                )
                return _html(start_response, _dashboard(message=f"Nota guardada correctamente: {ev.grade:g}/100"))

            match = re.fullmatch(r"/tasks/(\d+)/complete", path)
            if match:
                task = database.get_task(int(match.group(1)), database.DATABASE_PATH)
                database.update_task(
                    task.id,
                    task.subject_id,
                    task.name,
                    task.description,
                    task.deadline,
                    task.difficulty,
                    task.estimated_minutes,
                    100,
                    "completed",
                    database.DATABASE_PATH,
                )
                return _html(start_response, _dashboard(message="Tarea marcada como completada."))

            match = re.fullmatch(r"/subjects/(\d+)/delete", path)
            if match:
                database.delete_subject(int(match.group(1)), database.DATABASE_PATH)
                return _html(start_response, _dashboard(message="Materia eliminada correctamente."))

        except (ValueError, TypeError, KeyError, database.DatabaseError) as exc:
            return _operation_error(start_response, f"No se pudo completar la operación: {exc}", "200 OK")
        except Exception:
            LOGGER.exception("Error inesperado procesando una operación POST")
            return _error_page(start_response, "Ocurrió un error interno. No se perdió la información guardada.", "500 Internal Server Error", "Error interno")

    return _html(
        start_response,
        _page('<section class="card"><h2>404</h2><p>Página no encontrada.</p><form method="get" action="/"><button type="submit">Volver al inicio</button></form></section>', "404"),
        "404 Not Found",
    )

def run():
    host=os.getenv('HOST','0.0.0.0'); port=int(os.getenv('PORT','8000'))
    print(f"StudyFlow web server running at http://{host}:{port}")
    with make_server(host,port,application) as server: server.serve_forever()


if __name__ == '__main__': run()
