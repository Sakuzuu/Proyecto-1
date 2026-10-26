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
