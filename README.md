# StudyFlow

Aplicación de Python para gestionar el estudio y analizar el rendimiento académico.

## Estado actual

**Punto 1 — Estructura general:** completado.  
**Punto 2 — Sistema de materias:** completado.  
**Punto 3 — Base de datos:** completado.  
**Punto 4 — Sistema de tareas y actividades:** completado.  
**Punto 5 — Sistema de exámenes:** completado.

## Sistema de exámenes

Los exámenes están relacionados con una materia mediante `subject_id`.

Cada examen almacena:

```text
id
subject_id
name
date
difficulty
weight
```

El backend permite:

- Crear exámenes.
- Consultar un examen por ID.
- Listar exámenes.
- Filtrar por materia.
- Editar exámenes.
- Eliminar exámenes.
- Validar nombre, fecha, dificultad y peso.
- Rechazar exámenes asociados a materias inexistentes.

El registro de las notas de estos exámenes se mantiene separado y se implementará en el siguiente módulo para conservar una separación clara entre **examen programado** y **resultado obtenido**.

## Arquitectura preparada para web

El sistema de exámenes sigue usando el mismo backend independiente de Tkinter:

```text
Navegador
   ↓ HTTP
Capa web / API
   ↓
Lógica StudyFlow
   ↓
SQLite
```

No se añade lógica de interfaz al modelo ni al acceso a datos. Así, la futura interfaz web podrá consumir estas operaciones sin duplicar el código de negocio.

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
│   ├── test_tasks.py
│   └── test_exams.py
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

Pruebas del sistema de exámenes:

```bash
python -m unittest discover -s tests -p "test_exams.py" -v
```

Suite general:

```bash
python -m unittest discover -s tests -v
```
