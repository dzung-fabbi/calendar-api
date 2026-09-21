/* Sample data. Shapes mirror the API:
   - fam   = GET /v1/family (+ links[] from the plan's phase 4)
   - clans = /clans/{id}: persons (version for optimistic lock), members, invites, change requests
   The demo "today" is the real device date; giỗ countdowns are computed live. */
(function (g) {
  let seq = 0;
  const DAY = 86400000;
  // Person factory: same fields for personal and clan persons (clan adds `version`).
  function P(id, name, gender, o = {}) {
    return {
      id, name, gender, deceased: !!o.deceased,
      fatherId: o.f || null, motherId: o.m || null,
      spouses: (o.sp || []).map((s) => (typeof s === "string" ? { id: s, type: "married" } : s)),
      birth: o.birth || null, birthTime: o.birthTime || null,
      lunarDeath: o.ld || null, relationship: o.rel || null, note: o.note || null,
      createdAt: Date.UTC(2024, 0, 1) + (seq++) * DAY, version: 1,
    };
  }
  function map(list) { const m = {}; list.forEach((p) => { m[p.id] = p; }); return m; }

  function seed() {
    seq = 0;
    const personal = map([
      P("p_khai", "Nguyễn Văn Khải", "male", { deceased: true, ld: { d: 20, m: 12, y: null }, sp: ["p_luu"], rel: "Cụ / Tổ tiên" }),
      P("p_luu", "Trần Thị Lựu", "female", { deceased: true, birth: "02-03-1918", ld: { d: 8, m: 3, y: 1998 }, sp: ["p_khai"], rel: "Cụ / Tổ tiên" }),
      P("p_binh", "Nguyễn Văn Bình", "male", { deceased: true, f: "p_khai", m: "p_luu", birth: "05-02-1940", ld: { d: 24, m: 8, y: 2010 }, sp: ["p_mai"], rel: "Ông nội", note: "Mộ ở quê nội, Lý Nhân" }),
      P("p_mai", "Lê Thị Mai", "female", { birth: "12-10-1943", sp: ["p_binh"], rel: "Bà nội" }),
      P("p_hoa", "Nguyễn Thị Hoa", "female", { f: "p_khai", m: "p_luu", birth: "20-06-1945", rel: "Bà cô" }),
      P("p_hung", "Nguyễn Văn Hùng", "male", { f: "p_binh", m: "p_mai", birth: "14-06-1968", sp: ["p_thu"], rel: "Cha" }),
      P("p_thu", "Phạm Thị Thu", "female", { birth: "21-04-1970", sp: ["p_hung"], rel: "Mẹ", note: "Thích hoa sen" }),
      P("p_dung", "Nguyễn Văn Dũng", "male", { f: "p_binh", m: "p_mai", birth: "03-11-1972", rel: "Chú" }),
      P("p_anh", "Nguyễn Minh Anh", "male", { f: "p_hung", m: "p_thu", birth: "09-09-1995", birthTime: "06:15", sp: ["p_chi"] }),
      P("p_chi", "Đỗ Lan Chi", "female", { birth: "17-01-1996", sp: ["p_anh"], rel: "Vợ" }),
      P("p_ha", "Nguyễn Thu Hà", "female", { f: "p_hung", m: "p_thu", birth: "30-07-1999", rel: "Em" }),
      P("p_khang", "Nguyễn Minh Khang", "male", { f: "p_anh", m: "p_chi", birth: "02-05-2022", rel: "Con" }),
      P("p_tu", "Bác Tư", "male", { deceased: true, rel: "Cụ / Tổ tiên", note: "Chưa rõ thuộc chi nào" }),
      P("p_bin", "Bé Bin", "female", { rel: "Cháu" }),
    ]);
    seq = 100;
    const clanPersons = map([
      P("c_khai", "Nguyễn Văn Khải", "male", { deceased: true, ld: { d: 20, m: 12, y: null }, sp: ["c_luu"] }),
      P("c_luu", "Trần Thị Lựu", "female", { deceased: true, birth: "02-03-1918", ld: { d: 8, m: 3, y: 1998 }, sp: ["c_khai"] }),
      P("c_thanh", "Nguyễn Văn Thành", "male", { deceased: true, f: "c_khai", m: "c_luu", birth: "11-08-1938", sp: ["c_yen"] }),
      P("c_yen", "Vũ Thị Yến", "female", { deceased: true, birth: "01-01-1941", ld: { d: 15, m: 1, y: 2005 }, sp: ["c_thanh"] }),
      P("c_binh", "Nguyễn Văn Bình", "male", { deceased: true, f: "c_khai", m: "c_luu", birth: "05-02-1940", ld: { d: 24, m: 8, y: 2010 }, sp: ["c_mai"] }),
      P("c_mai", "Lê Thị Mai", "female", { birth: "12-10-1943", sp: ["c_binh"] }),
      P("c_hoa", "Nguyễn Thị Hoa", "female", { f: "c_khai", m: "c_luu", birth: "20-06-1945" }),
      P("c_quang", "Nguyễn Văn Quang", "male", { f: "c_thanh", m: "c_yen", birth: "08-12-1965" }),
      P("c_tam", "Nguyễn Văn Tâm", "male", { f: "c_quang", birth: "19-05-1990" }),
      P("c_ty", "Nguyễn Văn Tý", "male", { f: "c_quang", birth: "23-02-1993" }),
      P("c_hung", "Nguyễn Văn Hùng", "male", { f: "c_binh", m: "c_mai", birth: "14-06-1968", sp: ["c_thu"] }),
      P("c_thu", "Phạm Thị Thu", "female", { birth: "21-04-1970", sp: ["c_hung"] }),
      P("c_dung", "Nguyễn Văn Dũng", "male", { f: "c_binh", m: "c_mai", birth: "03-11-1972", sp: [{ id: "c_nga", type: "divorced" }] }),
      P("c_nga", "Trần Thị Nga", "female", { birth: "10-10-1975", sp: [{ id: "c_dung", type: "divorced" }] }),
      P("c_anh", "Nguyễn Minh Anh", "male", { f: "c_hung", m: "c_thu", birth: "09-09-1995", sp: ["c_chi"] }),
      P("c_chi", "Đỗ Lan Chi", "female", { birth: "17-01-1996", sp: ["c_anh"] }),
    ]);
    const now = Date.now();
    return {
      userId: "u_anh",
      fam: {
        selfId: "p_anh",
        persons: personal,
        // personId -> { clanId, cp } : shared fields are read from the clan person (no sync).
        links: Object.fromEntries(["khai", "luu", "binh", "mai", "hoa", "hung", "thu", "dung", "anh"]
          .map((k) => ["p_" + k, { clanId: "nguyen", cp: "c_" + k }])),
      },
      // Giỗ reminders (Sự kiện with repeat = yearly lunar). personId -> { remind: [days before] }
      events: { p_binh: { remind: [1, 3], createdAt: now - 40 * DAY } },
      clans: {
        nguyen: {
          id: "nguyen", name: "Họ Nguyễn Văn", place: "Lý Nhân, Hà Nam",
          persons: clanPersons,
          members: [
            { uid: "u_hung", name: "Nguyễn Văn Hùng", role: "owner", person: "c_hung", verified: true },
            { uid: "u_loc", name: "Nguyễn Văn Lộc", role: "manager", person: null, verified: false },
            { uid: "u_quang", name: "Nguyễn Văn Quang", role: "editor", scopeRoot: "c_thanh", person: "c_quang", verified: true },
            { uid: "u_phuc", name: "Nguyễn Văn Phúc", role: "editor", person: null, verified: false },
            { uid: "u_anh", name: "Nguyễn Minh Anh", role: "viewer", person: "c_anh", verified: true },
            { uid: "u_tam", name: "Nguyễn Văn Tâm", role: "viewer", person: "c_tam", verified: false },
          ],
          invites: [
            { id: "inv_1", by: "u_quang", person: "c_ty", role: "viewer", status: "active", code: "NGV-TY93-Q2", note: "", createdAt: now - 3 * DAY },
          ],
          crs: [
            { id: "cr_1", by: "u_tam", target: "c_yen", action: "update_person", payload: { note: "Bà mất tại Nam Định" , birth: "01-03-1941" },
              note: "Theo sổ họ chi 2 do ông Quang giữ", status: "pending", baseVersion: 1, createdAt: now - 26 * DAY },
          ],
        },
      },
      log: [],
    };
  }
  g.SEED = seed;
})(window);
