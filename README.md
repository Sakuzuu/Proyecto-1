# StudyFlow

Versión de navegador de StudyFlow para registrar materias y notas y calcular el rendimiento académico durante la sesión.

## Punto 11 — Versión HTML, CSS y JavaScript

Esta entrega responde a la observación del profesor: la aplicación funciona directamente en el navegador y **no necesita Python, SQLite, un servidor de aplicación ni una API**.

Incluye:

- Registro de materias durante la sesión.
- Registro de notas de 0 a 100 asociadas a cada materia.
- Cálculo del promedio general en tiempo real.
- Cálculo del promedio por materia.
- Meta académica elegida por el usuario, con valor inicial de 70/100.
- Aviso visual automático cuando el promedio queda por debajo de la meta.
- Confirmación visual cuando se alcanza o supera la meta.
- Validación de datos y mensajes de error sin cerrar ni recargar la página.
- Eliminación de materias y notas.
- Botón para limpiar toda la sesión.
- Diseño responsive para escritorio y móvil.

### Funcionamiento de la sesión

Los datos se mantienen únicamente en la memoria de JavaScript mientras la página está abierta. No se guardan en una base de datos ni en `localStorage`; al cerrar o recargar la página se inicia una sesión nueva.

## Ejecutar

No se necesita instalar Python ni una base de datos. También puede abrirse `index.html` directamente en un navegador moderno.

Para probarlo mediante un servidor de archivos estáticos, cualquier servidor HTTP estático es suficiente.

## Pruebas

Las pruebas usan Node.js y comprueban la lógica de promedios, validaciones, alertas de meta, estructura HTML/CSS/JS y el flujo de interacción de la interfaz con un DOM simulado.

```bash
node --test tests/test_app.mjs
```

## Publicación

La configuración de Render usa un **Static Site**, por lo que la aplicación publicada se sirve como archivos estáticos y no ejecuta Python.

## Tecnologías

- HTML5
- CSS3
- JavaScript (ES2022+)
- Node.js únicamente para ejecutar las pruebas del proyecto
