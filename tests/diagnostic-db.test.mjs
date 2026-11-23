import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import {execFileSync} from "node:child_process";
const url=process.env.DIAGNOSTIC_TEST_DATABASE_URL;
const uid="00000000-0000-4000-8000-000000000001",other="00000000-0000-4000-8000-000000000002";
const literal=v=>"'"+String(v).replaceAll("'","''")+"'";
function sql(query){return execFileSync("psql",["-X","-qAt","-v","ON_ERROR_STOP=1",url],{input:query,encoding:"utf8",stdio:["pipe","pipe","pipe"]}).trim();}
function rpc(action,id=null,payload={},user=uid){
 const result=sql("begin; set local request.jwt.claim.sub="+literal(user)+"; set local role authenticated; select public.diagnostic_action("+literal(action)+","+(id?literal(id)+"::uuid":"null")+","+literal(JSON.stringify(payload))+"::jsonb); commit;");
 return result?JSON.parse(result):null;
}
test("Postgres: aislamiento, corrección, adaptación y persistencia",{skip:!url},async t=>{
 sql("create role anon; create role authenticated; create schema auth; create table auth.users(id uuid primary key); create function auth.uid() returns uuid language sql stable as $$ select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $$; grant usage on schema auth to authenticated; grant execute on function auth.uid() to authenticated; insert into auth.users values("+literal(uid)+"),("+literal(other)+");");
 sql(fs.readFileSync(new URL("../supabase/ia1.sql",import.meta.url),"utf8"));
 const bank=JSON.parse(fs.readFileSync(new URL("../supabase/seed/diagnostic-questions.json",import.meta.url)));
 await t.test("soluciones y escrituras bloqueadas al cliente",()=>{
  assert.throws(()=>sql("set role authenticated; select * from public.diagnostic_solutions;"));
  assert.throws(()=>sql("set role anon; select public.diagnostic_action('load');"));
  assert.throws(()=>sql("set role authenticated; select public.diagnostic_action('load');"));
  assert.throws(()=>sql("set role authenticated; insert into public.diagnostic_sessions(user_id,topics,duration_minutes,deadline) values("+literal(uid)+",array['basics'],15,now());"));
 });
 let s;
 await t.test("inicio idempotente y respuestas ocultas",()=>{
  s=rpc("start",null,{topics:["chain"],minutes:15});
  assert.equal(s.question.difficulty,2); assert.ok(!JSON.stringify(s).includes("correct_option"));
  assert.equal(rpc("start",null,{topics:["chain"],minutes:15}).id,s.id);
  assert.equal(rpc("load").id,s.id);
  assert.throws(()=>rpc("load",s.id,{},other));
  assert.equal(sql("begin; set local request.jwt.claim.sub="+literal(other)+"; set local role authenticated; select count(*) from public.diagnostic_sessions; commit;"),"0");
 });
 await t.test("pistas sobreviven recarga y no cuentan como dominio independiente",()=>{
  s=rpc("hint",s.id,{question_id:s.question.id});
  assert.equal(s.question.hints.length,1);assert.equal(rpc("load",s.id).question.hints.length,1);
  const q=bank.find(q=>q.id===s.question.id);
  s=rpc("answer",s.id,{question_id:q.id,option:q.correct_option,explanation:"Procedimiento"});
  assert.equal(s.feedback.correct,true);assert.equal(s.feedback.hints_used,1);
  const duplicate=rpc("answer",s.id,{question_id:q.id,option:"skip"});
  assert.equal(duplicate.answered,1);assert.equal(duplicate.feedback.correct,true);
  s=rpc("next",s.id,{question_id:q.id});
  assert.equal(s.question.difficulty,2);
 });
 await t.test("dos errores conducen a un requisito previo",()=>{
  for(let i=0;i<2;i++){
   const q=s.question;
   s=rpc("answer",s.id,{question_id:q.id,option:"skip"});
   s=rpc("next",s.id,{question_id:q.id});
  }
  assert.equal(s.question.topic,"basics");assert.match(s.reason,/requisito previo/);
 });
 await t.test("una pestaña antigua no altera la pregunta nueva",()=>{
  const before=s.question.id;
  s=rpc("hint",s.id,{question_id:"stale"});
  assert.equal(s.question.id,before);assert.equal(s.question.hints.length,0);
 });
 await t.test("finalizar guarda progreso y permite revisar el historial",()=>{
  const id=s.id;
  s=rpc("finish",id);assert.equal(s.status,"completed");
  assert.equal(rpc("load",id).answered,s.answered);
  assert.equal(rpc("history")[0].id,id);
  assert.ok(Number(sql("select count(*) from public.topic_progress;"))>0);
  assert.equal(rpc("load",null,{},other),null);
 });
 await t.test("dos aciertos sin pistas suben nivel y termina en diez",()=>{
  s=rpc("start",null,{topics:["basics"],minutes:15});
  for(let i=0;i<10;i++){
   const q=bank.find(q=>q.id===s.question.id);
   s=rpc("answer",s.id,{question_id:q.id,option:q.correct_option});
   s=rpc("next",s.id,{question_id:q.id});
   if(i===1) assert.equal(s.question.difficulty,3);
   if(s.status==="completed")break;
  }
  // A single topic has only nine questions: stop cleanly when the bank is exhausted.
  assert.equal(s.status,"completed");assert.equal(s.answered,9);
 });
 await t.test("límite de diez con todos los temas y sin repeticiones",()=>{
  s=rpc("start",null,{topics:["basics","product","chain"],minutes:15});
  const seen=new Set();
  for(let i=0;i<10;i++){
   assert.ok(!seen.has(s.question.id));seen.add(s.question.id);
   const q=bank.find(q=>q.id===s.question.id);
   s=rpc("answer",s.id,{question_id:q.id,option:q.correct_option});
   s=rpc("next",s.id,{question_id:q.id});
  }
  assert.equal(s.status,"completed");assert.equal(s.answered,10);
 });
 await t.test("la fecha límite se aplica en el servidor",()=>{
  s=rpc("start",null,{topics:["product"],minutes:10});
  sql("update public.diagnostic_sessions set deadline=now()-interval '1 second' where id="+literal(s.id));
  s=rpc("load",s.id);assert.equal(s.status,"completed");assert.match(s.reason,/tiempo/);
 });
});
