-- Keep pending chess invitations aligned with the underlying friendship.
-- Locking the friendship row serializes invitation creation/acceptance with removal.
create or replace function public.remove_friend(p_friend_id uuid)
returns boolean
language plpgsql security definer set search_path = '' as $$
declare
  requester_id uuid := (select auth.uid());
  deleted_count integer;
begin
  if requester_id is null or p_friend_id is null or requester_id = p_friend_id then return false; end if;
  delete from public.friendships f
    where f.user_a_id = least(requester_id, p_friend_id)
      and f.user_b_id = greatest(requester_id, p_friend_id);
  get diagnostics deleted_count = row_count;
  if deleted_count > 0 then
    update public.chess_games g
      set status = 'declined', current_turn = null, updated_at = pg_catalog.now(), revision = g.revision + 1
      where g.status = 'pending'
        and ((g.challenger_id = requester_id and g.opponent_id = p_friend_id)
          or (g.challenger_id = p_friend_id and g.opponent_id = requester_id));
  end if;
  return deleted_count > 0;
end;
$$;
revoke execute on function public.remove_friend(uuid) from public, anon, authenticated;
grant execute on function public.remove_friend(uuid) to authenticated;

create or replace function public.create_chess_invite(p_challenger_id uuid, p_opponent_id uuid)
returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  friendship_row public.friendships%rowtype;
  game_row public.chess_games%rowtype;
begin
  if p_challenger_id is null or p_opponent_id is null or p_challenger_id = p_opponent_id then
    raise exception 'invalid chess invite participants';
  end if;

  select * into friendship_row
    from public.friendships f
    where f.user_a_id = least(p_challenger_id, p_opponent_id)
      and f.user_b_id = greatest(p_challenger_id, p_opponent_id)
    for update;
  if not found then return pg_catalog.jsonb_build_object('ok', false, 'reason', 'not_friends'); end if;

  insert into public.chess_games(challenger_id, opponent_id, status)
    values (p_challenger_id, p_opponent_id, 'pending')
    returning * into game_row;
  return pg_catalog.jsonb_build_object('ok', true, 'game', pg_catalog.to_jsonb(game_row));
end;
$$;
revoke all on function public.create_chess_invite(uuid, uuid) from public, anon, authenticated;
grant execute on function public.create_chess_invite(uuid, uuid) to service_role;

create or replace function public.respond_chess_invite(p_game_id uuid, p_user_id uuid, p_accept boolean)
returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  game_row public.chess_games%rowtype;
  friendship_row public.friendships%rowtype;
begin
  if p_game_id is null or p_user_id is null or p_accept is null then raise exception 'invalid chess invite response'; end if;
  select * into game_row from public.chess_games g where g.id = p_game_id;
  if not found or game_row.opponent_id <> p_user_id or game_row.status <> 'pending' then
    return pg_catalog.jsonb_build_object('ok', false, 'reason', 'not_pending');
  end if;

  if p_accept then
    select * into friendship_row
      from public.friendships f
      where f.user_a_id = least(game_row.challenger_id, game_row.opponent_id)
        and f.user_b_id = greatest(game_row.challenger_id, game_row.opponent_id)
      for update;
    if not found then
      update public.chess_games g
        set status = 'declined', current_turn = null, updated_at = pg_catalog.now(), revision = g.revision + 1
        where g.id = p_game_id and g.opponent_id = p_user_id and g.status = 'pending';
      return pg_catalog.jsonb_build_object('ok', false, 'reason', 'not_friends');
    end if;
  end if;

  select * into game_row from public.chess_games g where g.id = p_game_id for update;
  if not found or game_row.opponent_id <> p_user_id or game_row.status <> 'pending' then
    return pg_catalog.jsonb_build_object('ok', false, 'reason', 'not_pending');
  end if;

  update public.chess_games g
    set status = case when p_accept then 'active' else 'declined' end,
        current_turn = case when p_accept then game_row.challenger_id else null end,
        started_at = case when p_accept then pg_catalog.now() else null end,
        updated_at = pg_catalog.now(), revision = g.revision + 1
    where g.id = p_game_id
    returning * into game_row;
  return pg_catalog.jsonb_build_object('ok', true, 'game', pg_catalog.to_jsonb(game_row));
end;
$$;
revoke all on function public.respond_chess_invite(uuid, uuid, boolean) from public, anon, authenticated;
grant execute on function public.respond_chess_invite(uuid, uuid, boolean) to service_role;
