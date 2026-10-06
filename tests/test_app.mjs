import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import path from "node:path";
import test from "node:test";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const StudyFlow = require("../app.js");
const root = path.resolve(new URL("..", import.meta.url).pathname);

function load(file) { return fs.readFileSync(path.join(root, file), "utf8"); }

test("calcula el promedio correctamente", () => {
  assert.equal(StudyFlow.calculateAverage([]), null);
  assert.equal(StudyFlow.calculateAverage([80, 90, 100]), 90);
  assert.equal(StudyFlow.calculateAverage([85, 86]), 85.5);
});

test("calcula promedio por materia y general", () => {
  const grades = [
    { subjectId: 1, value: 90 },
    { subjectId: 1, value: 80 },
    { subjectId: 2, value: 70 }
  ];
  assert.equal(StudyFlow.calculateSubjectAverage(1, grades), 85);
  assert.equal(StudyFlow.calculateSubjectAverage(2, grades), 70);
  assert.equal(StudyFlow.calculateOverallAverage(grades), 80);
});

test("detecta correctamente el estado frente a la meta", () => {
  assert.equal(StudyFlow.evaluateGoal(null, 70), "empty");
  assert.equal(StudyFlow.evaluateGoal(69.9, 70), "below");
  assert.equal(StudyFlow.evaluateGoal(70, 70), "met");
  assert.equal(StudyFlow.evaluateGoal(85, 70), "met");
});

test("valida meta y notas dentro de 0 a 100", () => {
  assert.equal(StudyFlow.isValidGoal(0), true);
  assert.equal(StudyFlow.isValidGoal(100), true);
  assert.equal(StudyFlow.isValidGoal(-1), false);
  assert.equal(StudyFlow.isValidGoal(101), false);
  assert.equal(StudyFlow.isValidGrade(0), true);
  assert.equal(StudyFlow.isValidGrade(100), true);
  assert.equal(StudyFlow.isValidGrade("abc"), false);
});

test("normaliza nombres correctamente", () => {
  assert.equal(StudyFlow.normalizeName("   cálculo   diferencial  "), "cálculo diferencial");
});

test("la interfaz solo depende de HTML, CSS y JavaScript", () => {
  const html = load("index.html");
  const css = load("styles.css");
  const js = load("app.js");
  assert.match(html, /<link rel="stylesheet" href="styles\.css">/);
  assert.match(html, /<script src="app\.js" defer><\/script>/);
  for (const id of ["goalForm", "subjectForm", "gradeForm", "overallAverage", "goalStatus", "averagesTable"]) {
    assert.match(html, new RegExp(`id="${id}"`));
  }
  assert.ok(css.includes("@media"));
  assert.ok(js.includes("calculateOverallAverage"));
  assert.ok(!js.includes("sqlite"));
  assert.ok(!js.includes("fetch("));
  assert.ok(!js.includes("localStorage"));
});

class Element {
  constructor(id, tag = "div") {
    this.id = id;
    this.tagName = tag.toUpperCase();
    this.listeners = {};
    this.textContent = "";
    this.innerHTML = "";
    this.hidden = false;
    this.disabled = false;
    this.value = "";
    this.className = "";
    this.dataset = {};
  }
  addEventListener(type, fn) { (this.listeners[type] ??= []).push(fn); }
  dispatchEvent(event) {
    for (const fn of this.listeners[event.type] ?? []) fn({ preventDefault() {}, target: this });
    return true;
  }
  focus() {}
  closest(selector) {
    if (selector === "[data-delete-subject]" && this.dataset.deleteSubject) return this;
    if (selector === "[data-delete-grade]" && this.dataset.deleteGrade) return this;
    return null;
  }
}

class Document {
  constructor(ids) {
    this.elements = new Map(ids.map(([id, tag]) => [id, new Element(id, tag)]));
  }
  getElementById(id) { return this.elements.get(id) ?? null; }
}

test("simula el flujo de la interfaz", () => {
  const ids = [
    ["goalForm", "form"], ["goal", "input"], ["goalError", "p"],
    ["subjectForm", "form"], ["subjectName", "input"], ["subjectError", "p"],
    ["gradeForm", "form"], ["gradeSubject", "select"], ["gradeValue", "input"],
    ["gradeLabel", "input"], ["gradeError", "p"], ["addGrade", "button"],
    ["clearSession", "button"], ["overallAverage", "p"], ["gradeCount", "p"],
    ["goalDisplay", "p"], ["goalStatus", "div"], ["statusTitle", "p"],
    ["statusText", "p"], ["subjectCount", "span"], ["noteCount", "span"],
    ["subjectsList", "div"], ["gradesList", "div"], ["averagesTable", "div"]
  ];
  const document = new Document(ids);
  const code = fs.readFileSync(new URL("../app.js", import.meta.url), "utf8");
  const context = vm.createContext({ console, globalThis: {} });
  vm.runInContext(code, context);
  const app = context.globalThis.StudyFlow.init(document);
  const submit = (id) => document.getElementById(id).dispatchEvent({ type: "submit" });

  document.getElementById("subjectName").value = "Matemáticas";
  submit("subjectForm");
  assert.equal(app.state.subjects.length, 1);
  assert.equal(document.getElementById("gradeSubject").disabled, false);
  document.getElementById("gradeSubject").value = "1";

  document.getElementById("gradeValue").value = "60";
  submit("gradeForm");
  assert.equal(app.state.grades.length, 1);
  assert.equal(document.getElementById("overallAverage").textContent, "60/100");
  assert.match(document.getElementById("goalStatus").className, /status-warning/);
  assert.match(document.getElementById("statusTitle").textContent, /por debajo/);

  document.getElementById("gradeValue").value = "90";
  submit("gradeForm");
  assert.equal(document.getElementById("overallAverage").textContent, "75/100");
  assert.match(document.getElementById("goalStatus").className, /status-success/);

  const before = app.state.grades.length;
  document.getElementById("gradeValue").value = "101";
  submit("gradeForm");
  assert.equal(app.state.grades.length, before);
  assert.equal(document.getElementById("gradeError").hidden, false);

  const subjectCount = app.state.subjects.length;
  document.getElementById("subjectName").value = "matemáticas";
  submit("subjectForm");
  assert.equal(app.state.subjects.length, subjectCount);
  assert.equal(document.getElementById("subjectError").hidden, false);

  document.getElementById("goal").value = "80";
  submit("goalForm");
  assert.match(document.getElementById("goalStatus").className, /status-warning/);

  document.getElementById("clearSession").dispatchEvent({ type: "click" });
  assert.equal(app.state.subjects.length, 0);
  assert.equal(app.state.grades.length, 0);
  assert.equal(document.getElementById("overallAverage").textContent, "—");
  assert.equal(document.getElementById("gradeSubject").disabled, true);
});
