/* Shared clan: clan operations, tree with family scope, person detail, edit / propose / add-child form. */
(function (g) {
  const DAY = 86400000;
  const short = (p) => p.name.split(" ").slice(-2).join(" ");
  const rid = () => Math.random().toString(36).slice(2, 7);
  const EDIT_KEYS = ["name", "gender", "deceased", "birth", "lunarDeath", "note"];

  const ClanOps = {
    memberName: (clan, uid) => { const m = Perm.member(clan, uid); return m ? m.name : "Người dùng"; },
    age: (cr) => Math.floor((Date.now() - cr.createdAt) / DAY),
    expired: (cr) => cr.status === "pending" && ClanOps.age(cr) >= 30,
    createCR(clan, uid, o) {
      const cr = { id: "cr_" + rid(), by: uid, target: o.target || null, action: o.action, payload: o.payload, note: o.note || "",
        status: "pending", baseVersion: o.target ? clan.persons[o.target].version : null, createdAt: Date.now(), familyPersonId: o.familyPersonId || null };
      clan.crs.unshift(cr);
      S.api("POST", `/clans/${clan.id}/change-requests`, { action: o.action, target_person: cr.target, payload: o.payload, proposer_note: cr.note }, "201 · pending");
      return cr;
    },
    applyUpdate(clan, pid, payload) {
      const p = clan.persons[pid];
      Object.assign(p, JSON.parse(JSON.stringify(payload)));
      p.version += 1;
    },
    createPerson(clan, draft, fatherId, motherId) {
      const p = Mut.create(clan.persons, JSON.parse(JSON.stringify(draft)), "c_");
      p.fatherId = fatherId || null; p.motherId = motherId || null;
      return p;
    },
    /** Plan phase 5: shared fields edited in the personal tree go to the clan directly or as a proposal. */
    writeFromPersonal(l, keys, draft, uid) {
      const clan = S.get().clans[l.clanId], cp = clan.persons[l.cp], payload = {};
      keys.forEach((k) => { payload[k] = draft[k]; });
      const what = keys.map((k) => PersonForm.LABEL[k].toLowerCase()).join(", ");
      if (Perm.canEdit(clan, uid, l.cp)) {
        const v = cp.version;
        ClanOps.applyUpdate(clan, l.cp, payload);
        S.api("PATCH", `/clans/${clan.id}/persons/${l.cp}`, Object.assign({ version: v }, payload), "200 · version " + cp.version);
        return { i: "✓", t: clan.name, s: `Đã cập nhật ${what} (trong phạm vi của bạn)`, r: "applied" };
      }
      ClanOps.createCR(clan, uid, { action: "update_person", target: l.cp, payload, note: "Sửa từ gia phả cá nhân" });
      return { i: "⏳", t: clan.name, s: `${what[0].toUpperCase() + what.slice(1)} đã gửi thành đề xuất (ngoài phạm vi của bạn)`, r: "proposed" };
    },
  };
  g.ClanOps = ClanOps;

  const clanOf = (p) => S.get().clans[p.clan || "nguyen"];

  UI.Screens.ctree = (p) => {
    const st = S.get(), clan = clanOf(p), ps = clan.persons, uid = st.userId, m = Perm.member(clan, uid);
    const head = UI.bar(UI.esc(clan.name) + " ▾", { back: false, titleAct: "switcher",
      right: m ? `<button class="ic" data-act="goMembers" aria-label="Thành viên">👥${badge(adminCount(clan, uid))}</button><button class="ic" data-act="goReview" aria-label="Đề xuất">📥${badge(reviewCount(clan, uid))}</button>` : "" });
    if (!m) return head + `<div class="body"><div class="empty">Bạn chưa tham gia họ này.<div class="btns"><button class="btn pri" data-act="goJoin">Nhập mã mời</button></div></div></div>${UI.tabs("giapha")}`;
    const w = Perm.writable(clan, uid), me = m.person && ps[m.person];
    const marks = {};
    clan.members.forEach((x) => { if (x.person) marks[x.person] = x.verified ? "👤" : "⏳"; });
    clan.invites.forEach((i) => { if (i.person && !marks[i.person] && (i.status === "active" || i.status === "pending")) marks[i.person] = "✉"; });
    const root = G.lineageRoot(ps, me ? me.id : Object.keys(ps)[0]);
    const view = TreeView.render(ps, root, { self: me ? me.id : null, scope: w, marks, act: "cnode" });
    const hint = w === null ? "Bạn sửa được toàn bộ cây họ."
      : w.size ? `<i></i>${m.role === "editor" ? "Chi của bạn và gia đình bạn" : "Gia đình bạn"}: sửa trực tiếp. Người khác: gửi đề xuất.`
      : me ? "Bạn đang chờ xác minh: chưa sửa trực tiếp được, vẫn gửi đề xuất được." : "Bạn chưa chọn mình là ai trong cây nên chỉ gửi đề xuất được.";
    UI.after = (app) => {
      if (UI.scroll.ctree) return;
      const b = app.querySelector("#ctreeBody"), n = view.layout.nodes.find((x) => me && x.id === me.id) || view.layout.nodes[0];
      b.scrollLeft = n.x - b.clientWidth / 2 + 50; b.scrollTop = Math.max(0, n.y - b.clientHeight / 2);
      UI.scroll.ctree = [b.scrollLeft, b.scrollTop];
    };
    return head + `<div class="chips"><span class="chip on">${Perm.roleLabel(m)}${me ? " · " + UI.esc(short(me)) + (m.verified ? " ✓" : " ⏳") : ""}</span>
        <button class="chip" data-act="goReview">Đề xuất${reviewCount(clan, uid) ? " · " + reviewCount(clan, uid) : ""}</button>
        <button class="chip" data-act="goMembers">Thành viên · ${clan.members.length}</button></div>
      <div class="hint">${hint} · 👤 có tài khoản ⏳ chờ xác minh ✉ đã mời</div>
      <div class="body" data-keep="ctree" id="ctreeBody">${view.html}</div>
      ${Perm.canInvite(clan, uid) ? '<button class="fab" data-act="goInvite">＋ Mời người nhà</button>' : ""}${UI.tabs("giapha")}`;
  };
  const badge = (n) => (n ? `<span class="badge">${n}</span>` : "");
  const reviewCount = (clan, uid) => clan.crs.filter((c) => c.status === "pending" && !ClanOps.expired(c) && Perm.canReview(clan, uid, c)).length;
  const adminCount = (clan, uid) => clan.members.filter((x) => x.person && !x.verified && Perm.canVerify(clan, uid, x)).length +
    clan.invites.filter((i) => i.status === "pending" && Perm.canApproveInvite(clan, uid, i)).length;

  UI.Screens.cdetail = (p) => {
    const st = S.get(), clan = clanOf(p), ps = clan.persons, q = ps[p.id], uid = st.userId;
    if (!q) return UI.bar("") + '<div class="body"><div class="empty">Không tìm thấy người này.</div></div>';
    const m = Perm.member(clan, uid), can = m && Perm.canEdit(clan, uid, q.id);
    const claimed = clan.members.find((x) => x.person === q.id);
    const n = G.gio(q), ld = q.lunarDeath;
    const chips = (ids) => ids.map((x) => `<button data-act="cnode" data-id="${x}">${UI.esc(ps[x].name)}</button>`).join("");
    const rel = (l, ids) => (ids.length ? `<dt>${l}</dt><dd class="rel">${chips(ids)}</dd>` : "");
    const inMine = Object.entries(st.fam.links).find(([, l]) => l.clanId === clan.id && l.cp === q.id);
    return UI.bar("", { right: m ? `<button class="ic" data-act="cEdit" data-id="${q.id}" aria-label="${can ? "Sửa" : "Đề xuất sửa"}">✎</button>` : "" }) + `<div class="body">
      <div class="hero">${UI.av(q)}<h5>${UI.esc(q.name)}</h5><small>${G.years(q)}</small>
        <div class="tags">${q.deceased ? '<span class="tag dead">Đã mất</span>' : ""}${claimed ? `<span class="tag">${claimed.verified ? "👤 " + UI.esc(claimed.name) : "⏳ Chờ xác minh"}</span>` : ""}<span class="tag">Phiên bản ${q.version}</span></div></div>
      ${n ? `<div class="gio"><small>Giỗ · ${Lunar.lunarText(ld.d, ld.m)} âm lịch</small><div class="gb"><div><div class="big">${n.days === 0 ? "Hôm nay" : "Còn " + n.days + " ngày"}</div><small>${Lunar.solarText(n.date)}</small></div></div></div>` : ""}
      <div class="pad">
      ${m ? (can ? '<div class="hintbox">Người này trong phạm vi của bạn: sửa trực tiếp, có lịch sử để khôi phục.</div>'
        : '<div class="warnbox">Người này ngoài phạm vi của bạn. Sửa sẽ thành <b>đề xuất</b> gửi trưởng họ, Ban quản lý, biên tập viên duyệt.</div>') : ""}
      <dl class="kv"><dt>Ngày sinh</dt><dd>${q.birth ? q.birth.replace(/-/g, "/") : "—"}</dd>
        ${q.deceased ? `<dt>Ngày mất</dt><dd>${ld ? PersonForm.show("lunarDeath", ld) : "Không rõ"}</dd>` : ""}${q.note ? `<dt>Ghi chú</dt><dd>${UI.esc(q.note)}</dd>` : ""}
        ${rel("Cha · Mẹ", G.parents(ps, q.id))}${rel("Vợ / chồng", G.partners(ps, q.id))}${rel("Anh chị em", G.siblings(ps, q.id).map((x) => x.id))}${rel("Con", G.children(ps, q.id).map((x) => x.id))}</dl>
      ${inMine && uid === "u_anh" ? `<div class="hintbox">🔗 Liên kết với <b>${UI.esc(st.fam.persons[inMine[0]].name)}</b> trong gia phả của bạn.</div>` : ""}
      ${m ? `<div class="btns"><button class="btn ${can ? "ok" : ""}" data-act="cEdit" data-id="${q.id}">${can ? "Sửa" : "Đề xuất sửa"}</button>
        <button class="btn" data-act="cAddChild" data-id="${q.id}">${can ? "Thêm con" : "Đề xuất thêm con"}</button></div>
        ${!claimed && !q.deceased && Perm.canInvite(clan, uid) ? `<div class="btns"><button class="btn" data-act="goInvite" data-person="${q.id}">✉ Mời người này</button></div>` : ""}` : ""}
      </div></div>`;
  };

  UI.Screens.cform = (p) => {
    const clan = clanOf(p), ps = clan.persons, uid = S.get().userId;
    const adding = p.mode === "addchild", cur = adding ? { name: "", gender: "unknown", deceased: false } : ps[p.id];
    const propose = adding ? !Perm.canEdit(clan, uid, p.parent) : !Perm.canEdit(clan, uid, p.id);
    const title = adding ? `${propose ? "Đề xuất thêm con" : "Thêm con"} cho ${short(ps[p.parent])}` : `${propose ? "Đề xuất sửa" : "Sửa"} · ${short(cur)}`;
    let other = "";
    if (adding) {
      const c = Mut.otherParentCandidates(ps, p.parent);
      if (c.length >= 2) other = UI.field("Cha/mẹ còn lại", UI.select("f_other", [["", "Chưa rõ"], ...c.map((x) => [x, ps[x].name])], ""));
      else if (c.length === 1) other = `<div class="hintbox">Cha/mẹ còn lại: <b>${UI.esc(ps[c[0]].name)}</b> (tự điền)</div>`;
    }
    return UI.bar(UI.esc(title), { close: true }) + `<div class="body"><div class="form">
      ${propose ? `<div class="warnbox">${adding ? "Người cha/mẹ này" : "Người này"} nằm ngoài phạm vi của bạn. Thay đổi sẽ gửi tới ban quản lý họ duyệt; được kiểm tra ngay khi gửi.</div>` : ""}
      ${other}${PersonForm.fields(cur, { sourceNote: propose })}</div></div>
      <div class="savebar"><button class="btn pri" data-act="cSave">${propose ? "Gửi đề xuất" : "Lưu"}</button></div>`;
  };

  Object.assign(UI.Actions, {
    cnode: (d) => UI.go("cdetail", { clan: UI.top().p.clan || "nguyen", id: d.id }),
    cEdit: (d) => UI.go("cform", { clan: UI.top().p.clan || "nguyen", id: d.id, mode: "edit" }),
    cAddChild: (d) => UI.go("cform", { clan: UI.top().p.clan || "nguyen", parent: d.id, mode: "addchild" }),
    goReview: () => UI.go("creview", { clan: UI.top().p.clan || "nguyen" }),
    goMembers: () => UI.go("cmembers", { clan: UI.top().p.clan || "nguyen" }),
    goInvite: (d) => { UI.state.invPick = d.person || undefined; UI.go("cinvite", { clan: UI.top().p.clan || "nguyen" }); },
    cSave: () => {
      const p = UI.top().p, clan = clanOf(p), ps = clan.persons, uid = S.get().userId;
      const r = PersonForm.read();
      if (r.error) return UI.toast(r.error, "err");
      if (p.mode === "addchild") {
        const parent = ps[p.parent], slot = parent.gender === "female" ? "motherId" : "fatherId", otherSlot = slot === "fatherId" ? "motherId" : "fatherId";
        const c = Mut.otherParentCandidates(ps, p.parent), pick = UI.val("f_other") || (c.length === 1 ? c[0] : null);
        const edges = { [slot]: p.parent, [otherSlot]: pick };
        if (!Perm.canEdit(clan, uid, p.parent)) {
          ClanOps.createCR(clan, uid, { action: "create_person", payload: { person: r.draft, fatherId: edges.fatherId, motherId: edges.motherId }, note: r.source });
          UI.back(); return UI.toast("Đã gửi đề xuất thêm người. Chờ duyệt.");
        }
        ClanOps.createPerson(clan, r.draft, edges.fatherId, edges.motherId);
        S.api("POST", `/clans/${clan.id}/persons`, { ho_ten: r.draft.name, father_id: edges.fatherId, mother_id: edges.motherId }, "201");
        UI.back(); return UI.toast(`Đã thêm ${UI.esc(r.draft.name)} vào họ.`);
      }
      const cur = ps[p.id], keys = PersonForm.changed(cur, r.draft, EDIT_KEYS);
      if (!keys.length) return UI.toast("Chưa có gì thay đổi.", "err");
      const payload = {}; keys.forEach((k) => { payload[k] = r.draft[k]; });
      if (!Perm.canEdit(clan, uid, p.id)) {
        ClanOps.createCR(clan, uid, { action: "update_person", target: p.id, payload, note: r.source });
        UI.back(); return UI.toast("Đã gửi đề xuất. Trưởng họ, Ban quản lý hoặc biên tập viên sẽ duyệt.");
      }
      const v = cur.version;
      ClanOps.applyUpdate(clan, p.id, payload);
      S.api("PATCH", `/clans/${clan.id}/persons/${p.id}`, Object.assign({ version: v }, payload), "200 · version " + cur.version);
      UI.back(); UI.toast("Đã lưu. Ai đã liên kết người này sẽ thấy ngay.");
    },
  });
})(window);
