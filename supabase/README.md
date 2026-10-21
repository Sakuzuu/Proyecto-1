# Configurar la autenticación de StudyFlow

1. Crea un proyecto en https://supabase.com/dashboard.
2. En **Project Settings → API Keys**, copia la **Project URL** y la **publishable key** (normalmente empieza por `sb_publishable_`). Nunca uses la `secret` ni la `service_role` key en archivos del navegador.
3. Edita `supabase-config.js` y completa `url` y `publishableKey`.
4. En el proyecto, abre **SQL Editor**, pega el contenido de `supabase/schema.sql` y ejecútalo.
5. En **Authentication → URL Configuration**, añade la URL de GitHub Pages de StudyFlow a **Redirect URLs**. Para probarlo en local, añade también la URL local que uses.
6. En **Authentication → Sign In / Providers**, deja habilitado Email. Configura el correo de verificación según tus preferencias.
7. Publica los cambios de GitHub Pages y prueba registro, confirmación de correo, inicio de sesión, restablecimiento y cierre de sesión.

Los datos del perfil solo son visibles para su propio usuario en este primer paso. La búsqueda de perfiles, amistades y notas compartidas se implementará después con políticas de permisos propias.
