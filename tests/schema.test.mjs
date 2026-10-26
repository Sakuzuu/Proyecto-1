import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = path.resolve(new URL("..", import.meta.url).pathname);
const read = file => fs.readFileSync(path.join(root, file), "utf8");

test("materias y notas se aislan por propietario con RLS", () => {
  const sql = read("supabase/schema.sql");
  assert.match(sql, /alter table public\.subjects enable row level security/i);
  assert.match(sql, /alter table public\.grades enable row level security/i);
  assert.match(sql, /auth\.uid\(\)\) = user_id/i);
  assert.match(sql, /foreign key \(subject_id, user_id\)/i);
  assert.match(sql, /grades_subject_owner_fkey/i);
  assert.match(sql, /grant select, insert, update, delete on public\.subjects to authenticated/i);
  assert.match(sql, /grant select, insert, update, delete on public\.grades to authenticated/i);
});
test("las notas individuales no se conceden a amigos; RPC devuelve promedios agregados", () => {
  const sql = read("supabase/schema.sql");
  assert.match(sql, /function public\.get_shared_academic_averages\(p_friend_id uuid\)/i);
  assert.match(sql, /from public\.friendships\s+(?:as\s+)?f/i);
  assert.match(sql, /p\.share_academic_averages is true/i);
  assert.match(sql, /group by s\.id, s\.name, g\.academic_year/i);
  assert.match(sql, /group by g\.academic_year/i);
  assert.match(sql, /revoke execute on function public\.get_shared_academic_averages\(uuid\) from public, anon, authenticated/i);
  assert.match(sql, /grant execute on function public\.get_shared_academic_averages\(uuid\) to authenticated/i);
});
test("las solicitudes de amistad no se pueden duplicar en estado pendiente", () => {
  const sql = read("supabase/schema.sql");
  assert.match(sql, /friend_requests_pending_pair_unique/i);
  assert.match(sql, /where status = 'pending'/i);
  assert.match(sql, /recipient_id <> \(select auth\.uid\(\)\)/i);
  assert.match(sql, /Recipients respond to pending friend requests/i);
  assert.match(sql, /on_friend_request_response/i);
});
test("las RPC de perfiles no entregan correo y protegen las operaciones", () => {
  const sql = read("supabase/schema.sql");
  assert.match(sql, /function public\.search_profiles_by_username\(p_query text\)/i);
  assert.match(sql, /function public\.list_my_friends\(\)/i);
  assert.match(sql, /function public\.list_my_friend_requests\(\)/i);
  assert.match(sql, /function public\.remove_friend\(p_friend_id uuid\)/i);
  assert.match(sql, /set search_path = ''/i);
  assert.doesNotMatch(sql, /grant execute on function public\.(?:search_profiles_by_username|list_my_friends|list_my_friend_requests|remove_friend)[^;]*to anon/i);
});
