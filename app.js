(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.StudyFlow = factory();
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function round(value) {
    return Math.round((value + Number.EPSILON) * 100) / 100;
  }

  function calculateAverage(grades) {
    if (!Array.isArray(grades) || grades.length === 0) return null;
    return round(grades.reduce((sum, grade) => sum + Number(grade), 0) / grades.length);
  }

  function calculateSubjectAverage(subjectId, grades) {
    return calculateAverage(
      grades.filter((grade) => grade.subjectId === subjectId).map((grade) => grade.value)
    );
  }

  function calculateOverallAverage(grades) {
    return calculateAverage(grades.map((grade) => grade.value));
  }

  function calculateAnnualAverage(academicYear, grades) {
    return calculateAverage(grades.filter((grade) => grade.academicYear === academicYear).map((grade) => grade.value));
  }

  function calculateAnnualAverages(grades) {
    return [...new Set(grades.map((grade) => grade.academicYear).filter(Boolean))]
      .sort((a, b) => b.localeCompare(a))
      .map((academicYear) => ({ academicYear, average: calculateAnnualAverage(academicYear, grades) }));
  }

  function isValidAcademicYear(value) {
    return /^\d{4}-\d{4}$/.test(String(value || "").trim());
  }

  function getDefaultAcademicYear(dateValue) {
    const date = isValidDate(dateValue) ? new Date(dateValue + "T00:00:00") : new Date();
    let year = date.getFullYear();
    if (date.getMonth() < 6) year -= 1;
    return year + "-" + (year + 1);
  }

  function evaluateGoal(average, goal) {
    if (average === null) return "empty";
    return average < goal ? "below" : "met";
  }

  function normalizeName(name) {
    return name.trim().replace(/\s+/g, " ");
  }

  function isValidGoal(value) {
    return Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 100;
  }

  function isValidGrade(value) {
    return Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 100;
  }
  function isValidDate(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
    const date = new Date(value + "T00:00:00");
    return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
  }
  function formatDate(value) {
    if (!isValidDate(value)) return "Sin fecha";
    return new Intl.DateTimeFormat("es-EC", { day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date(value + "T00:00:00"));
  }
  function getTodayDate() {
    const now = new Date();
    return [now.getFullYear(), String(now.getMonth()+1).padStart(2,"0"), String(now.getDate()).padStart(2,"0")].join("-");
  }

  function getMonthKey(date) { return date.slice(0, 7) + "-01"; }
  function shiftMonth(monthKey, delta) { const parts = monthKey.slice(0, 7).split("-").map(Number); const date = new Date(Date.UTC(parts[0], parts[1] - 1 + delta, 1)); return date.getUTCFullYear() + "-" + String(date.getUTCMonth() + 1).padStart(2, "0") + "-01"; }
  function monthLabel(monthKey) { return new Intl.DateTimeFormat("es-EC", { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(monthKey + "T00:00:00Z")); }
  function buildCalendar(monthKey, grades, subjects, selectedDate) {
    const parts=monthKey.slice(0,7).split("-").map(Number), year=parts[0], month=parts[1];
    const days=new Date(Date.UTC(year,month,0)).getUTCDate(), first=(new Date(Date.UTC(year,month-1,1)).getUTCDay()+6)%7, names=["Lun","Mar","Mié","Jue","Vie","Sáb","Dom"];
    let html="<table class=\"calendar-table\"><thead><tr>"+names.map(function(n){return "<th scope=\"col\">"+n+"</th>";}).join("")+"</tr></thead><tbody><tr>";
    for(let i=0;i<first;i++) html+="<td class=\"calendar-empty\"></td>";
    for(let day=1;day<=days;day++){const dateKey=year+"-"+String(month).padStart(2,"0")+"-"+String(day).padStart(2,"0"),dayGrades=grades.filter(function(g){return g.date===dateKey;}),avg=calculateAverage(dayGrades.map(function(g){return g.value;})),classes=["calendar-day",dateKey===selectedDate?"selected":"",dayGrades.length?"has-notes":""].filter(Boolean).join(" ");let details="<span class=\"day-empty\">—</span>";if(dayGrades.length)details="<span class=\"day-note-count\">"+dayGrades.length+" nota"+(dayGrades.length===1?"":"s")+"</span><span class=\"day-average\">"+avg+"/100</span>";html+="<td><button type=\"button\" class=\""+classes+"\" data-calendar-date=\""+dateKey+"\"><span class=\"day-number\">"+day+"</span>"+details+"</button></td>";if((first+day)%7===0&&day!==days)html+="</tr><tr>"}
    const used=(first+days)%7;if(used)for(let i=used;i<7;i++)html+="<td class=\"calendar-empty\"></td>";return html+"</tr></tbody></table>";
  }
  function buildDayDetails(dateKey, grades, subjects) { const dayGrades=grades.filter(function(g){return g.date===dateKey;}); if(!isValidDate(dateKey))return "<p class=\"empty\">Selecciona una fecha válida.</p>"; if(!dayGrades.length)return "<div class=\"calendar-detail-empty\"><strong>"+formatDate(dateKey)+"</strong><span>No hay notas registradas para este día.</span></div>"; const items=dayGrades.map(function(g){const subject=subjects.find(function(s){return s.id===g.subjectId;});return "<li><strong>"+escapeHtml(subject?subject.name:"Materia")+"</strong><span>"+g.value+"/100"+(g.label?" · "+escapeHtml(g.label):"")+"</span></li>";}).join(""); return "<div class=\"calendar-detail\"><div><strong>"+formatDate(dateKey)+"</strong><span>Promedio del día: "+calculateAverage(dayGrades.map(function(g){return g.value;}))+"/100</span></div><ul>"+items+"</ul></div>"; }

  function createState() {
    return {
      goal: 70,
      subjects: [],
      grades: [],
      nextSubjectId: 1,
      nextGradeId: 1,
      theme: "light",
      selectedDate: getTodayDate(),
      calendarMonth: getMonthKey(getTodayDate())
    };
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function init(document) {
    const state = createState();
    let cloudService = null;
    let cloudUserId = null;
    let cloudReady = false;
    const els = {
      goalForm: document.getElementById("goalForm"),
      goal: document.getElementById("goal"),
      goalError: document.getElementById("goalError"),
      subjectForm: document.getElementById("subjectForm"),
      subjectName: document.getElementById("subjectName"),
      subjectError: document.getElementById("subjectError"),
      gradeForm: document.getElementById("gradeForm"),
      gradeSubject: document.getElementById("gradeSubject"),
      gradeValue: document.getElementById("gradeValue"),
      gradeLabel: document.getElementById("gradeLabel"),
      gradeDate: document.getElementById("gradeDate"),
      academicYear: document.getElementById("academicYear"),
      gradeError: document.getElementById("gradeError"),
      addGrade: document.getElementById("addGrade"),
      clearSession: document.getElementById("clearSession"),
      themeToggle: document.getElementById("themeToggle"),
      overallAverage: document.getElementById("overallAverage"),
      gradeCount: document.getElementById("gradeCount"),
      goalDisplay: document.getElementById("goalDisplay"),
      goalStatus: document.getElementById("goalStatus"),
      statusTitle: document.getElementById("statusTitle"),
      statusText: document.getElementById("statusText"),
      subjectCount: document.getElementById("subjectCount"),
      noteCount: document.getElementById("noteCount"),
      subjectsList: document.getElementById("subjectsList"),
      gradesList: document.getElementById("gradesList"),
      averagesTable: document.getElementById("averagesTable"),
      annualAveragesTable: document.getElementById("annualAveragesTable"),
      cloudSyncStatus: document.getElementById("cloudSyncStatus"),
      calendarMonth: document.getElementById("calendarMonth"), calendar: document.getElementById("calendar"), calendarDetails: document.getElementById("calendarDetails"), calendarPrevious: document.getElementById("calendarPrevious"), calendarNext: document.getElementById("calendarNext"), calendarTitle: document.getElementById("calendarTitle")
    };

    const setError = (element, message) => {
      element.textContent = message;
      element.hidden = !message;
    };

    const setCloudStatus = (message, kind) => {
      if (!els.cloudSyncStatus) return;
      els.cloudSyncStatus.textContent = message || "";
      els.cloudSyncStatus.className = "cloud-sync-status" + (kind ? " is-" + kind : "");
      els.cloudSyncStatus.hidden = !message;
    };

    const connectCloud = async (service, userId) => {
      if (!service || !userId) return { error: new Error("No hay una sesión válida para sincronizar.") };
      cloudService = service;
      cloudUserId = userId;
      cloudReady = false;
      setCloudStatus("Conectando y cargando tus datos académicos…", "loading");
      let response;
      try { response = await service.loadAcademicData(userId); }
      catch (error) { setCloudStatus("No se pudieron cargar los datos de la nube. Recarga la página e inténtalo de nuevo.", "error"); return { error }; }
      if (response.error || !response.data) {
        setCloudStatus("No se pudieron cargar tus datos académicos. Revisa la conexión e inténtalo de nuevo.", "error");
        return { error: response.error || new Error("No se recibieron datos académicos.") };
      }
      state.subjects = (response.data.subjects || []).map((subject) => ({ id: subject.id, name: subject.name }));
      state.grades = (response.data.grades || []).map((grade) => ({
        id: grade.id, subjectId: grade.subject_id, value: Number(grade.value),
        label: grade.label || "", date: grade.grade_date, academicYear: grade.academic_year
      }));
      state.nextSubjectId = 1;
      state.nextGradeId = 1;
      cloudReady = true;
      render();
      setCloudStatus("Sincronizado con tu cuenta. Las materias y notas se guardan en la nube.", "success");
      return { data: { subjects: state.subjects.length, grades: state.grades.length }, error: null };
    };

    const disconnectCloud = () => {
      cloudService = null;
      cloudUserId = null;
      cloudReady = false;
      state.subjects = [];
      state.grades = [];
      state.nextSubjectId = 1;
      state.nextGradeId = 1;
      setCloudStatus("", "");
      render();
      return true;
    };

    const renderCalendar = () => { els.calendarMonth.value=state.calendarMonth.slice(0,7); els.calendarTitle.textContent=monthLabel(state.calendarMonth); els.calendar.innerHTML=buildCalendar(state.calendarMonth,state.grades,state.subjects,state.selectedDate); els.calendarDetails.innerHTML=buildDayDetails(state.selectedDate,state.grades,state.subjects); };

    const render = () => {
      document.documentElement.dataset.theme = state.theme;
      els.themeToggle.setAttribute("aria-pressed", String(state.theme === "dark"));
      els.themeToggle.textContent = state.theme === "dark" ? "☀️ Modo claro" : "🌙 Modo oscuro";
      els.goal.value = state.goal;
      els.goalDisplay.textContent = `${state.goal}/100`;
      els.subjectCount.textContent = String(state.subjects.length);
      els.noteCount.textContent = String(state.grades.length);

      const average = calculateOverallAverage(state.grades);
      els.overallAverage.textContent = average === null ? "—" : `${average}/100`;
      els.gradeCount.textContent = state.grades.length === 0
        ? "Sin notas registradas"
        : `${state.grades.length} ${state.grades.length === 1 ? "nota registrada" : "notas registradas"}`;

      const goalStatus = evaluateGoal(average, state.goal);
      els.goalStatus.className =
        `card status-card status-${goalStatus === "below" ? "warning" : goalStatus === "met" ? "success" : "neutral"}`;
      if (goalStatus === "below") {
        const difference = round(state.goal - average);
        els.statusTitle.textContent = "⚠️ Tu promedio está por debajo de la meta";
        els.statusText.textContent = `Te faltan ${difference} puntos para alcanzar ${state.goal}/100.`;
      } else if (goalStatus === "met") {
        els.statusTitle.textContent = "✅ Meta alcanzada";
        els.statusText.textContent = `Tu promedio supera o iguala la meta de ${state.goal}/100.`;
      } else {
        els.statusTitle.textContent = "Añade una nota para empezar.";
        els.statusText.textContent =
          "El aviso aparecerá automáticamente cuando haya un promedio que comparar.";
      }

      if (state.subjects.length === 0) {
        els.subjectsList.innerHTML =
          '<p class="empty">Todavía no tienes materias registradas.</p>';
      } else {
        els.subjectsList.innerHTML = state.subjects.map((subject) => {
          const avg = calculateSubjectAverage(subject.id, state.grades);
          return `<div class="list-item"><div><strong>${escapeHtml(subject.name)}</strong><small>${
            avg === null ? "Sin notas" : `Promedio: ${avg}/100`
          }</small></div><button class="delete-button" type="button" data-delete-subject="${subject.id}">Eliminar</button></div>`;
        }).join("");
      }

      els.gradeSubject.innerHTML = state.subjects.length === 0
        ? '<option value="">Primero agrega una materia</option>'
        : state.subjects.map((subject) =>
            `<option value="${subject.id}">${escapeHtml(subject.name)}</option>`
          ).join("");
      els.gradeSubject.disabled = state.subjects.length === 0;
      els.gradeValue.disabled = state.subjects.length === 0;
      els.addGrade.disabled = state.subjects.length === 0;

      if (state.grades.length === 0) {
        els.gradesList.innerHTML =
          '<p class="empty">Las notas que agregues aparecerán aquí.</p>';
      } else {
        els.gradesList.innerHTML = state.grades.slice().reverse().map((grade) => {
          const subject = state.subjects.find((item) => item.id === grade.subjectId);
          return `<div class="list-item"><div><strong>${grade.value}/100</strong><small>${
            escapeHtml(subject ? subject.name : "Materia")
          } · ${escapeHtml(grade.label || "Sin descripción")} · ${escapeHtml(formatDate(grade.date))}</small></div><button class="delete-button" type="button" data-delete-grade="${grade.id}">Eliminar</button></div>`;
        }).join("");
      }

      if (state.subjects.length === 0) {
        els.averagesTable.innerHTML =
          '<p class="table-empty">Agrega al menos una materia para ver sus promedios.</p>';
      } else {
        const rows = state.subjects.map((subject) => {
          const avg = calculateSubjectAverage(subject.id, state.grades);
          const status = evaluateGoal(avg, state.goal);
          const className = status === "below" ? "below" : status === "met" ? "above" : "muted";
          return `<tr><td><strong>${escapeHtml(subject.name)}</strong></td><td>${
            avg === null ? "—" : `<span class="score ${className}">${avg}/100</span>`
          }</td><td>${
            avg === null ? "Sin notas" : status === "below" ? "Debajo de la meta" : "Meta alcanzada"
          }</td></tr>`;
        }).join("");
        els.averagesTable.innerHTML =
          `<table><thead><tr><th>Materia</th><th>Promedio</th><th>Estado</th></tr></thead><tbody>${rows}</tbody></table>`;
      }

      const annualAverages = calculateAnnualAverages(state.grades);
      if (annualAverages.length === 0) {
        els.annualAveragesTable.innerHTML = '<p class="table-empty">Las notas que registres se agruparán aquí por año académico.</p>';
      } else {
        const annualRows = annualAverages.map((item) => `<tr><td><strong>${escapeHtml(item.academicYear)}</strong></td><td>${item.average === null ? "—" : item.average + "/100"}</td><td>${item.average === null ? "Sin notas" : "Promedio calculado"}</td></tr>`).join("");
        els.annualAveragesTable.innerHTML = `<table><thead><tr><th>Año académico</th><th>Promedio anual</th><th>Estado</th></tr></thead><tbody>${annualRows}</tbody></table>`;
      }
      renderCalendar();
    };

    els.goalForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const value = Number(els.goal.value);
      if (!isValidGoal(value)) {
        setError(els.goalError, "La meta debe ser un número entre 0 y 100.");
        return;
      }
      state.goal = round(value);
      setError(els.goalError, "");
      render();
    });

    els.subjectForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const name = normalizeName(els.subjectName.value);
      if (!name) {
        setError(els.subjectError, "Escribe el nombre de la materia.");
        return;
      }
      const duplicate = state.subjects.some(
        (subject) => subject.name.toLowerCase() === name.toLowerCase()
      );
      if (duplicate) {
        setError(els.subjectError, "Esa materia ya está registrada.");
        return;
      }
      if (cloudService && !cloudReady) {
        setError(els.subjectError, "Espera a que termine la sincronización antes de modificar materias.");
        return;
      }
      let subject = { id: state.nextSubjectId++, name };
      if (cloudService) {
        let result;
        try { result = await cloudService.addSubject(cloudUserId, name); }
        catch (_) { result = { error: new Error("No se pudo guardar la materia en la nube.") }; }
        if (result.error || !result.data) {
          setError(els.subjectError, "No se pudo guardar la materia. Comprueba tu conexión e inténtalo de nuevo.");
          return;
        }
        subject = { id: result.data.id, name: result.data.name };
      }
      state.subjects.push(subject);
      els.subjectName.value = "";
      setError(els.subjectError, "");
      render();
      els.subjectName.focus();
    });

    els.gradeForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (state.subjects.length === 0) {
        setError(els.gradeError, "Primero agrega una materia.");
        return;
      }
      const rawSubjectId = els.gradeSubject.value;
      const value = Number(els.gradeValue.value);
      const date = els.gradeDate.value;
      const academicYear = normalizeName(els.academicYear.value);
      const selectedSubject = state.subjects.find((subject) => String(subject.id) === String(rawSubjectId));
      if (!selectedSubject) {
        setError(els.gradeError, "Selecciona una materia válida.");
        return;
      }
      const subjectId = selectedSubject.id;
      if (cloudService && !cloudReady) {
        setError(els.gradeError, "Espera a que termine la sincronización antes de agregar notas.");
        return;
      }
      if (!isValidAcademicYear(academicYear)) {
        setError(els.gradeError, "El año académico debe tener el formato AAAA-AAAA, por ejemplo 2026-2027.");
        return;
      }
      if (!isValidGrade(value)) {
        setError(els.gradeError, "La nota debe ser un número entre 0 y 100.");
        return;
      }
      if (!isValidDate(date)) {
        setError(els.gradeError, "Selecciona una fecha válida.");
        return;
      }
      let grade = {
        id: state.nextGradeId++,
        subjectId,
        value: round(value),
        label: normalizeName(els.gradeLabel.value),
        date,
        academicYear
      };
      if (cloudService) {
        let result;
        try { result = await cloudService.addGrade(cloudUserId, grade); }
        catch (_) { result = { error: new Error("No se pudo guardar la nota en la nube.") }; }
        if (result.error || !result.data) {
          setError(els.gradeError, "No se pudo guardar la nota. Comprueba tu conexión e inténtalo de nuevo.");
          return;
        }
        grade = { id: result.data.id, subjectId: result.data.subject_id, value: Number(result.data.value), label: result.data.label || "", date: result.data.grade_date, academicYear: result.data.academic_year };
      }
      state.grades.push(grade);
      state.selectedDate = date;
      state.calendarMonth = getMonthKey(date);
      els.gradeValue.value = "";
      els.gradeLabel.value = "";
      els.gradeDate.value = getTodayDate();
      els.academicYear.value = getDefaultAcademicYear(els.gradeDate.value);
      lastSuggestedAcademicYear = els.academicYear.value;
      setError(els.gradeError, "");
      render();
      els.gradeValue.focus();
    });

    els.subjectsList.addEventListener("click", async (event) => {
      const button = event.target.closest("[data-delete-subject]");
      if (!button) return;
      const id = button.dataset.deleteSubject;
      if (cloudService && !cloudReady) {
        setCloudStatus("Espera a que termine la sincronización antes de eliminar materias.", "error");
        return;
      }
      if (cloudService) {
        let result;
        try { result = await cloudService.deleteSubject(cloudUserId, id); }
        catch (_) { result = { error: new Error("No se pudo eliminar la materia.") }; }
        if (result.error) {
          setCloudStatus("No se pudo eliminar la materia de la nube. Vuelve a intentarlo.", "error");
          return;
        }
      }
      state.subjects = state.subjects.filter((subject) => String(subject.id) !== String(id));
      state.grades = state.grades.filter((grade) => String(grade.subjectId) !== String(id));
      render();
      if (cloudService) setCloudStatus("Materia eliminada y cambios sincronizados.", "success");
    });

    els.gradesList.addEventListener("click", async (event) => {
      const button = event.target.closest("[data-delete-grade]");
      if (!button) return;
      const id = button.dataset.deleteGrade;
      if (cloudService && !cloudReady) {
        setCloudStatus("Espera a que termine la sincronización antes de eliminar notas.", "error");
        return;
      }
      if (cloudService) {
        let result;
        try { result = await cloudService.deleteGrade(cloudUserId, id); }
        catch (_) { result = { error: new Error("No se pudo eliminar la nota.") }; }
        if (result.error) {
          setCloudStatus("No se pudo eliminar la nota de la nube. Vuelve a intentarlo.", "error");
          return;
        }
      }
      state.grades = state.grades.filter((grade) => String(grade.id) !== String(id));
      render();
      if (cloudService) setCloudStatus("Nota eliminada y cambios sincronizados.", "success");
    });

    els.calendarMonth.addEventListener("change", () => { const value=els.calendarMonth.value; if(/^\d{4}-\d{2}$/.test(value)){state.calendarMonth=value+"-01";state.selectedDate=state.calendarMonth;renderCalendar();} });
    els.calendarPrevious.addEventListener("click", () => { state.calendarMonth=shiftMonth(state.calendarMonth,-1); state.selectedDate=state.calendarMonth; renderCalendar(); });
    els.calendarNext.addEventListener("click", () => { state.calendarMonth=shiftMonth(state.calendarMonth,1); state.selectedDate=state.calendarMonth; renderCalendar(); });
    els.calendar.addEventListener("click", (event) => { const button=event.target.closest("[data-calendar-date]"); if(!button)return; state.selectedDate=button.dataset.calendarDate; renderCalendar(); });

    let lastSuggestedAcademicYear = getDefaultAcademicYear(state.selectedDate);
    els.gradeDate.addEventListener("change", () => {
      const suggestion = getDefaultAcademicYear(els.gradeDate.value);
      if (!els.academicYear.value || els.academicYear.value === lastSuggestedAcademicYear) els.academicYear.value = suggestion;
      lastSuggestedAcademicYear = suggestion;
    });

    els.themeToggle.addEventListener("click", () => {
      state.theme = state.theme === "dark" ? "light" : "dark";
      render();
    });

    els.clearSession.addEventListener("click", () => {
      if (cloudService) {
        setCloudStatus("Las notas de una cuenta se conservan en la nube. Cierra sesión para salir o elimina los registros individualmente.", "error");
        return;
      }
      state.goal = 70;
      state.subjects = [];
      state.grades = [];
      state.nextSubjectId = 1;
      state.nextGradeId = 1;
      state.theme = "light";
      state.selectedDate = getTodayDate();
      state.calendarMonth = getMonthKey(state.selectedDate);
      setError(els.goalError, "");
      setError(els.subjectError, "");
      setError(els.gradeError, "");
      render();
      els.subjectName.focus();
    });

    els.gradeDate.value = state.selectedDate;
    els.academicYear.value = getDefaultAcademicYear(state.selectedDate);
    render();
    return {
      state, render, elements: els, connectCloud, disconnectCloud,
      getCloudStatus: () => ({ connected: Boolean(cloudService), ready: cloudReady, userId: cloudUserId })
    };
  }

  const api = {
    createState,
    calculateAverage,
    calculateSubjectAverage,
    calculateOverallAverage,
    calculateAnnualAverage,
    calculateAnnualAverages,
    isValidAcademicYear,
    getDefaultAcademicYear,
    evaluateGoal,
    isValidGoal,
    isValidGrade,
    normalizeName,
    isValidDate,
    formatDate,
    getTodayDate,
    getMonthKey,
    shiftMonth,
    monthLabel,
    buildCalendar,
    buildDayDetails,
    init
  };
  if (typeof document !== "undefined" && document.getElementById("goalForm")) {
    const instance = init(document);
    if (typeof globalThis !== "undefined") globalThis.StudyFlowApp = instance;
  }
  return api;
});