(function (root, factory) {
  const api = factory(root);
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.StudyFlowChess = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function (root) {
  "use strict";

  const PIECES = { k: "♚", q: "♛", r: "♜", b: "♝", n: "♞", p: "♟︎", K: "♔", Q: "♕", R: "♖", B: "♗", N: "♘", P: "♙" };
  const PROMOTIONS = [{ id: "q", label: "Dama", glyph: "♕" }, { id: "r", label: "Torre", glyph: "♖" }, { id: "b", label: "Alfil", glyph: "♗" }, { id: "n", label: "Caballo", glyph: "♘" }];
  const BACKGROUND_PATTERN = /^[a-z][a-z0-9_]{1,30}$/;

  function escapeHtml(value) {
    return String(value == null ? "" : value).replaceAll("&", "&amp;").replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  }
  function errorMessage(error) {
    const message = String(error && error.message || "").toLowerCase();
    if (/session|auth|jwt|401/.test(message)) return "Tu sesión puede haber expirado. Cierra sesión y vuelve a entrar.";
    if (/not your turn|todavía no es tu turno/.test(message)) return "Todavía no es tu turno.";
    if (/stale|changed|cambió|409/.test(message)) return "La partida se actualizó en el otro dispositivo; el tablero se ha sincronizado.";
    if (/insufficient_points|puntos|papucoins?/i.test(message)) return error.message;
    if (/no eres amigo|amigos/.test(message)) return error.message;
    if (/failed to fetch|network|conexión/.test(message)) return "No se pudo conectar con el servidor. Comprueba tu internet.";
    return error && error.message ? error.message : "No se pudo completar la operación.";
  }
  function uciToSan(ChessCtor, moves) {
    const chess = new ChessCtor();
    const san = [];
    for (const uci of Array.isArray(moves) ? moves : []) {
      const from = String(uci).slice(0, 2), to = String(uci).slice(2, 4), promotion = String(uci).slice(4, 5);
      const move = chess.move({ from, to, ...(promotion ? { promotion } : {}) });
      if (!move) return [];
      san.push({ san: move.san, color: move.color });
    }
    return san;
  }
  function renderBoard(chess, options = {}) {
    const board = chess.board();
    const selected = options.selected || "";
    const targets = new Set(options.targets || []);
    const interactive = Boolean(options.interactive);
    return '<div class="chess-board" role="group" aria-label="Tablero de ajedrez">' + board.map((row, rankIndex) =>
      row.map((piece, fileIndex) => {
        const square = piece && piece.square ? piece.square : "abcdefgh"[fileIndex] + (8 - rankIndex);
        const pieceChar = piece ? PIECES[piece.color === "w" ? piece.type.toUpperCase() : piece.type] || "" : "";
        const tone = ((rankIndex + fileIndex) % 2 === 0) ? "light" : "dark";
        const classes = ["chess-square", "chess-square-" + tone, selected === square ? "is-selected" : "", targets.has(square) ? "is-target" : ""].filter(Boolean).join(" ");
        const fileLabel = rankIndex === 7 ? '<span class="chess-file-label" aria-hidden="true">' + square[0] + "</span>" : "";
        const rankLabel = fileIndex === 0 ? '<span class="chess-rank-label" aria-hidden="true">' + square[1] + "</span>" : "";
        const aria = piece ? (piece.color === "w" ? "Blancas " : "Negras ") + ({ p: "peón", n: "caballo", b: "alfil", r: "torre", q: "dama", k: "rey" }[piece.type]) + ", " + square : "Casilla vacía " + square;
        return '<button class="' + classes + '" type="button" data-chess-square="' + square + '" aria-label="' + escapeHtml(aria) + '"' + (interactive ? "" : " disabled") + ">" +
          rankLabel + '<span class="chess-piece chess-piece-' + (piece ? piece.color === "w" ? "white" : "black" : "empty") + '">' + pieceChar + "</span>" + fileLabel + "</button>";
      }).join("")
    ).join("") + "</div>";
  }
  function renderGames(games, userId, selectedId) {
    if (!Array.isArray(games) || !games.length) return '<p class="empty">Todavía no tienes partidas. Invita a uno de tus amigos para empezar.</p>';
    return games.map(function (game) {
      const opponent = game.opponent && (game.opponent.display_name || game.opponent.username) || "Amigo";
      const incoming = game.status === "pending" && game.opponent_id === userId;
      const outgoing = game.status === "pending" && game.challenger_id === userId;
      const isActive = game.status === "active";
      const statusLabel = incoming ? "Invitación recibida" : outgoing ? "Esperando respuesta" :
        isActive ? (game.current_turn === userId ? "Tu turno" : "Turno del rival") :
        game.status === "declined" ? "Invitación cerrada" :
        game.winner_id ? (game.winner_id === userId ? "¡Ganaste! +10 Papucoins" : "Partida finalizada") : "Empate";
      let action = "";
      if (incoming) action = '<button class="button" type="button" data-chess-action="accept" data-game-id="' + escapeHtml(game.id) + '">Aceptar</button><button class="button button-secondary" type="button" data-chess-action="decline" data-game-id="' + escapeHtml(game.id) + '">Rechazar</button>';
      else if (outgoing) action = '<button class="button button-secondary" type="button" data-chess-action="cancel" data-game-id="' + escapeHtml(game.id) + '">Cancelar invitación</button>';
      else if (isActive) action = '<button class="button' + (selectedId === game.id ? " button-selected" : "") + '" type="button" data-chess-action="open" data-game-id="' + escapeHtml(game.id) + '">' + (selectedId === game.id ? "Partida abierta" : "Jugar") + "</button>";
      return '<article class="chess-game-item' + (selectedId === game.id ? " is-active" : "") + '"><div class="chess-game-info"><strong>' + escapeHtml(opponent) + "</strong><span>" +
        escapeHtml(statusLabel) + '</span><small>' + escapeHtml(game.player_color === "w" ? "Juegas con blancas" : "Juegas con negras") + "</small></div><div class=\"chess-game-actions\">" + action + "</div></article>";
    }).join("");
  }
  function renderShop(backgrounds, purchases, wallet) {
    const owned = new Set(purchases || []);
    const points = Number(wallet && wallet.points || 0);
    const active = wallet && wallet.active_background || "classic";
    return (backgrounds || []).map(function (background) {
      const has = owned.has(background.id);
      const current = active === background.id;
      const disabled = !has && points < background.cost;
      const action = current ? '<span class="chess-owned-label">En uso</span>' :
        has ? '<button class="button button-secondary" type="button" data-background-action="activate" data-background-id="' + escapeHtml(background.id) + '">Usar</button>' :
        '<button class="button" type="button" data-background-action="buy" data-background-id="' + escapeHtml(background.id) + '"' + (disabled ? " disabled" : "") + ">Comprar · " + escapeHtml(background.cost) + " Papucoins</button>";
      return '<article class="chess-shop-item' + (current ? " is-current" : "") + '"><div class="chess-swatch-pair" aria-hidden="true"><span style="background:' + escapeHtml(background.light_color) + '"></span><span style="background:' + escapeHtml(background.dark_color) + '"></span></div><div class="chess-shop-copy"><strong>' +
        escapeHtml(background.name) + '</strong><small>' + (has ? "Desbloqueado" : Number(background.cost) === 0 ? "Gratis" : "Cuesta " + escapeHtml(background.cost) + " Papucoins") + "</small></div><div class=\"chess-shop-action\">" + action + "</div></article>";
    }).join("");
  }

  function mount(options) {
    const opts = options || {};
    const doc = opts.document || (typeof document !== "undefined" ? document : null);
    const client = opts.client;
    const userId = String(opts.userId || "");
    const ChessCtor = opts.Chess || root.Chess;
    if (!doc || !client || !userId || typeof ChessCtor !== "function") throw new TypeError("Se necesita una sesión, Supabase y el motor de ajedrez para iniciar esta sección.");
    const ids = ["chessSection", "chessPoints", "chessMessage", "chessInviteForm", "chessInviteFriend", "chessGames", "chessRefresh", "chessBoardTitle", "chessBoardStatus", "chessBoard", "chessPromotion", "chessMoveHistory", "chessResign", "chessShop"];
    const el = {};
    ids.forEach(id => { el[id] = doc.getElementById(id); });
    if (ids.some(id => !el[id])) throw new Error("Faltan elementos de la interfaz de ajedrez.");
    const state = { wallet: { points: 0, active_background: "classic" }, backgrounds: [], purchases: [], games: [], friends: [],
      selectedGameId: null, selectedSquare: "", pendingPromotion: null, busy: false, destroyed: false };
    const listeners = [];
    let channel = null;
    let themeObserver = null;

    function bind(target, type, fn) {
      target.addEventListener(type, fn);
      listeners.push(() => target.removeEventListener(type, fn));
    }
    function message(text, kind = "") {
      el.chessMessage.textContent = text || "";
      el.chessMessage.hidden = !text;
      el.chessMessage.className = "chess-message" + (kind ? " is-" + kind : "");
    }
    async function invoke(body) {
      const response = await client.functions.invoke("chess-api", { body });
      if (response.error) {
        let details = response.error.message || "No se pudo conectar con el servicio de ajedrez.";
        const context = response.error.context;
        if (context && typeof context.json === "function") {
          try { const json = await context.json(); details = json.error || details; } catch (_) {}
        }
        throw new Error(details);
      }
      if (response.data && response.data.error) throw new Error(response.data.error);
      return response.data && response.data.data;
    }
    function getSelectedGame() {
      return state.games.find(game => game.id === state.selectedGameId) || null;
    }
    function syncBackground() {
      const selected = state.backgrounds.find(background => background.id === (state.wallet.active_background || "classic"));
      if (!selected) return;
      const theme = doc.documentElement.dataset.theme || "light";
      doc.documentElement.style.setProperty("--chess-page-bg", theme === "dark" ? selected.dark_color : selected.light_color);
    }
    function renderInviteFriends() {
      const selected = el.chessInviteFriend.value;
      el.chessInviteFriend.innerHTML = '<option value="">Elige un amigo…</option>' + state.friends.map(friend =>
        '<option value="' + escapeHtml(friend.id) + '">' + escapeHtml(friend.display_name || friend.username || "Estudiante") + " (@" + escapeHtml(friend.username || "") + ")</option>"
      ).join("");
      if (state.friends.some(friend => friend.id === selected)) el.chessInviteFriend.value = selected;
      const button = el.chessInviteForm.querySelector('button[type="submit"]');
      if (button) button.disabled = !state.friends.length || state.busy;
    }
    function renderGamesList() {
      el.chessGames.innerHTML = renderGames(state.games, userId, state.selectedGameId);
    }
    function renderSelectedGame() {
      const game = getSelectedGame();
      if (!game) {
        el.chessBoardTitle.textContent = "Selecciona una partida";
        el.chessBoardStatus.textContent = "Acepta una invitación o abre una partida activa.";
        el.chessBoard.innerHTML = '<p class="empty">Tu tablero aparecerá aquí cuando abras una partida.</p>';
        el.chessPromotion.hidden = true;
        el.chessResign.disabled = true;
        el.chessMoveHistory.innerHTML = "";
        return;
      }
      el.chessBoardTitle.textContent = "Contra " + (game.opponent && (game.opponent.display_name || game.opponent.username) || "tu amigo");
      const active = game.status === "active";
      const yourTurn = active && game.current_turn === userId;
      const winnerName = game.winner && (game.winner.display_name || game.winner.username);
      let status = active ? (yourTurn ? "Tu turno" : "Turno del rival") : game.status === "pending" ? "Esperando respuesta a la invitación" :
        game.status === "declined" ? "Invitación cerrada" : winnerName ? (game.winner_id === userId ? "¡Ganaste! Recibiste 10 Papucoins." : "Ganó " + winnerName + ".") : "Empate. Esta partida no entrega Papucoins.";
      if (active && game.fen) {
        try {
          const chess = new ChessCtor(game.fen);
          const inCheck = typeof chess.isCheck === "function" ? chess.isCheck() : chess.in_check();
          if (inCheck) status += " · Jaque";
        } catch (_) {}
      }
      el.chessBoardStatus.textContent = status;
      const chess = new ChessCtor(game.fen);
      const canPlay = yourTurn && !state.busy;
      const legal = state.selectedSquare ? chess.moves({ square: state.selectedSquare, verbose: true }) : [];
      const targets = legal.map(move => move.to);
      el.chessBoard.innerHTML = renderBoard(chess, { selected: state.selectedSquare, targets, interactive: canPlay });
      el.chessResign.disabled = !active || !canPlay || state.busy;
      el.chessPromotion.hidden = !state.pendingPromotion;
      if (state.pendingPromotion) {
        el.chessPromotion.innerHTML = '<span>Elige qué pieza quieres para la promoción:</span>' + PROMOTIONS.map(item =>
          '<button class="button button-secondary chess-promotion-choice" type="button" data-promotion="' + item.id + '"><span aria-hidden="true">' + item.glyph + '</span> ' + item.label + "</button>"
        ).join("") + '<button class="text-button" type="button" data-promotion="cancel">Cancelar</button>';
      } else el.chessPromotion.innerHTML = "";
      const history = uciToSan(ChessCtor, game.moves || []);
      const pairs = [];
      for (let i = 0; i < history.length; i += 2) pairs.push({ no: i / 2 + 1, white: history[i] && history[i].san, black: history[i + 1] && history[i + 1].san });
      el.chessMoveHistory.innerHTML = pairs.length
        ? '<ol class="chess-move-list">' + pairs.map(move => "<li><span>" + move.no + ".</span><strong>" + escapeHtml(move.white || "…") + "</strong><strong>" + escapeHtml(move.black || "…") + "</strong></li>").join("") + "</ol>"
        : '<p class="muted">La partida todavía no tiene jugadas.</p>';
    }
    function renderShopUI() {
      el.chessPoints.textContent = String(Number(state.wallet.points || 0));
      el.chessShop.innerHTML = renderShop(state.backgrounds, state.purchases, state.wallet);
      syncBackground();
    }
    function renderAll() {
      renderInviteFriends();
      renderGamesList();
      renderSelectedGame();
      renderShopUI();
    }
    async function refresh(quiet = false) {
      if (state.destroyed) return;
      try {
        const data = await invoke({ action: "load" });
        if (!data || !data.wallet) throw new Error("No se recibió el estado de tu cuenta.");
        state.wallet = data.wallet;
        state.backgrounds = data.backgrounds || [];
        state.purchases = data.purchases || [];
        state.games = data.games || [];
        state.friends = data.friends || [];
        if (state.selectedGameId && !state.games.some(game => game.id === state.selectedGameId && game.status === "active")) {
          const prior = state.games.find(game => game.id === state.selectedGameId);
          if (!prior || prior.status === "pending" || prior.status === "declined") state.selectedGameId = null;
        }
        if (state.selectedGameId && !state.games.some(game => game.id === state.selectedGameId)) state.selectedGameId = null;
        renderAll();
        if (!quiet) message("Partidas, Papucoins y fondos sincronizados.", "success");
      } catch (error) {
        message(errorMessage(error), "error");
      }
    }
    async function runAction(fn, successText) {
      if (state.busy) return;
      state.busy = true;
      renderAll();
      try {
        const result = await fn();
        await refresh(true);
        message(successText || (result && result.message) || "Cambios guardados.", "success");
        return result;
      } catch (error) {
        await refresh(true);
        message(errorMessage(error), "error");
      } finally {
        state.busy = false;
        renderAll();
      }
    }
    async function submitInvite(event) {
      event.preventDefault();
      const friendId = el.chessInviteFriend.value;
      if (!friendId) { message("Primero selecciona un amigo.", "error"); return; }
      await runAction(() => invoke({ action: "invite", friend_id: friendId }), "Invitación de ajedrez enviada.");
    }
    async function handleGameAction(event) {
      const button = event.target && event.target.closest ? event.target.closest("[data-chess-action]") : event.target;
      if (!button || !button.dataset || !button.dataset.chessAction || !button.dataset.gameId) return;
      const action = button.dataset.chessAction, gameId = button.dataset.gameId;
      const game = state.games.find(item => item.id === gameId);
      if (!game) return;
      if (action === "open") {
        state.selectedGameId = gameId; state.selectedSquare = ""; state.pendingPromotion = null; renderAll(); message("", "");
      } else if (action === "accept" || action === "decline") {
        await runAction(async () => {
          const result = await invoke({ action: "respond_invite", game_id: gameId, accept: action === "accept" });
          if (action === "accept") state.selectedGameId = gameId;
          return result;
        }, action === "accept" ? "Invitación aceptada. ¡Que empiece la partida!" : "Invitación rechazada.");
      } else if (action === "cancel") {
        await runAction(() => invoke({ action: "cancel_invite", game_id: gameId }), "Invitación cancelada.");
      }
    }
    async function squareClick(event) {
      const button = event.target && event.target.closest ? event.target.closest("[data-chess-square]") : event.target;
      if (!button || !button.dataset || !button.dataset.chessSquare || state.busy || state.pendingPromotion) return;
      const game = getSelectedGame();
      if (!game || game.status !== "active" || game.current_turn !== userId) return;
      const square = button.dataset.chessSquare;
      const chess = new ChessCtor(game.fen);
      if (state.selectedSquare) {
        const legal = chess.moves({ square: state.selectedSquare, verbose: true }).filter(move => move.to === square);
        if (legal.length) {
          const promotion = legal.filter(move => move.promotion);
          if (promotion.length) {
            state.pendingPromotion = { from: state.selectedSquare, to: square };
            renderSelectedGame();
            return;
          }
          await sendMove(state.selectedSquare, square, null);
          return;
        }
      }
      const piece = chess.get(square);
      if (piece && piece.color === chess.turn()) state.selectedSquare = square;
      else state.selectedSquare = "";
      renderSelectedGame();
    }
    async function choosePromotion(event) {
      const button = event.target && event.target.closest ? event.target.closest("[data-promotion]") : event.target;
      if (!button || !button.dataset || !button.dataset.promotion || !state.pendingPromotion) return;
      if (button.dataset.promotion === "cancel") { state.pendingPromotion = null; renderSelectedGame(); return; }
      const choice = button.dataset.promotion;
      const move = state.pendingPromotion;
      if (!["q", "r", "b", "n"].includes(choice)) return;
      state.pendingPromotion = null;
      await sendMove(move.from, move.to, choice);
    }
    async function sendMove(from, to, promotion) {
      const game = getSelectedGame();
      if (!game) return;
      state.selectedSquare = "";
      await runAction(() => invoke({
        action: "move", game_id: game.id, from, to, promotion: promotion || undefined,
        expected_revision: game.revision
      }), "Jugada registrada.");
    }
    async function resign() {
      const game = getSelectedGame();
      if (!game || game.status !== "active") return;
      const confirmAction = typeof opts.confirm === "function" ? opts.confirm : (root.confirm || (() => true));
      if (!confirmAction("¿Seguro que quieres rendirte? Tu amigo ganará y recibirá 10 Papucoins.")) return;
      await runAction(() => invoke({ action: "resign", game_id: game.id, expected_revision: game.revision }), "Partida finalizada.");
    }
    async function shopAction(event) {
      const button = event.target && event.target.closest ? event.target.closest("[data-background-action]") : event.target;
      if (!button || !button.dataset || !button.dataset.backgroundAction || !button.dataset.backgroundId) return;
      const action = button.dataset.backgroundAction, id = button.dataset.backgroundId;
      if (!BACKGROUND_PATTERN.test(id)) return;
      await runAction(() => invoke({ action: action === "buy" ? "purchase_background" : "activate_background", background_id: id }),
        action === "buy" ? "Fondo comprado y activado." : "Fondo activado.");
    }

    bind(el.chessInviteForm, "submit", submitInvite);
    bind(el.chessGames, "click", handleGameAction);
    bind(el.chessBoard, "click", squareClick);
    bind(el.chessPromotion, "click", choosePromotion);
    bind(el.chessResign, "click", resign);
    bind(el.chessShop, "click", shopAction);
    bind(el.chessRefresh, "click", () => refresh(false));
    el.chessSection.hidden = false;
    if (typeof root.MutationObserver === "function") {
      themeObserver = new root.MutationObserver(syncBackground);
      themeObserver.observe(doc.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    }
    if (client.channel) {
      channel = client.channel("studyflow-chess-" + userId)
        .on("postgres_changes", { event: "*", schema: "public", table: "chess_games" }, () => refresh(true))
        .subscribe();
    }
    const ready = refresh(true);
    return {
      state, ready, refresh, invoke,
      destroy: function () {
        if (state.destroyed) return;
        state.destroyed = true;
        listeners.forEach(remove => remove());
        if (themeObserver) themeObserver.disconnect();
        if (channel && client.removeChannel) client.removeChannel(channel);
        doc.documentElement.style.removeProperty("--chess-page-bg");
        el.chessSection.hidden = true;
      }
    };
  }

  return { escapeHtml, uciToSan, renderBoard, renderGames, renderShop, mount, errorMessage };
});

