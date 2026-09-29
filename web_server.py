"""Web entry point with milestone-11 insights layered onto the existing StudyFlow app."""
from datetime import date
from html import escape
import json
from urllib.parse import parse_qs

import analyzer
import database
import web_app

_ORIGINAL_APPLICATION = web_app.application


def _query(environ):
    return {k: (v[0] if v else "") for k, v in parse_qs(
        environ.get("QUERY_STRING", ""), keep_blank_values=True
    ).items()}


def _threshold(value, label, default):
    if value in (None, ""):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} debe ser un número válido.") from exc
    return number


def _render_group(title, rows, css_class):
    if not rows:
        return f"<section class='insight-group {css_class}'><h3>{escape(title)}</h3><p class='muted'>Ninguna materia en esta categoría.</p></section>"
    items = []
    for row in rows:
        items.append(
            f"<div class='insight-item'>"
            f"<strong>{escape(row['subject_name'])}</strong>"
            f"<span>{row['average']:g}/100</span>"
            f"</div>"
        )
    return (
        f"<section class='insight-group {css_class}'>"
        f"<h3>{escape(title)}</h3>{''.join(items)}</section>"
    )


def _analysis_dashboard(environ):
    q = _query(environ)
    defaults = analyzer.get_default_thresholds()
    strength = _threshold(q.get("strength"), "El umbral de fortaleza", defaults.strength)
    attention = _threshold(q.get("attention"), "El umbral de atención", defaults.attention)
    report = analyzer.detect_strengths_and_weaknesses(
        database.list_subjects(database_path=database.DATABASE_PATH),
        database.list_exams(database_path=database.DATABASE_PATH),
        database.list_evaluations(database_path=database.DATABASE_PATH),
        strength_threshold=strength,
        attention_threshold=attention,
    )

    groups = (
        _render_group("✓ Fortalezas", report["strengths"], "strength"),
        _render_group("• Rendimiento normal", report["normal"], "normal"),
        _render_group("⚠ Atención", report["attention"], "attention"),
    )
    trend_rows = []
    for row in report["trends"]:
        trend_class = (
            "trend-up" if row["trend_status"] == "up"
            else "trend-down" if row["trend_status"] == "down"
            else "trend-flat"
        )
        trend_rows.append(
            f"<tr><td>{escape(row['subject_name'])}</td>"
            f"<td><span class='badge {trend_class}'>{escape(row['trend'])}</span></td></tr>"
        )
    trends_table = (
        "<table><tr><th>Materia</th><th>Tendencia</th></tr>" + "".join(trend_rows) + "</table>"
        if trend_rows
        else "<p class='muted'>Todavía no hay suficientes evaluaciones para calcular tendencias.</p>"
    )
    no_data = (
        f"<p class='muted'>Sin evaluaciones: {', '.join(escape(r['subject_name']) for r in report['without_data'])}.</p>"
        if report["without_data"] else ""
    )

    body = f"""
<header><h1>StudyFlow</h1><div class='muted'>Análisis académico · <span class='badge'>Punto 11</span></div></header>
<section class='card wide'>
<h2>🔎 Fortalezas y debilidades</h2>
<p class='muted'>StudyFlow clasifica cada materia con su promedio actual y detecta si la tendencia está subiendo, bajando o aún no tiene suficientes datos.</p>
<form method='get' action='/analysis' class='threshold-form'>
<label>Umbral de fortaleza (≥)</label><input name='strength' type='number' min='0' max='100' step='0.1' value='{strength:g}' required>
<label>Umbral de atención (&lt;)</label><input name='attention' type='number' min='0' max='100' step='0.1' value='{attention:g}' required>
<button type='submit'>Actualizar análisis</button>
</form>
<p class='muted'>Valores por defecto: fortaleza ≥ {defaults.strength:g}; atención &lt; {defaults.attention:g}. También puedes configurarlos en Render con <code>STUDYFLOW_STRENGTH_THRESHOLD</code> y <code>STUDYFLOW_ATTENTION_THRESHOLD</code>.</p>
</section>
<section class='card wide'>
<div class='insight-grid'>{''.join(groups)}</div>
{no_data}
</section>
<section class='card wide'>
<h2>📉 Tendencias</h2>
{trends_table}
</section>
<section class='card wide'>
<h2>Resumen del análisis</h2>
<div class='metric-grid'>
<div class='metric-box'><div class='muted'>Fortalezas</div><div class='metric'>{len(report['strengths'])}</div></div>
<div class='metric-box'><div class='muted'>Normales</div><div class='metric'>{len(report['normal'])}</div></div>
<div class='metric-box'><div class='muted'>Atención</div><div class='metric'>{len(report['attention'])}</div></div>
<div class='metric-box'><div class='muted'>Sin datos</div><div class='metric'>{len(report['without_data'])}</div></div>
</div>
</section>
<div style='display:flex;gap:8px;flex-wrap:wrap'>
<form method='get' action='/'><button type='submit'>Volver al inicio</button></form>
<form method='get' action='/charts'><button type='submit'>Ver gráficos</button></form>
</div>
<style>
.insight-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}
.insight-group{{border:1px solid #e4e7ec;border-radius:12px;padding:14px}}
.insight-item{{display:flex;justify-content:space-between;gap:12px;padding:9px 0;border-bottom:1px solid #eaecf0}}
.insight-item:last-child{{border-bottom:0}}
.threshold-form{{display:grid;grid-template-columns:1fr 1fr auto;gap:8px;align-items:end}}
.threshold-form button{{height:42px}}
code{{background:#f2f4f7;padding:2px 5px;border-radius:5px}}
.trend-up{{background:#ecfdf3;color:#067647}}
.trend-down{{background:#fef3f2;color:#b42318}}
.trend-flat{{background:#f2f4f7;color:#344054}}
@media(max-width:800px){{.insight-grid,.threshold-form{{grid-template-columns:1fr}}}}
</style>
"""
    return web_app._page(body, "Análisis académico · StudyFlow")


def _json(start_response, payload, status="200 OK"):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    start_response(status, [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(data))),
    ])
    return [data]


def application(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET").upper()

    if path == "/analysis" and method == "GET":
        try:
            q = _query(environ)
            defaults = analyzer.get_default_thresholds()
            strength = _threshold(q.get("strength"), "El umbral de fortaleza", defaults.strength)
            attention = _threshold(q.get("attention"), "El umbral de atención", defaults.attention)
            if not 0 <= attention < strength <= 100:
                raise ValueError("Los umbrales deben cumplir 0 ≤ atención < fortaleza ≤ 100.")
            return web_app._html(start_response, _analysis_dashboard(environ))
        except (ValueError, database.DatabaseError) as exc:
            return web_app._html(
                start_response,
                web_app._page(
                    f"<section class='card'><h2>Error de configuración</h2><p>{escape(str(exc))}</p></section>",
                    "Error",
                ),
                "400 Bad Request",
            )

    if path == "/api/insights" and method == "GET":
        try:
            q = _query(environ)
            defaults = analyzer.get_default_thresholds()
            strength = _threshold(q.get("strength"), "El umbral de fortaleza", defaults.strength)
            attention = _threshold(q.get("attention"), "El umbral de atención", defaults.attention)
            if not 0 <= attention < strength <= 100:
                raise ValueError("Los umbrales deben cumplir 0 ≤ atención < fortaleza ≤ 100.")
            report = analyzer.detect_strengths_and_weaknesses(
                database.list_subjects(database_path=database.DATABASE_PATH),
                database.list_exams(database_path=database.DATABASE_PATH),
                database.list_evaluations(database_path=database.DATABASE_PATH),
                strength_threshold=strength,
                attention_threshold=attention,
            )
            return _json(start_response, report)
        except (ValueError, database.DatabaseError) as exc:
            return _json(start_response, {"error": str(exc)}, "400 Bad Request")

    return _ORIGINAL_APPLICATION(environ, start_response)


if __name__ == "__main__":
    web_app.run.__globals__["application"] = application
    web_app.run()
