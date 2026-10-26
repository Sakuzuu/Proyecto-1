import { createClient } from "npm:@supabase/supabase-js@2.58.0";
import { Chess } from "npm:chess.js@1.4.0";
import { START_FEN, replayMoves, applyLegalMove } from "./chess-rules.mjs";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, x-client-info, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Content-Type": "application/json; charset=utf-8"
};

function respond(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: corsHeaders });
}
function httpError(status: number, message: string, code?: string) {
  return Object.assign(new Error(message), { status, code });
}
function isUuid(value: unknown): value is string {
  return typeof value === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}
function dbError(error: any): never {
  if (error?.code === "23505") throw httpError(409, "Ya existe una invitación pendiente entre estas cuentas.", "duplicate_invite");
  console.error("chess-api database operation failed", { code: error?.code, message: error?.message });
  throw httpError(500, "No se pudo guardar el cambio de ajedrez.", error?.code);
}
function requireObject(value: unknown): Record<string, any> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw httpError(400, "La solicitud debe contener un objeto JSON.");
  return value as Record<string, any>;
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST") return respond({ error: "Usa POST para esta operación." }, 405);

  try {
    const authHeader = req.headers.get("Authorization");
    if (!authHeader?.startsWith("Bearer ")) throw httpError(401, "Inicia sesión para jugar.");
    const token = authHeader.slice("Bearer ".length).trim();
    if (!token) throw httpError(401, "La sesión no es válida.");

    const supabaseUrl = Deno.env.get("SUPABASE_URL") ?? "";
    const publicKey = Deno.env.get("SUPABASE_ANON_KEY") ?? Deno.env.get("SUPABASE_PUBLISHABLE_KEY") ?? "";
    const secretKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? Deno.env.get("SUPABASE_SECRET_KEY") ?? "";
    if (!supabaseUrl || !publicKey || !secretKey) throw httpError(500, "Falta configuración interna de Supabase.");

    const authClient = createClient(supabaseUrl, publicKey, {
      auth: { persistSession: false, autoRefreshToken: false },
      global: { headers: { Authorization: "Bearer " + token } }
    });
    const { data: authData, error: authError } = await authClient.auth.getUser(token);
    if (authError || !authData?.user) throw httpError(401, "La sesión expiró. Inicia sesión de nuevo.");
    const user = authData.user;
    const admin = createClient(supabaseUrl, secretKey, {
      auth: { persistSession: false, autoRefreshToken: false }
    });
    const body = requireObject(await req.json());
    const action = body.action;

    async function loadState() {
      const walletResult = await admin.from("chess_wallets")
        .upsert({ user_id: user.id }, { onConflict: "user_id", ignoreDuplicates: true });
      if (walletResult.error) dbError(walletResult.error);
      const freeBackgroundResult = await admin.from("chess_background_purchases")
        .upsert({ user_id: user.id, background_id: "classic" }, { onConflict: "user_id,background_id", ignoreDuplicates: true });
      if (freeBackgroundResult.error) dbError(freeBackgroundResult.error);

      const [wallet, purchases, backgrounds, gameResult, friendshipResult] = await Promise.all([
        admin.from("chess_wallets").select("user_id, points, active_background, updated_at").eq("user_id", user.id).single(),
        admin.from("chess_background_purchases").select("background_id, created_at").eq("user_id", user.id),
        admin.from("chess_background_catalog").select("id, name, light_color, dark_color, cost, sort_order").order("sort_order"),
        admin.from("chess_games").select("id, challenger_id, opponent_id, status, moves, fen, current_turn, winner_id, finish_reason, revision, reward_granted, created_at, updated_at, started_at, finished_at")
          .or("challenger_id.eq." + user.id + ",opponent_id.eq." + user.id).order("updated_at", { ascending: false }).limit(50),
        admin.from("friendships").select("user_a_id, user_b_id")
          .or("user_a_id.eq." + user.id + ",user_b_id.eq." + user.id)
      ]);
      for (const result of [wallet, purchases, backgrounds, gameResult, friendshipResult]) if (result.error) dbError(result.error);

      const friendIds = (friendshipResult.data || []).map((f: any) => f.user_a_id === user.id ? f.user_b_id : f.user_a_id);
      const opponentIds = [...new Set((gameResult.data || []).map((g: any) => g.challenger_id === user.id ? g.opponent_id : g.challenger_id))];
      const profileIds = [...new Set(friendIds.concat(opponentIds))];
      const profileResult = profileIds.length
        ? await admin.from("profiles").select("id, username, display_name").in("id", profileIds)
        : { data: [], error: null };
      if (profileResult.error) dbError(profileResult.error);
      const profileMap = new Map((profileResult.data || []).map((p: any) => [p.id, p]));
      const games = (gameResult.data || []).map((g: any) => {
        const opponentId = g.challenger_id === user.id ? g.opponent_id : g.challenger_id;
        const winner = g.winner_id ? profileMap.get(g.winner_id) : null;
        const opponent = profileMap.get(opponentId);
        return {
          ...g,
          player_color: g.challenger_id === user.id ? "w" : "b",
          opponent: opponent ? { id: opponent.id, username: opponent.username, display_name: opponent.display_name } : { id: opponentId, username: "estudiante", display_name: "Estudiante" },
          winner: winner ? { id: winner.id, username: winner.username, display_name: winner.display_name } : null
        };
      });
      const friends = friendIds.map((id: string) => {
        const profile = profileMap.get(id);
        return profile ? { id: profile.id, username: profile.username, display_name: profile.display_name } : null;
      }).filter(Boolean);
      return {
        wallet: wallet.data,
        backgrounds: backgrounds.data || [],
        purchases: (purchases.data || []).map((p: any) => p.background_id),
        games,
        friends
      };
    }

    if (action === "load") return respond({ data: await loadState() });

    if (action === "invite") {
      const friendId = body.friend_id;
      if (!isUuid(friendId) || friendId === user.id) throw httpError(400, "Selecciona un amigo válido.");
      const pair = [user.id, friendId].sort();
      const friendship = await admin.from("friendships").select("user_a_id")
        .eq("user_a_id", pair[0]).eq("user_b_id", pair[1]).maybeSingle();
      if (friendship.error) dbError(friendship.error);
      if (!friendship.data) throw httpError(403, "Solo puedes invitar a personas que ya sean tus amigos.");
      const result = await admin.from("chess_games").insert({
        challenger_id: user.id, opponent_id: friendId, status: "pending",
        moves: [], fen: START_FEN, current_turn: null
      }).select("id, status, created_at").single();
      if (result.error) dbError(result.error);
      return respond({ data: result.data, message: "Invitación enviada." });
    }

    if (action === "respond_invite") {
      const gameId = body.game_id, accept = body.accept === true;
      if (!isUuid(gameId)) throw httpError(400, "La invitación no es válida.");
      const update = await admin.from("chess_games").update({
        status: accept ? "active" : "declined",
        moves: [],
        fen: START_FEN,
        current_turn: null,
        started_at: accept ? new Date().toISOString() : null,
        updated_at: new Date().toISOString(),
        revision: 0
      }).eq("id", gameId).eq("opponent_id", user.id).eq("status", "pending")
        .select("id, status, challenger_id, opponent_id, fen, current_turn, revision").maybeSingle();
      if (update.error) dbError(update.error);
      if (!update.data) throw httpError(409, "La invitación ya no está pendiente o no te pertenece.");
      if (accept) {
        const start = await admin.from("chess_games").update({ current_turn: update.data.challenger_id })
          .eq("id", gameId).eq("revision", 0).eq("status", "active").select("id").single();
        if (start.error) dbError(start.error);
      }
      return respond({ data: update.data, message: accept ? "Partida aceptada. Juegan blancas primero." : "Invitación rechazada." });
    }

    if (action === "move") {
      const gameId = body.game_id;
      if (!isUuid(gameId) || !Number.isInteger(body.expected_revision) || body.expected_revision < 0) {
        throw httpError(400, "La jugada o versión de la partida no es válida.");
      }
      const gameResult = await admin.from("chess_games").select("*").eq("id", gameId).maybeSingle();
      if (gameResult.error) dbError(gameResult.error);
      const game = gameResult.data;
      if (!game || ![game.challenger_id, game.opponent_id].includes(user.id)) throw httpError(404, "No encontramos esa partida para tu cuenta.");
      if (game.status !== "active") throw httpError(409, "La partida ya no está activa.");
      if (game.current_turn !== user.id) throw httpError(403, "Todavía no es tu turno.");
      if (game.revision !== body.expected_revision) throw httpError(409, "La partida cambió en otro dispositivo. Se actualizará el tablero.");
      let currentPosition;
      try { currentPosition = replayMoves(Chess, game.moves || []); }
      catch { throw httpError(500, "El historial de la partida no es válido."); }
      if (currentPosition.fen() !== game.fen) throw httpError(409, "El estado de la partida no coincide con su historial. Recarga la página.");
      let result;
      try { result = applyLegalMove(Chess, game.moves || [], { from: body.from, to: body.to, promotion: body.promotion }); }
      catch (error) { throw httpError(400, error instanceof Error ? error.message : "Esa jugada no es legal."); }
      const winnerId = result.winnerColor === "w" ? game.challenger_id : result.winnerColor === "b" ? game.opponent_id : null;
      const nextTurn = result.status === "active" ? (result.nextColor === "w" ? game.challenger_id : game.opponent_id) : null;
      const committed = await admin.rpc("commit_chess_move", {
        p_game_id: game.id,
        p_expected_revision: game.revision,
        p_moves: result.moves,
        p_fen: result.fen,
        p_current_turn: nextTurn,
        p_status: result.status,
        p_winner_id: winnerId,
        p_finish_reason: result.finishReason
      });
      if (committed.error) dbError(committed.error);
      if (!committed.data?.ok) throw httpError(409, "La partida cambió mientras enviabas la jugada. Se actualizará el tablero.");
      return respond({ data: { game_id: game.id, ...result, revision: committed.data.revision, reward_awarded: committed.data.reward_awarded } });
    }

    if (action === "resign") {
      const gameId = body.game_id;
      if (!isUuid(gameId) || !Number.isInteger(body.expected_revision) || body.expected_revision < 0) throw httpError(400, "La partida no es válida.");
      const gameResult = await admin.from("chess_games").select("id, challenger_id, opponent_id, status, revision")
        .eq("id", gameId).maybeSingle();
      if (gameResult.error) dbError(gameResult.error);
      const game = gameResult.data;
      if (!game || ![game.challenger_id, game.opponent_id].includes(user.id)) throw httpError(404, "No encontramos esa partida para tu cuenta.");
      if (game.status !== "active") throw httpError(409, "La partida ya no está activa.");
      if (game.revision !== body.expected_revision) throw httpError(409, "La partida cambió en el otro dispositivo. Actualiza la lista.");
      const winnerId = game.challenger_id === user.id ? game.opponent_id : game.challenger_id;
      const result = await admin.rpc("finish_chess_game", { p_game_id: game.id, p_expected_revision: game.revision, p_winner_id: winnerId });
      if (result.error) dbError(result.error);
      if (!result.data?.ok) throw httpError(409, "La partida ya terminó en el otro dispositivo.");
      return respond({ data: result.data, message: "Te has rendido. Tu rival recibe 10 puntos." });
    }

    if (action === "purchase_background") {
      const backgroundId = body.background_id;
      if (typeof backgroundId !== "string" || !/^[a-z][a-z0-9_]{1,30}$/.test(backgroundId)) throw httpError(400, "Selecciona un fondo válido.");
      const result = await admin.rpc("purchase_chess_background", { p_user_id: user.id, p_background_id: backgroundId });
      if (result.error) dbError(result.error);
      if (!result.data?.ok) {
        const reason = result.data?.reason;
        if (reason === "insufficient_points") throw httpError(409, "Necesitas " + result.data.cost + " puntos; tienes " + result.data.points + ".", reason);
        throw httpError(400, "No se pudo comprar ese fondo.", reason);
      }
      return respond({ data: result.data, message: result.data.already_owned ? "Ya tienes este fondo." : "Fondo comprado y activado." });
    }

    if (action === "activate_background") {
      const backgroundId = body.background_id;
      if (typeof backgroundId !== "string" || !/^[a-z][a-z0-9_]{1,30}$/.test(backgroundId)) throw httpError(400, "Selecciona un fondo válido.");
      const result = await admin.rpc("activate_chess_background", { p_user_id: user.id, p_background_id: backgroundId });
      if (result.error) dbError(result.error);
      if (!result.data?.ok) throw httpError(403, "Primero debes comprar este fondo.");
      return respond({ data: result.data, message: "Fondo activado." });
    }

    throw httpError(400, "La acción solicitada no existe.");
  } catch (error: any) {
    const status = Number.isInteger(error?.status) ? error.status : 500;
    if (status >= 500) console.error("chess-api request failed", { status, message: error?.message, code: error?.code });
    return respond({ error: String(error?.message || "Error interno."), code: error?.code || "chess_api_error" }, status);
  }
});
