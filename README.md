# StudyFlow

Aplicación de Python para gestionar el estudio y analizar el rendimiento académico.

## Estado actual

**Punto 1 — Estructura general:** completado.  
**Punto 2 — Sistema de materias:** completado.  
**Punto 3 — Base de datos:** completado.

## Arquitectura de datos

StudyFlow utiliza **SQLite** como capa de persistencia. El esquema completo está separado en `schema.sql` para que la lógica de acceso a datos no dependa de la interfaz gráfica.

Tablas principales:

- `subjects`: materias.
- `tasks`: tareas y actividades.
- `exams`: exámenes programados.
- `evaluations`: resultados de evaluaciones.

Relaciones:

```text
subjects
   ├── tasks
   └── exams
          └── evaluations
```

Las claves foráneas, restricciones de rango e índices se aplican directamente en SQLite. La inicialización es idempotente y mantiene la versión del esquema mediante `PRAGMA user_version`.

## Sistema de materias

- Crear materias.
- Consultar una materia por ID.
- Listar y buscar materias.
- Editar materias.
- Eliminar materias.
- Validar nombre, profesor y meta de nota.
- Evitar nombres duplicados sin importar mayúsculas/minúsculas.
- Impedir la eliminación cuando ya existen tareas o exámenes asociados.
- Persistir los datos en SQLite.

## Preparación para interfaz web

La capa de base de datos crea una conexión independiente por operación y no importa componentes de Tkinter. Esto permite que el mismo backend sea utilizado posteriormente por:

```text
                  ┌── Interfaz web (navegador)
                  │
Usuario → HTTP → Capa de aplicación
                  │
                  ├── Analizador
                  ├── Planificador
                  └── Base de datos SQLite
                  │
                  └── interfaz de escritorio temporal
```

La interfaz gráfica definitiva podrá ser web, de modo que el usuario acceda a StudyFlow desde un navegador sin duplicar la lógica de datos.

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
│   └── test_database_schema.py
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

Ejecutar toda la suite con:

```bash
python -m unittest discover -s tests -v
```
