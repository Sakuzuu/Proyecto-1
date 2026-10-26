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
