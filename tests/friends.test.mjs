import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import Friends from "../friends.js";

const user = { id: "me", username: "student_me", display_name: "Yo" };
const friend = { id: "friend-1", username: "friend_one", display_name: "Amiga Uno", share_academic_averages: true };
const averageRows = [
  { metric_type: "subject", subject_name: "Cálculo", academic_year: "2026-2027", average: 85.25 },
  { metric_type: "year", subject_name: null, academic_year: "2026-2027", average: 88.5 }
];

test("valida y normaliza nombres de usuario sin alterar la forma permitida", () => {
  assert.equal(Friends.normalizeUsername("  ANA_2026 "), "ana_2026");
  assert.equal(Friends.isValidUsername("ana_2026"), true);
  assert.equal(Friends.isValidUsername("ab"), false);
  assert.equal(Friends.isValidUsername("user.name"), false);
  assert.equal(Friends.isValidUsername("usuario con espacios"), false);
  assert.equal(Friends.isValidUsername("A".repeat(25)), false);
});

test("escapa todo el contenido dinámico al construir resultados de búsqueda", () => {
  const markup = Friends.renderSearchResults([
    { id: "x", username: "<script>alert(1)</script>", display_name: "<img src=x onerror=alert(1)>" }
  ], { userId: "me", friends: [], requests: [] });
  assert.doesNotMatch(markup, /<script>|<img/);
  assert.match(markup, /&lt;script&gt;/);
  assert.match(markup, /&lt;img/);
});

test("la búsqueda distingue amigos, solicitudes pendientes y nuevos usuarios", () => {
  const results = [
    { id: "friend-1", username: "friend_one", display_name: "Amiga Uno" },
    { id: "out-1", username: "sent_user", display_name: "Solicitud ya enviada" },
    { id: "in-1", username: "incoming", display_name: "Te escribió" },
    { id: "new-1", username: "new_user", display_name: "Nueva persona" }
  ];
  const markup = Friends.renderSearchResults(results, {
    userId: "me",
    friends: [{ id: "friend-1" }],
    requests: [
      { id: "r1", sender_id: "me", recipient_id: "out-1", status: "pending", direction: "sent" },
      { id: "r2", sender_id: "in-1", recipient_id: "me", status: "pending", direction: "received" }
    ]
  });
  assert.match(markup, /Ya son amigos/);
  assert.match(markup, /Solicitud enviada/);
  assert.match(markup, /Tienes una solicitud pendiente/);
  assert.match(markup, /data-send-request="new-1"/);
});

test("las solicitudes renderizan acciones solo para las recibidas que sigan pendientes", () => {
  const markup = Friends.renderRequests([
    { id: "incoming-1", direction: "received", status: "pending", other_username: "a_user" },
    { id: "sent-1", direction: "sent", status: "pending", other_username: "b_user" },
    { id: "old-1", direction: "received", status: "accepted", other_username: "old_user" }
  ]);
  assert.match(markup, /data-request-action="accepted" data-request-id="incoming-1"/);
  assert.match(markup, /data-request-action="rejected" data-request-id="incoming-1"/);
  assert.match(markup, /Esperando respuesta/);
  assert.doesNotMatch(markup, /data-request-id="old-1"/);
});

test("promedios compartidos solo se representan como agregados y escapan nombres", () => {
  const markup = Friends.renderAverages(averageRows.concat([
    { metric_type: "subject", subject_name: "<script>", academic_year: "2025-2026", average: 50 }
  ]));
  assert.match(markup, /Promedio general/);
  assert.match(markup, /Cálculo/);
  assert.match(markup, /88,5\/100/);
  assert.doesNotMatch(markup, /<script>/);
  assert.match(markup, /&lt;script&gt;/);
  assert.match(Friends.renderFriends([friend]), /Promedios habilitados/);
  assert.match(Friends.renderFriends([{ ...friend, share_academic_averages: false }]), /Promedios privados/);
});

test("traduce duplicados y errores de red a mensajes útiles", () => {
  assert.match(Friends.friendlyError({ code: "23505", message: "duplicate friend_requests_pending_pair_unique" }), /solicitud pendiente/);
  assert.match(Friends.friendlyError({ message: "Failed to fetch" }), /conectar con el servidor/);
});

class FakeElement {
  constructor(id) {
    this.id = id;
    this.listeners = {};
    this.hidden = false;
    this.disabled = false;
    this.checked = false;
    this.value = "";
    this.textContent = "";
    this.innerHTML = "";
    this.className = "";
    this.dataset = {};
    this.submitButton = new FakeElementButton();
  }
  addEventListener(type, callback) { (this.listeners[type] ||= []).push(callback); }
  removeEventListener(type, callback) {
    this.listeners[type] = (this.listeners[type] || []).filter(item => item !== callback);
  }
  querySelector(selector) { return selector === 'button[type="submit"]' ? this.submitButton : null; }
  closest(selector) {
    if (selector === "[data-send-request]" && this.dataset.sendRequest) return this;
    if (selector === "[data-request-action]" && this.dataset.requestAction) return this;
    if (selector === "[data-friend-action]" && this.dataset.friendAction) return this;
    return null;
  }
  async dispatch(type, extras = {}) {
    const event = { type, target: extras.target || this, currentTarget: this, preventDefault() {} };
    return Promise.all((this.listeners[type] || []).map(callback => callback(event)));
  }
}
class FakeElementButton { constructor() { this.disabled = false; } }
class FakeDocument {
  constructor() {
    const ids = [
      "friendsSection", "friendsPrivacyToggle", "friendsPrivacyMessage", "friendsSearchForm",
      "friendsSearchUsername", "friendsSearchMessage", "friendsSearchResults", "friendsRequestsMessage",
      "friendsRequestsList", "friendsListMessage", "friendsList", "sharedAveragesHeading",
      "sharedAveragesMessage", "sharedAveragesTable"
    ];
    this.elements = new Map(ids.map(id => [id, new FakeElement(id)]));
  }
  getElementById(id) { return this.elements.get(id) || null; }
}

function makeService() {
  let friends = [{ ...friend }];
  let requests = [{
    id: "request-in", sender_id: "student-2", recipient_id: "me", status: "pending", direction: "received",
    other_username: "student_two", other_display_name: "Estudiante Dos"
  }];
  let sharePreference = true;
  const calls = [];
  const service = {
    async listFriends(id) { calls.push(["listFriends", id]); return { data: friends.map(item => ({ ...item })), error: null }; },
    async listFriendRequests(id) { calls.push(["listFriendRequests", id]); return { data: requests.map(item => ({ ...item })), error: null }; },
    async searchProfilesByUsername(username) {
      calls.push(["searchProfilesByUsername", username]);
      return { data: [{ id: "new-1", username: "new_user", display_name: "Nueva persona" }], error: null };
    },
    async sendFriendRequest(senderId, recipientId) {
      calls.push(["sendFriendRequest", senderId, recipientId]);
      const row = { id: "request-out", sender_id: senderId, recipient_id: recipientId, status: "pending", direction: "sent", other_username: "new_user", other_display_name: "Nueva persona" };
      requests.push(row);
      return { data: row, error: null };
    },
    async respondToFriendRequest(userId, requestId, status) {
      calls.push(["respondToFriendRequest", userId, requestId, status]);
      const row = requests.find(item => item.id === requestId);
      if (!row || row.status !== "pending" || row.recipient_id !== userId) return { data: null, error: new Error("not pending") };
      row.status = status;
      if (status === "accepted") friends.push({ id: row.sender_id, username: row.other_username, display_name: row.other_display_name, share_academic_averages: true });
      return { data: { ...row }, error: null };
    },
    async getSharedAcademicAverages(friendId) {
      calls.push(["getSharedAcademicAverages", friendId]);
      return { data: averageRows, error: null };
    },
    async removeFriend(friendId) {
      calls.push(["removeFriend", friendId]);
      friends = friends.filter(item => item.id !== friendId);
      return { data: true, error: null };
    },
    async updateSharingPreference(userId, enabled) {
      calls.push(["updateSharingPreference", userId, enabled]);
      sharePreference = Boolean(enabled);
      return { data: { id: userId, share_academic_averages: sharePreference }, error: null };
    }
  };
  return { service, calls, snapshot: () => ({ friends, requests, sharePreference }) };
}
function clickTarget(dataset) {
  const target = new FakeElement("dynamic-button");
  target.dataset = dataset;
  return target;
}
function createUI(options = {}) {
  const doc = new FakeDocument();
  const mock = makeService();
  const profile = { share_academic_averages: true };
  const controller = Friends.createController({
    document: doc,
    service: mock.service,
    userId: "me",
    profile,
    confirm: options.confirm || (() => true)
  });
  return { doc, mock, profile, controller };
}

test("la interfaz carga listas, busca usuarios y envía solicitudes", async () => {
  const { doc, mock, controller } = createUI();
  await controller.ready;
  assert.equal(doc.getElementById("friendsSection").hidden, false);
  assert.match(doc.getElementById("friendsList").innerHTML, /friend_one/);
  assert.match(doc.getElementById("friendsRequestsList").innerHTML, /request-action="accepted"/);

  doc.getElementById("friendsSearchUsername").value = " new_user ";
  await doc.getElementById("friendsSearchForm").dispatch("submit");
  assert.ok(mock.calls.some(call => call[0] === "searchProfilesByUsername" && call[1] === "new_user"));
  assert.match(doc.getElementById("friendsSearchResults").innerHTML, /data-send-request="new-1"/);

  await doc.getElementById("friendsSearchResults").dispatch("click", {
    target: clickTarget({ sendRequest: "new-1" })
  });
  assert.ok(mock.calls.some(call => call[0] === "sendFriendRequest" && call[1] === "me" && call[2] === "new-1"));
  assert.match(doc.getElementById("friendsSearchMessage").textContent, /Solicitud enviada/);
  assert.match(doc.getElementById("friendsSearchResults").innerHTML, /Solicitud enviada/);
  controller.destroy();
  assert.equal(doc.getElementById("friendsSection").hidden, true);
});

test("la interfaz acepta solicitudes, muestra promedios y elimina amistades", async () => {
  const { doc, mock, controller } = createUI();
  await controller.ready;
  await doc.getElementById("friendsRequestsList").dispatch("click", {
    target: clickTarget({ requestAction: "accepted", requestId: "request-in" })
  });
  assert.ok(mock.calls.some(call => call[0] === "respondToFriendRequest" && call[3] === "accepted"));
  assert.ok(controller.state.friends.some(item => item.id === "student-2"));

  await doc.getElementById("friendsList").dispatch("click", {
    target: clickTarget({ friendAction: "averages", friendId: "friend-1" })
  });
  assert.ok(mock.calls.some(call => call[0] === "getSharedAcademicAverages" && call[1] === "friend-1"));
  assert.match(doc.getElementById("sharedAveragesTable").innerHTML, /Promedio general/);

  await doc.getElementById("friendsList").dispatch("click", {
    target: clickTarget({ friendAction: "remove", friendId: "friend-1" })
  });
  assert.ok(mock.calls.some(call => call[0] === "removeFriend" && call[1] === "friend-1"));
  assert.ok(!controller.state.friends.some(item => item.id === "friend-1"));
  controller.destroy();
});

test("la preferencia de privacidad se guarda y un usuario sin consentimiento no expone promedios", async () => {
  const { doc, mock, profile, controller } = createUI();
  await controller.ready;
  const toggle = doc.getElementById("friendsPrivacyToggle");
  assert.equal(toggle.checked, true);
  toggle.checked = false;
  await toggle.dispatch("change");
  assert.equal(mock.snapshot().sharePreference, false);
  assert.equal(profile.share_academic_averages, false);
  assert.match(doc.getElementById("friendsPrivacyMessage").textContent, /ya no se compartirán/);

  await controller.loadAverages({ ...friend, share_academic_averages: false });
  assert.doesNotMatch(JSON.stringify(mock.calls), /getSharedAcademicAverages/);
  assert.match(doc.getElementById("sharedAveragesMessage").textContent, /no ha activado/);
  controller.destroy();
});

test("la búsqueda rechaza nombres de usuario inválidos sin consultar Supabase", async () => {
  const { doc, mock, controller } = createUI();
  await controller.ready;
  doc.getElementById("friendsSearchUsername").value = "xx";
  const result = await controller.search();
  assert.ok(result.error);
  assert.equal(mock.calls.some(call => call[0] === "searchProfilesByUsername"), false);
  assert.match(doc.getElementById("friendsSearchMessage").textContent, /3 a 24 caracteres/);
  controller.destroy();
});


test("la página registra la sección de amigos y carga el módulo antes de auth", () => {
  const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");
  const auth = fs.readFileSync(new URL("../auth.js", import.meta.url), "utf8");
  const css = fs.readFileSync(new URL("../styles.css", import.meta.url), "utf8");
  for (const id of [
    "friendsSection", "friendsPrivacyToggle", "friendsPrivacyMessage", "friendsSearchForm",
    "friendsSearchUsername", "friendsSearchMessage", "friendsSearchResults", "friendsRequestsMessage",
    "friendsRequestsList", "friendsListMessage", "friendsList", "sharedAveragesHeading",
    "sharedAveragesMessage", "sharedAveragesTable"
  ]) assert.ok(html.includes('id="' + id + '"'), "Falta el elemento #" + id);
  assert.match(html, /src="friends\.js" defer><\/script>\s*<script src="auth\.js" defer>/);
  assert.match(auth, /StudyFlowFriends\.mount/);
  assert.match(auth, /destroyFriendsUI\(\)/);
  assert.match(css, /\.friends-grid/);
  assert.match(css, /@media \(max-width: 820px\)[\s\S]*?\.friends-grid/);
});
