(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.StudyFlowCloud = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const SUBJECT_COLUMNS = "id, user_id, name, created_at, updated_at";
  const GRADE_COLUMNS = "id, user_id, subject_id, value, label, grade_date, academic_year, created_at, updated_at";
  const YEAR_PATTERN = /^\d{4}-\d{4}$/;
  function validUserId(userId) { return typeof userId === "string" && userId.trim().length > 0; }
  function normalizeName(value) { return String(value || "").trim().replace(/\s+/g, " "); }
  function validDate(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(String(value || ""))) return false;
    const parsed = new Date(value + "T00:00:00");
    return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
  }
  function validateGrade(grade) {
    if (!grade || !validUserId(String(grade.subjectId || ""))) return "Selecciona una materia válida.";
    const value = Number(grade.value);
    if (!Number.isFinite(value) || value < 0 || value > 100) return "La nota debe estar entre 0 y 100.";
    if (!validDate(grade.date)) return "Selecciona una fecha válida.";
    if (!YEAR_PATTERN.test(String(grade.academicYear || ""))) return "El año académico debe tener el formato AAAA-AAAA.";
    if (String(grade.label || "").length > 60) return "La descripción no puede superar los 60 caracteres.";
    return "";
  }
  function failure(message) { return { data: null, error: new Error(message) }; }
  function createService(client) {
    if (!client || typeof client.from !== "function" || typeof client.rpc !== "function") throw new TypeError("Se necesita un cliente válido de Supabase.");
    return {
      async loadAcademicData(userId) {
        if (!validUserId(userId)) return failure("Falta el usuario autenticado.");
        try {
          const [subjectsResult, gradesResult] = await Promise.all([
            client.from("subjects").select(SUBJECT_COLUMNS).eq("user_id", userId).order("created_at", { ascending: true }),
            client.from("grades").select(GRADE_COLUMNS).eq("user_id", userId).order("grade_date", { ascending: true })
          ]);
          if (subjectsResult.error) return { data: null, error: subjectsResult.error };
          if (gradesResult.error) return { data: null, error: gradesResult.error };
          return { data: { subjects: subjectsResult.data || [], grades: gradesResult.data || [] }, error: null };
        } catch (error) { return { data: null, error }; }
      },
      async addSubject(userId, name) {
        const normalizedName = normalizeName(name);
        if (!validUserId(userId)) return failure("Falta el usuario autenticado.");
        if (normalizedName.length < 1 || normalizedName.length > 60) return failure("El nombre de la materia debe tener entre 1 y 60 caracteres.");
        try { return await client.from("subjects").insert({ user_id: userId, name: normalizedName }).select(SUBJECT_COLUMNS).single(); }
        catch (error) { return { data: null, error }; }
      },
      async addGrade(userId, grade) {
        if (!validUserId(userId)) return failure("Falta el usuario autenticado.");
        const invalid = validateGrade(grade);
        if (invalid) return failure(invalid);
        const record = {
          user_id: userId, subject_id: String(grade.subjectId),
          value: Math.round((Number(grade.value) + Number.EPSILON) * 100) / 100,
          label: normalizeName(grade.label || ""), grade_date: grade.date,
          academic_year: String(grade.academicYear)
        };
        try { return await client.from("grades").insert(record).select(GRADE_COLUMNS).single(); }
        catch (error) { return { data: null, error }; }
      },
      async deleteSubject(userId, subjectId) {
        if (!validUserId(userId) || !validUserId(String(subjectId || ""))) return failure("Falta la materia o el usuario.");
        try {
          const result = await client.from("subjects").delete().eq("id", String(subjectId)).eq("user_id", userId).select("id");
          if (result.error) return { data: null, error: result.error };
          if (!result.data || result.data.length === 0) return failure("La materia no existe o no pertenece a esta cuenta.");
          return { data: true, error: null };
        } catch (error) { return { data: null, error }; }
      },
      async deleteGrade(userId, gradeId) {
        if (!validUserId(userId) || !validUserId(String(gradeId || ""))) return failure("Falta la nota o el usuario.");
        try {
          const result = await client.from("grades").delete().eq("id", String(gradeId)).eq("user_id", userId).select("id");
          if (result.error) return { data: null, error: result.error };
          if (!result.data || result.data.length === 0) return failure("La nota no existe o no pertenece a esta cuenta.");
          return { data: true, error: null };
        } catch (error) { return { data: null, error }; }
      },
      async updateSharingPreference(userId, enabled) {
        if (!validUserId(userId)) return failure("Falta el usuario autenticado.");
        try { return await client.from("profiles").update({ share_academic_averages: Boolean(enabled) }).eq("id", userId).select("id, share_academic_averages").single(); }
        catch (error) { return { data: null, error }; }
      },
      async searchProfilesByUsername(username) {
        const query = String(username || "").trim().toLowerCase();
        if (query.length < 3 || query.length > 24 || !/^[a-z0-9_]+$/.test(query)) return { data: [], error: null };
        try { return await client.rpc("search_profiles_by_username", { p_query: query }); }
        catch (error) { return { data: null, error }; }
      },
      async sendFriendRequest(senderId, recipientId) {
        if (!validUserId(senderId) || !validUserId(recipientId) || senderId === recipientId) return failure("No puedes enviarte una solicitud a ti mismo.");
        try { return await client.from("friend_requests").insert({ sender_id: senderId, recipient_id: recipientId, status: "pending" }).select("id, sender_id, recipient_id, status, created_at").single(); }
        catch (error) { return { data: null, error }; }
      },
      async listFriendRequests(userId) {
        if (!validUserId(userId)) return failure("Falta el usuario autenticado.");
        try { return await client.rpc("list_my_friend_requests"); }
        catch (error) { return { data: null, error }; }
      },
      async respondToFriendRequest(userId, requestId, status) {
        if (!validUserId(userId) || !validUserId(requestId)) return failure("Falta la solicitud o el usuario.");
        if (!["accepted", "rejected"].includes(status)) return failure("Respuesta de solicitud no válida.");
        try {
          const result = await client.from("friend_requests").update({ status }).eq("id", requestId).eq("recipient_id", userId).eq("status", "pending").select("id, sender_id, recipient_id, status, responded_at").maybeSingle();
          if (!result.error && !result.data) return failure("La solicitud ya fue respondida o no te pertenece.");
          return result;
        } catch (error) { return { data: null, error }; }
      },
      async listFriends(userId) {
        if (!validUserId(userId)) return failure("Falta el usuario autenticado.");
        try { return await client.rpc("list_my_friends"); }
        catch (error) { return { data: null, error }; }
      },
      async getSharedAcademicAverages(friendId) {
        if (!validUserId(friendId)) return failure("Selecciona un amigo válido.");
        try { return await client.rpc("get_shared_academic_averages", { p_friend_id: friendId }); }
        catch (error) { return { data: null, error }; }
      },
      async removeFriend(friendId) {
        if (!validUserId(friendId)) return failure("Selecciona un amigo válido.");
        try { return await client.rpc("remove_friend", { p_friend_id: friendId }); }
        catch (error) { return { data: null, error }; }
      }
    };
  }
  return { createService, validDate, validateGrade, normalizeName, YEAR_PATTERN };
});
