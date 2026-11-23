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
