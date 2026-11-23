-- StudyFlow Step 1: protected user profiles.
create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  username text not null unique check (username = pg_catalog.lower(username) and username ~ '^[a-z0-9_]{3,24}$'),
  display_name text not null check (char_length(btrim(display_name)) between 2 and 60),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table public.profiles enable row level security;
drop policy if exists "Users can view their own profile" on public.profiles;
create policy "Users can view their own profile" on public.profiles for select to authenticated using ((select auth.uid()) = id);
drop policy if exists "Users can update their own profile" on public.profiles;
create policy "Users can update their own profile" on public.profiles for update to authenticated using ((select auth.uid()) = id) with check ((select auth.uid()) = id);
revoke all on public.profiles from public, anon, authenticated;
grant select, update on public.profiles to authenticated;
create or replace function public.set_profile_updated_at()
returns trigger language plpgsql set search_path = '' as $$
begin
  new.updated_at = pg_catalog.now();
  return new;
end;
$$;

revoke execute on function public.set_profile_updated_at() from public, anon, authenticated;
drop trigger if exists set_profile_updated_at on public.profiles;
create trigger set_profile_updated_at before update on public.profiles for each row execute function public.set_profile_updated_at();
create or replace function public.handle_new_studyflow_user()
returns trigger language plpgsql security definer set search_path = '' as $$
declare
  requested_username text;
  requested_display_name text;
begin
  requested_username := pg_catalog.lower(pg_catalog.btrim(coalesce(new.raw_user_meta_data ->> 'username', '')));
  requested_display_name := pg_catalog.left(pg_catalog.btrim(coalesce(new.raw_user_meta_data ->> 'display_name', '')), 60);
  if requested_username !~ '^[a-z0-9_]{3,24}$' then requested_username := 'u_' || pg_catalog.left(pg_catalog.replace(new.id::text, '-', ''), 22); end if;
  if requested_display_name = '' then
    requested_display_name := pg_catalog.left(coalesce(nullif(pg_catalog.split_part(coalesce(new.email, ''), '@', 1), ''), 'Estudiante'), 60);
  end if;
  insert into public.profiles (id, username, display_name) values (new.id, requested_username, requested_display_name);
  return new;
end;
$$;
revoke execute on function public.handle_new_studyflow_user() from public, anon, authenticated;
drop trigger if exists on_auth_user_created_studyflow on auth.users;
create trigger on_auth_user_created_studyflow after insert on auth.users for each row execute function public.handle_new_studyflow_user();

-- StudyFlow Step 2: academic data and protected friendship foundation.
alter table public.profiles add column if not exists share_academic_averages boolean not null default false;

create table if not exists public.subjects (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  name text not null check (char_length(btrim(name)) between 1 and 60),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id, user_id)
);
create unique index if not exists subjects_user_name_unique on public.subjects (user_id, (lower(name)));
create index if not exists subjects_user_created_idx on public.subjects (user_id, created_at);

create table if not exists public.grades (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  subject_id uuid not null,
  value numeric(5,2) not null check (value >= 0 and value <= 100),
  label text not null default '' check (char_length(label) <= 60),
  grade_date date not null,
  academic_year text not null check (academic_year ~ '^[0-9]{4}-[0-9]{4}$'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint grades_subject_owner_fkey foreign key (subject_id, user_id)
    references public.subjects (id, user_id) on delete cascade
);
create index if not exists grades_user_year_idx on public.grades (user_id, academic_year);
create index if not exists grades_subject_year_idx on public.grades (subject_id, academic_year);
alter table public.subjects enable row level security;
alter table public.grades enable row level security;
drop policy if exists "Users manage their own subjects" on public.subjects;
create policy "Users manage their own subjects" on public.subjects for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
drop policy if exists "Users manage their own grades" on public.grades;
create policy "Users manage their own grades" on public.grades for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
revoke all on public.subjects, public.grades from public, anon, authenticated;
grant select, insert, update, delete on public.subjects to authenticated;
grant select, insert, update, delete on public.grades to authenticated;
create or replace function public.set_academic_record_updated_at()
returns trigger language plpgsql set search_path = '' as $$
begin
  new.updated_at = pg_catalog.now();
  return new;
end;
$$;
revoke execute on function public.set_academic_record_updated_at() from public, anon, authenticated;
drop trigger if exists set_subject_updated_at on public.subjects;
create trigger set_subject_updated_at before update on public.subjects for each row execute function public.set_academic_record_updated_at();
drop trigger if exists set_grade_updated_at on public.grades;
create trigger set_grade_updated_at before update on public.grades for each row execute function public.set_academic_record_updated_at();

create table if not exists public.friend_requests (
  id uuid primary key default gen_random_uuid(),
  sender_id uuid not null references auth.users (id) on delete cascade,
  recipient_id uuid not null references auth.users (id) on delete cascade,
  status text not null default 'pending' check (status in ('pending', 'accepted', 'rejected')),
  created_at timestamptz not null default now(),
  responded_at timestamptz,
  check (sender_id <> recipient_id)
);
create unique index if not exists friend_requests_pending_pair_unique on public.friend_requests (least(sender_id, recipient_id), greatest(sender_id, recipient_id)) where status = 'pending';
create index if not exists friend_requests_recipient_status_idx on public.friend_requests (recipient_id, status, created_at desc);
create index if not exists friend_requests_sender_status_idx on public.friend_requests (sender_id, status, created_at desc);
create table if not exists public.friendships (
  user_a_id uuid not null references auth.users (id) on delete cascade,
  user_b_id uuid not null references auth.users (id) on delete cascade,
  created_at timestamptz not null default now(),
  constraint friendships_canonical_order check (user_a_id < user_b_id),
  primary key (user_a_id, user_b_id)
);
create index if not exists friendships_user_b_idx on public.friendships (user_b_id, user_a_id);
alter table public.friend_requests enable row level security;
alter table public.friendships enable row level security;
drop policy if exists "Users view their own friend requests" on public.friend_requests;
create policy "Users view their own friend requests" on public.friend_requests for select to authenticated using ((select auth.uid()) = sender_id or (select auth.uid()) = recipient_id);
drop policy if exists "Users send their own friend requests" on public.friend_requests;
create policy "Users send their own friend requests" on public.friend_requests for insert to authenticated with check ((select auth.uid()) = sender_id and recipient_id <> (select auth.uid()) and status = 'pending');
drop policy if exists "Recipients respond to pending friend requests" on public.friend_requests;
create policy "Recipients respond to pending friend requests" on public.friend_requests for update to authenticated using ((select auth.uid()) = recipient_id and status = 'pending') with check ((select auth.uid()) = recipient_id and status in ('accepted', 'rejected'));
drop policy if exists "Friends can view their friendship" on public.friendships;
create policy "Friends can view their friendship" on public.friendships for select to authenticated using ((select auth.uid()) = user_a_id or (select auth.uid()) = user_b_id);
revoke all on public.friend_requests, public.friendships from public, anon, authenticated;
grant select, insert on public.friend_requests to authenticated;
grant update (status) on public.friend_requests to authenticated;
grant select on public.friendships to authenticated;

create or replace function public.handle_friend_request_response()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if old.status = 'pending' and new.status in ('accepted', 'rejected') then new.responded_at := pg_catalog.now(); end if;
  if old.status = 'pending' and new.status = 'accepted' then
    insert into public.friendships (user_a_id, user_b_id)
    values (least(new.sender_id, new.recipient_id), greatest(new.sender_id, new.recipient_id))
    on conflict do nothing;
  end if;
  return new;
end;
$$;
revoke execute on function public.handle_friend_request_response() from public, anon, authenticated;
drop trigger if exists on_friend_request_response on public.friend_requests;
create trigger on_friend_request_response before update of status on public.friend_requests for each row execute function public.handle_friend_request_response();

create or replace function public.search_profiles_by_username(p_query text)
returns table (id uuid, username text, display_name text)
language plpgsql stable security definer set search_path = '' as $$
declare normalized_query text := pg_catalog.lower(pg_catalog.btrim(coalesce(p_query, '')));
begin
  if (select auth.uid()) is null or pg_catalog.char_length(normalized_query) < 3 then return; end if;
  return query select p.id, p.username, p.display_name from public.profiles p
    where p.username = normalized_query and p.id <> (select auth.uid()) limit 1;
end;
$$;
revoke execute on function public.search_profiles_by_username(text) from public, anon, authenticated;
grant execute on function public.search_profiles_by_username(text) to authenticated;

create or replace function public.get_shared_academic_averages(p_friend_id uuid)
returns table (metric_type text, subject_name text, academic_year text, average numeric)
language plpgsql stable security definer set search_path = '' as $$
declare requester_id uuid := (select auth.uid());
begin
  if requester_id is null or p_friend_id is null or requester_id = p_friend_id then return; end if;
  if not exists (select 1 from public.friendships f where f.user_a_id = least(requester_id, p_friend_id) and f.user_b_id = greatest(requester_id, p_friend_id)) then return; end if;
  if not exists (select 1 from public.profiles p where p.id = p_friend_id and p.share_academic_averages is true) then return; end if;
  return query select results.metric_type, results.subject_name, results.academic_year, results.average
  from (
    select 'subject'::text metric_type, s.name subject_name, g.academic_year academic_year, pg_catalog.round(pg_catalog.avg(g.value)::numeric, 2) average
    from public.subjects s join public.grades g on g.subject_id = s.id and g.user_id = s.user_id
    where s.user_id = p_friend_id group by s.id, s.name, g.academic_year
    union all
    select 'year'::text metric_type, null::text subject_name, g.academic_year academic_year, pg_catalog.round(pg_catalog.avg(g.value)::numeric, 2) average
    from public.grades g where g.user_id = p_friend_id group by g.academic_year
  ) results order by results.academic_year, results.metric_type, results.subject_name;
end;
$$;
revoke execute on function public.get_shared_academic_averages(uuid) from public, anon, authenticated;
grant execute on function public.get_shared_academic_averages(uuid) to authenticated;

-- Friend list helpers; profile basics only, no email fields.
create or replace function public.list_my_friends()
returns table (id uuid, username text, display_name text, share_academic_averages boolean, friendship_created_at timestamptz)
language sql stable security definer set search_path = '' as $$
  select case when f.user_a_id = (select auth.uid()) then p_b.id else p_a.id end,
    case when f.user_a_id = (select auth.uid()) then p_b.username else p_a.username end,
    case when f.user_a_id = (select auth.uid()) then p_b.display_name else p_a.display_name end,
    case when f.user_a_id = (select auth.uid()) then p_b.share_academic_averages else p_a.share_academic_averages end,
    f.created_at
  from public.friendships f join public.profiles p_a on p_a.id=f.user_a_id join public.profiles p_b on p_b.id=f.user_b_id
  where (select auth.uid())=f.user_a_id or (select auth.uid())=f.user_b_id order by f.created_at desc;
$$;
revoke execute on function public.list_my_friends() from public, anon, authenticated;
grant execute on function public.list_my_friends() to authenticated;

create or replace function public.list_my_friend_requests()
returns table (id uuid, sender_id uuid, recipient_id uuid, status text, created_at timestamptz, responded_at timestamptz, direction text, other_username text, other_display_name text)
language sql stable security definer set search_path = '' as $$
  select r.id, r.sender_id, r.recipient_id, r.status, r.created_at, r.responded_at,
    case when r.sender_id=(select auth.uid()) then 'sent'::text else 'received'::text end,
    p.username, p.display_name
  from public.friend_requests r join public.profiles p on p.id=case when r.sender_id=(select auth.uid()) then r.recipient_id else r.sender_id end
  where (select auth.uid())=r.sender_id or (select auth.uid())=r.recipient_id order by r.created_at desc;
$$;
revoke execute on function public.list_my_friend_requests() from public, anon, authenticated;
grant execute on function public.list_my_friend_requests() to authenticated;

create or replace function public.remove_friend(p_friend_id uuid)
returns boolean language plpgsql security definer set search_path = '' as $$
declare requester_id uuid := (select auth.uid()); deleted_count integer;
begin
  if requester_id is null or p_friend_id is null or requester_id=p_friend_id then return false; end if;
  delete from public.friendships f where f.user_a_id=least(requester_id,p_friend_id) and f.user_b_id=greatest(requester_id,p_friend_id);
  get diagnostics deleted_count = row_count;
  return deleted_count > 0;
end;
$$;
revoke execute on function public.remove_friend(uuid) from public, anon, authenticated;
grant execute on function public.remove_friend(uuid) to authenticated;

create index if not exists grades_subject_user_idx on public.grades (subject_id, user_id);


-- Chess point wallet and background shop, consolidated with the existing schema.
-- StudyFlow chess games, reward ledger, wallet, and purchasable background catalog.
create table if not exists public.chess_background_catalog (
  id text primary key check (id ~ '^[a-z][a-z0-9_]{1,30}$'),
  name text not null check (char_length(name) between 2 and 40),
  light_color text not null check (light_color ~ '^#[0-9A-Fa-f]{6}$'),
  dark_color text not null check (dark_color ~ '^#[0-9A-Fa-f]{6}$'),
  cost integer not null check (cost >= 0),
  sort_order integer not null default 0,
  created_at timestamptz not null default now()
);
insert into public.chess_background_catalog (id, name, light_color, dark_color, cost, sort_order) values
 ('classic', 'Clásico', '#f8fafc', '#111827', 0, 0),
 ('ocean', 'Océano', '#e0f2fe', '#0c4a6e', 20, 1),
 ('forest', 'Bosque', '#dcfce7', '#14532d', 20, 2),
 ('sunset', 'Atardecer', '#ffedd5', '#7c2d12', 20, 3),
 ('lavender', 'Lavanda', '#ede9fe', '#4c1d95', 20, 4),
 ('rose', 'Rosa', '#ffe4e6', '#881337', 20, 5),
 ('midnight', 'Medianoche', '#dbeafe', '#172554', 30, 6)
on conflict (id) do update set name=excluded.name, light_color=excluded.light_color,
  dark_color=excluded.dark_color, cost=excluded.cost, sort_order=excluded.sort_order;

create table if not exists public.chess_wallets (
  user_id uuid primary key references auth.users(id) on delete cascade,
  points integer not null default 0 check (points >= 0),
  active_background text not null default 'classic' references public.chess_background_catalog(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create table if not exists public.chess_games (
  id uuid primary key default gen_random_uuid(),
  challenger_id uuid not null references auth.users(id) on delete cascade,
  opponent_id uuid not null references auth.users(id) on delete cascade,
  status text not null default 'pending' check (status in ('pending', 'active', 'finished', 'declined')),
  moves jsonb not null default '[]'::jsonb check (jsonb_typeof(moves) = 'array'),
  fen text not null default 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
  current_turn uuid references auth.users(id) on delete set null,
  winner_id uuid references auth.users(id) on delete set null,
  finish_reason text check (finish_reason is null or finish_reason in ('checkmate', 'stalemate', 'draw', 'resignation')),
  revision integer not null default 0 check (revision >= 0),
  reward_granted boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz,
  constraint chess_games_distinct_players check (challenger_id <> opponent_id),
  constraint chess_games_winner_is_participant check (winner_id is null or winner_id in (challenger_id, opponent_id)),
  constraint chess_games_turn_is_participant check (current_turn is null or current_turn in (challenger_id, opponent_id)),
  constraint chess_games_terminal_consistency check (
    (status = 'finished' and current_turn is null and finish_reason is not null and finished_at is not null)
    or (status <> 'finished' and winner_id is null and finish_reason is null and finished_at is null)
  )
);
create unique index if not exists chess_games_pending_pair_unique
  on public.chess_games (least(challenger_id, opponent_id), greatest(challenger_id, opponent_id))
  where status = 'pending';
create index if not exists chess_games_challenger_updated_idx on public.chess_games (challenger_id, updated_at desc);
create index if not exists chess_games_opponent_updated_idx on public.chess_games (opponent_id, updated_at desc);

create table if not exists public.chess_background_purchases (
  user_id uuid not null references auth.users(id) on delete cascade,
  background_id text not null references public.chess_background_catalog(id),
  created_at timestamptz not null default now(),
  primary key (user_id, background_id)
);
create table if not exists public.chess_point_ledger (
  id uuid primary key default gen_random_uuid(),
  game_id uuid not null unique references public.chess_games(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  points_delta integer not null check (points_delta = 10),
  reason text not null check (reason in ('checkmate', 'resignation')),
  created_at timestamptz not null default now()
);

alter table public.chess_background_catalog enable row level security;
alter table public.chess_wallets enable row level security;
alter table public.chess_games enable row level security;
alter table public.chess_background_purchases enable row level security;
alter table public.chess_point_ledger enable row level security;

drop policy if exists "Anyone signed in can read chess background catalog" on public.chess_background_catalog;
create policy "Anyone signed in can read chess background catalog" on public.chess_background_catalog
  for select to authenticated using (true);
drop policy if exists "Users can read their chess wallet" on public.chess_wallets;
create policy "Users can read their chess wallet" on public.chess_wallets
  for select to authenticated using ((select auth.uid()) = user_id);
drop policy if exists "Players can read their own chess games" on public.chess_games;
create policy "Players can read their own chess games" on public.chess_games
  for select to authenticated using ((select auth.uid()) = challenger_id or (select auth.uid()) = opponent_id);
drop policy if exists "Users can read their background purchases" on public.chess_background_purchases;
create policy "Users can read their background purchases" on public.chess_background_purchases
  for select to authenticated using ((select auth.uid()) = user_id);
drop policy if exists "Users can read their point ledger" on public.chess_point_ledger;
create policy "Users can read their point ledger" on public.chess_point_ledger
  for select to authenticated using ((select auth.uid()) = user_id);

grant select on public.chess_background_catalog to authenticated;
grant select on public.chess_wallets, public.chess_games, public.chess_background_purchases, public.chess_point_ledger to authenticated;
revoke insert, update, delete, truncate, references, trigger on public.chess_background_catalog from anon, authenticated;
revoke insert, update, delete, truncate, references, trigger on public.chess_wallets, public.chess_games, public.chess_background_purchases, public.chess_point_ledger from anon, authenticated;
revoke all on public.chess_wallets, public.chess_games, public.chess_background_purchases, public.chess_point_ledger from anon;
grant select, insert, update, delete on public.chess_wallets, public.chess_games, public.chess_background_purchases, public.chess_point_ledger to service_role;

create or replace function public.commit_chess_move(
  p_game_id uuid, p_expected_revision integer, p_moves jsonb, p_fen text,
  p_current_turn uuid, p_status text, p_winner_id uuid, p_finish_reason text
) returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  game_row public.chess_games%rowtype;
  ledger_row uuid;
  final_revision integer;
  reward_awarded boolean := false;
begin
  if p_status not in ('active', 'finished') or p_moves is null or pg_catalog.jsonb_typeof(p_moves) <> 'array'
     or p_fen is null or pg_catalog.char_length(p_fen) > 200 then
    raise exception 'invalid chess move payload';
  end if;
  select * into game_row from public.chess_games where id = p_game_id for update;
  if not found or game_row.status <> 'active' or game_row.revision <> p_expected_revision then
    return pg_catalog.jsonb_build_object('ok', false, 'reason', 'stale_or_finished');
  end if;
  if p_status = 'active' then
    if p_current_turn is null or p_current_turn not in (game_row.challenger_id, game_row.opponent_id)
       or p_winner_id is not null or p_finish_reason is not null then raise exception 'invalid active game state'; end if;
  else
    if p_current_turn is not null or p_finish_reason not in ('checkmate', 'stalemate', 'draw')
       or (p_winner_id is not null and p_winner_id not in (game_row.challenger_id, game_row.opponent_id))
       or (p_finish_reason in ('stalemate', 'draw') and p_winner_id is not null)
       or (p_finish_reason = 'checkmate' and p_winner_id is null) then raise exception 'invalid terminal game state'; end if;
  end if;
  update public.chess_games
    set moves=p_moves, fen=p_fen, current_turn=p_current_turn, status=p_status,
        winner_id=p_winner_id, finish_reason=p_finish_reason,
        updated_at=pg_catalog.now(), revision=revision+1,
        started_at=coalesce(started_at, pg_catalog.now()),
        finished_at=case when p_status='finished' then pg_catalog.now() else null end
    where id=p_game_id and status='active' and revision=p_expected_revision returning revision into final_revision;
  if not found then return pg_catalog.jsonb_build_object('ok', false, 'reason', 'stale_or_finished'); end if;
  if p_status='finished' and p_winner_id is not null then
    insert into public.chess_point_ledger (game_id,user_id,points_delta,reason)
      values (p_game_id,p_winner_id,10,'checkmate') on conflict (game_id) do nothing returning id into ledger_row;
    if ledger_row is not null then
      insert into public.chess_wallets (user_id,points) values (p_winner_id,10)
        on conflict (user_id) do update set points=public.chess_wallets.points+10,updated_at=pg_catalog.now();
      update public.chess_games set reward_granted=true where id=p_game_id;
      reward_awarded := true;
    end if;
  end if;
  return pg_catalog.jsonb_build_object('ok',true,'revision',final_revision,'reward_awarded',reward_awarded);
end;
$$;
revoke all on function public.commit_chess_move(uuid,integer,jsonb,text,uuid,text,uuid,text) from public, anon, authenticated;
grant execute on function public.commit_chess_move(uuid,integer,jsonb,text,uuid,text,uuid,text) to service_role;

create or replace function public.finish_chess_game(p_game_id uuid,p_expected_revision integer,p_winner_id uuid)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  game_row public.chess_games%rowtype;
  ledger_row uuid;
  final_revision integer;
begin
  select * into game_row from public.chess_games where id=p_game_id for update;
  if not found or game_row.status<>'active' or game_row.revision<>p_expected_revision then
    return pg_catalog.jsonb_build_object('ok',false,'reason','stale_or_finished');
  end if;
  if p_winner_id is null or p_winner_id not in (game_row.challenger_id,game_row.opponent_id) then raise exception 'winner must be a player in the game'; end if;
  update public.chess_games
    set status='finished',current_turn=null,winner_id=p_winner_id,finish_reason='resignation',
        finished_at=pg_catalog.now(),updated_at=pg_catalog.now(),revision=revision+1
    where id=p_game_id and status='active' and revision=p_expected_revision returning revision into final_revision;
  if not found then return pg_catalog.jsonb_build_object('ok',false,'reason','stale_or_finished'); end if;
  insert into public.chess_point_ledger (game_id,user_id,points_delta,reason)
    values (p_game_id,p_winner_id,10,'resignation') on conflict (game_id) do nothing returning id into ledger_row;
  if ledger_row is not null then
    insert into public.chess_wallets (user_id,points) values (p_winner_id,10)
      on conflict (user_id) do update set points=public.chess_wallets.points+10,updated_at=pg_catalog.now();
    update public.chess_games set reward_granted=true where id=p_game_id;
  end if;
  return pg_catalog.jsonb_build_object('ok',true,'revision',final_revision,'reward_awarded',ledger_row is not null);
end;
$$;
revoke all on function public.finish_chess_game(uuid,integer,uuid) from public, anon, authenticated;
grant execute on function public.finish_chess_game(uuid,integer,uuid) to service_role;

create or replace function public.purchase_chess_background(p_user_id uuid,p_background_id text)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare background_cost integer; current_points integer;
begin
  if p_user_id is null or p_background_id is null then raise exception 'missing wallet or background'; end if;
  select cost into background_cost from public.chess_background_catalog where id=p_background_id;
  if not found then return pg_catalog.jsonb_build_object('ok',false,'reason','background_not_found'); end if;
  insert into public.chess_wallets(user_id,points) values(p_user_id,0) on conflict(user_id) do nothing;
  select points into current_points from public.chess_wallets where user_id=p_user_id for update;
  if exists(select 1 from public.chess_background_purchases where user_id=p_user_id and background_id=p_background_id) then
    return pg_catalog.jsonb_build_object('ok',true,'already_owned',true,'points',current_points);
  end if;
  if current_points<background_cost then
    return pg_catalog.jsonb_build_object('ok',false,'reason','insufficient_points','points',current_points,'cost',background_cost);
  end if;
  update public.chess_wallets set points=points-background_cost,active_background=p_background_id,updated_at=pg_catalog.now()
    where user_id=p_user_id returning points into current_points;
  insert into public.chess_background_purchases(user_id,background_id) values(p_user_id,p_background_id);
  return pg_catalog.jsonb_build_object('ok',true,'already_owned',false,'points',current_points,'active_background',p_background_id);
end;
$$;
revoke all on function public.purchase_chess_background(uuid,text) from public, anon, authenticated;
grant execute on function public.purchase_chess_background(uuid,text) to service_role;

create or replace function public.activate_chess_background(p_user_id uuid,p_background_id text)
returns jsonb language plpgsql security definer set search_path = '' as $$
begin
  if p_user_id is null or p_background_id is null then raise exception 'missing wallet or background'; end if;
  if not exists(select 1 from public.chess_background_catalog where id=p_background_id)
     or not exists(select 1 from public.chess_background_purchases where user_id=p_user_id and background_id=p_background_id) then
    return pg_catalog.jsonb_build_object('ok',false,'reason','background_not_owned');
  end if;
  insert into public.chess_wallets(user_id,points,active_background) values(p_user_id,0,p_background_id)
    on conflict(user_id) do update set active_background=p_background_id,updated_at=pg_catalog.now();
  return pg_catalog.jsonb_build_object('ok',true,'active_background',p_background_id);
end;
$$;
revoke all on function public.activate_chess_background(uuid,text) from public, anon, authenticated;
grant execute on function public.activate_chess_background(uuid,text) to service_role;

do $$
begin
  if exists(select 1 from pg_catalog.pg_publication where pubname='supabase_realtime')
     and not exists(select 1 from pg_catalog.pg_publication_tables where pubname='supabase_realtime' and schemaname='public' and tablename='chess_games') then
    execute 'alter publication supabase_realtime add table public.chess_games';
  end if;
end;
$$;

-- Keep pending chess invitations aligned with the underlying friendship.
-- These definitions mirror 20261031151058_studyflow_chess_invite_lifecycle.sql.
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
    values (p_challenger_id, p_opponent_id, 'pending') returning * into game_row;
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
    where g.id = p_game_id returning * into game_row;
  return pg_catalog.jsonb_build_object('ok', true, 'game', pg_catalog.to_jsonb(game_row));
end;
$$;
revoke all on function public.respond_chess_invite(uuid, uuid, boolean) from public, anon, authenticated;
grant execute on function public.respond_chess_invite(uuid, uuid, boolean) to service_role;



-- IA1: diagnóstico adaptativo
-- IA1: diagnostic foundation. No external AI calls or paid services.
create schema if not exists studyflow_diagnostic;
revoke all on schema studyflow_diagnostic from public, anon;
grant usage on schema studyflow_diagnostic to authenticated;

create table public.diagnostic_questions (
 id text primary key,
 topic text not null check (topic in ('basics','product','chain')),
 difficulty smallint not null check (difficulty between 1 and 3),
 prompt text not null,
 options jsonb not null check (jsonb_array_length(options) = 4),
 prerequisite text
);
create table public.diagnostic_solutions (
 question_id text primary key references public.diagnostic_questions(id),
 correct_option text not null check(correct_option in ('a','b','c','d')),
 solution text not null,
 hints jsonb not null,
 error_hint text not null
);
create table public.diagnostic_sessions (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references auth.users(id) on delete cascade,
 topics text[] not null,
 duration_minutes integer not null check(duration_minutes in (10,15,20)),
 status text not null default 'active' check(status in ('active','completed')),
 current_question_id text references public.diagnostic_questions(id),
 hint_count integer not null default 0 check(hint_count between 0 and 2),
 reason text not null default 'Comenzamos con una pregunta intermedia.',
 created_at timestamptz not null default now(),
 deadline timestamptz not null,
 completed_at timestamptz,
 unique(id,user_id)
);
create unique index diagnostic_one_active_per_user on public.diagnostic_sessions(user_id) where status='active';
create index diagnostic_sessions_owner_date on public.diagnostic_sessions(user_id,created_at desc);
create table public.diagnostic_answers (
 id bigint generated always as identity primary key,
 session_id uuid not null,
 user_id uuid not null references auth.users(id) on delete cascade,
 question_id text not null references public.diagnostic_questions(id),
 selected_option text not null check(selected_option in ('a','b','c','d','skip')),
 explanation text not null default '' check(length(explanation)<=2000),
 correct boolean not null,
 hints_used integer not null check(hints_used between 0 and 2),
 answered_at timestamptz not null default now(),
 foreign key(session_id,user_id) references public.diagnostic_sessions(id,user_id) on delete cascade,
 unique(session_id,question_id)
);
create index diagnostic_answers_owner on public.diagnostic_answers(user_id);
create table public.topic_progress (
 user_id uuid not null references auth.users(id) on delete cascade,
 topic text not null check(topic in ('basics','product','chain')),
 session_id uuid not null,
 attempted integer not null,
 independent_correct integer not null,
 helped_correct integer not null,
 updated_at timestamptz not null default now(),
 primary key(user_id,topic),
 foreign key(session_id,user_id) references public.diagnostic_sessions(id,user_id) on delete cascade
);
alter table public.diagnostic_questions enable row level security;
alter table public.diagnostic_solutions enable row level security;
alter table public.diagnostic_sessions enable row level security;
alter table public.diagnostic_answers enable row level security;
alter table public.topic_progress enable row level security;
revoke all on public.diagnostic_questions, public.diagnostic_solutions, public.diagnostic_sessions, public.diagnostic_answers, public.topic_progress from anon, authenticated;
grant select on public.diagnostic_sessions, public.diagnostic_answers, public.topic_progress to authenticated;
create policy diagnostic_sessions_owner on public.diagnostic_sessions for select to authenticated using ((select auth.uid())=user_id);
create policy diagnostic_answers_owner on public.diagnostic_answers for select to authenticated using ((select auth.uid())=user_id);
create policy diagnostic_progress_owner on public.topic_progress for select to authenticated using ((select auth.uid())=user_id);
-- No direct policies/grants for solutions, grading or question selection.
-- Only the guarded transaction below may change assessment state.

create function studyflow_diagnostic.pick_question(p_session uuid)
returns text language plpgsql set search_path='' as $$
declare
 s public.diagnostic_sessions;
 t text; qid text; last_level integer; desired integer; n integer; wins integer; losses integer;
 recent record; topic_count integer; basics_wins integer; result_reason text;
begin
 select * into strict s from public.diagnostic_sessions where id=p_session;
 -- Cover selected topics fairly, then revisit prerequisites after repeated errors.
 for t in
   select x.topic from unnest(s.topics) with ordinality as x(topic,ord)
   order by (select count(*) from public.diagnostic_answers a join public.diagnostic_questions q on q.id=a.question_id where a.session_id=s.id and q.topic=x.topic), x.ord
 loop
   desired:=2;
   select q.difficulty into last_level from public.diagnostic_answers a join public.diagnostic_questions q on q.id=a.question_id
   where a.session_id=s.id and q.topic=t order by a.id desc limit 1;
   if found then
     desired:=last_level;
     select count(*),count(*) filter(where z.correct and z.hints_used=0),count(*) filter(where not z.correct)
     into n,wins,losses from (
       select a.correct,a.hints_used,q.difficulty from public.diagnostic_answers a join public.diagnostic_questions q on q.id=a.question_id
       where a.session_id=s.id and q.topic=t order by a.id desc limit 2
     ) z where z.difficulty=last_level;
     if n=2 and wins=2 then desired:=least(3,last_level+1);
     elsif n=2 and losses=2 then desired:=greatest(1,last_level-1);
     end if;
   end if;
   select q.id into qid from public.diagnostic_questions q
   where q.topic=t and not exists(select 1 from public.diagnostic_answers a where a.session_id=s.id and a.question_id=q.id)
   order by abs(q.difficulty-desired),q.id limit 1;
   if qid is not null then
     result_reason:=case when desired>coalesce(last_level,2) then 'Dos aciertos sin pistas: aumentamos la dificultad.'
       when desired<coalesce(last_level,2) then 'Dos errores relacionados: repasamos un nivel anterior.'
       else 'Comprobamos otro ejercicio y equilibramos los temas elegidos.' end;
     exit;
   end if;
 end loop;
 -- A prerequisite may be included even if not selected; label it explicitly.
 select q.topic into t from public.diagnostic_answers a join public.diagnostic_questions q on q.id=a.question_id
 where a.session_id=s.id order by a.id desc limit 1;
 if t in ('product','chain') then
   select count(*) into losses from (
     select a.correct from public.diagnostic_answers a join public.diagnostic_questions q on q.id=a.question_id
     where a.session_id=s.id and q.topic=t order by a.id desc limit 2
   ) z where not z.correct;
   select count(*) into basics_wins from public.diagnostic_answers a join public.diagnostic_questions q on q.id=a.question_id
   where a.session_id=s.id and q.topic='basics' and a.correct and a.hints_used=0;
   if losses=2 and basics_wins<2 then
     select q.id into t from public.diagnostic_questions q where q.topic='basics' and q.difficulty=1
     and not exists(select 1 from public.diagnostic_answers a where a.session_id=s.id and a.question_id=q.id)
     order by q.id limit 1;
     if t is not null then qid:=t; result_reason:='Revisamos reglas básicas como requisito previo tras dos errores.'; end if;
   end if;
 end if;
 update public.diagnostic_sessions set current_question_id=qid,hint_count=0,reason=coalesce(result_reason,'No quedan preguntas disponibles.') where id=s.id;
 return qid;
end $$;

create function studyflow_diagnostic.session_payload(p_session uuid)
returns jsonb language plpgsql set search_path='' as $$
declare s public.diagnostic_sessions; question_row public.diagnostic_questions; sol public.diagnostic_solutions;
 answer_row public.diagnostic_answers; question jsonb; feedback jsonb; report jsonb;
begin
 select * into strict s from public.diagnostic_sessions where id=p_session;
 select * into question_row from public.diagnostic_questions where id=s.current_question_id;
 select * into sol from public.diagnostic_solutions where question_id=question_row.id;
 select * into answer_row from public.diagnostic_answers where session_id=s.id and question_id=question_row.id;
 if question_row.id is not null and s.status='active' then
   question:=jsonb_build_object('id',question_row.id,'topic',question_row.topic,'difficulty',question_row.difficulty,'prompt',question_row.prompt,'options',question_row.options,
    'hints',(select coalesce(jsonb_agg(h.value order by h.ord),'[]'::jsonb) from jsonb_array_elements(sol.hints) with ordinality h(value,ord) where h.ord<=s.hint_count));
   if answer_row.id is not null then
     feedback:=jsonb_build_object('correct',answer_row.correct,'selected_option',answer_row.selected_option,'explanation',answer_row.explanation,
     'hints_used',answer_row.hints_used,'solution',sol.solution,'correct_option',sol.correct_option,
     'message',case when answer_row.correct then 'Respuesta correcta.' when answer_row.selected_option='skip' then 'Repasa la solución y prueba otro ejercicio.' else sol.error_hint end);
   end if;
 end if;
 select coalesce(jsonb_agg(r order by r.topic),'[]'::jsonb) into report from (
   select t.topic,count(a.id)::integer attempted,
    (count(a.id) filter(where a.correct and a.hints_used=0))::integer independent_correct,
    (count(a.id) filter(where a.correct and a.hints_used>0))::integer helped_correct,
    (count(a.id) filter(where not a.correct))::integer errors,
    coalesce(max(q.difficulty) filter(where a.correct and a.hints_used=0),0) highest_level
   from (select unnest(s.topics) topic union select q.topic from public.diagnostic_answers a join public.diagnostic_questions q on q.id=a.question_id where a.session_id=s.id) t
   left join public.diagnostic_questions q on q.topic=t.topic
   left join public.diagnostic_answers a on a.question_id=q.id and a.session_id=s.id group by t.topic
 ) r;
 return jsonb_build_object('id',s.id,'status',s.status,'topics',s.topics,'deadline',s.deadline,'created_at',s.created_at,
 'reason',s.reason,'max_questions',10,'answered',(select count(*) from public.diagnostic_answers where session_id=s.id),
 'question',question,'feedback',feedback,'report',report);
end $$;

create function studyflow_diagnostic.action(p_action text,p_session_id uuid,p_payload jsonb)
returns jsonb language plpgsql security definer set search_path='' as $$
declare uid uuid:=auth.uid(); s public.diagnostic_sessions; a public.diagnostic_answers;
 sol public.diagnostic_solutions; topics text[]; minutes integer; qid text; total integer; result jsonb; r jsonb;
begin
 if uid is null then raise exception 'Inicia sesión para usar el diagnóstico.' using errcode='42501'; end if;
 if p_action not in ('load','start','answer','hint','next','finish','history') then raise exception 'Acción inválida.'; end if;
 -- Serialize across tabs, including start, so retries never create duplicate sessions.
 perform pg_advisory_xact_lock(hashtextextended(uid::text,0));
 if p_action='history' then
   return (select coalesce(jsonb_agg(x),'[]'::jsonb) from (
    select id,created_at,status from public.diagnostic_sessions where user_id=uid order by created_at desc limit 8
   ) x);
 end if;
 if p_session_id is null then
   select * into s from public.diagnostic_sessions where user_id=uid and status='active' for update;
 else
   select * into s from public.diagnostic_sessions where user_id=uid and id=p_session_id for update;
   if not found then raise exception 'La sesión no existe o no pertenece a esta cuenta.' using errcode='42501'; end if;
 end if;
 if s.id is not null and s.status='active' and now()>=s.deadline then
   update public.diagnostic_sessions set status='completed',completed_at=now(),reason='Se terminó el tiempo de la sesión.' where id=s.id returning * into s;
 end if;
 if p_action='start' and (s.id is null or s.status='completed') then
   select array_agg(distinct value) into topics from jsonb_array_elements_text(p_payload->'topics');
   if topics is null or cardinality(topics)<1 or cardinality(topics)>3 or not topics <@ array['basics','product','chain']::text[] then raise exception 'Selecciona al menos un tema válido.'; end if;
   minutes:=coalesce((p_payload->>'minutes')::integer,15);
   if minutes not in (10,15,20) then raise exception 'Duración inválida.'; end if;
   insert into public.diagnostic_sessions(user_id,topics,duration_minutes,deadline)
   values(uid,topics,minutes,now()+make_interval(mins=>minutes)) returning * into s;
   perform studyflow_diagnostic.pick_question(s.id);
 elsif s.id is null then return null;
 elsif s.status='active' and p_action in ('answer','hint','next') then
   -- A stale tab cannot submit to, hint at, or advance a different question.
   if coalesce(p_payload->>'question_id','')<>s.current_question_id then
     return studyflow_diagnostic.session_payload(s.id);
   end if;
   select * into a from public.diagnostic_answers where session_id=s.id and question_id=s.current_question_id;
   select * into strict sol from public.diagnostic_solutions where question_id=s.current_question_id;
   if p_action='hint' and a.id is null then
     update public.diagnostic_sessions set hint_count=least(2,hint_count+1) where id=s.id;
   elsif p_action='answer' and a.id is null then
     if coalesce(p_payload->>'option','') not in ('a','b','c','d','skip') then raise exception 'Selecciona una respuesta.'; end if;
     if length(coalesce(p_payload->>'explanation',''))>2000 then raise exception 'La explicación supera 2000 caracteres.'; end if;
     insert into public.diagnostic_answers(session_id,user_id,question_id,selected_option,explanation,correct,hints_used)
     values(s.id,uid,s.current_question_id,p_payload->>'option',coalesce(p_payload->>'explanation',''),
      p_payload->>'option'=sol.correct_option,s.hint_count);
   elsif p_action='next' and a.id is not null then
     select count(*) into total from public.diagnostic_answers where session_id=s.id;
     if total>=10 then
       update public.diagnostic_sessions set status='completed',completed_at=now(),reason='Completaste las 10 preguntas.' where id=s.id;
     else
       qid:=studyflow_diagnostic.pick_question(s.id);
       if qid is null then update public.diagnostic_sessions set status='completed',completed_at=now() where id=s.id; end if;
     end if;
   end if;
 elsif s.status='active' and p_action='finish' then
   update public.diagnostic_sessions set status='completed',completed_at=now(),reason='Finalizaste la sesión antes del límite.' where id=s.id;
 end if;
 result:=studyflow_diagnostic.session_payload(s.id);
 if result->>'status'='completed' then
   for r in select value from jsonb_array_elements(result->'report') loop
     insert into public.topic_progress(user_id,topic,session_id,attempted,independent_correct,helped_correct)
     values(uid,r->>'topic',s.id,(r->>'attempted')::integer,(r->>'independent_correct')::integer,(r->>'helped_correct')::integer)
     on conflict(user_id,topic) do update set session_id=excluded.session_id,attempted=excluded.attempted,
      independent_correct=excluded.independent_correct,helped_correct=excluded.helped_correct,updated_at=now()
     where (select created_at from public.diagnostic_sessions where id=public.topic_progress.session_id)<=s.created_at;
   end loop;
 end if;
 return result;
end $$;
revoke all on all functions in schema studyflow_diagnostic from public,anon,authenticated;
grant execute on function studyflow_diagnostic.action(text,uuid,jsonb) to authenticated;
create function public.diagnostic_action(p_action text,p_session_id uuid default null,p_payload jsonb default '{}'::jsonb)
returns jsonb language sql security invoker set search_path='' as $$
 select studyflow_diagnostic.action(p_action,p_session_id,p_payload);
$$;
revoke all on function public.diagnostic_action(text,uuid,jsonb) from public,anon;
grant execute on function public.diagnostic_action(text,uuid,jsonb) to authenticated;

insert into public.diagnostic_questions values('b11','basics',1,'Deriva f(x) = x⁴.','[{"id":"a","text":"4x³"},{"id":"b","text":"x³"},{"id":"c","text":"4x⁴"},{"id":"d","text":"0"}]',null);
insert into public.diagnostic_solutions values('b11','a','Aplica (xⁿ)'' = nxⁿ⁻¹: baja el 4 y resta uno al exponente.','["Identifica el exponente.","Multiplica por el exponente y réstale uno."]','Revisa el coeficiente y el exponente.');
insert into public.diagnostic_questions values('b12','basics',1,'Deriva f(x) = 5x³.','[{"id":"a","text":"5x²"},{"id":"b","text":"15x³"},{"id":"c","text":"3x²"},{"id":"d","text":"15x²"}]',null);
insert into public.diagnostic_solutions values('b12','d','Conserva el 5 y deriva x³: 5·3x² = 15x².','["La constante 5 se conserva.","Deriva x³ y multiplica por 5."]','Revisa el factor constante.');
insert into public.diagnostic_questions values('b13','basics',1,'Deriva f(x) = 7.','[{"id":"a","text":"0"},{"id":"b","text":"1"},{"id":"c","text":"7"},{"id":"d","text":"x"}]',null);
insert into public.diagnostic_solutions values('b13','a','Una constante no cambia con x; su derivada es 0.','["¿Cambia 7 cuando cambia x?","La pendiente de una función constante es cero."]','Repasa la derivada de una constante.');
insert into public.diagnostic_questions values('b21','basics',2,'Deriva f(x) = 3x⁴ − 2x² + 5.','[{"id":"a","text":"12x³ − 4x + 5"},{"id":"b","text":"12x³ − 4x"},{"id":"c","text":"12x⁴ − 4x²"},{"id":"d","text":"3x³ − 2x"}]',null);
insert into public.diagnostic_solutions values('b21','b','Deriva cada término: 12x³, −4x y 0. Resultado: 12x³ − 4x.','["Deriva término a término.","La derivada del término constante es cero."]','Revisa las potencias y el término constante.');
insert into public.diagnostic_questions values('b22','basics',2,'Deriva f(x) = 2/x + √x, con x > 0.','[{"id":"a","text":"−2/x² + 1/(2√x)"},{"id":"b","text":"2/x² + 1/(2√x)"},{"id":"c","text":"−2/x + √x"},{"id":"d","text":"−2/x² + 2√x"}]',null);
insert into public.diagnostic_solutions values('b22','a','Escribe 2x⁻¹ + x¹ᐟ². Su derivada es −2x⁻² + ½x⁻¹ᐟ².','["Reescribe usando exponentes.","Usa los exponentes −1 y 1/2."]','Revisa exponentes negativos y fraccionarios.');
insert into public.diagnostic_questions values('b23','basics',2,'Deriva f(x) = 4x⁵ − 3x + 8.','[{"id":"a","text":"20x⁴ − 3x"},{"id":"b","text":"4x⁴ − 3"},{"id":"c","text":"20x⁵ − 3"},{"id":"d","text":"20x⁴ − 3"}]',null);
insert into public.diagnostic_solutions values('b23','d','(4x⁵)'' = 20x⁴, (−3x)'' = −3 y 8'' = 0.','["Trata cada término por separado.","La derivada de ax es a."]','Revisa la derivada del término lineal.');
insert into public.diagnostic_questions values('b31','basics',3,'Deriva f(x) = 3/x² − 2√x, con x > 0.','[{"id":"a","text":"−6/x² − 1/√x"},{"id":"b","text":"−6/x³ − 2/√x"},{"id":"c","text":"−6/x³ − 1/√x"},{"id":"d","text":"6/x³ − 1/√x"}]',null);
insert into public.diagnostic_solutions values('b31','c','Deriva 3x⁻² − 2x¹ᐟ²: −6x⁻³ − x⁻¹ᐟ².','["Convierte ambos términos a potencias.","Multiplica cada coeficiente por su exponente."]','Revisa signos y exponentes fraccionarios.');
insert into public.diagnostic_questions values('b32','basics',3,'Deriva f(x) = (x³ + 2x)/x, con x ≠ 0.','[{"id":"a","text":"x²"},{"id":"b","text":"2x"},{"id":"c","text":"3x² + 2"},{"id":"d","text":"2x + 2"}]',null);
insert into public.diagnostic_solutions values('b32','b','Simplifica primero: f(x) = x² + 2. Luego f''(x) = 2x.','["Simplifica la división antes de derivar.","Divide cada término del numerador por x."]','Simplificar puede evitar una regla innecesaria.');
insert into public.diagnostic_questions values('b33','basics',3,'Deriva f(x) = x^(3/2) + x^(−2), con x > 0.','[{"id":"a","text":"(3/2)√x − 2/x³"},{"id":"b","text":"(3/2)√x + 2/x³"},{"id":"c","text":"(3/2)x − 2/x²"},{"id":"d","text":"√x − 2/x³"}]',null);
insert into public.diagnostic_solutions values('b33','a','Resta uno a cada exponente: 3/2 − 1 = 1/2 y −2 − 1 = −3.','["Usa la regla de la potencia en ambos términos.","Un exponente negativo mantiene su signo al multiplicar."]','Revisa la resta de exponentes.');
insert into public.diagnostic_questions values('p11','product',1,'Deriva f(x) = x(x + 1).','[{"id":"a","text":"x + 1"},{"id":"b","text":"2x"},{"id":"c","text":"1"},{"id":"d","text":"2x + 1"}]','basics');
insert into public.diagnostic_solutions values('p11','d','Usa u''v + uv'': (x + 1) + x = 2x + 1.','["Hay dos factores que dependen de x.","Suma la derivada del primero por el segundo y viceversa."]','No multipliques solamente las derivadas.');
insert into public.diagnostic_questions values('p12','product',1,'Deriva f(x) = x²(x + 2).','[{"id":"a","text":"2x² + 4x"},{"id":"b","text":"3x² + 2"},{"id":"c","text":"3x² + 4x"},{"id":"d","text":"2x"}]','basics');
insert into public.diagnostic_solutions values('p12','c','2x(x + 2) + x² = 3x² + 4x.','["Identifica u = x² y v = x + 2.","Incluye los dos sumandos de la regla."]','Comprueba que incluiste los dos sumandos.');
insert into public.diagnostic_questions values('p13','product',1,'Deriva f(x) = (x + 1)(x + 3).','[{"id":"a","text":"2x + 3"},{"id":"b","text":"2x + 4"},{"id":"c","text":"1"},{"id":"d","text":"x + 4"}]','basics');
insert into public.diagnostic_solutions values('p13','b','(x + 3) + (x + 1) = 2x + 4.','["Cada factor tiene derivada 1.","Suma los factores originales."]','La derivada de un producto no es el producto de derivadas.');
insert into public.diagnostic_questions values('p21','product',2,'Deriva f(x) = (x² + 1)(x³ − 2).','[{"id":"a","text":"2x(x³ − 2) + 3x²(x² + 1)"},{"id":"b","text":"6x³"},{"id":"c","text":"2x(x³ − 2)"},{"id":"d","text":"3x²(x² + 1)"}]','basics');
insert into public.diagnostic_solutions values('p21','a','u'' = 2x y v'' = 3x². Combina u''v + uv''.','["Nombra los factores u y v.","Deriva cada factor y conserva el otro en cada sumando."]','Comprueba u''v + uv''.');
insert into public.diagnostic_questions values('p22','product',2,'Deriva f(x) = x² sen(x).','[{"id":"a","text":"2x cos(x)"},{"id":"b","text":"x² cos(x)"},{"id":"c","text":"2x sen(x) − x² cos(x)"},{"id":"d","text":"2x sen(x) + x² cos(x)"}]','basics');
insert into public.diagnostic_solutions values('p22','d','Deriva x² y sen(x) por separado: 2x sen(x) + x² cos(x).','["La derivada de sen(x) es cos(x).","Conserva el factor que no estás derivando."]','Revisa la regla del producto y la derivada de seno.');
insert into public.diagnostic_questions values('p23','product',2,'Deriva f(x) = x eˣ.','[{"id":"a","text":"x eˣ"},{"id":"b","text":"2x eˣ"},{"id":"c","text":"eˣ(1 + x)"},{"id":"d","text":"eˣ"}]','basics');
insert into public.diagnostic_solutions values('p23','c','1·eˣ + x·eˣ = eˣ(1 + x).','["La derivada de eˣ es eˣ.","Debes obtener dos sumandos."]','Revisa el sumando que aporta la derivada de x.');
insert into public.diagnostic_questions values('p31','product',3,'Deriva f(x) = (x² + 1)²(x − 1).','[{"id":"a","text":"4x(x² + 1)(x − 1)"},{"id":"b","text":"4x(x² + 1)(x − 1) + (x² + 1)²"},{"id":"c","text":"2(x² + 1)(x − 1) + (x² + 1)²"},{"id":"d","text":"4x(x² + 1)"}]','basics');
insert into public.diagnostic_solutions values('p31','b','Combina producto y cadena: u'' = 4x(x² + 1), v'' = 1.','["El primer factor necesita la regla de la cadena.","Después aplica u''v + uv''."]','Revisa la cadena dentro de la regla del producto.');
insert into public.diagnostic_questions values('p32','product',3,'Deriva f(x) = x² e^(2x).','[{"id":"a","text":"e^(2x)(2x + 2x²)"},{"id":"b","text":"e^(2x)(2x + x²)"},{"id":"c","text":"4x e^(2x)"},{"id":"d","text":"2x² e^(2x)"}]','basics');
insert into public.diagnostic_solutions values('p32','a','La derivada de e^(2x) es 2e^(2x). Aplica producto y factoriza.','["La derivada interna de 2x es 2.","Suma 2x e^(2x) y 2x² e^(2x)."]','Revisa el factor interno de la exponencial.');
insert into public.diagnostic_questions values('p33','product',3,'Deriva f(x) = (x + 1) sen(3x).','[{"id":"a","text":"sen(3x) + (x + 1) cos(3x)"},{"id":"b","text":"3 cos(3x)"},{"id":"c","text":"3(x + 1) cos(3x)"},{"id":"d","text":"sen(3x) + 3(x + 1) cos(3x)"}]','basics');
insert into public.diagnostic_solutions values('p33','d','(x + 1)'' = 1 y (sen(3x))'' = 3cos(3x). Aplica producto.','["Combina producto y cadena.","La derivada de sen(3x) incluye el factor 3."]','Revisa ambos sumandos y el factor 3.');
insert into public.diagnostic_questions values('c11','chain',1,'Deriva f(x) = (2x + 1)².','[{"id":"a","text":"(2x + 1)²"},{"id":"b","text":"4"},{"id":"c","text":"4(2x + 1)"},{"id":"d","text":"2(2x + 1)"}]','basics');
insert into public.diagnostic_solutions values('c11','c','La derivada exterior es 2(2x + 1). Multiplícala por la interna, 2.','["Hay una función dentro de una potencia.","No olvides derivar 2x + 1."]','Revisa la derivada interna.');
insert into public.diagnostic_questions values('c12','chain',1,'Deriva f(x) = (x + 3)³.','[{"id":"a","text":"3(x + 3)³"},{"id":"b","text":"3(x + 3)²"},{"id":"c","text":"(x + 3)²"},{"id":"d","text":"3x²"}]','basics');
insert into public.diagnostic_solutions values('c12','b','Deriva la potencia y multiplica por (x + 3)'' = 1.','["Conserva toda la expresión interna.","Resta uno al exponente exterior."]','Conserva la expresión interna completa.');
insert into public.diagnostic_questions values('c13','chain',1,'Deriva f(x) = sen(2x).','[{"id":"a","text":"2 cos(2x)"},{"id":"b","text":"cos(2x)"},{"id":"c","text":"−2 cos(2x)"},{"id":"d","text":"2 sen(2x)"}]','basics');
insert into public.diagnostic_solutions values('c13','a','Deriva seno a coseno y multiplica por (2x)'' = 2.','["La función exterior es seno.","Multiplica por la derivada de 2x."]','Revisa el factor interno y la derivada trigonométrica.');
insert into public.diagnostic_questions values('c21','chain',2,'Deriva f(x) = (3x² + 1)⁴.','[{"id":"a","text":"4(3x² + 1)³"},{"id":"b","text":"24x(3x² + 1)⁴"},{"id":"c","text":"12x(3x² + 1)³"},{"id":"d","text":"24x(3x² + 1)³"}]','basics');
insert into public.diagnostic_solutions values('c21','d','4(3x² + 1)³ · 6x = 24x(3x² + 1)³.','["Primero deriva la potencia exterior.","La derivada de 3x² + 1 es 6x."]','Puede faltar el factor 6x o el ajuste del exponente.');
insert into public.diagnostic_questions values('c22','chain',2,'Deriva f(x) = cos(x²).','[{"id":"a","text":"2x sen(x²)"},{"id":"b","text":"−2x cos(x²)"},{"id":"c","text":"−2x sen(x²)"},{"id":"d","text":"−sen(x²)"}]','basics');
insert into public.diagnostic_solutions values('c22','c','La derivada exterior es −sen(x²); la interna es 2x.','["La derivada de coseno lleva signo negativo.","Deriva también x²."]','Revisa el signo del coseno y el factor 2x.');
insert into public.diagnostic_questions values('c23','chain',2,'Deriva f(x) = e^(x² + 2x).','[{"id":"a","text":"(2x + 2)eˣ"},{"id":"b","text":"(2x + 2)e^(x² + 2x)"},{"id":"c","text":"e^(x² + 2x)"},{"id":"d","text":"2x e^(x² + 2x)"}]','basics');
insert into public.diagnostic_solutions values('c23','b','Conserva la exponencial y multiplícala por (x² + 2x)'' = 2x + 2.','["e^u se deriva como e^u · u''.","Deriva todos los términos del exponente."]','Revisa la derivada completa del exponente.');
insert into public.diagnostic_questions values('c31','chain',3,'Deriva f(x) = sen((x² + 1)³).','[{"id":"a","text":"6x(x² + 1)² cos((x² + 1)³)"},{"id":"b","text":"3(x² + 1)² cos((x² + 1)³)"},{"id":"c","text":"6x cos((x² + 1)³)"},{"id":"d","text":"6x(x² + 1)² sen((x² + 1)³)"}]','basics');
insert into public.diagnostic_solutions values('c31','a','Deriva de fuera hacia dentro: cos((x² + 1)³) · 3(x² + 1)² · 2x.','["Identifica tres capas: seno, cubo y x² + 1.","Multiplica las derivadas de las tres capas."]','Revisa cada capa de la composición.');
insert into public.diagnostic_questions values('c32','chain',3,'Deriva f(x) = (1 + e^(2x))³.','[{"id":"a","text":"3(1 + e^(2x))²"},{"id":"b","text":"3e^(2x)(1 + e^(2x))²"},{"id":"c","text":"6e^(2x)(1 + e^(2x))³"},{"id":"d","text":"6e^(2x)(1 + e^(2x))²"}]','basics');
insert into public.diagnostic_solutions values('c32','d','3(1 + e^(2x))² · 2e^(2x) = 6e^(2x)(1 + e^(2x))².','["Deriva la potencia y después la exponencial.","El exponente 2x también debe derivarse."]','Revisa los factores 3 y 2.');
insert into public.diagnostic_questions values('c33','chain',3,'Deriva f(x) = √(1 + x⁴).','[{"id":"a","text":"4x³/√(1 + x⁴)"},{"id":"b","text":"2x³√(1 + x⁴)"},{"id":"c","text":"2x³/√(1 + x⁴)"},{"id":"d","text":"1/(2√(1 + x⁴))"}]','basics');
insert into public.diagnostic_solutions values('c33','c','Escribe (1 + x⁴)¹ᐟ². Deriva: ½(1 + x⁴)⁻¹ᐟ² · 4x³.','["Reescribe la raíz como potencia 1/2.","Multiplica por la derivada de 1 + x⁴."]','Revisa la potencia exterior y el factor 4x³.');

-- Cover diagnostic foreign keys and make direct-read denial explicit.
create index diagnostic_answers_question on public.diagnostic_answers(question_id);
create index diagnostic_answers_session_owner on public.diagnostic_answers(session_id,user_id);
create index diagnostic_sessions_question on public.diagnostic_sessions(current_question_id);
create index topic_progress_session_owner on public.topic_progress(session_id,user_id);
create policy diagnostic_questions_no_direct_read on public.diagnostic_questions for select to authenticated using (false);
create policy diagnostic_solutions_no_direct_read on public.diagnostic_solutions for select to authenticated using (false);
