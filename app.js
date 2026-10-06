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
    if (!/^\\d{4}-\\d{2}-\\d{2}$/.test(value)) return false;
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

  function createState() {
    return {
      goal: 70,
      subjects: [],
      grades: [],
      nextSubjectId: 1,
      nextGradeId: 1,
      theme: "light"
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
      averagesTable: document.getElementById("averagesTable")
    };

    const setError = (element, message) => {
      element.textContent = message;
      element.hidden = !message;
    };

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

    els.subjectForm.addEventListener("submit", (event) => {
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
      state.subjects.push({ id: state.nextSubjectId++, name });
      els.subjectName.value = "";
      setError(els.subjectError, "");
      render();
      els.subjectName.focus();
    });

    els.gradeForm.addEventListener("submit", (event) => {
      event.preventDefault();
      if (state.subjects.length === 0) {
        setError(els.gradeError, "Primero agrega una materia.");
        return;
      }
      const subjectId = Number(els.gradeSubject.value);
      const value = Number(els.gradeValue.value);
      const date = els.gradeDate.value;
      if (!state.subjects.some((subject) => subject.id === subjectId)) {
        setError(els.gradeError, "Selecciona una materia válida.");
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
      state.grades.push({
        id: state.nextGradeId++,
        subjectId,
        value: round(value),
        label: normalizeName(els.gradeLabel.value),
        date
      });
      els.gradeValue.value = "";
      els.gradeLabel.value = "";
      els.gradeDate.value = getTodayDate();
      setError(els.gradeError, "");
      render();
      els.gradeValue.focus();
    });

    els.subjectsList.addEventListener("click", (event) => {
      const button = event.target.closest("[data-delete-subject]");
      if (!button) return;
      const id = Number(button.dataset.deleteSubject);
      state.subjects = state.subjects.filter((subject) => subject.id !== id);
      state.grades = state.grades.filter((grade) => grade.subjectId !== id);
      render();
    });

    els.gradesList.addEventListener("click", (event) => {
      const button = event.target.closest("[data-delete-grade]");
      if (!button) return;
      const id = Number(button.dataset.deleteGrade);
      state.grades = state.grades.filter((grade) => grade.id !== id);
      render();
    });

    els.themeToggle.addEventListener("click", () => {
      state.theme = state.theme === "dark" ? "light" : "dark";
      render();
    });

    els.clearSession.addEventListener("click", () => {
      state.goal = 70;
      state.subjects = [];
      state.grades = [];
      state.nextSubjectId = 1;
      state.nextGradeId = 1;
      state.theme = "light";
      setError(els.goalError, "");
      setError(els.subjectError, "");
      setError(els.gradeError, "");
      render();
      els.subjectName.focus();
    });

    render();
    return { state, render, elements: els };
  }

  const api = {
    createState,
    calculateAverage,
    calculateSubjectAverage,
    calculateOverallAverage,
    evaluateGoal,
    isValidGoal,
    isValidGrade,
    normalizeName,
    isValidDate,
    formatDate,
    getTodayDate,
    init
  };
  if (typeof document !== "undefined" && document.getElementById("goalForm")) init(document);
  return api;
});