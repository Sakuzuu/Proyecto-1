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
