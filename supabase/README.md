# Configuración de autenticación de StudyFlow

El proyecto Supabase ya está creado y se aplicó el esquema de `supabase/schema.sql`. Su panel:
https://supabase.com/dashboard/project/liuogfkzppxevvaclvpl

## Configuración necesaria de URL para correo

En **Authentication → URL Configuration** configura:

- **Site URL:** `https://sakuzuu.github.io/Proyecto-1/`
- **Redirect URLs:** añade `https://sakuzuu.github.io/Proyecto-1/**`
- Para pruebas locales, añade solo el origen local que vayas a utilizar, por ejemplo `http://localhost:8000/**`.

Supabase exige que la URL enviada en `emailRedirectTo` esté en la lista permitida. La aplicación envía la URL de StudyFlow al solicitar confirmación o restablecimiento de contraseña. La documentación oficial: https://supabase.com/docs/guides/auth/redirect-urls

## Lo que ya está configurado

- Proyecto Supabase existente: `liuogfkzppxevvaclvpl`.
- Tabla `public.profiles` enlazada con `auth.users`.
- RLS activado; cada persona solo puede leer y actualizar su propio perfil.
- Trigger para crear el perfil tras registrar una cuenta.
- Frontend conectado mediante la URL del proyecto y la clave pública `publishable`.
- Cliente JavaScript cargado desde jsDelivr con versión fija `2.118.0`.

## Comprobar autenticación

1. En **Authentication → Sign In / Providers**, confirma que Email está activado.
2. Revisa los ajustes de confirmación por correo y los límites de envío.
3. Abre https://sakuzuu.github.io/Proyecto-1/ después de que GitHub Pages publique el commit.
4. Registra una cuenta de prueba con una dirección de correo a la que tengas acceso.
5. Abre el enlace de confirmación que llega a ese correo; debe regresar a StudyFlow.
6. Inicia sesión y verifica que aparezca el perfil creado.
7. Prueba cierre de sesión y recuperación de contraseña.

La clave `sb_publishable_` está diseñada para clientes web. No publiques nunca una clave `secret` o `service_role`.

## Límite de esta etapa

Esta fase habilita identidad y perfiles. Todavía no guarda materias ni notas en la nube: en esta etapa siguen estando en la sesión del navegador. La sincronización académica y las amistades se desarrollarán después con políticas RLS independientes.
