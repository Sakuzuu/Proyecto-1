import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { createRequire } from "node:module";
import { Chess } from "chess.js";
import { START_FEN, parseUci, replayMoves, inspectPosition, applyLegalMove } from "../supabase/functions/chess-api/chess-rules.mjs";

const require = createRequire(import.meta.url);
const ChessUI = require("../chess-ui.js");
const root = path.resolve(new URL("..", import.meta.url).pathname);
const read = file => fs.readFileSync(path.join(root, file), "utf8");

function playLine(moves) {
  let position = [];
  let result;
  for (const uci of moves) {
    result = applyLegalMove(Chess, position, { from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci.slice(4) || undefined });
    position = result.moves;
  }
  return result;
}

test("el motor parte de la posición estándar y acepta una jugada legal", () => {
  const game = replayMoves(Chess, []);
  assert.equal(game.fen(), START_FEN);
  const result = applyLegalMove(Chess, [], { from: "e2", to: "e4" });
  assert.deepEqual(result.moves, ["e2e4"]);
  assert.equal(result.uci, "e2e4");
  assert.equal(result.status, "active");
  assert.equal(result.nextColor, "b");
  assert.equal(result.winnerColor, null);
  const expected = new Chess();
  expected.move("e4");
  assert.equal(result.fen, expected.fen());
});

test("rechaza movimientos ilegales, coordenadas inválidas e historiales manipulados", () => {
  assert.deepEqual(parseUci("e2e5"), { from: "e2", to: "e5" });
  assert.throws(() => parseUci("e2e2"), /UCI inválido/);
  assert.throws(() => applyLegalMove(Chess, [], { from: "e2", to: "e5" }), /no es legal/);
  assert.throws(() => replayMoves(Chess, ["e2e5"]), /ilegal/);
  assert.throws(() => replayMoves(Chess, ["e2e4", "e7e5", "e1e4"]), /ilegal/);
});

test("reconstruye el historial y encuentra jaque mate con ganador y motivo correctos", () => {
  const result = playLine(["f2f3", "e7e5", "g2g4", "d8h4"]);
  assert.equal(result.status, "finished");
  assert.equal(result.finishReason, "checkmate");
  assert.equal(result.winnerColor, "b");
  assert.equal(result.nextColor, null);
  assert.equal(new Chess(result.fen).isCheckmate(), true);
});

test("el enroque legal mantiene derechos y casillas correctos", () => {
  const result = playLine(["e2e4", "e7e5", "g1f3", "b8c6", "f1e2", "g8f6", "e1g1"]);
  const game = replayMoves(Chess, result.moves);
  assert.equal(result.moves.at(-1), "e1g1");
  assert.equal(game.get("g1").type, "k");
  assert.equal(game.get("f1").type, "r");
  assert.equal(game.get("e1") || null, null);
  assert.equal(game.fen().split(" ")[2].includes("K"), false);
});

test("captura al paso se aplica legalmente", () => {
  const result = playLine(["e2e4", "a7a6", "e4e5", "d7d5", "e5d6"]);
  const game = replayMoves(Chess, result.moves);
  assert.equal(game.get("d6").type, "p");
  assert.equal(game.get("d5") || null, null);
  assert.equal(result.moves.at(-1), "e5d6");
});

test("promoción exige elegir pieza y permite dama, torre, alfil o caballo", () => {
  const fen = "4k3/P7/8/8/8/8/8/4K3 w - - 0 1";
  assert.throws(() => applyLegalMove(Chess, [], { from: "a7", to: "a8" }, fen), /promoción/);
  for (const promotion of ["q", "r", "b", "n"]) {
    const result = applyLegalMove(Chess, [], { from: "a7", to: "a8", promotion }, fen);
    assert.equal(result.moves[0], "a7a8" + promotion);
    assert.equal(new Chess(result.fen).get("a8").type, promotion);
  }
});

test("reconoce un empate por ahogado sin conceder ganador", () => {
  const position = new Chess("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1");
  const result = inspectPosition(position);
  assert.equal(result.status, "finished");
  assert.equal(result.winnerColor, null);
  assert.equal(result.finishReason, "stalemate");
  assert.equal(position.isCheck(), false);
});

test("la UI representa las 64 casillas, la orientación y el historial SAN", () => {
  const chess = new Chess();
  const board = ChessUI.renderBoard(chess, { interactive: true });
  assert.equal((board.match(/data-chess-square=/g) || []).length, 64);
  assert.match(board, /data-chess-square="a1"/);
  assert.match(board, /data-chess-square="h1"/);
  assert.match(board, /♙/);
  assert.match(board, /♟︎/);
  assert.match(ChessUI.uciToSan(Chess, ["e2e4", "e7e5", "g1f3"]).map(m => m.san).join(" "), /e4 e5 Nf3/);
});

test("renderiza invitaciones, desafíos y nombres no confiables de forma segura", () => {
  const markup = ChessUI.renderGames([
    { id: "g1", status: "pending", challenger_id: "other", opponent_id: "me", player_color: "b", opponent: { username: "rival", display_name: "<script>" } },
    { id: "g2", status: "active", challenger_id: "me", opponent_id: "other", current_turn: "me", player_color: "w", opponent: { username: "rival", display_name: "Rival" } },
    { id: "g3", status: "pending", challenger_id: "me", opponent_id: "other", player_color: "w", opponent: { username: "rival", display_name: "Rival" } },
    { id: "g4", status: "finished", challenger_id: "me", opponent_id: "other", winner_id: "me", player_color: "w", opponent: { username: "rival", display_name: "Rival" } }
  ], "me", "g2");
  assert.match(markup, /data-chess-action="accept" data-game-id="g1"/);
  assert.match(markup, /data-chess-action="decline" data-game-id="g1"/);
  assert.match(markup, /data-chess-action="open" data-game-id="g2"/);
  assert.match(markup, /data-chess-action="cancel" data-game-id="g3"/);
  assert.match(markup, /¡Ganaste! \+10 Papucoins/);
  assert.doesNotMatch(markup, /<script>/);
  assert.match(markup, /&lt;script&gt;/);
});

test("la tienda no deja comprar fondos sin puntos, y activa fondos ya comprados", () => {
  const backgrounds = [
    { id: "classic", name: "Clásico", light_color: "#f8fafc", dark_color: "#111827", cost: 0 },
    { id: "ocean", name: "Océano", light_color: "#e0f2fe", dark_color: "#0c4a6e", cost: 20 }
  ];
  const shop = ChessUI.renderShop(backgrounds, ["classic"], { points: 10, active_background: "classic" });
  assert.match(shop, /En uso/);
  assert.match(shop, /Cuesta 20 Papucoins/);
  assert.match(shop, /data-background-action="buy" data-background-id="ocean" disabled/);
  const owned = ChessUI.renderShop(backgrounds, ["classic", "ocean"], { points: 0, active_background: "classic" });
  assert.match(owned, /data-background-action="activate" data-background-id="ocean"/);
});

test("la Edge Function valida sesión, jugadas, amistades y operaciones protegidas", () => {
  const edge = read("supabase/functions/chess-api/index.ts");
  const sql = read("supabase/migrations/20261026214010_studyflow_chess_points_and_background_shop.sql");
  const inviteLifecycle = read("supabase/migrations/20261031144138_studyflow_chess_invite_lifecycle.sql");
  const schema = read("supabase/schema.sql");
  assert.match(edge, /auth\.getUser\(token\)/);
  assert.match(edge, /Chess/);
  assert.match(edge, /replayMoves\(Chess/);
  assert.match(edge, /only invite.*friends|Solo puedes invitar a personas que ya sean tus amigos/i);
  assert.match(edge, /rpc\("create_chess_invite"/);
  assert.match(edge, /rpc\("respond_chess_invite"/);
  assert.match(edge, /action === "cancel_invite"[\s\S]*?challenger_id", user\.id[\s\S]*?revision/);
  assert.match(edge, /typeof body\.accept !== "boolean"/);
  assert.match(edge, /commit_chess_move/);
  assert.match(edge, /purchase_chess_background/);
  assert.match(sql, /alter table public\.chess_games enable row level security/i);
  assert.match(sql, /Players can read their own chess games/i);
  assert.match(sql, /chess_point_ledger[\s\S]*?game_id uuid not null unique/i);
  assert.match(sql, /revoke all on function public\.commit_chess_move[\s\S]*?from public, anon, authenticated/i);
  assert.match(sql, /grant execute on function public\.commit_chess_move[\s\S]*?to service_role/i);
  assert.match(sql, /grant execute on function public\.purchase_chess_background[\s\S]*?to service_role/i);
  assert.match(sql, /points\s*=\s*public\.chess_wallets\.points\s*\+\s*10/i);
  assert.match(inviteLifecycle, /create or replace function public\.create_chess_invite/i);
  assert.match(inviteLifecycle, /create or replace function public\.respond_chess_invite/i);
  assert.match(inviteLifecycle, /from public\.friendships[\s\S]*?for update/i);
  assert.match(inviteLifecycle, /update public\.chess_games[\s\S]*?status = 'declined'[\s\S]*?g\.status = 'pending'/i);
  assert.match(inviteLifecycle, /grant execute on function public\.create_chess_invite\(uuid, uuid\) to service_role/i);
  assert.match(inviteLifecycle, /grant execute on function public\.respond_chess_invite\(uuid, uuid, boolean\) to service_role/i);
  assert.match(schema, /create or replace function public\.create_chess_invite/i);
  assert.match(schema, /create or replace function public\.respond_chess_invite/i);
});

test("la página carga la biblioteca, la sección y el controlador antes de autenticar", () => {
  const html = read("index.html");
  const auth = read("auth.js");
  const css = read("styles.css");
  const chess = read("chess-ui.js");
  for (const id of ["chessSection", "chessPoints", "chessMessage", "chessInviteForm", "chessInviteFriend", "chessGames", "chessBoard", "chessPromotion", "chessShop", "chessResign"]) {
    assert.ok(html.includes('id="' + id + '"'), "Falta #" + id);
  }
  assert.match(html, /chess\.min\.js" defer><\/script>\s*<script src="chess-ui\.js" defer><\/script>\s*<script src="auth\.js" defer>/);
  assert.match(html, /10 Papucoins/);
  assert.match(auth, /StudyFlowChess\.mount/);
  assert.match(auth, /destroyChessUI\(\)/);
  assert.match(chess, /client\.channel\("studyflow-chess-/);
  assert.match(chess, /postgres_changes"\s*,\s*\{ event: "\*", schema: "public", table: "chess_games" \}/);
  assert.match(css, /\.chess-board/);
  assert.match(css, /--chess-page-bg/);
});

