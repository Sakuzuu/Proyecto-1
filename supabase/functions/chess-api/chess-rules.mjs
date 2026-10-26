export const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

export function parseUci(uci) {
  if (typeof uci !== "string") throw new Error("Movimiento UCI inválido.");
  const match = uci.trim().match(/^([a-h][1-8])([a-h][1-8])([qrbn])?$/);
  if (!match || match[1] === match[2]) throw new Error("Movimiento UCI inválido.");
  return { from: match[1], to: match[2], ...(match[3] ? { promotion: match[3] } : {}) };
}

export function replayMoves(ChessCtor, moves, startFen = START_FEN) {
  if (typeof ChessCtor !== "function") throw new TypeError("No se recibió un motor de ajedrez válido.");
  if (!Array.isArray(moves) || moves.length > 600) throw new Error("Historial de partida inválido.");
  const chess = new ChessCtor(startFen);
  for (const uci of moves) {
    const move = chess.move(parseUci(uci));
    if (!move) throw new Error("El historial contiene una jugada ilegal.");
  }
  return chess;
}

export function inspectPosition(chess) {
  const isGameOver = typeof chess.isGameOver === "function" ? chess.isGameOver() : chess.game_over();
  if (!isGameOver) return { status: "active", winnerColor: null, finishReason: null };
  const isCheckmate = typeof chess.isCheckmate === "function" ? chess.isCheckmate() : chess.in_checkmate();
  if (isCheckmate) return { status: "finished", winnerColor: chess.turn() === "w" ? "b" : "w", finishReason: "checkmate" };
  const isStalemate = typeof chess.isStalemate === "function" ? chess.isStalemate() : chess.in_stalemate();
  if (isStalemate) return { status: "finished", winnerColor: null, finishReason: "stalemate" };
  return { status: "finished", winnerColor: null, finishReason: "draw" };
}

export function applyLegalMove(ChessCtor, previousMoves, input, startFen = START_FEN) {
  const chess = replayMoves(ChessCtor, previousMoves, startFen);
  if (inspectPosition(chess).status !== "active") throw new Error("La partida ya terminó.");
  if (!input || !/^[a-h][1-8]$/.test(String(input.from || "")) || !/^[a-h][1-8]$/.test(String(input.to || ""))) {
    throw new Error("Selecciona casillas válidas.");
  }
  const legalDestinations = chess.moves({ square: input.from, verbose: true }).filter(move => move.to === input.to);
  if (!legalDestinations.length) throw new Error("Esa jugada no es legal.");
  const promotes = legalDestinations.some(move => Boolean(move.promotion));
  let promotion;
  if (promotes) {
    promotion = String(input.promotion || "").toLowerCase();
    if (!["q", "r", "b", "n"].includes(promotion)) throw new Error("Elige una pieza para la promoción.");
  } else if (input.promotion) {
    throw new Error("Esta jugada no necesita promoción.");
  }
  const applied = chess.move({ from: input.from, to: input.to, ...(promotion ? { promotion } : {}) });
  if (!applied) throw new Error("Esa jugada no es legal.");
  const uci = applied.from + applied.to + (applied.promotion || "");
  const moves = previousMoves.concat(uci);
  const outcome = inspectPosition(chess);
  return {
    moves,
    fen: chess.fen(),
    san: applied.san,
    uci,
    nextColor: outcome.status === "active" ? chess.turn() : null,
    status: outcome.status,
    winnerColor: outcome.winnerColor,
    finishReason: outcome.finishReason
  };
}
