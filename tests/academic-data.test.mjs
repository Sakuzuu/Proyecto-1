import assert from "node:assert/strict";
import test from "node:test";
import Academic from "../academic-data.js";

function mockClient() {
  const calls = [];
  const grade = { id: "grade-1", user_id: "user-1", subject_id: "subject-1", value: 87.5, label: "Parcial", grade_date: "2026-10-20", academic_year: "2026-2027" };
  const subject = { id: "subject-1", user_id: "user-1", name: "Cálculo" };
  function builder(table) {
    const b = { table, operation: "select", filters: [], payload: null, columns: "*", sort: null, deleted: false,
      select(columns) { this.columns = columns; return this; },
      eq(column, value) { this.filters.push([column, value]); return this; },
      order(column, options) { this.sort = [column, options]; return this; },
      or(filter) { this.filters.push(["or", filter]); return this; },
      insert(payload) { this.operation = "insert"; this.payload = payload; return this; },
      update(payload) { this.operation = "update"; this.payload = payload; return this; },
      delete() { this.operation = "delete"; return this; },
      single() { return Promise.resolve(resolve(this, true)); },
      maybeSingle() { return Promise.resolve(resolve(this, true)); },
      then(onFulfilled, onRejected) { return Promise.resolve(resolve(this, false)).then(onFulfilled, onRejected); }
    };
    return b;
  }
  function resolve(b, one) {
    calls.push({ table: b.table, operation: b.operation, filters: b.filters, payload: b.payload, columns: b.columns, sort: b.sort });
    if (b.table === "subjects" && b.operation === "select") return { data: [subject], error: null };
    if (b.table === "grades" && b.operation === "select") return { data: [grade], error: null };
    if (b.table === "subjects" && b.operation === "insert") return { data: { ...subject, name: b.payload.name }, error: null };
    if (b.table === "grades" && b.operation === "insert") return { data: { ...grade, ...b.payload }, error: null };
    if (b.table === "subjects" && b.operation === "delete") return { data: [{ id: "subject-1" }], error: null };
    if (b.table === "grades" && b.operation === "delete") return { data: [{ id: "grade-1" }], error: null };
    if (b.table === "profiles" && b.operation === "update") return { data: { id: "user-1", ...b.payload }, error: null };
    if (b.table === "friend_requests" && b.operation === "insert") return { data: { id: "request-1", ...b.payload }, error: null };
    if (b.table === "friend_requests" && b.operation === "select") return { data: [], error: null };
    if (b.table === "friend_requests" && b.operation === "update") return { data: { id: "request-1", status: b.payload.status }, error: null };
    if (b.operation === "delete") return { data: [{ id: "row" }], error: null };
    return { data: [], error: null };
  }
  return {
    calls,
    from: table => builder(table),
    rpc: async (name, args) => { calls.push({ rpc: name, args }); return { data: name === "search_profiles_by_username" ? [{ id: "friend-1", username: "amigo", display_name: "Amigo" }] : [], error: null }; }
  };
}

test("carga materias y notas desde las consultas filtradas por propietario", async () => {
  const client = mockClient(), service = Academic.createService(client);
  const result = await service.loadAcademicData("user-1");
  assert.equal(result.error, null);
  assert.equal(result.data.subjects[0].id, "subject-1");
  assert.equal(result.data.grades[0].academic_year, "2026-2027");
  assert.deepEqual(client.calls.map(c => [c.table, c.operation, c.filters[0]]), [
    ["subjects", "select", ["user_id", "user-1"]],
    ["grades", "select", ["user_id", "user-1"]]
  ]);
});
test("guarda materias normalizadas en la cuenta propietaria", async () => {
  const client = mockClient(), service = Academic.createService(client);
  const result = await service.addSubject("user-1", "  Cálculo   Diferencial  ");
  assert.equal(result.error, null);
  assert.equal(result.data.name, "Cálculo Diferencial");
  assert.equal(client.calls[0].payload.user_id, "user-1");
  assert.equal((await service.addSubject("user-1", " ")).error.message.includes("nombre"), true);
});
test("valida y guarda una nota con materia, fecha y período", async () => {
  const client = mockClient(), service = Academic.createService(client);
  const result = await service.addGrade("user-1", { subjectId: "subject-1", value: 87.5, label: "Parcial", date: "2026-10-20", academicYear: "2026-2027" });
  assert.equal(result.error, null);
  assert.equal(client.calls[0].payload.user_id, "user-1");
  assert.equal(client.calls[0].payload.subject_id, "subject-1");
  assert.equal(client.calls[0].payload.academic_year, "2026-2027");
  assert.equal((await service.addGrade("user-1", { subjectId: "subject-1", value: 120, date: "2026-10-20", academicYear: "2026-2027" })).error.message.includes("0 y 100"), true);
  assert.equal((await service.addGrade("user-1", { subjectId: "subject-1", value: 70, date: "2026-02-30", academicYear: "2026-2027" })).error.message.includes("fecha"), true);
  assert.equal((await service.addGrade("user-1", { subjectId: "subject-1", value: 70, date: "2026-10-20", academicYear: "2026" })).error.message.includes("AAAA-AAAA"), true);
});
test("eliminaciones están siempre acotadas por usuario", async () => {
  const client = mockClient(), service = Academic.createService(client);
  assert.equal((await service.deleteSubject("user-1", "subject-1")).data, true);
  assert.equal((await service.deleteGrade("user-1", "grade-1")).data, true);
  assert.ok(client.calls.every(c => c.filters.some(f => f[0] === "user_id" && f[1] === "user-1")));
});
test("las preferencias de privacidad y las futuras funciones de amistad usan RPC o perfil", async () => {
  const client = mockClient(), service = Academic.createService(client);
  assert.equal((await service.updateSharingPreference("user-1", true)).data.share_academic_averages, true);
  assert.equal((await service.searchProfilesByUsername(" Amigo ")).data[0].username, "amigo");
  assert.equal((await service.searchProfilesByUsername("ab")).data.length, 0);
  assert.equal((await service.sendFriendRequest("user-1", "friend-1")).data.status, "pending");
  assert.equal((await service.respondToFriendRequest("user-1", "request-1", "accepted")).data.status, "accepted");
  assert.equal((await service.getSharedAcademicAverages("friend-1")).error, null);
  assert.equal((await service.removeFriend("friend-1")).error, null);
  assert.ok(client.calls.some(c => c.rpc === "get_shared_academic_averages"));
  assert.ok(client.calls.some(c => c.rpc === "remove_friend"));
});
test("rechaza IDs faltantes y no permite solicitud a uno mismo", async () => {
  const service = Academic.createService(mockClient());
  assert.ok((await service.loadAcademicData("")).error);
  assert.ok((await service.addSubject("", "Cálculo")).error);
  assert.ok((await service.sendFriendRequest("user-1", "user-1")).error);
  assert.ok((await service.respondToFriendRequest("user-1", "request-1", "pending")).error);
});
