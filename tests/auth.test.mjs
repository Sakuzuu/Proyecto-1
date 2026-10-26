import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import path from "node:path";
import Auth from "../auth.js";

const repoRoot = path.resolve(new URL("..", import.meta.url).pathname);

function mockClient() {
  const calls = [];
  const profile = { id: "user-1", username: "isaac_123", display_name: "Isaac Paz", created_at: "2026-10-21T00:00:00Z" };
  return {
    calls,
    auth: {
      signUp: async args => { calls.push(["signUp", args]); return { data: { user: { id: "user-1" }, session: null }, error: null }; },
      signInWithPassword: async args => { calls.push(["signIn", args]); return { data: { user: { id: "user-1" }, session: { user: { id: "user-1" } } }, error: null }; },
      resetPasswordForEmail: async (email, options) => { calls.push(["reset", email, options]); return { data: {}, error: null }; },
      updateUser: async args => { calls.push(["updateUser", args]); return { data: { user: { id: "user-1" } }, error: null }; },
      signOut: async () => { calls.push(["signOut"]); return { error: null }; },
      onAuthStateChange: callback => { calls.push(["onAuthStateChange", callback]); return { data: { subscription: { unsubscribe() {} } } }; }
    },
    from: table => ({
      select: columns => ({ eq: (column, id) => ({ maybeSingle: async () => { calls.push(["profile", table, columns, column, id]); return { data: id === profile.id ? profile : null, error: null }; } }) }),
      update: payload => ({ eq: (column, id) => ({ select: columns => ({ single: async () => { calls.push(["updateProfile", table, payload, column, id, columns]); return { data: { id, ...payload }, error: null }; } }) }) })
    })
  };
}
const goodFields = { displayName: "Isaac Paz", username: "Isaac_123", email: "ISAAC@example.com", password: "correct horse battery", confirmPassword: "correct horse battery" };

test("valida los nombres de usuario", () => {
  assert.equal(Auth.validateUsername("Isaac_123"), "");
  assert.match(Auth.validateUsername("ab"), /entre 3 y 24/);
  assert.match(Auth.validateUsername("nombre con espacios"), /solo letras/);
  assert.match(Auth.validateUsername("ñandú"), /solo letras/);
  assert.equal(Auth.normalizeUsername("  Isaac_123 "), "isaac_123");
});
test("valida registro y detecta errores antes de llamar al servidor", () => {
  assert.equal(Auth.validateRegistration(goodFields), "");
  assert.match(Auth.validateRegistration({ ...goodFields, confirmPassword: "otra" }), /no coinciden/);
  assert.match(Auth.validateRegistration({ ...goodFields, password: "123" }), /al menos 8/);
  assert.match(Auth.validateRegistration({ ...goodFields, email: "correo-invalido" }), /correo electrónico válido/);
  assert.match(Auth.validateRegistration({ ...goodFields, displayName: "A" }), /nombre visible/);
});
test("registro normaliza correo y usuario y envía metadatos del perfil", async () => {
  const client = mockClient(), service = Auth.createService(client);
  const result = await service.signUp(goodFields, "https://sakuzuu.github.io/Proyecto-1/");
  assert.equal(result.error, null);
  assert.equal(client.calls[0][0], "signUp");
  assert.equal(client.calls[0][1].email, "isaac@example.com");
  assert.equal(client.calls[0][1].options.data.username, "isaac_123");
  assert.equal(client.calls[0][1].options.data.display_name, "Isaac Paz");
  assert.equal(client.calls[0][1].options.emailRedirectTo, "https://sakuzuu.github.io/Proyecto-1/");
});
test("registro inválido no llama a Supabase", async () => {
  const client = mockClient(), result = await Auth.createService(client).signUp({ ...goodFields, confirmPassword: "wrong" }, "https://example.com");
  assert.match(result.error.message, /no coinciden/);
  assert.equal(client.calls.length, 0);
});
test("inicio de sesión normaliza el correo y valida entradas", async () => {
  const client = mockClient(), service = Auth.createService(client);
  assert.equal((await service.signIn(" ISAAC@EXAMPLE.COM ", "password")).error, null);
  assert.deepEqual(client.calls[0], ["signIn", { email: "isaac@example.com", password: "password" }]);
  assert.match((await service.signIn("bad", "password")).error.message, /correo electrónico válido/);
  assert.equal(client.calls.length, 1);
});
test("recuperación y cambio de contraseña", async () => {
  const client = mockClient(), service = Auth.createService(client);
  assert.equal((await service.requestPasswordReset("ISAAC@example.com", "https://example.com/Proyecto-1/")).error, null);
  assert.deepEqual(client.calls[0], ["reset", "isaac@example.com", { redirectTo: "https://example.com/Proyecto-1/" }]);
  assert.match((await service.updatePassword("short", "short")).error.message, /al menos 8/);
  assert.match((await service.updatePassword("12345678", "87654321")).error.message, /no coinciden/);
  assert.equal((await service.updatePassword("12345678", "12345678")).error, null);
  assert.deepEqual(client.calls.at(-1), ["updateUser", { password: "12345678" }]);
});
test("el perfil se consulta por el ID autenticado", async () => {
  const client = mockClient(), service = Auth.createService(client);
  assert.equal((await service.getProfile("user-1")).data.username, "isaac_123");
  assert.deepEqual(client.calls[0], ["profile", "profiles", "id, username, display_name, share_academic_averages, created_at", "id", "user-1"]);
  assert.match((await service.getProfile("")).error.message, /sesión/);
});
test("valida configuración y rechaza claves privilegiadas", () => {
  const key = "sb_publishable_abcdefghijklmnopqrstuvwxyz123456";
  assert.equal(Auth.isConfigured({ url: "https://abc-123.supabase.co", publishableKey: key }), true);
  assert.equal(Auth.isConfigured({ url: "https://abc.supabase.co", publishableKey: "service_role_secret" }), false);
  assert.equal(Auth.isConfigured({ url: "http://abc.supabase.co", publishableKey: key }), false);
  assert.equal(Auth.isConfigured({ url: "", publishableKey: "" }), false);
  assert.equal(Auth.isConfigured({ url: "http://127.0.0.1:54321", publishableKey: key }), true);
});
test("escapa texto no confiable y traduce errores frecuentes", () => {
  assert.equal(Auth.escapeHtml(`<script x="1">'&</script>`), "&lt;script x=&quot;1&quot;&gt;&#039;&amp;&lt;/script&gt;");
  assert.match(Auth.friendlyError({ message: "Invalid login credentials" }), /incorrectos/);
  assert.match(Auth.friendlyError({ message: "duplicate key value violates unique constraint on username" }), /ocupado/);
  assert.match(Auth.friendlyError({ message: "relation profiles does not exist" }), /schema.sql/);
});
test("el esquema limita los perfiles al propietario y activa RLS", () => {
  const sql = fs.readFileSync(path.join(repoRoot, "supabase", "schema.sql"), "utf8");
  assert.match(sql, /alter table public\.profiles enable row level security/i);
  assert.match(sql, /using \(\(select auth\.uid\(\)\) = id\)/i);
  assert.match(sql, /with check \(\(select auth\.uid\(\)\) = id\)/i);
  assert.match(sql, /after insert on auth\.users/i);
  assert.match(sql, /revoke execute on function public\.handle_new_studyflow_user\(\) from public, anon, authenticated/i);
  assert.match(sql, /references auth\.users \(id\) on delete cascade/i);
});
test("la configuración no contiene credenciales y la guía explica el setup", () => {
  const config = fs.readFileSync(path.join(repoRoot, "supabase-config.js"), "utf8");
  const guide = fs.readFileSync(path.join(repoRoot, "supabase", "README.md"), "utf8");
  assert.match(config, /url: "https:\/\/liuogfkzppxevvaclvpl\.supabase\.co"/);
  assert.match(config, /publishableKey: "sb_publishable_[A-Za-z0-9_-]+"/);
  assert.doesNotMatch(config, /(?:service_role_|sb_secret_)[A-Za-z0-9_-]{8,}/);
  assert.match(guide, /schema\.sql/);
  assert.match(guide, /Redirect URLs/);
});


test("detecta enlaces de recuperación en query y hash", () => {
  assert.equal(Auth.isPasswordRecoveryUrl("https://example.com/Proyecto-1/?type=recovery"), true);
  assert.equal(Auth.isPasswordRecoveryUrl("https://example.com/Proyecto-1/#access_token=abc&type=recovery"), true);
  assert.equal(Auth.isPasswordRecoveryUrl("https://example.com/Proyecto-1/#access_token=abc&type=signup"), false);
  assert.equal(Auth.isPasswordRecoveryUrl("not a url"), false);
});

test("guarda la preferencia de privacidad del promedio en el perfil", async () => {
  const client = mockClient(), service = Auth.createService(client);
  const result = await service.updateSharingPreference("user-1", true);
  assert.equal(result.error, null);
  assert.equal(result.data.share_academic_averages, true);
  assert.deepEqual(client.calls[0], ["updateProfile", "profiles", { share_academic_averages: true }, "id", "user-1", "id, share_academic_averages"]);
});
