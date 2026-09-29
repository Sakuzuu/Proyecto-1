"""Dependency-free WSGI web application for StudyFlow."""
from datetime import date, datetime, time
from html import escape
import json
import os
import re
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

import analyzer
import database
import planner


def _page(body, title="StudyFlow"):
    return f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title><style>
body{{margin:0;background:#f4f6fb;color:#182230;font:15px system-ui,sans-serif}}main{{max-width:1100px;margin:auto;padding:24px 16px}}h1{{margin:0}}h2{{margin-bottom:10px}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.card{{background:#fff;border:1px solid #e4e7ec;border-radius:14px;padding:16px}}.wide{{grid-column:1/-1}}.metric{{font-size:30px;font-weight:800}}.muted{{color:#667085}}form{{display:grid;gap:7px}}input,select,textarea,button{{padding:9px;border:1px solid #d0d5dd;border-radius:8px;font:inherit}}button{{background:#182230;color:#fff;cursor:pointer}}table{{width:100%;border-collapse:collapse}}th,td{{padding:8px;text-align:left;border-bottom:1px solid #eaecf0}}th{{color:#667085}}.badge{{display:inline-block;padding:3px 7px;border-radius:999px;background:#f2f4f7;font-size:12px}}.red{{background:#fef3f2;color:#b42318}}.orange{{background:#fffaeb;color:#b54708}}.green{{background:#ecfdf3;color:#067647}}.notice,.error,.warning{{padding:10px 12px;border-radius:8px;margin-bottom:12px}}.notice{{background:#ecfdf3;color:#067647}}.error{{background:#fef3f2;color:#b42318}}.warning{{background:#fffaeb;color:#b54708}}.session{{border:1px solid #e4e7ec;border-radius:10px;padding:10px;margin:8px 0}}.session-time{{font-size:17px;font-weight:800}}@media(max-width:800px){{.grid{{grid-template-columns:1fr}}.wide{{grid-column:auto}}}}
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
    data = body.encode()
    start_response(status, [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(data)))])
    return [data]


def _form(environ):
    length = int(environ.get("CONTENT_LENGTH") or 0)
    if length < 0 or length > 10000:
        raise ValueError("El formulario es demasiado grande.")
    raw = environ.get("wsgi.input").read(length).decode()
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


def _dashboard(message="", error="", plan=None):
    subjects = database.list_subjects(database_path=database.DATABASE_PATH)
    tasks = database.list_tasks(database_path=database.DATABASE_PATH)
    exams = database.list_exams(database_path=database.DATABASE_PATH)
    evaluations = database.list_evaluations(database_path=database.DATABASE_PATH)
    report = analyzer.build_average_report(subjects, exams, evaluations)
    names = _names(subjects); today = date.today().isoformat()
    notice = (f'<div class="notice">{escape(message)}</div>' if message else '') + (f'<div class="error">{escape(error)}</div>' if error else '')
    overdue = sum(1 for x in planner.rank_study_items(tasks, exams, date.today()) if x['overdue'])
    if overdue: notice += f'<div class="warning">Hay {overdue} elemento(s) vencido(s). No se programan en el plan.</div>'
    subs = ''.join(f'<option value="{s.id}">{escape(s.name)}</option>' for s in subjects)
    exs = ''.join(f'<option value="{e.id}">{escape(names.get(e.subject_id,"Materia"))} — {escape(e.name)}</option>' for e in exams)
    dis = ' disabled' if not subjects else ''; edis = ' disabled' if not exams else ''
    start = planner._round_up_to_five_minutes(datetime.now()).strftime('%H:%M')
    body = f'''<header><h1>StudyFlow</h1><div class="muted">Planificación y análisis académico · <span class="badge">Punto 8</span></div></header>{notice}<div class="grid">
<section class="card"><h2>📅 Generador de plan de estudio</h2><p class="muted">Introduce tus horas disponibles y StudyFlow distribuye el tiempo entre tareas y exámenes según prioridad, tiempo y fecha límite.</p><form method="post" action="/plan"><label>Horas disponibles hoy</label><input name="hours" type="number" min="0.25" max="16" step="0.25" value="3" required><label>Hora de inicio</label><input name="start_time" type="time" value="{start}" required><button>Generar plan de hoy</button></form><p class="muted">Máximo 80 min por sesión y 15 min de descanso.</p></section>
<section class="card"><h2>📊 Promedio actual</h2><div class="metric">{report['general_average']:g}/100</div><p class="muted">Promedio general actual</p><p><span class="badge">{len(tasks)} tareas</span> <span class="badge">{len(exams)} exámenes</span></p></section>
<section class="card wide"><h2>🎯 Prioridades de estudio</h2>{_priority_html(tasks, exams, subjects)}</section>
<section class="card wide"><h2>➕ Agregar datos</h2><div class="grid"><form method="post" action="/tasks"><h3>Nueva tarea</h3><label>Materia</label><select name="subject_id" required{dis}>{subs}</select><label>Nombre</label><input name="name" required><label>Descripción</label><textarea name="description"></textarea><label>Fecha límite</label><input name="deadline" type="date" min="{today}" required><label>Dificultad (1–10)</label><input name="difficulty" type="number" min="1" max="10" value="5" required><label>Tiempo estimado (min)</label><input name="estimated_minutes" type="number" min="1" value="60" required><label>Progreso</label><input name="progress" type="number" min="0" max="100" value="0" required><label>Estado</label><select name="status"><option value="pending">Pendiente</option><option value="in_progress">En progreso</option><option value="completed">Completada</option></select><button{dis}>Guardar tarea</button></form><form method="post" action="/exams"><h3>Nuevo examen</h3><label>Materia</label><select name="subject_id" required{dis}>{subs}</select><label>Nombre</label><input name="name" required><label>Fecha del examen</label><input name="exam_date" type="date" min="{today}" required><label>Dificultad (1–10)</label><input name="difficulty" type="number" min="1" max="10" value="7" required><label>Peso (%)</label><input name="weight" type="number" min="0" max="100" step="0.1" value="20" required><button{dis}>Guardar examen</button></form></div></section>
<section class="card"><h2>📝 Registrar nota</h2><form method="post" action="/evaluations"><label>Examen</label><select name="exam_id" required{edis}>{exs}</select><label>Nota (0–100)</label><input name="grade" type="number" min="0" max="100" step="0.01" required{edis}><label>Fecha</label><input name="date" type="date" value="{today}" required{edis}><label>Tipo de evaluación</label><input name="type" required{edis}><button{edis}>Guardar nota</button></form></section>
<section class="card"><h2>📈 Resumen</h2><p><strong>{report['evaluated_exams']}</strong> exámenes con nota.</p><p><strong>{report['total_evaluations']}</strong> evaluaciones almacenadas.</p></section>
<section class="card wide"><h2>Promedios por materia</h2><table><tr><th>Materia</th><th>Promedio</th><th>Meta</th><th>Notas</th></tr>{''.join(f"<tr><td>{escape(r['subject_name'])}</td><td><strong>{r['average']:g}</strong></td><td>{r['target_grade']:g}</td><td>{r['evaluation_count']}</td></tr>" for r in report['subjects'])}</table></section>
<section class="card wide"><h2>Tareas registradas</h2>{'<p class="muted">No hay tareas registradas.</p>' if not tasks else ''.join(f"<p><strong>{escape(names.get(t.subject_id,'Materia'))}</strong> · {escape(t.name)} · {t.deadline} · {t.progress}% {'✅' if t.status=='completed' else ''}</p>" for t in tasks)}</section>
<section class="card wide"><h2>Exámenes registrados</h2>{'<p class="muted">No hay exámenes registrados.</p>' if not exams else ''.join(f"<p><strong>{escape(names.get(e.subject_id,'Materia'))}</strong> · {escape(e.name)} · {e.date} · preparación sugerida: {planner.estimate_exam_minutes(e)} min</p>" for e in exams)}</section>
<section class="card wide"><h2>Evaluaciones registradas</h2>{'<p class="muted">Todavía no hay notas registradas.</p>' if not evaluations else ''.join(f"<p>{escape(names.get(next((e.subject_id for e in exams if e.id==v.exam_id),0),'Materia'))} · {v.grade:g}/100 · {v.date} · {escape(v.evaluation_type)}</p>" for v in evaluations)}</section>'''
    if plan is not None: body += f'<section class="card wide"><h2>HOY · Plan generado</h2>{_plan_html(plan)}</section>'
    return _page(body+'</div>')


def _make_plan(form):
    subjects = database.list_subjects(database_path=database.DATABASE_PATH)
    return planner.generate_study_plan(database.list_tasks(database_path=database.DATABASE_PATH), database.list_exams(database_path=database.DATABASE_PATH), _float(form,'hours','Las horas'), start_datetime=_start(form.get('start_time','')), subject_names=_names(subjects))


def _session_dict(x):
    return {'kind':x.kind,'source_id':x.source_id,'subject_id':x.subject_id,'subject_name':x.subject_name,'title':x.title,'minutes':x.minutes,'priority':x.priority,'deadline':x.deadline.isoformat(),'start':x.start.isoformat(),'end':x.end.isoformat()}


def application(environ, start_response):
    path = environ.get('PATH_INFO','/'); method = environ.get('REQUEST_METHOD','GET').upper()
    if path == '/health':
        try: database.initialize_database(database.DATABASE_PATH); return _json(start_response, {'status':'ok'})
        except database.DatabaseError as exc: return _json(start_response, {'status':'error','detail':str(exc)}, '500 Internal Server Error')
    if path == '/api/averages' and method == 'GET':
        try: return _json(start_response, analyzer.build_average_report(database.list_subjects(database_path=database.DATABASE_PATH), database.list_exams(database_path=database.DATABASE_PATH), database.list_evaluations(database_path=database.DATABASE_PATH)))
        except database.DatabaseError as exc: return _json(start_response, {'error':str(exc)}, '500 Internal Server Error')
    if path == '/api/priorities' and method == 'GET':
        try:
            subjects=database.list_subjects(database_path=database.DATABASE_PATH); items=planner.rank_study_items(database.list_tasks(database_path=database.DATABASE_PATH), database.list_exams(database_path=database.DATABASE_PATH), date.today()); names=_names(subjects)
            for item in items: item['subject_name']=names.get(item['subject_id'],'Materia')
            return _json(start_response, {'date':date.today(),'items':items})
        except (ValueError,database.DatabaseError) as exc: return _json(start_response, {'error':str(exc)}, '400 Bad Request')
    if path == '/api/study-plan' and method == 'GET':
        try:
            q={k:(v[0] if v else '') for k,v in parse_qs(environ.get('QUERY_STRING',''),keep_blank_values=True).items()}; plan=_make_plan(q)
            return _json(start_response, {'date':date.today(),'available_hours':_float(q,'hours','Las horas'),'sessions':[_session_dict(x) for x in plan],'study_minutes':sum(x.minutes for x in plan)})
        except (ValueError,database.DatabaseError) as exc: return _json(start_response, {'error':str(exc)}, '400 Bad Request')
    if path in {'/','/evaluations'} and method == 'GET':
        try: return _html(start_response, _dashboard())
        except (ValueError,database.DatabaseError) as exc: return _html(start_response, _page(f'<section class="card"><h2>Error</h2><p>{escape(str(exc))}</p></section>','Error'),'500 Internal Server Error')
    if method == 'POST':
        try:
            form=_form(environ)
            if path == '/plan': return _html(start_response,_dashboard(plan=_make_plan(form)))
            if path == '/tasks':
                sid=_int(form,'subject_id','La materia'); deadline=_date(form,'deadline','La fecha límite'); progress=_int(form,'progress','El progreso'); status=_text(form,'status','El estado')
                if deadline < date.today(): raise ValueError('La fecha límite no puede estar antes de hoy.')
                if progress == 100: status='completed'
                elif status == 'completed': raise ValueError('Una tarea completada debe tener 100% de progreso.')
                database.create_task(sid,_text(form,'name','El nombre'),form.get('description','').strip(),deadline,_int(form,'difficulty','La dificultad'),_int(form,'estimated_minutes','El tiempo estimado'),progress,status,database.DATABASE_PATH)
                return _html(start_response,_dashboard(message='Tarea creada correctamente.'))
            if path == '/exams':
                sid=_int(form,'subject_id','La materia'); exam_date=_date(form,'exam_date','La fecha del examen')
                if exam_date < date.today(): raise ValueError('La fecha del examen no puede estar antes de hoy.')
                database.create_exam(sid,_text(form,'name','El nombre'),exam_date,_int(form,'difficulty','La dificultad'),_float(form,'weight','El peso'),database.DATABASE_PATH)
                return _html(start_response,_dashboard(message='Examen creado correctamente.'))
            if path == '/evaluations':
                try:
                    ev=database.create_evaluation(_int(form,'exam_id','El examen'),_float(form,'grade','La nota'),_date(form,'date','La fecha'),_text(form,'type','El tipo de evaluación'),database.DATABASE_PATH)
                except (ValueError,TypeError,KeyError,database.DatabaseError) as exc:
                    return _html(start_response,_dashboard(error=f'No se pudo guardar la evaluación: {exc}'))
                return _html(start_response,_dashboard(message=f'Nota guardada correctamente: {ev.grade:g}/100'))
            m=re.fullmatch(r'/tasks/(\d+)/complete',path)
            if m:
                task=database.get_task(int(m.group(1)),database.DATABASE_PATH); database.update_task(task.id,task.subject_id,task.name,task.description,task.deadline,task.difficulty,task.estimated_minutes,100,'completed',database.DATABASE_PATH)
                return _html(start_response,_dashboard(message='Tarea marcada como completada.'))
        except (ValueError,TypeError,KeyError,database.DatabaseError) as exc:
            return _html(start_response,_dashboard(error=f'No se pudo completar la operación: {exc}'))
    return _html(start_response,_page('<section class="card"><h2>404</h2><p>Página no encontrada.</p></section>','404'),'404 Not Found')


def run():
    host=os.getenv('HOST','0.0.0.0'); port=int(os.getenv('PORT','8000'))
    print(f"StudyFlow web server running at http://{host}:{port}")
    with make_server(host,port,application) as server: server.serve_forever()


if __name__ == '__main__': run()
