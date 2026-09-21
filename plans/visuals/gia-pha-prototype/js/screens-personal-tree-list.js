/* Personal tree (GET /v1/family), person menu, list, events tab, calendar + profile tabs. */
(function () {
  const ME = "u_anh"; // the personal tree in this demo belongs to Nguyễn Minh Anh
  const short = (p) => p.name.split(" ").slice(-2).join(" ");
  const norm = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D").toLowerCase();
  const asOther = () => {
    const st = S.get();
    if (st.userId === ME) return "";
    const m = Perm.member(st.clans.nguyen, st.userId);
    return `<div class="banner">Bạn đang dùng với tư cách <b>${UI.esc(m ? m.name : st.userId)}</b>. Gia phả cá nhân trong bản demo là của Minh Anh.</div>`;
  };

  UI.Screens.tree = () => {
    const st = S.get(), ps = famMap(), list = G.all(ps);
    const head = UI.bar("Gia phả của tôi ▾", { back: false, titleAct: "switcher", right: '<button class="ic" data-act="goList" aria-label="Danh sách">☰</button>' });
    if (!list.length) {
      return head + `<div class="body"><div class="empty">Chưa có ai trong gia phả.<div class="btns"><button class="btn pri" data-act="addStandalone">Thêm chính bạn</button></div></div></div>` + UI.tabs("giapha");
    }
    const selfId = st.fam.selfId && ps[st.fam.selfId] ? st.fam.selfId : null;
    const roots = TreeView.rootOptions(ps);
    let root = UI.state.root;
    if (!root || !ps[root] || G.isUnlinked(ps, root)) root = selfId && !G.isUnlinked(ps, selfId) ? G.lineageRoot(ps, selfId) : roots[0];
    UI.state.root = root;
    const unlinked = list.filter((p) => G.isUnlinked(ps, p.id)).length;
    const chips = `<div class="chips">${root ? `<button class="chip on" data-act="chooseRoot">Nhà ${UI.esc(short(ps[root]))} ▾</button>` : ""}
      ${unlinked ? `<button class="chip warn" data-act="goList">Chưa nối vào cây · ${unlinked}</button>` : ""}</div>`;
    if (!root) return head + asOther() + chips + `<div class="body"><div class="empty">Chưa ai được nối với nhau. Bấm một người trong danh sách để thêm cha, mẹ hoặc con.</div></div>` + UI.tabs("giapha");
    const view = TreeView.render(ps, root, { self: selfId, showLinks: true });
    UI.after = (app) => {
      if (UI.scroll.tree) return;
      const b = app.querySelector("#treeBody"), n = view.layout.nodes.find((x) => x.id === selfId) || view.layout.nodes[0];
      b.scrollLeft = n.x * UI.state.zoom - b.clientWidth / 2 + 50;
      b.scrollTop = Math.max(0, n.y * UI.state.zoom - b.clientHeight / 2);
      UI.scroll.tree = [b.scrollLeft, b.scrollTop];
    };
    return head + asOther() + chips +
      (view.layout.hidden ? `<div class="hint">${view.layout.hidden} người không nằm trên nhánh này, đổi “Nhà …” để xem</div>` : "") +
      `<div class="body" data-keep="tree" id="treeBody"><div style="zoom:${UI.state.zoom}">${view.html}</div></div>
      <div class="zoom"><button data-act="zoom" data-d="0.15" aria-label="Phóng to">＋</button><button data-act="zoom" data-d="-0.15" aria-label="Thu nhỏ">－</button><button data-act="zoom" data-d="0" aria-label="Về giữa">⤢</button></div>
      <button class="fab" data-act="addStandalone">＋ Thêm người</button>${UI.tabs("giapha")}`;
  };

  UI.Overlays.personMenu = ({ id }) => {
    const ps = famMap(), p = ps[id];
    const kinds = [["father", "♂", "Thêm cha"], ["mother", "♀", "Thêm mẹ"], ["spouse", "⚭", "Thêm vợ / chồng"], ["child", "⇣", "Thêm con"], ["sibling", "⇄", "Thêm anh / chị / em"]];
    return `<div class="sheet"><div class="grab"></div>
      <div class="who">${UI.av(p)}<div><b>${UI.esc(p.name)}</b><small>${UI.esc([p.relationship, G.years(p), p.deceased ? "đã mất" : ""].filter(Boolean).join(" · "))}</small></div></div>
      ${UI.row({ act: "detail", data: `data-id="${id}"`, lead: '<span class="g">👁</span>', title: "Xem chi tiết" })}
      ${kinds.map(([k, i, l]) => {
        const b = Rules.addBlock(ps, id, k);
        return UI.row({ act: "addRel", data: `data-id="${id}" data-kind="${k}"`, disabled: !!b, lead: `<span class="g">${i}</span>`, title: l,
          sub: b ? b.message : (k === "sibling" ? "Dùng chung cha mẹ với " + UI.esc(short(p)) : "") });
      }).join("")}</div>`;
  };

  UI.Overlays.chooseRoot = () => {
    const ps = famMap();
    return `<div class="sheet"><div class="grab"></div><h5>Xem theo dòng</h5>${TreeView.rootOptions(ps).map((r) =>
      UI.row({ act: "setRoot", data: `data-id="${r}"`, lead: UI.av(ps[r]), title: "Nhà " + UI.esc(ps[r].name),
        sub: `${TreeView.layout(ps, r).nodes.length} người trên nhánh${r === UI.state.root ? " · đang xem" : ""}` })).join("")}</div>`;
  };

  UI.Overlays.switcher = () => {
    const st = S.get(), n = Object.keys(st.fam.persons).length, linked = Object.keys(st.fam.links).length;
    const clans = Object.values(st.clans).map((c) => {
      const m = Perm.member(c, st.userId), bound = m && m.person && c.persons[m.person];
      const who = !m ? "Chưa tham gia" : bound ? `Bạn là ${UI.esc(bound.name)}${m.verified ? " ✓" : " · chờ xác minh"}` : "Chưa chọn mình là ai";
      return UI.row({ act: "goClan", data: `data-id="${c.id}"`, lead: '<span class="av dead">N</span>', title: `${UI.esc(c.name)} · ${UI.esc(c.place)}`,
        sub: `${Object.keys(c.persons).length} người · ${c.members.length} thành viên · ${who}`,
        trail: `<span class="role ${m ? m.role : ""}">${Perm.roleLabel(m)}</span>` });
    }).join("");
    return `<div class="sheet"><div class="grab"></div><h5>Chọn gia phả</h5>
      ${UI.row({ act: "goPersonal", lead: '<span class="av male">🌳</span>', title: "Gia phả của tôi", sub: `${n} người · chỉ mình bạn xem · 🔗 ${linked} người đã liên kết` })}
      <div class="sec">Dòng họ</div>${clans}
      <div class="sec">Thêm</div>
      ${UI.row({ act: "goMatch", lead: '<span class="g">⇄</span>', title: "Ghép cây của tôi với dòng họ" })}
      ${UI.row({ act: "goJoin", lead: '<span class="g">⌨</span>', title: "Nhập mã mời" })}</div>`;
  };

  UI.Screens.list = () => {
    const ps = famMap(), q = norm(UI.state.q || "");
    const hit = (p) => !q || norm(p.name).includes(q);
    const all = G.all(ps).filter(hit).sort(G.byCreated);
    const gio = all.map((p) => ({ p, n: G.gio(p) })).filter((x) => x.n).sort((a, b) => a.n.days - b.n.days);
    const unl = all.filter((p) => G.isUnlinked(ps, p.id));
    const r = (p, trail) => UI.row({ act: "detail", data: `data-id="${p.id}"`, lead: UI.av(p), title: UI.esc(p.name) + (p._linked ? " 🔗" : ""),
      sub: UI.esc([p.relationship, G.years(p)].filter(Boolean).join(" · ")), trail });
    return UI.bar("Mọi người", { right: '<button class="ic" data-act="addStandalone" aria-label="Thêm người">＋</button>' }) +
      `<div class="chips" style="padding-bottom:10px"><input class="input" id="q" data-input="search" data-refocus="1" placeholder="⌕ Tìm theo tên" value="${UI.esc(UI.state.q || "")}" aria-label="Tìm theo tên"></div>
      <div class="body"><div class="list">
      ${gio.length ? `<div class="sec">Sắp giỗ</div>${gio.map(({ p, n }) => r(p, `<span class="cd">${n.days === 0 ? "Hôm nay" : n.days + " ngày"}</span>`)).join("")}` : ""}
      ${unl.length ? `<div class="sec">Chưa nối vào cây · ${unl.length}</div>${unl.map((p) => r(p)).join("")}` : ""}
      <div class="sec">Tất cả · ${all.length}</div>${all.map((p) => r(p)).join("") || '<div class="empty">Không tìm thấy ai.</div>'}
      </div></div>${UI.tabs("giapha")}`;
  };

  UI.Screens.events = () => {
    const st = S.get(), ps = famMap();
    // A reminder survives deleting its person (spec §8.4: event kept); show it under the saved name.
    const set = Object.keys(st.events).map((id) => {
      const e = st.events[id], p = ps[id] || (e.orphanName ? { id, name: e.orphanName + " (đã xoá khỏi cây)", deceased: true, lunarDeath: e.lunarDeath } : null);
      return p && G.hasGio(p) ? { p, n: G.gio(p), e, gone: !ps[id] } : null;
    }).filter(Boolean).sort((a, b) => a.n.days - b.n.days);
    const unset = G.all(ps).filter((p) => G.hasGio(p) && !st.events[p.id]);
    return UI.bar("Sự kiện", { back: false }) + `<div class="body"><div class="list">
      <div class="sec">Nhắc giỗ · lặp theo năm âm lịch</div>
      ${set.map(({ p, n, e, gone }) => UI.row({ act: gone ? null : "detail", data: `data-id="${p.id}"`, lead: '<span class="g">🔔</span>', title: "Giỗ " + UI.esc(p.name),
        sub: `${Lunar.lunarText(p.lunarDeath.d, p.lunarDeath.m)} · ${Lunar.solarText(n.date)} · nhắc trước ${e.remind.map((x) => (x ? x + " ngày" : "khi diễn ra")).join(", ")}`,
        trail: `<span class="cd">${n.days === 0 ? "Hôm nay" : n.days + " ngày"}</span>` })).join("") || '<div class="empty">Chưa đặt nhắc giỗ nào.</div>'}
      ${unset.length ? `<div class="sec">Có ngày giỗ, chưa đặt nhắc</div>${unset.map((p) => UI.row({ act: "detail", data: `data-id="${p.id}"`, lead: UI.av(p), title: UI.esc(p.name), sub: Lunar.lunarText(p.lunarDeath.d, p.lunarDeath.m) })).join("")}` : ""}
      </div></div>${UI.tabs("events")}`;
  };

  UI.Screens.cal = () => {
    const t = new Date(), [ld, lm, ly, leap] = Lunar.toLunar(t.getDate(), t.getMonth() + 1, t.getFullYear());
    const ps = famMap();
    const soon = G.all(ps).map((p) => ({ p, n: G.gio(p) })).filter((x) => x.n && x.n.days <= 60).sort((a, b) => a.n.days - b.n.days);
    return UI.bar("Lịch", { back: false }) + `<div class="body"><div class="pad">
      <div class="crd" style="text-align:center"><small style="color:#6B736E">${Lunar.solarText(t)}</small>
        <div style="font:700 44px/1.1 'Noto Serif',Georgia,serif">${t.getDate()}</div>
        <div>Âm lịch: ${Lunar.lunarText(ld, lm)}${leap ? " (nhuận)" : ""} năm ${ly}</div></div>
      <div class="sec">Giỗ trong 60 ngày tới</div>
      ${soon.map(({ p, n }) => UI.row({ act: "detail", data: `data-id="${p.id}"`, lead: UI.av(p), title: "Giỗ " + UI.esc(p.name), sub: Lunar.solarText(n.date), trail: `<span class="cd">${n.days} ngày</span>` })).join("") || '<div class="empty">Không có giỗ nào trong 60 ngày tới.</div>'}
      <p class="empty" style="padding:16px 0">Lịch tháng đầy đủ nằm ngoài phạm vi bản demo gia phả.</p></div></div>${UI.tabs("cal")}`;
  };

  UI.Screens.me = () => {
    const st = S.get(), m = Perm.member(st.clans.nguyen, st.userId);
    return UI.bar("Cá nhân", { back: false }) + `<div class="body"><div class="pad">
      <div class="who" style="padding-top:6px"><span class="av male">${UI.esc((m ? m.name : "?").split(" ").pop()[0])}</span><div><b>${UI.esc(m ? m.name : st.userId)}</b><small>${Perm.roleLabel(m)} · Họ Nguyễn Văn</small></div></div>
      <div class="sec">Gia phả</div>
      <div class="card">${UI.row({ title: "Gia phả đã lưu trên tài khoản", sub: "Đổi máy không mất; dùng được liên kết dòng họ", trail: '<span class="conf hi">Đã đồng bộ</span>' })}
      ${UI.row({ act: "importDemo", lead: '<span class="g">⇪</span>', title: "Mô phỏng: đưa gia phả từ máy cũ lên", sub: "Người dùng cũ lưu trên máy (phase 3)" })}</div>
      </div></div>${UI.tabs("me")}`;
  };

  Object.assign(UI.Actions, {
    switcher: () => UI.open("switcher"),
    goList: () => UI.go("list"),
    goPersonal: () => UI.home("tree"),
    goClan: (d) => UI.home("ctree", { clan: d.id }),
    goMatch: () => UI.go("cmatch", { clan: "nguyen" }),
    goJoin: () => UI.go("cjoin", {}),
    chooseRoot: () => UI.open("chooseRoot"),
    setRoot: (d) => { UI.state.root = d.id; UI.scroll.tree = null; UI.close(); },
    node: (d) => UI.open("personMenu", { id: d.id }),
    zoom: (d) => {
      const v = +d.d;
      UI.state.zoom = v === 0 ? 1 : Math.min(1.5, Math.max(0.55, UI.state.zoom + v));
      if (v === 0) UI.scroll.tree = null;
      UI.render();
    },
    search: (el) => { UI.state.q = el.value; UI.render(); },
    importDemo: () => {
      const n = Object.keys(S.get().fam.persons).length;
      S.api("PUT", "/v1/family/import", { importKey: "b3f1…", persons: `[${n} người]` }, `200 · idMap ${n} · skippedEdges 1 · warnings 1`);
      UI.toast(`Đã đưa ${n} người lên tài khoản. 1 quan hệ lỗi (vòng lặp) được bỏ qua và báo lại.`);
    },
  });
})();
