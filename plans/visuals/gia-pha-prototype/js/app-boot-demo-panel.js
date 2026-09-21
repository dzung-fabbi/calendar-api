/* Side panel (switch user, guided scenarios, API log, reset) + boot. */
(function (g) {
  const CLAN = "nguyen";
  const as = (uid) => { S.get().userId = uid; UI.scroll = {}; };
  // [label, handler]: each scenario jumps to the right screen as the right user.
  const TRIES = [
    ["Thêm con cho Minh Anh (cây riêng)", () => { UI.home("tree"); UI.go("pform", { mode: "add", kind: "child", anchor: S.get().fam.selfId || "p_anh" }); }],
    ["Đặt nhắc giỗ cho ông Bình", () => { UI.home("tree"); UI.go("pdetail", { id: "p_binh" }); }],
    ["Chú Dũng: người đã liên kết + khác biệt với họ", () => { UI.home("tree"); UI.go("pdetail", { id: "p_dung" }); }],
    ["Sửa cụ Khải trong họ → thành đề xuất", () => { as("u_anh"); UI.home("ctree", { clan: CLAN }); UI.go("cdetail", { clan: CLAN, id: "c_khai" }); }],
    ["Mời chú Dũng (vượt cấp → cần duyệt)", () => { as("u_anh"); UI.state.invPick = "c_dung"; UI.home("ctree", { clan: CLAN }); UI.go("cinvite", { clan: CLAN }); }],
    ["Đổi sang Trưởng họ: duyệt lời mời, xác minh", () => { as("u_hung"); UI.home("ctree", { clan: CLAN }); UI.go("cmembers", { clan: CLAN }); }],
    ["Trưởng chi 2 duyệt đề xuất của Tâm", () => { as("u_quang"); UI.home("ctree", { clan: CLAN }); UI.go("creview", { clan: CLAN }); }],
    ["Ghép cây của tôi với dòng họ", () => { as("u_anh"); UI.home("tree"); UI.go("cmatch", { clan: CLAN }); }],
  ];

  const Panel = {
    render() {
      const el = document.getElementById("panel"); if (!el) return;
      const st = S.get(), clan = st.clans[CLAN];
      const log = st.log.map((x) => `<div><span class="m ${x.method}">${x.method}</span><code>${UI.esc(x.path)}</code>
        <small>${UI.esc(x.body)}${x.result ? " → " + UI.esc(x.result) : ""}</small></div>`).join("") || '<div class="empty">Chưa có thao tác. Bấm thử trên điện thoại.</div>';
      el.innerHTML = `<h2>Bảng điều khiển demo</h2>
        <div><h3>Đang dùng với tư cách</h3>
          <select id="p_user" data-change="switchUser" aria-label="Người dùng">${clan.members.map((m) =>
            `<option value="${m.uid}" ${m.uid === st.userId ? "selected" : ""}>${UI.esc(m.name)} · ${Perm.roleLabel(m)}${m.person && !m.verified ? " (chờ xác minh)" : ""}</option>`).join("")}</select>
          <p class="note">Quyền trong dòng họ đổi theo người bạn chọn. Gia phả cá nhân luôn là của Minh Anh.</p></div>
        <div><h3>Thử các luồng</h3><ul class="tries">${TRIES.map(([l], i) => `<li><button data-act="try" data-i="${i}">${l}</button></li>`).join("")}</ul></div>
        <div><h3>API app sẽ gọi · mới nhất trước</h3><div class="log">${log}</div></div>
        <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="pbtn warn" data-act="resetDemo">${UI.state.resetArm ? "Bấm lần nữa để đặt lại" : "Đặt lại dữ liệu mẫu"}</button></div>
        <p class="note">Dữ liệu lưu trong trình duyệt này. Không gửi đi đâu.</p>`;
    },
  };

  Object.assign(UI.Actions, {
    try: (d) => TRIES[+d.i][1](),
    switchUser: (el) => { as(el.value); UI.render(); },
    resetDemo: () => {
      if (!UI.state.resetArm) { UI.state.resetArm = true; Panel.render(); setTimeout(() => { UI.state.resetArm = false; Panel.render(); }, 4000); return; }
      UI.state.resetArm = false; S.reset();
      Object.assign(UI.state, { root: null, zoom: 1, q: "", matchSel: {}, invPick: undefined, invRole: "viewer" });
      UI.scroll = {}; UI.home("tree"); UI.toast("Đã đặt lại dữ liệu mẫu.");
    },
  });

  g.Panel = Panel;
  S.load();
  UI.render();
  setInterval(() => { const s = document.querySelector("#app .status span"); if (s) { const d = new Date(); s.textContent = `${d.getHours()}:${Lunar.pad(d.getMinutes())}`; } }, 30000);
})(window);
