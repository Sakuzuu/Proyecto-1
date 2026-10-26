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
