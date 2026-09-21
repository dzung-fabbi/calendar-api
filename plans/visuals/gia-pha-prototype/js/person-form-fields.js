/* Person info fields shared by the personal form and the clan form. Only name is required (spec §9). */
(function (g) {
  const LABELS = ["Ông nội", "Bà nội", "Ông ngoại", "Bà ngoại", "Cha", "Mẹ", "Chồng", "Vợ", "Anh", "Chị", "Em", "Con", "Cụ / Tổ tiên", "Cháu", "Chắt", "Hậu duệ"];
  const days = [["", "Ngày"], ...Array.from({ length: 30 }, (_, i) => [String(i + 1), String(i + 1)])];
  const months = [["", "Tháng"], ...Array.from({ length: 12 }, (_, i) => [String(i + 1), Lunar.MONTHS[i + 1].replace("tháng ", "Th. ")])];

  /**
   * p: current values (or defaults). o: { personal: bool, linkedTo: "Họ Nguyễn Văn" | null, sourceNote: bool }
   */
  function fields(p, o = {}) {
    const ld = p.lunarDeath || {};
    const src = o.linkedTo ? `<span class="src">🔗 từ ${UI.esc(o.linkedTo)}</span>` : "";
    return `
      ${UI.field("Họ tên *", UI.input("f_name", p.name || "", { ph: "Ví dụ: Nguyễn Văn An", max: 60 }), src)}
      ${UI.field("Giới tính", UI.seg("f_gender", [["male", "Nam"], ["female", "Nữ"], ["unknown", "Chưa rõ"]], p.gender || "unknown"), src)}
      ${UI.field("Ngày sinh (dương lịch)", UI.input("f_birth", UI.toInputDate(p.birth), { type: "date", attrs: 'min="1800-01-01"' }), src)}
      ${o.personal ? UI.field("Giờ sinh", UI.input("f_btime", p.birthTime || "", { type: "time" })) : ""}
      ${UI.switch("f_dead", p.deceased, "Đã mất" + (o.linkedTo ? " " + src : ""), "Không cần nhớ ngày mất vẫn bật được", 'data-change="toggleDead"')}
      <div id="f_death_box" ${p.deceased ? "" : "hidden"}>
        ${UI.field("Ngày mất (âm lịch) · dùng để nhắc giỗ", `<div class="grid3">${UI.select("f_ld_d", days, ld.d ? String(ld.d) : "")}${UI.select("f_ld_m", months, ld.m ? String(ld.m) : "")}${UI.input("f_ld_y", ld.y || "", { type: "number", ph: "Năm (nếu nhớ)", attrs: 'min="1800" max="2100"' })}</div>`, src)}
        <div style="margin-top:8px">${UI.switch("f_ld_leap", !!ld.leap, "Tháng nhuận", "Giỗ vẫn cúng vào tháng thường")}</div>
      </div>
      ${o.personal ? `${UI.field("Quan hệ với bạn", UI.input("f_rel", p.relationship || "", { ph: "Chọn hoặc tự nhập", list: "rel_list", max: 24 }))}
        <datalist id="rel_list">${LABELS.map((l) => `<option value="${l}">`).join("")}</datalist>` : ""}
      ${o.sourceNote ? UI.field("Nguồn / lý do (người duyệt sẽ thấy)", `<textarea id="f_src" maxlength="500" placeholder="Ví dụ: theo bia mộ ở quê"></textarea>`) : ""}
      ${UI.field("Ghi chú", `<textarea id="f_note" maxlength="200" placeholder="Tối đa 200 ký tự">${UI.esc(p.note || "")}</textarea>`)}`;
  }

  /** Read the fields back. Returns { draft } or { error }. */
  function read(o = {}) {
    const name = UI.val("f_name").trim();
    if (!name) return { error: "Nhập họ tên trước khi lưu." };
    const deceased = UI.checked("f_dead");
    let lunarDeath = null;
    if (deceased) {
      const d = +UI.val("f_ld_d") || null, m = +UI.val("f_ld_m") || null, y = +UI.val("f_ld_y") || null;
      if (d || m || y) {
        if (!d || !m) return { error: "Ngày giỗ cần đủ ngày và tháng âm lịch (năm có thể bỏ trống)." };
        lunarDeath = { d, m, y };
        if (UI.checked("f_ld_leap")) lunarDeath.leap = true; // only stored when true, like the API
      }
    }
    const draft = {
      name: name.slice(0, 60), gender: UI.radio("f_gender") || "unknown", deceased,
      birth: UI.fromInputDate(UI.val("f_birth")), lunarDeath,
      note: UI.val("f_note").trim() || null,
    };
    if (o.personal) {
      draft.relationship = UI.val("f_rel").trim().slice(0, 24) || null;
      draft.birthTime = UI.val("f_btime") || null;
    }
    return { draft, source: UI.val("f_src").trim() };
  }

  /** Human text for a field value (used in diffs). */
  function show(k, v) {
    if (v == null || v === "") return "trống";
    if (k === "gender") return { male: "Nam", female: "Nữ", unknown: "Chưa rõ" }[v];
    if (k === "deceased") return v ? "Đã mất" : "Còn sống";
    if (k === "lunarDeath") return `${Lunar.lunarText(v.d, v.m)}${v.y ? " năm " + v.y : " (chưa rõ năm)"}${v.leap ? ", nhuận" : ""}`;
    if (k === "birth") return v.replace(/-/g, "/");
    return String(v);
  }
  const LABEL = { name: "Họ tên", gender: "Giới tính", deceased: "Tình trạng", birth: "Ngày sinh", lunarDeath: "Ngày mất (âm)", note: "Ghi chú" };
  const same = (a, b) => JSON.stringify(a == null ? null : a) === JSON.stringify(b == null ? null : b);
  /** Keys whose value differs between person p and draft d. */
  const changed = (p, d, keys) => keys.filter((k) => k in d && !same(p[k], d[k]));

  UI.Actions.toggleDead = (el) => { document.getElementById("f_death_box").hidden = !el.checked; };
  g.PersonForm = { fields, read, show, LABEL, changed, same };
})(window);
