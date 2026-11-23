import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { createRequire } from "node:module";
const require=createRequire(import.meta.url), D=require("../diagnostic.js");
const bank=JSON.parse(fs.readFileSync(new URL("../supabase/seed/diagnostic-questions.json",import.meta.url)));
test("27 preguntas: cobertura y respuestas matemáticas independientes",()=>{
 assert.equal(bank.length,27);
 assert.equal(new Set(bank.map(q=>q.id)).size,27);
 for(const topic of Object.keys(D.TOPICS)) for(const level of [1,2,3]) assert.equal(bank.filter(q=>q.topic===topic&&q.difficulty===level).length,3);
 for(const q of bank) {
  const f=new Function("x","return "+q.source), correct=new Function("x","return "+q.formulas[q.correct_option.charCodeAt(0)-97]);
  for(const x of [.25,.6,1.1]) { const h=1e-6, expected=(f(x+h)-f(x-h))/(2*h); assert.ok(Math.abs(expected-correct(x))<1e-4*Math.max(1,Math.abs(expected)),q.id); }
  q.formulas.forEach((formula,index)=>{ if(index===q.correct_option.charCodeAt(0)-97)return; const wrong=new Function("x","return "+formula); assert.ok([.25,.6,1.1].some(x=>Math.abs(wrong(x)-correct(x))>1e-7),q.id+" opción equivalente"); });
 }
});
test("informe reconoce evidencia insuficiente y distingue apoyo",()=>{
 assert.match(D.summarize({attempted:2,independent_correct:2}).label,/insuficiente/);
 assert.match(D.summarize({attempted:3,independent_correct:3,highest_level:2}).label,/Buen desempeño/);
 assert.match(D.summarize({attempted:3,helped_correct:3}).label,/desarrollo/);
 assert.match(D.summarize({attempted:3,errors:2}).label,/refuerzo/);
});
test("escapa explicaciones y mensajes de servidor",()=>{
 assert.equal(D.escapeHtml('<img src=x onerror="bad()">'),"&lt;img src=x onerror=&quot;bad()&quot;&gt;");
 assert.match(D.errorMessage({message:"Could not find diagnostic_action in the schema cache"}),/todavía no está habilitado/);
 const html=D.renderReport({report:[{topic:"<script>",attempted:0,independent_correct:0,helped_correct:0,errors:0}],reason:"<img>",answered:0});
 assert.ok(!html.includes("<script>")); assert.ok(!html.includes("<img>"));
});
test("el servicio transmite solamente la acción y los datos del alumno",async()=>{
 const calls=[]; const s=D.createService({async rpc(...args){calls.push(args);return {data:{id:"s"},error:null};}});
 await s.act("answer","s",{question_id:"q",option:"b"});
 assert.deepEqual(calls[0],["diagnostic_action",{p_action:"answer",p_session_id:"s",p_payload:{question_id:"q",option:"b"}}]);
 await assert.rejects(D.createService({rpc:async()=>({error:new Error("offline")})}).act("load"),/offline/);
});
test("interfaz: configuración, envío, pista, recarga y cierre de sesión",async()=>{
 const {JSDOM}=require("jsdom");
 const dom=new JSDOM('<section id="diagnosticSection" hidden><p id="diagnosticStatus"></p><div id="diagnosticView"></div></section>',{url:"https://studyflow.test"});
 const doc=dom.window.document, calls=[];
 let response=null;
 const service={async act(action,id,payload){calls.push({action,id,payload});return action==="history"?[]:response;}};
 const controller=D.mount({document:doc,userId:"u1",service,storage:dom.window.sessionStorage});
 try {
  await controller.ready;
  doc.querySelectorAll('[name="topic"]').forEach(input=>input.checked=false);
  doc.getElementById("diagnosticSetupForm").dispatchEvent(new dom.window.Event("submit",{bubbles:true,cancelable:true}));
  assert.match(doc.getElementById("diagnosticStatus").textContent,/Selecciona/);
  response={id:"s1",status:"active",answered:0,deadline:new Date(Date.now()+600000).toISOString(),reason:"Inicio",question:{...bank[0],hints:[]},feedback:null};
  doc.querySelector('[name="topic"]').checked=true;
  doc.getElementById("diagnosticSetupForm").dispatchEvent(new dom.window.Event("submit",{bubbles:true,cancelable:true}));
  await new Promise(resolve=>setImmediate(resolve));
  assert.ok(doc.getElementById("diagnosticAnswerForm"));
  assert.equal(doc.querySelectorAll(".diagnostic-option").length,4);
  assert.ok(!doc.getElementById("diagnosticView").textContent.includes(bank[0].solution));
  const textarea=doc.getElementById("diagnosticExplanation");
  textarea.value="<script>mi procedimiento</script>"; textarea.dispatchEvent(new dom.window.Event("input",{bubbles:true}));
  doc.querySelector('input[value="a"]').checked=true;
  response={...response,question:{...response.question,hints:["Una pista"]}};
  doc.querySelector('[data-diag="hint"]').click();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(doc.querySelector("textarea").value,"<script>mi procedimiento</script>");
  assert.equal(doc.querySelectorAll(".diagnostic-hints li").length,1);
  response={...response,answered:1,feedback:{correct:true,selected_option:"a",correct_option:"a",explanation:"<img>",hints_used:1,solution:"Solución verificada",message:"Correcto"}};
  doc.getElementById("diagnosticAnswerForm").dispatchEvent(new dom.window.Event("submit",{bubbles:true,cancelable:true}));
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls.at(-1).action,"answer");
  assert.equal(doc.querySelector("#diagnosticAnswerForm fieldset").disabled,true);
  assert.ok(!doc.querySelector("img"));
  controller.destroy();
  assert.equal(doc.getElementById("diagnosticSection").hidden,true);
  assert.equal(doc.getElementById("diagnosticView").innerHTML,"");
 } finally {controller.destroy();dom.window.close();}
});
