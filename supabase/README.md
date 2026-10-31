# StudyFlow: datos académicos y bases para amistades

El proyecto Supabase conectado está en:
https://supabase.com/dashboard/project/liuogfkzppxevvaclvpl

## Configuración de producción

- Proyecto Supabase: `liuogfkzppxevvaclvpl`.
- `supabase-config.js` contiene la URL y la clave pública `sb_publishable_` para el navegador. No reemplazarla por una clave secret/service_role.
- GitHub Pages: `https://sakuzuu.github.io/Proyecto-1/`.
- Las migraciones de perfiles, materias, notas, amistades y consultas agregadas ya están aplicadas en la base de datos.

## Datos y privacidad

- `subjects`: materias con usuario propietario y nombre único por cuenta (ignorando mayúsculas).
- `grades`: notas con fecha, descripción, valor y período académico `AAAA-AAAA`. Una clave foránea compuesta impide asociar una nota a la materia de otra cuenta.
- `friend_requests`: solicitudes pendientes, aceptadas o rechazadas. Solo el destinatario puede responder.
- `friendships`: una relación única por pareja; al aceptar una solicitud, un trigger crea la amistad.
- `profiles.share_academic_averages`: consentimiento desactivado por defecto.

RLS protege todas las tablas. Materias y notas solo pueden leerse o modificarse por su propietario. El acceso de amigos a notas individuales está denegado; `get_shared_academic_averages` devuelve solamente promedios agregados por materia y período si la amistad está aceptada y el propietario permite compartir. Los RPCs de búsqueda/listado devuelven datos básicos, nunca correos. Las funciones SECURITY DEFINER tienen `search_path` vacío, comprueban `auth.uid()` y revocan EXECUTE a `public`/ `anon`; el rol `authenticated` solo puede ejecutar las que necesita.

## Reproducir la configuración

En una base vacía, aplica `supabase/migrations/` por orden de versión o utiliza `supabase/schema.sql`. No ejecutes el esquema consolidado sobre una base que contenga datos no respaldados.

En Supabase → Authentication → URL Configuration, configura la Site URL y añade `https://sakuzuu.github.io/Proyecto-1/` en **Redirect URLs** (lista de redirecciones permitidas). Deja Email habilitado.

## Pruebas

GitHub Actions ejecuta la comprobación de sintaxis JavaScript y `node --test tests/*.mjs`. El registro real y la confirmación de correo requieren una prueba manual con una dirección que controles.


## Amigos e intercambio de promedios

La sección Amigos e intercambio de promedios está disponible después de iniciar sesión y entrar a StudyFlow. Permite buscar un nombre de usuario exacto, enviar solicitudes, aceptar/rechazar solicitudes recibidas, ver amistades y eliminar una amistad. La lista se vuelve a cargar tras cada operación para reflejar el estado almacenado en Supabase.

El consentimiento "Permitir compartir mis promedios" se puede modificar desde el perfil o desde la sección de amigos. Empieza desactivado. Solo una amistad aceptada puede consultar datos y solo mientras el propietario tenga activada la preferencia. El resultado contiene promedios agrupados por materia y período académico y un promedio general por período; no permite consultar calificaciones individuales ni correos electrónicos. El permiso se aplica en la base de datos mediante las funciones RPC, no solo en la interfaz.

Las pruebas automatizadas verifican el escape de contenido, validación de usuario, representación de solicitudes, flujo de aceptar/rechazar, privacidad, consulta de promedios y eliminación de amistades. Una validación completa entre dos cuentas reales aún requiere iniciar sesión con dos usuarios de prueba y comprobar la confirmación por correo en el entorno desplegado.


## Ajedrez y tienda de fondos

La sección Ajedrez permite invitar a amigos aceptados, aceptar/rechazar desafíos, jugar con el tablero legal, sincronizar movimientos entre sesiones y rendirse. Las jugadas se revalidan en la Edge Function privada usando el historial UCI y el motor chess.js; los cambios de estado usan una revisión incremental para evitar que dos movimientos simultáneos sobrescriban el resultado. La app escucha cambios de partidas en Supabase Realtime y también ofrece un botón para actualizar.

Cada victoria por jaque mate o rendición concede 10 Papucoins. Los empates no conceden Papucoins. La recompensa y la compra de fondos se aplican mediante funciones SQL transaccionales que solo puede ejecutar el rol de servidor; el navegador no tiene permisos de escritura sobre saldo, compras o partidas. El historial tiene una restricción única por partida para impedir cobrar dos veces la misma victoria.

Fondos disponibles: Clásico (gratis), Océano (20 Papucoins), Bosque (20), Atardecer (20), Lavanda (20), Rosa (20) y Medianoche (30). Los fondos comprados quedan asociados a la cuenta y se pueden volver a activar sin coste. El saldo se guarda en Supabase, no en el almacenamiento local del navegador.

El esquema y las migraciones studyflow_chess_points_and_background_shop y studyflow_chess_invite_lifecycle contienen RLS, restricciones y los flujos de invitación; una invitación pendiente se cierra al cancelar o eliminar la amistad, y solo el destinatario puede aceptarla. El backend está en supabase/functions/chess-api/. La función se despliega con autenticación JWT activa; nunca expongas la clave secreta/service-role en archivos del navegador. La validación automatizada usa chess.js para probar reglas de movimiento y flujos de invitación/recompensa. La prueba final en producción debe completarse con dos cuentas distintas en GitHub Pages.

