# StudyFlow

Aplicación de Python para gestionar el estudio y analizar el rendimiento académico.

## Estado actual

**Punto 1 — Estructura general:** completado.  
**Punto 2 — Sistema de materias:** completado.  
**Punto 3 — Base de datos:** completado.  
**Punto 4 — Sistema de tareas y actividades:** completado.

## Sistema de tareas

Las tareas están relacionadas con una materia mediante `subject_id`.

Cada tarea almacena:

```text
id
subject_id
name
description
deadline
difficulty
estimated_minutes
progress
status
```

Estados válidos:

- `pending`
- `in_progress`
- `completed`

El modelo valida los campos antes de enviarlos a SQLite y la base de datos mantiene las restricciones como segunda línea de defensa.

El backend permite:

- Crear tareas.
- Consultar tareas por ID.
- Listar tareas.
- Filtrar por materia.
- Filtrar por estado.
- Editar tareas.
- Eliminar tareas.
- Rechazar tareas asociadas a materias inexistentes.

## Arquitectura preparada para web

La lógica de tareas y la persistencia siguen sin depender de Tkinter. Esto permite que más adelante una capa HTTP/REST exponga estas operaciones a una interfaz web.

La idea será:

```text
Navegador
   ↓ HTTP
Capa web / API
   ↓
Lógica StudyFlow
   ↓
SQLite
```

La aplicación de escritorio actual queda como interfaz temporal; no será necesario duplicar la lógica de negocio para la versión web.

## Estructura

```text
StudyFlow/
├── main.py
├── database.py
├── models.py
├── planner.py
├── analyzer.py
├── calculations.py
├── interface.py
├── charts.py
├── schema.sql
├── tests/
│   ├── test_subjects.py
│   ├── test_database_schema.py
│   └── test_tasks.py
├── README.md
└── data/
```

## Tecnologías

- Python 3
- SQLite
- Tkinter (interfaz temporal existente)
- Futuro frontend web sobre navegador
- Matplotlib (fase posterior)
- API de IA opcional (fase posterior)

## Pruebas

Pruebas del sistema de tareas:

```bash
python -m unittest discover -s tests -p "test_tasks.py" -v
```

Suite general:

```bash
python -m unittest discover -s tests -v
```
