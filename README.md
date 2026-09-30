# StudyFlow

Aplicación de Python para gestionar el estudio y analizar el rendimiento académico.

## Estado actual

**Punto 1 — Estructura general:** completado.  
**Punto 2 — Sistema de materias:** completado.  
**Punto 3 — Base de datos:** completado.  
**Punto 4 — Sistema de tareas y actividades:** completado.  
**Punto 5 — Sistema de exámenes:** completado.  
**Punto 6 — Registro de notas y evaluaciones:** completado.  
**Punto 7 — Promedios:** completado.  
**Punto 8 — Generador de plan de estudio:** completado.  
**Punto 9 — Dashboard de rendimiento:** completado.  
**Punto 10 — Visualizaciones académicas:** completado.  
**Punto 11 — Detección de fortalezas y debilidades:** completado.  \n**Punto 15 — Validación y manejo de errores:** completado.

## Punto 15 — Validación y manejo de errores

La aplicación valida campos obligatorios, números, rangos y fechas antes de guardar datos. Los errores de formularios se muestran en la página sin cerrar el programa, mientras que las APIs devuelven respuestas JSON controladas. La eliminación de materias está protegida cuando existen tareas o exámenes asociados. La base de datos se crea automáticamente cuando falta el archivo y los fallos de infraestructura se registran sin exponer trazas al usuario.

La integración de una API de IA todavía no forma parte de los puntos implementados; cuando se incorpore, sus fallos deberán manejarse como errores de servicio y no como excepciones que detengan la aplicación.

## Punto 7 — Promedios

StudyFlow calcula los promedios académicos a partir de las evaluaciones registradas.

Reglas actuales:

- Para cada examen se toma la **evaluación más reciente** como resultado actual.
- El promedio de una materia usa los pesos de sus exámenes cuando la suma de pesos es mayor que cero.
- Si todos los pesos relevantes son cero, se usa el promedio aritmético.
- Las evaluaciones históricas siguen almacenadas para las fases futuras de tendencias y progreso.
- También se calcula un promedio general con la misma regla de ponderación.

## Interfaz web

La aplicación funciona como una página web con WSGI y la biblioteca estándar de Python.

Incluye:

- Registro de notas.
- Promedio general actual.
- Promedios por materia.
- Comparación con la meta de cada materia.
- Historial de evaluaciones.
- Endpoint JSON `/api/averages`.
- Endpoint JSON `/api/priorities`.
- Endpoint JSON `/api/study-plan`.
- Endpoint JSON `/api/performance`.
- Endpoint JSON `/api/insights` para fortalezas, rendimiento normal, atención y tendencias.
- Dashboard de rendimiento con promedio general, mejor materia, menor promedio y tendencia.
- Página de análisis detallado en `/analysis`, con umbrales configurables para fortalezas y atención.
- Página de gráficos en `/charts` con evolución de notas, promedios por materia y tiempo de estudio.
- Endpoint de salud `/health`.
- Diseño responsive para escritorio y móvil.

Ejecutar localmente:

```bash
python web_server.py
```

Abrir:

```text
http://localhost:8000
```

## Publicación en internet

El repositorio contiene `render.yaml` configurado para Render como servicio web Python, incluyendo `/health` como health check.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Sakuzuu/Proyecto-1)

Render asigna una URL pública `onrender.com` al servicio cuando se crea el despliegue. El botón anterior permite crear el servicio desde este repositorio público. Una vez creado, los siguientes cambios en la rama conectada pueden redeplegarse automáticamente.

## Arquitectura

```text
Navegador
   ↓ HTTP
web_server.py (WSGI)
   ↓
web_app.py + analyzer.py
   ↓
database.py
   ↓
SQLite
```

## Estructura

```text
StudyFlow/
├── main.py
├── web_app.py
├── web_server.py
├── database.py
├── models.py
├── planner.py
├── analyzer.py
├── calculations.py
├── interface.py
├── charts.py
├── schema.sql
├── Procfile
├── render.yaml
├── tests/
│   ├── test_subjects.py
│   ├── test_database_schema.py
│   ├── test_tasks.py
│   ├── test_exams.py
│   ├── test_evaluations.py
│   ├── test_averages.py
│   ├── test_planner.py
│   ├── test_performance.py
│   └── test_charts.py
├── .github/
│   └── workflows/
│       └── tests.yml
├── README.md
└── data/
```

## Tecnologías

- Python 3
- SQLite
- WSGI + HTML/CSS
- Tkinter (interfaz de escritorio temporal)
- SVG generado directamente desde Python (sin dependencias externas)
- API de IA opcional (fase posterior)

## Pruebas

```bash
python -m unittest discover -s tests -v
```
