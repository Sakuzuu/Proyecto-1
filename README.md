# StudyFlow

Aplicación de Python para gestionar el estudio y analizar el rendimiento académico.

## Estado actual

**Punto 1 — Estructura general:** completado.  
**Punto 2 — Sistema de materias:** completado.  
**Punto 3 — Base de datos:** completado.  
**Punto 4 — Sistema de tareas y actividades:** completado.  
**Punto 5 — Sistema de exámenes:** completado.  
**Punto 6 — Registro de notas y evaluaciones:** completado.

## Punto 6 — Registro de notas

Los resultados se almacenan como evaluaciones separadas del examen programado.

Cada evaluación contiene:

```text
id
exam_id
grade
date
evaluation_type
```

El backend permite:

- Registrar notas.
- Consultar una nota por ID.
- Listar evaluaciones.
- Filtrar evaluaciones por examen.
- Editar notas.
- Eliminar notas.
- Validar nota entre 0 y 100.
- Validar fecha, examen y tipo de evaluación.
- Impedir evaluaciones asociadas a exámenes inexistentes.

La separación entre `exams` y `evaluations` permitirá analizar la evolución histórica sin modificar el modelo de exámenes.

## Primera interfaz web funcional

El proyecto incluye una interfaz web en `web_app.py`.

No depende de Tkinter ni de paquetes externos: utiliza WSGI y la biblioteca estándar de Python.

Ejecutarla localmente:

```bash
python web_app.py
```

Abrir:

```text
http://localhost:8000
```

La página permite:

- Ver materias y exámenes.
- Registrar una nota mediante formulario.
- Ver evaluaciones registradas.
- Consultar `/health`.

### Publicación mediante enlace

`web_app.py` expone una aplicación WSGI y escucha en `0.0.0.0`, usando la variable de entorno `PORT`.

El proyecto queda listo para ser conectado a un servicio de hosting Python que proporcione una URL pública. La creación de esa URL requiere desplegar el repositorio en un proveedor de hosting; este commit ya incluye el punto de entrada web.

## Arquitectura

```text
Navegador
   ↓ HTTP
web_app.py (WSGI)
   ↓
database.py
   ↓
SQLite
```

La interfaz web reutiliza el mismo backend de datos que las futuras funciones del proyecto.

## Estructura

```text
StudyFlow/
├── main.py
├── web_app.py
├── database.py
├── models.py
├── planner.py
├── analyzer.py
├── calculations.py
├── interface.py
├── charts.py
├── schema.sql
├── Procfile
├── tests/
│   ├── test_subjects.py
│   ├── test_database_schema.py
│   ├── test_tasks.py
│   ├── test_exams.py
│   └── test_evaluations.py
├── README.md
└── data/
```

## Tecnologías

- Python 3
- SQLite
- WSGI + HTML/CSS (interfaz web)
- Tkinter (interfaz de escritorio temporal)
- Matplotlib (fase posterior)
- API de IA opcional (fase posterior)

## Pruebas

```bash
python -m unittest discover -s tests -v
```
