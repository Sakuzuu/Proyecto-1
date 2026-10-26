(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.StudyFlowFriends = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  }

  function normalizeUsername(value) { return String(value || "").trim().toLowerCase(); }
  function isValidUsername(value) { return /^[a-z0-9_]{3,24}$/.test(normalizeUsername(value)); }

  function friendlyError(error) {
    const message = String(error && error.message || "").toLowerCase();
    const code = String(error && error.code || "");
    if (code === "23505" || message.includes("friend_requests_pending_pair_unique")) {
      return "Ya existe una solicitud pendiente entre estas cuentas. Revisa tus solicitudes o espera la respuesta.";
    }
    if (message.includes("friendships") && (code === "23505" || message.includes("duplicate"))) {
      return "Ya existe una amistad con esta cuenta. Actualiza la lista de amigos.";
    }
    if (/failed to fetch|network|timeout/.test(message)) return "No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.";
    if (message.includes("permission denied") || message.includes("not authorized")) return "La operación no está permitida para esta cuenta.";
    return "No se pudo completar la operación. Inténtalo de nuevo y, si persiste, revisa tu conexión.";
  }

  function renderEmpty(message) {
    return '<p class="empty">' + escapeHtml(message) + "</p>";
  }

  function renderSearchResults(results, context) {
    const users = Array.isArray(results) ? results : [];
    const ctx = context || {};
    if (!users.length) return renderEmpty(ctx.searched ? "No encontramos ese nombre de usuario. Comprueba cómo está escrito." : "Busca un nombre de usuario para enviar una solicitud.");
    return users.map(function (user) {
      const existingFriend = (ctx.friends || []).some(function (friend) { return friend.id === user.id; });
      const request = (ctx.requests || []).find(function (item) {
        return item.status === "pending" &&
          ((item.sender_id === ctx.userId && item.recipient_id === user.id) ||
           (item.sender_id === user.id && item.recipient_id === ctx.userId));
      });
      let action = "";
      if (existingFriend) action = '<span class="friend-state">Ya son amigos</span>';
      else if (request && request.sender_id === ctx.userId) action = '<button class="button button-secondary" type="button" disabled>Solicitud enviada</button>';
      else if (request) action = '<span class="friend-state">Tienes una solicitud pendiente de esta persona</span>';
      else action = '<button class="button friend-action-button" type="button" data-send-request="' + escapeHtml(user.id) + '">Enviar solicitud</button>';
      return '<article class="friend-item"><div class="friend-identity"><strong>' + escapeHtml(user.display_name || user.username || "Estudiante") +
        '</strong><small>@' + escapeHtml(user.username || "") + '</small></div><div class="friend-item-action">' + action + "</div></article>";
    }).join("");
  }

  function renderRequests(requests) {
    const all = Array.isArray(requests) ? requests : [];
    const received = all.filter(function (request) { return request.status === "pending" && request.direction === "received"; });
    const sent = all.filter(function (request) { return request.status === "pending" && request.direction === "sent"; });
    const receivedHtml = received.length ? received.map(function (request) {
      return '<article class="friend-item"><div class="friend-identity"><strong>' + escapeHtml(request.other_display_name || request.other_username || "Estudiante") +
        '</strong><small>@' + escapeHtml(request.other_username || "") + '</small></div><div class="friend-item-action friend-actions"><button class="button" type="button" data-request-action="accepted" data-request-id="' + escapeHtml(request.id) + '">Aceptar</button><button class="button button-secondary" type="button" data-request-action="rejected" data-request-id="' + escapeHtml(request.id) + '">Rechazar</button></div></article>';
    }).join("") : renderEmpty("No tienes solicitudes recibidas pendientes.");
    const sentHtml = sent.length ? sent.map(function (request) {
      return '<article class="friend-item"><div class="friend-identity"><strong>' + escapeHtml(request.other_display_name || request.other_username || "Estudiante") +
        '</strong><small>@' + escapeHtml(request.other_username || "") + '</small></div><span class="friend-state">Esperando respuesta</span></article>';
    }).join("") : renderEmpty("No tienes solicitudes enviadas pendientes.");
    return '<div class="friend-subsection"><h4>Recibidas</h4>' + receivedHtml + '</div><div class="friend-subsection"><h4>Enviadas</h4>' + sentHtml + "</div>";
  }

  function renderFriends(friends) {
    const all = Array.isArray(friends) ? friends : [];
    if (!all.length) return renderEmpty("Todavía no tienes amigos agregados.");
    return all.map(function (friend) {
      const name = friend.display_name || friend.username || "Estudiante";
      const sharing = friend.share_academic_averages
        ? '<span class="friend-state friend-state-shared">Promedios habilitados</span>'
        : '<span class="friend-state">Promedios privados</span>';
      return '<article class="friend-item friend-list-item"><div class="friend-identity"><strong>' + escapeHtml(name) +
        '</strong><small>@' + escapeHtml(friend.username || "") + '</small>' + sharing + '</div><div class="friend-item-action friend-actions"><button class="button button-secondary" type="button" data-friend-action="averages" data-friend-id="' +
        escapeHtml(friend.id) + '">Ver promedios</button><button class="text-button danger-text" type="button" data-friend-action="remove" data-friend-id="' +
        escapeHtml(friend.id) + '">Eliminar</button></div></article>';
    }).join("");
  }

  function renderAverages(rows) {
    const values = Array.isArray(rows) ? rows : [];
    if (!values.length) return renderEmpty("No hay promedios disponibles para mostrar en este momento.");
    const ordered = values.slice().sort(function (a, b) {
      const year = String(b.academic_year || "").localeCompare(String(a.academic_year || ""));
      if (year) return year;
      return String(a.metric_type || "").localeCompare(String(b.metric_type || ""));
    });
    const body = ordered.map(function (row) {
      const title = row.metric_type === "year" ? "Promedio general" : (row.subject_name || "Materia");
      const average = Number(row.average);
      const value = Number.isFinite(average) ? average.toLocaleString("es-EC", { maximumFractionDigits: 2 }) + "/100" : "—";
      return "<tr><td>" + escapeHtml(title) + "</td><td>" + escapeHtml(row.academic_year || "—") +
        "</td><td><strong>" + escapeHtml(value) + "</strong></td></tr>";
    }).join("");
    return '<table class="friends-average-table"><thead><tr><th>Indicador</th><th>Año académico</th><th>Promedio</th></tr></thead><tbody>' + body + "</tbody></table>";
  }

  function createController(options) {
    const opts = options || {};
    const doc = opts.document;
    const service = opts.service;
    const userId = String(opts.userId || "");
    const profile = opts.profile || {};
    const confirmAction = typeof opts.confirm === "function" ? opts.confirm : function () { return true; };
    if (!doc || !service || !userId) throw new TypeError("Se requiere documento, servicio de datos y usuario autenticado.");

    const ids = [
      "friendsSection", "friendsPrivacyToggle", "friendsPrivacyMessage", "friendsSearchForm", "friendsSearchUsername",
      "friendsSearchMessage", "friendsSearchResults", "friendsRequestsMessage", "friendsRequestsList",
      "friendsListMessage", "friendsList", "sharedAveragesHeading", "sharedAveragesMessage", "sharedAveragesTable"
    ];
    const els = {};
    ids.forEach(function (id) { els[id] = doc.getElementById(id); });
    if (ids.some(function (id) { return !els[id]; })) throw new Error("Faltan elementos de la interfaz de amigos en index.html.");

    const state = {
      friends: [], requests: [], searchMatches: [], searched: false,
      sharePreference: Boolean(profile.share_academic_averages), selectedFriend: null, destroyed: false
    };
    const listeners = [];

    function bind(element, type, callback) {
      element.addEventListener(type, callback);
      listeners.push(function () { element.removeEventListener(type, callback); });
    }

    function message(element, text, kind) {
      element.textContent = text || "";
      element.hidden = !text;
      element.className = "friends-message" + (kind ? " is-" + kind : "");
    }

    function renderSearch() {
      els.friendsSearchResults.innerHTML = renderSearchResults(state.searchMatches, {
        friends: state.friends, requests: state.requests, userId: userId, searched: state.searched
      });
    }
    function renderLists() {
      els.friendsRequestsList.innerHTML = renderRequests(state.requests);
      els.friendsList.innerHTML = renderFriends(state.friends);
      renderSearch();
    }
    async function refreshLists() {
      const results = await Promise.all([
        service.listFriends(userId),
        service.listFriendRequests(userId)
      ]);
      const failed = results.find(function (result) { return result && result.error; });
      if (failed) {
        message(els.friendsRequestsMessage, friendlyError(failed.error), "error");
        message(els.friendsListMessage, "No se pudieron actualizar las listas. Comprueba la conexión.", "error");
        return { error: failed.error };
      }
      state.friends = Array.isArray(results[0] && results[0].data) ? results[0].data : [];
      state.requests = Array.isArray(results[1] && results[1].data) ? results[1].data : [];
      renderLists();
      message(els.friendsRequestsMessage, "", "");
      message(els.friendsListMessage, state.friends.length ? "" : "Cuando aceptes una solicitud, tus amigos aparecerán aquí.", state.friends.length ? "" : "info");
      if (state.selectedFriend) {
        const current = state.friends.find(function (friend) { return friend.id === state.selectedFriend.id; });
        if (!current) {
          state.selectedFriend = null;
          els.sharedAveragesHeading.textContent = "Promedios compartidos";
          els.sharedAveragesTable.innerHTML = renderEmpty("Selecciona un amigo para consultar sus promedios.");
          message(els.sharedAveragesMessage, "", "");
        } else {
          state.selectedFriend = current;
        }
      }
      return { data: { friends: state.friends.length, requests: state.requests.length }, error: null };
    }

    async function search() {
      const username = normalizeUsername(els.friendsSearchUsername.value);
      if (!isValidUsername(username)) {
        state.searched = false;
        state.searchMatches = [];
        renderSearch();
        message(els.friendsSearchMessage, "Escribe un usuario de 3 a 24 caracteres, usando letras, números o guion bajo.", "error");
        return { error: new Error("Nombre de usuario no válido.") };
      }
      message(els.friendsSearchMessage, "Buscando usuario…", "loading");
      let result;
      try { result = await service.searchProfilesByUsername(username); }
      catch (error) { result = { data: null, error: error }; }
      if (result.error) {
        state.searched = false;
        state.searchMatches = [];
        renderSearch();
        message(els.friendsSearchMessage, friendlyError(result.error), "error");
        return result;
      }
      state.searchMatches = (Array.isArray(result.data) ? result.data : []).filter(function (user) { return user && user.id !== userId; });
      state.searched = true;
      renderSearch();
      message(els.friendsSearchMessage, state.searchMatches.length ? "Revisa que el nombre de usuario sea correcto antes de enviar la solicitud." : "No encontramos ese nombre de usuario.", state.searchMatches.length ? "info" : "info");
      return { data: state.searchMatches, error: null };
    }

    async function handleSearchSubmit(event) {
      event.preventDefault();
      const button = els.friendsSearchForm.querySelector('button[type="submit"]');
      if (button) button.disabled = true;
      try { await search(); }
      finally { if (button) button.disabled = false; }
    }

    async function handleSendRequest(event) {
      const button = event.target && event.target.closest ? event.target.closest("[data-send-request]") : event.target;
      if (!button || !button.dataset || !button.dataset.sendRequest) return;
      const friendId = button.dataset.sendRequest;
      if (button.disabled) return;
      button.disabled = true;
      let result;
      try { result = await service.sendFriendRequest(userId, friendId); }
      catch (error) { result = { data: null, error: error }; }
      if (result.error || !result.data) {
        message(els.friendsSearchMessage, friendlyError(result.error || new Error("La solicitud no se pudo enviar.")), "error");
        button.disabled = false;
        return;
      }
      message(els.friendsSearchMessage, "Solicitud enviada. Aparecerá como pendiente hasta que la otra persona responda.", "success");
      await refreshLists();
    }

    async function handleRequestResponse(event) {
      const button = event.target && event.target.closest ? event.target.closest("[data-request-action]") : event.target;
      if (!button || !button.dataset || !button.dataset.requestAction || !button.dataset.requestId) return;
      if (button.disabled) return;
      const status = button.dataset.requestAction;
      const requestId = button.dataset.requestId;
      button.disabled = true;
      let result;
      try { result = await service.respondToFriendRequest(userId, requestId, status); }
      catch (error) { result = { data: null, error: error }; }
      if (result.error || !result.data) {
        message(els.friendsRequestsMessage, friendlyError(result.error || new Error("La solicitud ya no está pendiente.")), "error");
        button.disabled = false;
        return;
      }
      message(els.friendsRequestsMessage, status === "accepted" ? "Solicitud aceptada. Ya son amigos." : "Solicitud rechazada.", "success");
      await refreshLists();
    }

    async function loadAverages(friend) {
      state.selectedFriend = friend;
      els.sharedAveragesHeading.textContent = "Promedios de " + (friend.display_name || friend.username || "tu amigo");
      els.sharedAveragesTable.innerHTML = renderEmpty("Cargando promedios…");
      if (!friend.share_academic_averages) {
        message(els.sharedAveragesMessage, "Esta persona no ha activado el intercambio de promedios. Sus notas individuales nunca se comparten.", "info");
        els.sharedAveragesTable.innerHTML = renderEmpty("Promedios privados.");
        return { data: [], error: null };
      }
      message(els.sharedAveragesMessage, "Solo se muestran promedios agrupados por materia y año; no se muestran notas individuales.", "info");
      let result;
      try { result = await service.getSharedAcademicAverages(friend.id); }
      catch (error) { result = { data: null, error: error }; }
      if (result.error) {
        els.sharedAveragesTable.innerHTML = renderEmpty("No se pudieron cargar los promedios.");
        message(els.sharedAveragesMessage, friendlyError(result.error), "error");
        return result;
      }
      const rows = Array.isArray(result.data) ? result.data : [];
      els.sharedAveragesTable.innerHTML = renderAverages(rows);
      if (!rows.length) message(els.sharedAveragesMessage, "El intercambio está activado, pero todavía no hay promedios registrados para mostrar.", "info");
      return result;
    }

    async function handleFriendAction(event) {
      const button = event.target && event.target.closest ? event.target.closest("[data-friend-action]") : event.target;
      if (!button || !button.dataset || !button.dataset.friendAction || !button.dataset.friendId) return;
      const friend = state.friends.find(function (item) { return item.id === button.dataset.friendId; });
      if (!friend || button.disabled) return;
      if (button.dataset.friendAction === "averages") {
        button.disabled = true;
        try { await loadAverages(friend); }
        finally { button.disabled = false; }
      } else if (button.dataset.friendAction === "remove") {
        const name = friend.display_name || friend.username || "este amigo";
        if (!confirmAction("¿Eliminar a " + name + " de tus amigos? Tendrán que enviarse una nueva solicitud para volver a conectar.")) return;
        button.disabled = true;
        let result;
        try { result = await service.removeFriend(friend.id); }
        catch (error) { result = { data: null, error: error }; }
        if (result.error || result.data === false || result.data == null) {
          message(els.friendsListMessage, friendlyError(result.error || new Error("No se pudo eliminar la amistad.")), "error");
          button.disabled = false;
          return;
        }
        message(els.friendsListMessage, "Amistad eliminada.", "success");
        await refreshLists();
      }
    }

    async function handlePrivacyChange() {
      const toggle = els.friendsPrivacyToggle;
      const desired = Boolean(toggle.checked);
      toggle.disabled = true;
      let result;
      try { result = await service.updateSharingPreference(userId, desired); }
      catch (error) { result = { data: null, error: error }; }
      toggle.disabled = false;
      if (result.error || !result.data) {
        toggle.checked = state.sharePreference;
        message(els.friendsPrivacyMessage, friendlyError(result.error || new Error("No se guardó la preferencia.")), "error");
        return result;
      }
      state.sharePreference = Boolean(result.data.share_academic_averages);
      profile.share_academic_averages = state.sharePreference;
      toggle.checked = state.sharePreference;
      message(els.friendsPrivacyMessage, state.sharePreference
        ? "Preferencia guardada. Tus amigos aceptados podrán consultar solo tus promedios agregados."
        : "Preferencia guardada. Tus promedios ya no se compartirán.", "success");
      return result;
    }

    bind(els.friendsSearchForm, "submit", handleSearchSubmit);
    bind(els.friendsSearchResults, "click", handleSendRequest);
    bind(els.friendsRequestsList, "click", handleRequestResponse);
    bind(els.friendsList, "click", handleFriendAction);
    bind(els.friendsPrivacyToggle, "change", handlePrivacyChange);

    els.friendsPrivacyToggle.checked = state.sharePreference;
    els.friendsSection.hidden = false;
    els.sharedAveragesTable.innerHTML = renderEmpty("Selecciona un amigo para consultar sus promedios.");
    const ready = refreshLists().catch(function (error) {
      message(els.friendsRequestsMessage, friendlyError(error), "error");
      message(els.friendsListMessage, friendlyError(error), "error");
      return { error: error };
    });

    return {
      state: state,
      ready: ready,
      search: search,
      refreshLists: refreshLists,
      loadAverages: loadAverages,
      destroy: function () {
        if (state.destroyed) return;
        state.destroyed = true;
        listeners.forEach(function (remove) { remove(); });
        els.friendsSection.hidden = true;
      }
    };
  }

  function mount(options) { return createController(options); }

  return {
    escapeHtml: escapeHtml,
    normalizeUsername: normalizeUsername,
    isValidUsername: isValidUsername,
    friendlyError: friendlyError,
    renderSearchResults: renderSearchResults,
    renderRequests: renderRequests,
    renderFriends: renderFriends,
    renderAverages: renderAverages,
    createController: createController,
    mount: mount
  };
});
