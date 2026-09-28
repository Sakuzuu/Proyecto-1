# StudyFlow

Aplicación de escritorio en Python para gestionar el estudio y analizar el rendimiento académico.

## Estado actual

**Punto 1 — Estructura general:** completado.  
**Punto 2 — Sistema de materias:** completado.

## Funcionalidades implementadas

### Sistema de materias
- Crear materias.
- Consultar una materia por ID.
- Listar y buscar materias.
- Editar materias.
- Eliminar materias.
- Validar nombre, profesor y meta de nota.
- Evitar nombres duplicados sin importar mayúsculas/minúsculas.
- Impedir la eliminación cuando ya existen tareas o exámenes asociados.
- Persistir los datos en SQLite.

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
├── tests/
│   └── test_subjects.py
├── README.md
└── data/
```

## Tecnologías

- Python 3
- Tkinter
- SQLite
- Matplotlib (fase posterior)
- API de IA opcional (fase posterior)

## Pruebas

Las pruebas del sistema de materias se ejecutan con:

```bash
python -m unittest discover -s tests -v
```
