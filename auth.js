(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.StudyFlowAuth = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const USERNAME = /^[a-z0-9_]{3,24}$/;
  const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const normalizeEmail = value => String(value || "").trim().toLowerCase();
  const normalizeUsername = value => String(value || "").trim().toLowerCase();

  function validateUsername(value) {
    return USERNAME.test(normalizeUsername(value)) ? "" : "El nombre de usuario debe tener entre 3 y 24 caracteres y usar solo letras, números o guion bajo.";
  }
  function validateEmail(value) {
    return EMAIL.test(normalizeEmail(value)) ? "" : "Escribe un correo electrónico válido.";
  }
  function validateLogin(email, password) {
    return validateEmail(email) || (!String(password || "") ? "Escribe tu contraseña." : "");
  }
  function validateRegistration(fields) {
    const f = fields || {};
    const name = String(f.displayName || "").trim(), password = String(f.password || "");
    if (name.length < 2 || name.length > 60) return "Tu nombre visible debe tener entre 2 y 60 caracteres.";
    const usernameError = validateUsername(f.username);
    if (usernameError) return usernameError;
    const emailError = validateEmail(f.email);
    if (emailError) return emailError;
    if (password.length < 8) return "La contraseña debe tener al menos 8 caracteres.";
    if (password !== String(f.confirmPassword || "")) return "Las contraseñas no coinciden.";
    return "";
  }
  function friendlyError(error) {
    const message = String(error && error.message || "").toLowerCase();
    if (message.includes("invalid login credentials")) return "El correo o la contraseña son incorrectos.";
    if (message.includes("user already registered") || message.includes("already been registered")) return "Ya existe una cuenta con ese correo.";
    if (message.includes("password should be at least") || message.includes("password is too short")) return "La contraseña debe tener al menos 8 caracteres.";
    if (message.includes("email not confirmed")) return "Primero confirma tu correo desde el enlace que te enviamos.";
    if (message.includes("rate limit") || message.includes("too many requests")) return "Has realizado demasiados intentos. Espera un momento y vuelve a intentarlo.";
    if (message.includes("username") && /duplicate|unique|already exists/.test(message)) return "Ese nombre de usuario ya está ocupado. Prueba con otro.";
    if (message.includes("profiles") && /does not exist|schema cache/.test(message)) return "Falta crear la tabla de perfiles. Ejecuta supabase/schema.sql y revisa supabase/README.md.";
    if (/failed to fetch|network/.test(message)) return "No se pudo conectar con Supabase. Revisa tu conexión y la configuración del proyecto.";
    return "No se pudo completar la operación. Revisa los datos e inténtalo de nuevo.";
  }
  function createService(client) {
    if (!client || !client.auth) throw new TypeError("Se necesita un cliente de Supabase válido.");
    return {
      async signUp(fields, redirectTo) {
        const invalid = validateRegistration(fields);
        if (invalid) return { data: null, error: new Error(invalid) };
        return client.auth.signUp({ email: normalizeEmail(fields.email), password: String(fields.password), options: { emailRedirectTo: redirectTo, data: { username: normalizeUsername(fields.username), display_name: String(fields.displayName).trim() } } });
      },
      async signIn(email, password) {
        const invalid = validateLogin(email, password);
        if (invalid) return { data: null, error: new Error(invalid) };
        return client.auth.signInWithPassword({ email: normalizeEmail(email), password: String(password) });
      },
      async requestPasswordReset(email, redirectTo) {
        const invalid = validateEmail(email);
        if (invalid) return { data: null, error: new Error(invalid) };
        return client.auth.resetPasswordForEmail(normalizeEmail(email), { redirectTo });
      },
      async updatePassword(password, confirmation) {
        if (String(password || "").length < 8) return { data: null, error: new Error("La contraseña debe tener al menos 8 caracteres.") };
        if (password !== confirmation) return { data: null, error: new Error("Las contraseñas no coinciden.") };
        return client.auth.updateUser({ password: String(password) });
      },
      signOut: () => client.auth.signOut(),
      getProfile(userId) {
        if (!userId) return Promise.resolve({ data: null, error: new Error("No hay una sesión de usuario activa.") });
        return client.from("profiles").select("id, username, display_name, share_academic_averages, created_at").eq("id", userId).maybeSingle();
      },
      updateSharingPreference(userId, enabled) {
        if (!userId) return Promise.resolve({ data: null, error: new Error("No hay una sesión activa.") });
        return client.from("profiles").update({ share_academic_averages: Boolean(enabled) }).eq("id", userId).select("id, share_academic_averages").single();
      },
      onAuthStateChange: callback => client.auth.onAuthStateChange(callback)
    };
  }
  function isConfigured(config) {
    if (!config || typeof config.url !== "string" || typeof config.publishableKey !== "string") return false;
    let url;
    try { url = new URL(config.url.trim()); } catch (_) { return false; }
    const hosted = url.protocol === "https:" && /^[a-z0-9-]+\.supabase\.co$/i.test(url.hostname);
    const local = url.protocol === "http:" && ["localhost", "127.0.0.1"].includes(url.hostname) && Boolean(url.port);
    return (hosted || local) && /^sb_publishable_[A-Za-z0-9_-]+$/.test(config.publishableKey.trim());
  }
  function isPasswordRecoveryUrl(value) {
    try {
      const url = new URL(value);
      const hash = new URLSearchParams(url.hash.replace(/^#/, ""));
      return url.searchParams.get("type") === "recovery" || hash.get("type") === "recovery";
    } catch (_) { return false; }
  }
  function escapeHtml(value) {
    return String(value == null ? "" : value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  }
  function initBrowser(options) {
    const opts = options || {}, doc = opts.document || (typeof window !== "undefined" ? window.document : null), win = opts.window || (typeof window !== "undefined" ? window : null);
    if (!doc || !win || !doc.body) return { ready: false, reason: "no-dom" };
    const config = opts.config || win.STUDYFLOW_SUPABASE_CONFIG || {}, sdk = opts.sdk || win.supabase;
    const app = doc.querySelector("main.shell");
    if (!app) return { ready: false, reason: "no-app" };
    let view = doc.getElementById("studyflow-auth-root");
    if (!view) { view = doc.createElement("section"); view.id = "studyflow-auth-root"; view.className = "auth-layout"; view.setAttribute("aria-live", "polite"); app.parentNode.insertBefore(view, app); }
    app.hidden = true; app.setAttribute("aria-hidden", "true");
    if (!doc.getElementById("studyflow-auth-css")) { const link = doc.createElement("link"); link.id = "studyflow-auth-css"; link.rel = "stylesheet"; link.href = "auth.css"; doc.head.appendChild(link); }

    if (!isConfigured(config) || !sdk || typeof sdk.createClient !== "function") {
      const hasConfig = Boolean(String(config.url || "").trim() || String(config.publishableKey || "").trim());
      view.innerHTML = `<article class="auth-card"><p class="eyebrow">STUDYFLOW · CUENTAS</p><h1>Conecta tu cuenta</h1><p class="auth-muted">Estamos preparando el acceso seguro para guardar tu perfil. Tus notas siguen disponibles en modo local.</p><div class="auth-notice" role="status">${escapeHtml(hasConfig ? "La configuración de Supabase no es válida o la biblioteca no se pudo cargar." : "Crea un proyecto Supabase, configura supabase-config.js y ejecuta el esquema SQL.")}</div><ol class="auth-steps"><li>Crea un proyecto en <a href="https://supabase.com/dashboard" target="_blank" rel="noopener noreferrer">Supabase</a>.</li><li>Añade la URL y la clave publishable en <code>supabase-config.js</code>.</li><li>Ejecuta <code>supabase/schema.sql</code> desde SQL Editor.</li></ol><button class="button" id="auth-local-mode" type="button">Continuar con la versión local</button><p class="auth-small">El modo local no crea cuentas ni sincroniza datos entre dispositivos.</p></article>`;
      doc.getElementById("auth-local-mode").addEventListener("click", () => { view.hidden = true; app.hidden = false; app.removeAttribute("aria-hidden"); app.dataset.accountMode = "local"; });
      return { ready: true, configured: false, authRoot: view, appShell: app };
    }

    const client = sdk.createClient(config.url.trim(), config.publishableKey.trim(), { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true } });
    const service = createService(client), redirectTo = win.location ? win.location.href.split(/[?#]/)[0] : "";
    let recoveryMode = Boolean(win.location && isPasswordRecoveryUrl(win.location.href)), activeUserId = null, changeToken = 0;
    let currentView = "login";

    function destroyFriendsUI() {
      if (win.StudyFlowFriendsController && typeof win.StudyFlowFriendsController.destroy === "function") {
        win.StudyFlowFriendsController.destroy();
      }
      win.StudyFlowFriendsController = null;
    }

    function renderAuth(message, kind, viewName) {
      if (viewName) currentView = viewName;
      view.hidden = false;
      const alert = message ? `<p class="auth-message ${kind === "error" ? "is-error" : "is-success"}" role="status">${escapeHtml(message)}</p>` : "";
      let forms;
      if (recoveryMode) forms = `<form id="auth-reset-form" class="auth-form"><label for="auth-new-password">Nueva contraseña</label><input id="auth-new-password" type="password" minlength="8" autocomplete="new-password" required><label for="auth-confirm-password">Confirmar contraseña</label><input id="auth-confirm-password" type="password" minlength="8" autocomplete="new-password" required><button class="button" type="submit">Guardar contraseña</button></form>`;
      else if (currentView === "forgot") forms = `<form id="auth-forgot-form" class="auth-form"><label for="auth-reset-email">Correo electrónico</label><input id="auth-reset-email" type="email" autocomplete="email" maxlength="254" required><button class="button" type="submit">Enviar enlace</button><button class="auth-link" type="button" data-action="login">Volver al inicio de sesión</button></form>`;
      else forms = `<div class="auth-tabs" role="tablist" aria-label="Acceso a StudyFlow"><button type="button" class="auth-tab ${currentView === "login" ? "is-active" : ""}" role="tab" aria-selected="${currentView === "login"}" data-action="login">Iniciar sesión</button><button type="button" class="auth-tab ${currentView === "register" ? "is-active" : ""}" role="tab" aria-selected="${currentView === "register"}" data-action="register">Crear cuenta</button></div>
      <form id="auth-login-form" class="auth-form" ${currentView !== "login" ? "hidden" : ""} novalidate><label for="auth-login-email">Correo electrónico</label><input id="auth-login-email" type="email" autocomplete="email" maxlength="254" required><label for="auth-login-password">Contraseña</label><input id="auth-login-password" type="password" autocomplete="current-password" required><button class="button" type="submit">Iniciar sesión</button><button class="auth-link" type="button" data-action="forgot">Olvidé mi contraseña</button></form>
      <form id="auth-register-form" class="auth-form" ${currentView !== "register" ? "hidden" : ""} novalidate><label for="auth-display-name">Nombre visible</label><input id="auth-display-name" type="text" minlength="2" maxlength="60" autocomplete="name" required><label for="auth-username">Nombre de usuario</label><input id="auth-username" type="text" minlength="3" maxlength="24" pattern="[a-zA-Z0-9_]+" autocomplete="username" required><small>3–24 caracteres: letras, números y guion bajo.</small><label for="auth-register-email">Correo electrónico</label><input id="auth-register-email" type="email" maxlength="254" autocomplete="email" required><label for="auth-register-password">Contraseña</label><input id="auth-register-password" type="password" minlength="8" autocomplete="new-password" required><label for="auth-register-confirm">Confirmar contraseña</label><input id="auth-register-confirm" type="password" minlength="8" autocomplete="new-password" required><button class="button" type="submit">Crear cuenta</button><p class="auth-small">Te enviaremos un correo para verificar la dirección si la confirmación está activada.</p></form>`;
      view.innerHTML = `<article class="auth-card"><p class="eyebrow">STUDYFLOW · CUENTAS</p><h1>${recoveryMode ? "Restablecer contraseña" : currentView === "register" ? "Crea tu cuenta" : currentView === "forgot" ? "Recupera tu cuenta" : "Bienvenido a StudyFlow"}</h1><p class="auth-muted">${recoveryMode ? "Elige una nueva contraseña segura." : "Inicia sesión o crea una cuenta para guardar tu perfil."}</p>${alert}${forms}<p class="auth-small">Nunca compartas tu contraseña. Tus materias y notas se sincronizarán al entrar a StudyFlow.</p></article>`;
      view.querySelectorAll("[data-action]").forEach(button => button.addEventListener("click", () => {
        const action = button.dataset.action;
        if (action === "login" || action === "register") renderAuth("", "", action);
        else if (action === "forgot") {
          const email = doc.getElementById("auth-login-email").value;
          renderAuth("", "", "forgot");
          doc.getElementById("auth-reset-email").value = email;
        }
      }));
    }

    async function revealApp(profile) {
      view.hidden = true; app.hidden = false; app.removeAttribute("aria-hidden"); app.dataset.accountMode = "account";
      const clearButton = doc.getElementById("clearSession");
      if (clearButton) clearButton.hidden = true;
      let tools = doc.getElementById("studyflow-account-tools");
      if (!tools) { tools = doc.createElement("div"); tools.id = "studyflow-account-tools"; tools.className = "auth-account-tools"; const actions = app.querySelector(".hero-actions"); if (actions) actions.appendChild(tools); }
      tools.innerHTML = `<span class="auth-user-label">@${escapeHtml(profile.username)}</span><button id="auth-logout-from-app" class="button button-secondary" type="button">Cerrar sesión</button>`;
      doc.getElementById("auth-logout-from-app").addEventListener("click", handleSignOut);
      let notice = doc.getElementById("auth-stage-notice");
      if (!notice) { notice = doc.createElement("p"); notice.id = "auth-stage-notice"; notice.className = "auth-stage-notice"; const hero = app.querySelector(".hero"); if (hero && hero.parentNode) hero.parentNode.insertBefore(notice, hero.nextSibling); }
      notice.textContent = "Conectando tus materias y notas con tu cuenta…";
      if (!win.StudyFlowCloud || !win.StudyFlowApp || typeof win.StudyFlowApp.connectCloud !== "function") {
        notice.textContent = "No se pudo inicializar la sincronización académica. Recarga la página.";
        notice.classList.add("is-error");
        return;
      }
      try {
        const cloudService = win.StudyFlowCloud.createService(client);
        const result = await win.StudyFlowApp.connectCloud(cloudService, activeUserId || profile.id);
        if (result.error) {
          notice.textContent = "Tu cuenta está conectada, pero no se pudieron cargar los datos. Revisa la conexión y vuelve a entrar.";
          notice.classList.add("is-error");
        } else {
          notice.textContent = "Cuenta conectada. Tus materias y notas se guardan en la nube y estarán disponibles desde otros dispositivos.";
          notice.classList.remove("is-error");
        }
      } catch (_) {
        notice.textContent = "No se pudo inicializar la sincronización académica. Recarga la página.";
        notice.classList.add("is-error");
      }
      if (win.StudyFlowFriends) {
        try {
          destroyFriendsUI();
          win.StudyFlowFriendsController = win.StudyFlowFriends.mount({
            document: doc,
            service: win.StudyFlowCloud.createService(client),
            userId: activeUserId || profile.id,
            profile: profile
          });
        } catch (_) {
          const friendsMessage = doc.getElementById("friendsRequestsMessage");
          const friendsSection = doc.getElementById("friendsSection");
          if (friendsSection) friendsSection.hidden = false;
          if (friendsMessage) {
            friendsMessage.hidden = false;
            friendsMessage.className = "friends-message is-error";
            friendsMessage.textContent = "No se pudo inicializar la sección de amigos. Recarga la página.";
          }
        }
      }
    }
    function showProfile(profile, user) {
      view.hidden = false;
      view.innerHTML = `<article class="auth-card auth-profile-card"><p class="eyebrow">STUDYFLOW · PERFIL</p><h1>¡Hola, ${escapeHtml(profile.display_name || "estudiante")}!</h1><p class="auth-muted">Tu cuenta está activa.</p><div class="auth-profile-summary"><span class="auth-avatar" aria-hidden="true">${escapeHtml((profile.display_name || profile.username || "S").slice(0,1).toUpperCase())}</span><div><strong>${escapeHtml(profile.display_name)}</strong><p>@${escapeHtml(profile.username)}</p><small>${escapeHtml(user.email || "")}</small></div></div><label class="auth-share-toggle" for="auth-share-averages"><input id="auth-share-averages" type="checkbox" ${profile.share_academic_averages ? "checked" : ""}><span><strong>Permitir compartir mis promedios</strong><small>Cuando agregues amigos, podrán consultar promedios por materia y año, nunca las notas individuales. Está desactivado por defecto.</small></span></label><p id="auth-profile-message" class="auth-message" hidden role="status"></p><button id="auth-enter-app" class="button" type="button">Entrar a StudyFlow</button><button id="auth-sign-out" class="button button-secondary" type="button">Cerrar sesión</button></article>`;
      doc.getElementById("auth-enter-app").addEventListener("click", () => revealApp(profile));
      doc.getElementById("auth-sign-out").addEventListener("click", handleSignOut);
      doc.getElementById("auth-share-averages").addEventListener("change", async event => {
        const toggle = event.currentTarget;
        const message = doc.getElementById("auth-profile-message");
        toggle.disabled = true;
        const result = await service.updateSharingPreference(user.id, toggle.checked).catch(error => ({ error }));
        toggle.disabled = false;
        if (result.error || !result.data) {
          toggle.checked = !toggle.checked;
          message.hidden = false;
          message.className = "auth-message is-error";
          message.textContent = friendlyError(result.error || new Error("No se guardó la preferencia."));
          return;
        }
        profile.share_academic_averages = Boolean(result.data.share_academic_averages);
        message.hidden = false;
        message.className = "auth-message is-success";
        message.textContent = toggle.checked ? "Preferencia guardada. Solo se compartirán promedios cuando aceptes una amistad." : "Preferencia guardada. Tus promedios no se compartirán.";
      });
    }
    async function handleSession(event, session) {
      const token = ++changeToken, user = session && session.user;
      if (event === "PASSWORD_RECOVERY") { recoveryMode = true; renderAuth("Introduce tu nueva contraseña.", "success"); return; }
      if (recoveryMode && user) { renderAuth("Enlace verificado. Introduce tu nueva contraseña.", "success"); return; }
      if (!user) {
        destroyFriendsUI();
        if (win.StudyFlowApp && typeof win.StudyFlowApp.disconnectCloud === "function") win.StudyFlowApp.disconnectCloud();
        const clear = doc.getElementById("clearSession");
        if (clear) { clear.hidden = false; clear.click(); }
        activeUserId = null; app.hidden = true; app.setAttribute("aria-hidden", "true");
        const tools = doc.getElementById("studyflow-account-tools"); if (tools) tools.remove();
        const notice = doc.getElementById("auth-stage-notice"); if (notice) notice.remove();
        app.dataset.accountMode = "local";
        renderAuth("", "", "login"); return;
      }
      activeUserId = user.id;
      const result = await service.getProfile(user.id);
      if (token !== changeToken) return;
      if (result.error || !result.data) { app.hidden = true; app.setAttribute("aria-hidden", "true"); renderAuth(result.error ? friendlyError(result.error) : "Tu cuenta existe, pero el perfil no aparece. Ejecuta supabase/schema.sql.", "error", "login"); return; }
      recoveryMode = false; showProfile(result.data, user);
    }
    async function handleSignOut() {
      const result = await service.signOut();
      if (result.error) {
        let msg = doc.getElementById("auth-signout-error");
        if (!msg) { msg = doc.createElement("span"); msg.id = "auth-signout-error"; msg.className = "auth-message is-error"; const tools = doc.getElementById("studyflow-account-tools"); if (tools) tools.appendChild(msg); }
        if (msg) msg.textContent = friendlyError(result.error);
        return;
      }
      destroyFriendsUI();
      if (win.StudyFlowApp && typeof win.StudyFlowApp.disconnectCloud === "function") win.StudyFlowApp.disconnectCloud();
      const clear = doc.getElementById("clearSession"); if (clear) { clear.hidden = false; clear.click(); }
      activeUserId = null; app.hidden = true; app.setAttribute("aria-hidden", "true"); renderAuth("Has cerrado sesión.", "success", "login");
    }
    function setBusy(form, busy) {
      const button = form.querySelector('button[type="submit"]'); if (!button) return;
      if (busy) { button.disabled = true; button.dataset.originalLabel = button.textContent; button.textContent = "Procesando…"; }
      else { button.disabled = false; if (button.dataset.originalLabel) button.textContent = button.dataset.originalLabel; delete button.dataset.originalLabel; }
    }
    view.addEventListener("submit", async event => {
      const form = event.target; if (!form || !form.id) return; event.preventDefault(); let result;
      if (form.id === "auth-login-form") {
        const email = doc.getElementById("auth-login-email").value, password = doc.getElementById("auth-login-password").value, invalid = validateLogin(email, password);
        if (invalid) return renderAuth(invalid, "error", "login");
        setBusy(form, true); result = await service.signIn(email, password); setBusy(form, false);
        if (result.error) renderAuth(friendlyError(result.error), "error", "login");
        else if (result.data && result.data.session) await handleSession("SIGNED_IN", result.data.session);
        else renderAuth("Revisa tu correo si necesitas confirmar tu cuenta y luego inicia sesión.", "success", "login");
      } else if (form.id === "auth-register-form") {
        const fields = { displayName: doc.getElementById("auth-display-name").value, username: doc.getElementById("auth-username").value, email: doc.getElementById("auth-register-email").value, password: doc.getElementById("auth-register-password").value, confirmPassword: doc.getElementById("auth-register-confirm").value };
        const invalid = validateRegistration(fields); if (invalid) return renderAuth(invalid, "error", "register");
        setBusy(form, true); result = await service.signUp(fields, redirectTo); setBusy(form, false);
        if (result.error) renderAuth(friendlyError(result.error), "error", "register");
        else if (result.data && result.data.session) await handleSession("SIGNED_IN", result.data.session);
        else renderAuth("Cuenta creada. Revisa tu correo para confirmar la dirección y luego inicia sesión.", "success", "login");
      } else if (form.id === "auth-forgot-form") {
        const email = doc.getElementById("auth-reset-email").value, invalid = validateEmail(email); if (invalid) return renderAuth(invalid, "error", "forgot");
        setBusy(form, true); result = await service.requestPasswordReset(email, redirectTo); setBusy(form, false);
        renderAuth(result.error ? friendlyError(result.error) : "Si el correo existe, recibirás un enlace para restablecer la contraseña.", result.error ? "error" : "success", "forgot");
      } else if (form.id === "auth-reset-form") {
        const password = doc.getElementById("auth-new-password").value, confirmation = doc.getElementById("auth-confirm-password").value;
        setBusy(form, true); result = await service.updatePassword(password, confirmation); setBusy(form, false);
        if (result.error) renderAuth(friendlyError(result.error), "error");
        else {
          recoveryMode = false;
          const sessionResult = await client.auth.getSession().catch(() => null);
          const session = sessionResult && sessionResult.data && sessionResult.data.session;
          if (session) await handleSession("SIGNED_IN", session);
          else renderAuth("Contraseña actualizada. Ya puedes iniciar sesión.", "success", "login");
        }
      }
    });
    renderAuth("", "", "login");
    service.onAuthStateChange((event, session) => { Promise.resolve().then(() => handleSession(event, session)); });
    client.auth.getSession().then(result => {
      if (result.error) renderAuth(friendlyError(result.error), "error");
      else if (result.data && result.data.session) return handleSession("INITIAL_SESSION", result.data.session);
    }).catch(() => renderAuth("No se pudo comprobar la sesión. Recarga la página e inténtalo de nuevo.", "error"));
    return { ready: true, configured: true, client, service, authRoot: view, appShell: app };
  }
  return { normalizeEmail, normalizeUsername, validateUsername, validateRegistration, validateLogin, validateEmail, friendlyError, createService, isConfigured, isPasswordRecoveryUrl, escapeHtml, initBrowser };
});
if (typeof window !== "undefined" && window.document) window.addEventListener("DOMContentLoaded", () => { window.StudyFlowAuthInstance = window.StudyFlowAuth.initBrowser(); }, { once: true });
