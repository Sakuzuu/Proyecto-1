(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.StudyFlowDiagnostic = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const TOPICS = Object.freeze({ basics: "Reglas básicas", product: "Regla del producto", chain: "Regla de la cadena" });
  const LEVELS = ["", "Básica", "Intermedia", "Avanzada"];
  const escapeHtml = value => String(value == null ? "" : value).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  function summarize(row) {
    const attempted = Number(row.attempted || 0), wins = Number(row.independent_correct || 0);
    if (attempted < 3) return { label: "Evidencia insuficiente", recommendation: "Resuelve más preguntas de este tema para obtener un diagnóstico." };
    if (Number(row.errors) >= 2) return { label: "Necesita refuerzo", recommendation: "Repasa los procedimientos de esta sesión y practica sin pistas." };
    if (Number(row.helped_correct) > 0) return { label: "En desarrollo", recommendation: "Vuelve a resolver ejercicios de este tema sin apoyo." };
    if (wins >= 3 && Number(row.highest_level) >= 2) return { label: "Buen desempeño observado", recommendation: "Comprueba tu comprensión con ejercicios nuevos de mayor dificultad." };
    return { label: "En desarrollo", recommendation: "Practica en el siguiente nivel y vuelve a evaluarte." };
  }
  function createService(client) {
    return {
      async act(action, sessionId, payload) {
        const result = await client.rpc("diagnostic_action", { p_action: action, p_session_id: sessionId || null, p_payload: payload || {} });
        if (result.error) throw result.error;
        return result.data;
      }
    };
  }
  function errorMessage(error) {
    const text = String(error && error.message || "");
    if (/schema cache|does not exist|could not find|PGRST202/i.test(text)) return "El diagnóstico todavía no está habilitado en el servidor. Tus materias y notas siguen disponibles.";
    if (/sesión|cuenta|Selecciona|explicación|Duración/.test(text)) return text;
    return "No se pudo conectar con el diagnóstico. Revisa tu conexión y vuelve a intentarlo; tus respuestas enviadas se conservan.";
  }
  function renderReport(session) {
    const rows = (session.report || []).map(row => {
      const summary = summarize(row);
      return '<article class="diagnostic-result"><h4>' + escapeHtml(TOPICS[row.topic] || row.topic) + '</h4><span class="pill">' + escapeHtml(summary.label) + '</span><p>' +
        Number(row.independent_correct) + ' aciertos sin ayuda · ' + Number(row.helped_correct) + ' con pistas · ' + Number(row.errors) + ' errores o sin responder.</p><p class="muted">' + escapeHtml(summary.recommendation) + '</p></article>';
    }).join("");
    return '<h3 tabindex="-1" data-diagnostic-focus>Tu diagnóstico de esta sesión</h3><p class="muted">' + escapeHtml(session.reason) +
      ' Evaluamos ' + Number(session.answered) + ' de hasta 10 preguntas.</p><p>Este resultado orienta tu práctica. No es una nota oficial ni una medida definitiva de dominio.</p><div class="diagnostic-results">' +
      rows + '</div><button class="button" type="button" data-diag="new">Preparar otra sesión</button>';
  }
  function mount(options) {
    const doc = options.document, client = options.client, userId = options.userId;
    const section = doc.getElementById("diagnosticSection");
    if (!section || !userId) return { destroy() {} };
    const view = doc.getElementById("diagnosticView"), status = doc.getElementById("diagnosticStatus");
    const service = options.service || createService(client);
    const storage = options.storage || (typeof window !== "undefined" ? window.sessionStorage : null);
    let state = null, busy = false, destroyed = false, deadlineRequested = false;
    let history = [];
    section.hidden = false;
    function key() { return state && state.question ? "studyflow:diagnostic:draft:" + userId + ":" + state.id + ":" + state.question.id : null; }
    function readDraft() { try { return JSON.parse(storage && key() && storage.getItem(key()) || "{}"); } catch (_) { return {}; } }
    function saveDraft() {
      const form = view.querySelector("#diagnosticAnswerForm");
      if (!form || !key()) return;
      try { storage && storage.setItem(key(), JSON.stringify({ option: form.querySelector('input[name="answer"]:checked')?.value || "", explanation: form.querySelector("textarea")?.value || "" })); } catch (_) {}
    }
    function clearDraft() { try { if (key()) storage && storage.removeItem(key()); } catch (_) {} }
    function message(text, error) { status.textContent = text; status.hidden = !text; status.className = "diagnostic-status" + (error ? " is-error" : ""); }
    function controls(disabled) { view.querySelectorAll("button,input,select,textarea").forEach(el => { el.disabled = disabled; }); view.setAttribute("aria-busy", String(disabled)); }
    function focus() { const heading = view.querySelector("[data-diagnostic-focus]"); if (heading && typeof heading.focus === "function") heading.focus({ preventScroll: true }); }
    function historyHtml() {
      if (!history.length) return "";
      return '<details class="diagnostic-history"><summary>Mis sesiones recientes</summary>' + history.map(item => '<button type="button" class="button button-secondary" data-diag="history" data-session="' +
        escapeHtml(item.id) + '">' + escapeHtml(new Date(item.created_at).toLocaleString("es-EC")) + ' · ' + (item.status === "active" ? "En curso" : "Finalizada") + '</button>').join("") + '</details>';
    }
    function render() {
      if (destroyed) return;
      if (!state) {
        view.innerHTML = '<div class="diagnostic-intro"><div><h3 tabindex="-1" data-diagnostic-focus>Descubre qué necesitas reforzar</h3><p>Responde hasta 10 preguntas de cálculo. La dificultad cambia con tus respuestas y puedes pedir pistas.</p><p class="muted">Tus respuestas se guardan después de cada envío. Si recargas, podrás retomar la sesión dentro del tiempo elegido.</p></div><div class="diagnostic-overview"><strong>27 preguntas verificadas</strong><span>3 temas · 3 niveles</span><span>Resultados por concepto</span></div></div>' +
          '<form id="diagnosticSetupForm" class="diagnostic-setup"><label for="diagnosticSubject">Materia</label><select id="diagnosticSubject" disabled><option>Cálculo · Derivadas</option></select><fieldset><legend>¿Qué quieres practicar?</legend>' +
          Object.entries(TOPICS).map(([id,label]) => '<label class="diagnostic-check"><input type="checkbox" name="topic" value="' + id + '" checked><span>' + label + '</span></label>').join("") +
          '</fieldset><label for="diagnosticDuration">Tiempo disponible</label><select id="diagnosticDuration" name="minutes"><option value="10">10 minutos</option><option value="15" selected>15 minutos</option><option value="20">20 minutos</option></select><button class="button" type="submit">Comenzar diagnóstico</button></form><p class="diagnostic-note">La adaptación utiliza reglas y respuestas verificadas. Tu explicación se guarda como apunte; todavía no se evalúa automáticamente con IA.</p>' + historyHtml();
        return;
      }
      if (state.status === "completed") { view.innerHTML = renderReport(state) + historyHtml(); return; }
      const q = state.question, feedback = state.feedback, draft = readDraft();
      if (!q) { view.innerHTML = '<p>No hay una pregunta disponible.</p><button class="button" type="button" data-diag="retry">Volver a cargar</button>'; return; }
      const selected = feedback ? feedback.selected_option : draft.option;
      view.innerHTML = '<div class="diagnostic-meta"><span class="pill">' + escapeHtml(TOPICS[q.topic]) + ' · ' + LEVELS[q.difficulty] +
        '</span><span>Pregunta ' + Math.min(10,Number(state.answered) + (feedback ? 0 : 1)) + ' de hasta 10</span><span id="diagnosticTime" role="timer"></span></div><progress max="10" value="' + Number(state.answered) + '" aria-label="Preguntas respondidas"></progress>' +
        '<p class="diagnostic-reason">' + escapeHtml(state.reason) + '</p><h3 class="diagnostic-math" tabindex="-1" data-diagnostic-focus>' + escapeHtml(q.prompt) + '</h3>' +
        '<form id="diagnosticAnswerForm"><fieldset ' + (feedback ? "disabled" : "") + '><legend>Selecciona la derivada</legend><div class="diagnostic-options">' + q.options.map(option =>
          '<label class="diagnostic-option' + (feedback && option.id === feedback.correct_option ? " is-correct" : "") + '"><input type="radio" name="answer" value="' + escapeHtml(option.id) + '" ' +
          (selected === option.id ? "checked" : "") + '><span><strong>' + option.id.toUpperCase() + '</strong> ' + escapeHtml(option.text) + '</span></label>').join("") +
        '</div><label for="diagnosticExplanation">¿Cómo llegaste a tu respuesta? <span class="muted">(opcional)</span></label><textarea id="diagnosticExplanation" maxlength="2000" rows="3" placeholder="Escribe tu procedimiento…">' +
        escapeHtml(feedback ? feedback.explanation : draft.explanation) + '</textarea><p class="diagnostic-note">Este procedimiento se guarda, pero no se califica en esta versión.</p></fieldset>' +
        (!feedback ? '<div class="diagnostic-actions"><button class="button" type="submit">Comprobar respuesta</button><button class="button button-secondary" type="button" data-diag="hint" ' +
          (q.hints.length >= 2 ? "disabled" : "") + '>Pedir pista (' + q.hints.length + '/2)</button><button class="button button-secondary" type="button" data-diag="skip">No sé todavía</button></div>' : "") + '</form>' +
        (q.hints.length ? '<aside class="diagnostic-hints"><strong>Pistas utilizadas</strong><ol>' + q.hints.map(hint => '<li>' + escapeHtml(hint) + '</li>').join("") + '</ol></aside>' : "") +
        (feedback ? '<div class="diagnostic-feedback ' + (feedback.correct ? "is-success" : "is-review") + '"><h4>' + escapeHtml(feedback.message) + '</h4><p>' + escapeHtml(feedback.solution) +
          '</p><p>' + (feedback.hints_used ? "Resolviste con apoyo de pistas." : "Sin pistas utilizadas.") + '</p><button class="button" type="button" data-diag="next">' +
          (Number(state.answered) >= 10 ? "Ver mi diagnóstico" : "Continuar") + '</button></div>' : "") +
        '<div class="diagnostic-actions diagnostic-footer"><button class="button button-secondary" type="button" data-diag="finish">Finalizar y ver resultados</button><span class="muted">Se evaluará solo lo que hayas respondido.</span></div>';
      tick();
    }
    async function run(action, payload, sessionId) {
      if (busy || destroyed) return;
      busy = true; controls(true); message("Guardando y preparando tu diagnóstico…");
      try {
        const next = await service.act(action, sessionId === undefined ? state?.id : sessionId, payload);
        if (destroyed) return;
        if (action === "answer") clearDraft();
        state = next; deadlineRequested = false;
        if (state?.status === "completed" || action === "load" && !state) {
          try { history = await service.act("history", null, {}); } catch (_) {}
          if (destroyed) return;
        }
        message(""); render(); focus();
      } catch (error) {
        if (destroyed) return;
        message(errorMessage(error), true);
        // Keep the form and draft for a retry. A lost response is safely idempotent server-side.
      } finally {
        busy = false;
        if (!destroyed) {
          controls(false);
          const feedbackFields = view.querySelector("#diagnosticAnswerForm fieldset");
          if (state?.feedback && feedbackFields) feedbackFields.disabled = true;
          const hint = view.querySelector('[data-diag="hint"]');
          if (hint && state?.question?.hints.length >= 2) hint.disabled = true;
          const subject = view.querySelector("#diagnosticSubject"); if (subject) subject.disabled = true;
        }
      }
    }
    function tick() {
      if (destroyed || !state || state.status !== "active") return;
      const remaining = Math.max(0,Math.ceil((new Date(state.deadline).getTime()-Date.now())/1000));
      const timer = doc.getElementById("diagnosticTime");
      if (timer) timer.textContent = Math.floor(remaining/60) + ":" + String(remaining%60).padStart(2,"0") + " restantes";
      if (remaining === 0 && !busy && !deadlineRequested) { deadlineRequested = true; void run("load"); }
    }
    async function submit(event) {
      if (!event.target || !["diagnosticSetupForm","diagnosticAnswerForm"].includes(event.target.id)) return;
      event.preventDefault();
      if (event.target.id === "diagnosticSetupForm") {
        const topics = Array.from(view.querySelectorAll('input[name="topic"]:checked')).map(input => input.value);
        if (!topics.length) return message("Selecciona al menos un tema.",true);
        return run("start", { topics, minutes: Number(doc.getElementById("diagnosticDuration").value) }, null);
      }
      const option = view.querySelector('input[name="answer"]:checked')?.value;
      if (!option) return message("Selecciona una respuesta o pulsa «No sé todavía».",true);
      saveDraft();
      return run("answer", { question_id: state.question.id, option, explanation: doc.getElementById("diagnosticExplanation").value });
    }
    function click(event) {
      const button = event.target.closest && event.target.closest("[data-diag]");
      if (!button || !view.contains(button) || busy) return;
      const action = button.dataset.diag;
      if (action === "new") { state=null; render(); focus(); return; }
      if (action === "history") return void run("load",{},button.dataset.session);
      if (action === "retry") return void run("load");
      saveDraft();
      if (action === "skip") return void run("answer",{ question_id:state.question.id,option:"skip",explanation:doc.getElementById("diagnosticExplanation").value });
      if (action === "finish") return void run("finish");
      if (action === "hint" || action === "next") return void run(action,{question_id:state.question.id});
    }
    const interval = setInterval(tick,1000);
    view.addEventListener("submit",submit); view.addEventListener("click",click);
    view.addEventListener("input",saveDraft); view.addEventListener("change",saveDraft);
    render();
    const ready = run("load",{},null);
    return { ready, destroy() {
      destroyed=true; clearInterval(interval); clearDraft();
      view.removeEventListener("submit",submit); view.removeEventListener("click",click);
      view.removeEventListener("input",saveDraft); view.removeEventListener("change",saveDraft);
      view.innerHTML=""; section.hidden=true; message("");
    } };
  }
  return { TOPICS, LEVELS, escapeHtml, summarize, renderReport, createService, errorMessage, mount };
});
