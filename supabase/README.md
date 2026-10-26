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
