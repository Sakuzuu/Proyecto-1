# IA1 — Diagnóstico adaptativo de StudyFlow

Implementa los pasos 1 a 5: alcance, banco revisado, almacenamiento protegido, interfaz y adaptación por reglas. No utiliza modelos de IA, claves privadas ni servicios de pago.

## Uso

Inicia sesión, abre StudyFlow y elige **Diagnóstico adaptativo**. Selecciona uno o más temas y 10, 15 o 20 minutos. Responde hasta diez preguntas; con un único tema puede terminar antes al agotar sus nueve preguntas. Las pistas se registran y la sesión se retoma desde Supabase al recargar dentro de su plazo. Las explicaciones se guardan como apuntes; no se califican automáticamente.

Cada tema empieza en dificultad intermedia. Dos aciertos sin ayuda en el mismo nivel elevan la dificultad; dos errores la reducen. Los temas seleccionados se equilibran por cantidad de respuestas. Dos errores en producto o cadena pueden llevar a reglas básicas como requisito previo. Nunca se repite una pregunta dentro de una sesión.

El informe distingue aciertos independientes, aciertos con pistas y errores. Menos de tres respuestas en un tema se presenta como evidencia insuficiente. El resultado orienta la práctica y no es una nota oficial.

## Base de datos

`supabase/ia1.sql` es el script aditivo de instalación para un proyecto StudyFlow existente. Ejecutarlo una sola vez en el proyecto configurado. No elimina tablas ni datos existentes. El banco reproducible y sus expresiones para verificación numérica están en `supabase/seed/diagnostic-questions.json`.

Tablas: `diagnostic_questions`, `diagnostic_solutions`, `diagnostic_sessions`, `diagnostic_answers`, `topic_progress`. Todas tienen RLS. El navegador solo puede leer sus sesiones, respuestas y progreso. No tiene acceso directo a soluciones, preguntas futuras ni escrituras de calificación.

La RPC pública `diagnostic_action` es SECURITY INVOKER. Delega a una función SECURITY DEFINER en el esquema no expuesto `studyflow_diagnostic`, con identidad y propiedad verificadas, permisos limitados y search_path vacío. El acceso privilegiado es necesario para corregir con soluciones inaccesibles al cliente. El bloqueo transaccional por usuario serializa pestañas; respuestas y avances son idempotentes frente a reintentos. El plazo se comprueba en el servidor.

Los borradores se guardan solo en sessionStorage, separados por usuario, sesión y pregunta; se eliminan al enviar o cerrar sesión. Las respuestas enviadas viven en Supabase. La salida se escapa antes de mostrarse. No se envía información a un proveedor de IA.

## Verificación

GitHub Actions ejecuta sintaxis, los tests existentes, las 27 derivadas mediante diferencias finitas, los distractores y pruebas de interfaz con jsdom. Un PostgreSQL 17 efímero prueba permisos, propiedad entre dos identidades, pistas, recarga, reintentos, adaptación, límite, historial y vencimiento. Estas identidades solo existen en la base efímera de CI.

Comando: `node --test tests/*.mjs` después de instalar chess.js@1.4.0 y jsdom@26.1.0. Para pruebas SQL, proporcionar `DIAGNOSTIC_TEST_DATABASE_URL` de una base de pruebas vacía; nunca usar producción. La prueba crea roles de prueba y un esquema auth mínimo.

Antes de publicar, comprobar además la instalación real de Supabase y una sesión visual desde la página desplegada. Si Supabase no está disponible, la sección informa del problema y las funciones existentes de StudyFlow permanecen separadas.

## Próxima etapa

Análisis de explicaciones con una API de IA, validación de su salida y conexión del diagnóstico con el plan de estudio.
