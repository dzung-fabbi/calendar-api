/* Personal person: detail, add/edit form, delete, giỗ reminder, detach link. */
(function () {
  const ME = "u_anh";
  const short = (p) => p.name.split(" ").slice(-2).join(" ");
  const KIND = { father: "Thêm cha", mother: "Thêm mẹ", spouse: "Thêm vợ/chồng", child: "Thêm con", sibling: "Thêm anh/chị/em" };
  const chip = (q, extra = "") => `<button data-act="detail" data-id="${q.id}">${UI.esc(q.name)}${extra ? ` <em>${extra}</em>` : ""}</button>`;

  /** Relations that differ between the personal tree and the linked clan (plan phase 4 diff; never auto-fixed). */
  function linkDiffs(id) {
    const st = S.get(), l = linkOf(id); if (!l) return [];
    const clan = st.clans[l.clanId], cp = clan.persons[l.cp]; if (!cp) return [];
    const p = st.fam.persons[id], out = [];
    const mapped = (pid) => (pid && st.fam.links[pid] ? st.fam.links[pid].cp : null);
    [["father", "cha"], ["mother", "mẹ"]].forEach(([slot, word]) => {
      const clanP = cp[slot + "Id"];
      if (clanP && mapped(p[slot + "Id"]) !== clanP) {
        const mine = p[slot + "Id"] && st.fam.persons[p[slot + "Id"]];
        out.push(`Họ ghi ${word} là <b>${UI.esc(clan.persons[clanP].name)}</b>; cây của bạn ${mine ? "ghi " + UI.esc(mine.name) : "chưa có"}.`);
      }
    });
    cp.spouses.forEach((s) => {
      const has = p.spouses.some((x) => mapped(x.id) === s.id);
      if (!has && clan.persons[s.id]) out.push(`Họ ghi ${s.type === "divorced" ? "vợ/chồng cũ (đã ly hôn)" : "vợ/chồng"} là <b>${UI.esc(clan.persons[s.id].name)}</b>; cây của bạn chưa có.`);
    });
    return out;
  }

  UI.Screens.pdetail = ({ id }) => {
    const st = S.get(), ps = famMap(), p = ps[id];
    if (!p) return UI.bar("") + '<div class="body"><div class="empty">Người này không còn trong cây.</div></div>';
    const l = linkOf(id), clan = l && st.clans[l.clanId];
    const n = G.gio(p), ev = st.events[id];
    const kids = G.children(ps, id), grand = kids.flatMap((c) => G.children(ps, c.id));
    const sibs = G.siblings(ps, id).map((q) => chip(q, (p.fatherId && q.fatherId && p.fatherId !== q.fatherId) || (p.motherId && q.motherId && p.motherId !== q.motherId) ? "khác cha/mẹ" : ""));
    const sp = G.spouses(ps, id).map((s) => chip(ps[s.id], s.type === "divorced" ? "đã ly hôn" : ""))
      .concat(G.coParents(ps, id).map((x) => chip(ps[x], "có con chung")));
    const rel = (label, arr) => (arr.length ? `<dt>${label}</dt><dd class="rel">${arr.join("")}</dd>` : "");
    const diffs = linkDiffs(id);
    const ld = p.lunarDeath, derived = Lunar.deathSolar(ld);
    return UI.bar("", { right: `<button class="ic" data-act="editPerson" data-id="${id}" aria-label="Sửa">✎</button>` }) + `<div class="body">
      <div class="hero">${UI.av(p)}<h5>${UI.esc(p.name)}</h5><small>${G.years(p)}</small>
        <div class="tags">${p.relationship ? `<span class="tag">${UI.esc(p.relationship)}</span>` : ""}${id === st.fam.selfId ? '<span class="tag">Tôi</span>' : ""}
        ${p.deceased ? '<span class="tag dead">Đã mất</span>' : ""}${clan ? `<span class="tag link">🔗 ${UI.esc(clan.name)}</span>` : ""}</div></div>
      ${n ? `<div class="gio"><small>Giỗ · ${Lunar.lunarText(ld.d, ld.m)} âm lịch</small><div class="gb"><div><div class="big">${n.days === 0 ? "Hôm nay" : "Còn " + n.days + " ngày"}</div><small>${Lunar.solarText(n.date)}</small></div>
        <button data-act="openGio" data-id="${id}">${ev ? "🔔 Nhắc trước " + ev.remind.map((x) => (x ? x + " ngày" : "khi diễn ra")).join(", ") : "＋ Đặt nhắc giỗ"}</button></div></div>` : ""}
      <div class="pad">
      ${p.deceased && !n ? '<div class="hintbox">Chưa có ngày và tháng mất âm lịch nên chưa nhắc giỗ được. Bấm ✎ để thêm.</div>' : ""}
      <dl class="kv">
        <dt>Ngày sinh</dt><dd>${p.birth ? p.birth.replace(/-/g, "/") : "—"}${p.birthTime ? " · " + p.birthTime : ""}</dd>
        ${p.deceased ? `<dt>Ngày mất</dt><dd>${ld ? PersonForm.show("lunarDeath", ld) + (derived ? `<br><small style="color:#6B736E">→ dương lịch ${derived.replace(/-/g, "/")}</small>` : "") : "Không rõ"}</dd>` : ""}
        ${p.note ? `<dt>Ghi chú</dt><dd>${UI.esc(p.note)}</dd>` : ""}
      </dl>
      <div class="sec">Quan hệ</div>
      <dl class="kv">${rel("Cha · Mẹ", G.parents(ps, id).map((x) => chip(ps[x])))}${rel("Vợ / chồng", sp)}${rel("Anh chị em", sibs)}${rel("Con", kids.map((c) => chip(c)))}${rel("Cháu", grand.map((c) => chip(c)))}</dl>
      ${G.isUnlinked(ps, id) ? '<div class="hintbox">Người này chưa nối với ai nên nằm ở nhóm “Chưa nối vào cây”. Bấm ✎ để chọn cha, mẹ hoặc vợ/chồng.</div>' : ""}
      <div class="sec">Dòng họ</div>
      ${clan ? `<div class="card">${UI.row({ title: `🔗 ${UI.esc(clan.name)}`, sub: "Tên, giới tính, ngày sinh, ngày mất đang đọc từ dòng họ" })}
          <div class="btns" style="margin:0 0 10px"><button class="btn" data-act="viewInClan" data-clan="${l.clanId}" data-cp="${l.cp}">Xem trong họ</button><button class="btn" data-act="askDetach" data-id="${id}">Tách</button></div></div>
        ${diffs.length ? `<div class="warnbox" style="margin-top:10px">Khác với cây họ (app không tự sửa):<br>${diffs.join("<br>")}</div>` : ""}`
        : `<div class="card">${UI.row({ act: "goMatch", lead: '<span class="g">⇄</span>', title: "Liên kết với dòng họ", sub: "Ghép người này với người tương ứng trong Họ Nguyễn Văn" })}</div>`}
      <div class="btns" style="margin-top:18px"><button class="btn" data-act="editPerson" data-id="${id}">Sửa</button><button class="btn" data-act="askDelete" data-id="${id}" style="color:#9E2A20">Xoá</button></div>
      </div></div>`;
  };

  function defaults(p, ps) {
    const a = ps[p.anchor], st = S.get(), fromSelf = p.anchor && p.anchor === st.fam.selfId;
    const g = { father: "male", mother: "female", spouse: a && a.gender === "male" ? "female" : a && a.gender === "female" ? "male" : "unknown" }[p.kind] || "unknown";
    const rel = fromSelf ? ({ father: "Cha", mother: "Mẹ", child: "Con", spouse: a.gender === "male" ? "Vợ" : a.gender === "female" ? "Chồng" : "" }[p.kind] || "") : "";
    return { name: "", gender: g, deceased: false, relationship: rel };
  }

  UI.Screens.pform = (p) => {
    const st = S.get(), ps = famMap(), editing = p.mode === "edit";
    const cur = editing ? ps[p.id] : defaults(p, ps);
    const l = editing && linkOf(p.id), clanName = l ? st.clans[l.clanId].name : null;
    const title = editing ? "Sửa · " + short(cur) : p.mode === "standalone" ? "Thêm người" : `${KIND[p.kind]} cho ${short(ps[p.anchor])}`;
    let extra = "";
    if (p.kind === "child") {
      const cands = Mut.otherParentCandidates(ps, p.anchor), word = ps[p.anchor].gender === "female" ? "Cha" : "Mẹ";
      if (cands.length >= 2) extra = UI.field(`${word} của con *`, UI.select("f_other", [["", "Chọn…"], ...cands.map((x) => [x, ps[x].name]), ["none", "Chưa rõ"]], ""));
      else if (cands.length === 1) extra = `<div class="hintbox">${word}: <b>${UI.esc(ps[cands[0]].name)}</b>, tự điền vì chỉ có một người.</div>`;
    }
    if (p.mode === "standalone") extra = '<div class="hintbox">Chọn “Quan hệ với bạn” để app tự nối vào cây. Cụ, cháu, chắt hoặc nhãn tự nhập thì người này vào nhóm “Chưa nối”.</div>';
    if (l) extra = `<div class="hintbox">Người này đã 🔗 liên kết với <b>${UI.esc(clanName)}</b>. Sửa phần có nhãn 🔗 sẽ ghi vào dòng họ nếu bạn có quyền, không thì thành đề xuất.</div>`;
    let relations = "";
    if (editing) {
      const desc = G.descendants(ps, cur.id), others = G.all(ps).filter((q) => q.id !== cur.id && !desc.has(q.id));
      const sibs = new Set(G.siblings(ps, cur.id).map((q) => q.id)), spIds = new Set(G.spouses(ps, cur.id).map((s) => s.id));
      const spCands = G.all(ps).filter((q) => q.id !== cur.id && !spIds.has(q.id) && !sibs.has(q.id) &&
        !(q.gender !== "unknown" && cur.gender !== "unknown" && q.gender === cur.gender));
      relations = `<div class="sec">Quan hệ</div>
        ${UI.field("Cha", UI.select("f_father", [["", "Chưa rõ"], ...others.filter((q) => q.gender !== "female").map((q) => [q.id, q.name])], cur.fatherId || ""))}
        ${UI.field("Mẹ", UI.select("f_mother", [["", "Chưa rõ"], ...others.filter((q) => q.gender !== "male").map((q) => [q.id, q.name])], cur.motherId || ""))}
        ${G.spouses(ps, cur.id).length ? `<div class="card">${G.spouses(ps, cur.id).map((s) => UI.row({ lead: UI.av(ps[s.id]), title: UI.esc(ps[s.id].name), sub: s.type === "divorced" ? "Đã ly hôn" : "Vợ/chồng",
          trail: `<button class="act" data-act="pUnlinkSpouse" data-a="${cur.id}" data-b="${s.id}">Gỡ</button>` })).join("")}</div>` : ""}
        ${UI.field("Thêm vợ/chồng từ danh sách", UI.select("f_newsp", [["", "Không thêm"], ...spCands.map((q) => [q.id, q.name])], ""))}
        ${UI.switch("f_self", st.fam.selfId === cur.id, "Đây là tôi", st.fam.selfId && st.fam.selfId !== cur.id ? "Đang là: " + UI.esc(ps[st.fam.selfId].name) : "Cây sẽ mở từ tổ của người này", st.fam.selfId && st.fam.selfId !== cur.id ? "disabled" : "")}`;
    }
    const more = !editing && (p.kind === "child" || p.kind === "sibling");
    return UI.bar(UI.esc(title), { close: true }) + `<div class="body"><div class="form">${extra}
      ${PersonForm.fields(cur, { personal: true, linkedTo: clanName })}${relations}</div></div>
      <div class="savebar">${more ? '<button class="btn" data-act="savePerson" data-more="1">Lưu và thêm tiếp</button>' : ""}<button class="btn pri" data-act="savePerson">Lưu</button></div>`;
  };

  function saveEdit(id, draft) {
    const st = S.get(), ps = famMap(), cur = ps[id], raw = st.fam.persons[id];
    const newF = UI.val("f_father") || null, newM = UI.val("f_mother") || null;
    for (const [slot, v] of [["father", newF], ["mother", newM]]) {
      if (v !== (cur[slot + "Id"] || null)) { const e = Rules.setParent(ps, id, slot, v); if (e) return UI.toast(e.message, "err"); }
    }
    const l = linkOf(id), rows = [];
    if (l) {
      ["relationship", "note", "birthTime"].forEach((k) => { raw[k] = draft[k]; });
      const keys = PersonForm.changed(cur, draft, SHARED);
      rows.push({ i: "✓", t: "Cây của tôi", s: "Đã lưu phần riêng: nhãn quan hệ, ghi chú, giờ sinh" });
      if (keys.length) rows.push(ClanOps.writeFromPersonal(l, keys, draft, ME));
      S.api("PATCH", `/v1/family/persons/${id}`, { changed: keys, clanVersions: { [l.clanId]: st.clans[l.clanId].persons[l.cp].version } }, "clanWrites: " + rows.slice(1).map((r) => r.r).join(", "));
    } else {
      Object.assign(raw, draft);
      S.api("PATCH", `/v1/family/persons/${id}`, { name: draft.name }, "200");
    }
    [["father", newF], ["mother", newM]].forEach(([slot, v]) => {
      if (v !== (raw[slot + "Id"] || null)) { raw[slot + "Id"] = v; S.api("POST", "/v1/family/relations/set-parent", { childId: id, slot, parentId: v }, "200"); }
    });
    const ns = UI.val("f_newsp");
    let warn = null;
    if (ns) {
      const e = Rules.spouse(ps, id, ns);
      if (e) return UI.toast(e.message, "err");
      warn = Rules.spouseWarning(ps, id, ns);
      Mut.linkSpouse(ps, id, ns, "married");
      S.api("POST", "/v1/family/relations/link-spouse", { aId: id, bId: ns, type: "married" }, warn ? "200 · warning SPOUSE_IS_ANCESTOR" : "200");
    }
    const wantSelf = UI.checked("f_self");
    if (wantSelf !== (st.fam.selfId === id) && !(st.fam.selfId && st.fam.selfId !== id)) {
      st.fam.selfId = wantSelf ? id : null; UI.state.root = null; UI.scroll.tree = null;
      S.api("PUT", "/v1/family/self", { personId: st.fam.selfId }, "200");
    }
    UI.back();
    if (rows.length > 1) UI.open("saveResult", { rows });
    else UI.toast(warn ? warn.message : "Đã lưu.");
  }

  UI.Overlays.saveResult = ({ rows }) => `<div class="sheet"><div class="grab"></div><h5>Đã lưu</h5>
    ${rows.map((r) => UI.row({ lead: `<span class="g">${r.i}</span>`, title: UI.esc(r.t), sub: r.s })).join("")}
    <div class="btns"><button class="btn ok" data-act="close">Xong</button></div></div>`;

  UI.Overlays.confirmDelete = ({ id }) => {
    const st = S.get(), ps = famMap(), p = ps[id], kids = G.children(ps, id);
    return `<div class="dialog" role="dialog"><h5>Xoá ${UI.esc(p.name)}?</h5>
      <p>Chỉ xoá người này.${kids.length ? ` <b>${kids.map((k) => UI.esc(short(k))).join(", ")}</b> vẫn giữ lại, chỉ để trống ô ${p.gender === "female" ? "mẹ" : "cha"}.` : ""} Quan hệ vợ chồng với người này được gỡ.</p>
      ${st.events[id] ? "<p>Nhắc giỗ vẫn còn trong tab Sự kiện.</p>" : ""}${linkOf(id) ? "<p>Người này trong dòng họ vẫn giữ nguyên.</p>" : ""}
      <div class="btns"><button class="btn" data-act="close">Huỷ</button><button class="btn pri" data-act="doDelete" data-id="${id}">Xoá</button></div></div>`;
  };

  UI.Overlays.gio = ({ id }) => {
    const st = S.get(), p = famMap()[id], ev = st.events[id], cur = ev ? ev.remind : [1];
    return `<div class="sheet"><div class="grab"></div><h5>Nhắc giỗ ${UI.esc(p.name)}</h5>
      <p class="note" style="margin:0 0 10px">Lặp hằng năm theo âm lịch: ${Lunar.lunarText(p.lunarDeath.d, p.lunarDeath.m)}. Tháng nhuận vẫn cúng tháng thường.</p>
      <div class="f"><label class="lb">Nhắc trước</label><div class="pills">${[[0, "Khi diễn ra"], [1, "1 ngày"], [3, "3 ngày"], [7, "7 ngày"]].map(([v, l]) =>
        `<label class="pill"><input type="checkbox" id="gr_${v}" ${cur.includes(v) ? "checked" : ""}><span>${l}</span></label>`).join("")}</div></div>
      <div class="btns">${ev ? `<button class="btn" data-act="removeGio" data-id="${id}">Tắt nhắc</button>` : ""}<button class="btn pri" data-act="saveGio" data-id="${id}">Lưu nhắc giỗ</button></div></div>`;
  };

  UI.Overlays.confirmDetach = ({ id }) => {
    const st = S.get(), l = linkOf(id);
    return `<div class="dialog" role="dialog"><h5>Tách khỏi ${UI.esc(st.clans[l.clanId].name)}?</h5>
      <p>Tên, giới tính, ngày sinh, ngày mất hiện tại của dòng họ sẽ được chép về cây của bạn. Sau đó hai bên độc lập, sửa bên này không ảnh hưởng bên kia.</p>
      <div class="btns"><button class="btn" data-act="close">Huỷ</button><button class="btn pri" data-act="doDetach" data-id="${id}">Tách</button></div></div>`;
  };

  Object.assign(UI.Actions, {
    detail: (d) => { UI.ov = null; UI.go("pdetail", { id: d.id }); },
    addRel: (d) => UI.go("pform", { mode: "add", kind: d.kind, anchor: d.id }),
    addStandalone: () => UI.go("pform", { mode: "standalone" }),
    editPerson: (d) => UI.go("pform", { mode: "edit", id: d.id }),
    savePerson: (d) => {
      const p = UI.top().p, st = S.get(), ps = famMap();
      const r = PersonForm.read({ personal: true });
      if (r.error) return UI.toast(r.error, "err");
      if (p.mode === "edit") return saveEdit(p.id, r.draft);
      if (p.mode === "standalone") {
        const np = Mut.create(ps, r.draft, "p_");
        const hint = autoLinkByLabel(ps, st.fam.selfId, ps[np.id]);
        S.api("POST", "/v1/family/persons", { name: r.draft.name, relationship: r.draft.relationship }, hint ? "linked: false" : "linked: true");
        UI.back(); UI.scroll.tree = null;
        return UI.toast(hint ? `Đã lưu ${UI.esc(r.draft.name)}. ${hint}` : `Đã thêm ${UI.esc(r.draft.name)} và nối vào cây.`);
      }
      const cands = p.kind === "child" ? Mut.otherParentCandidates(ps, p.anchor) : [];
      const other = UI.val("f_other");
      if (cands.length >= 2 && !other) return UI.toast("Chọn cha/mẹ còn lại của con (hoặc “Chưa rõ”).", "err");
      const res = Mut.addRelative(ps, p.anchor, p.kind, r.draft, other && other !== "none" ? other : null, "p_");
      if (res.error) return UI.toast(res.error.message, "err");
      S.api("POST", "/v1/family/relations/add-relative", { anchorId: p.anchor, kind: p.kind, person: { name: r.draft.name }, otherParentId: other && other !== "none" ? other : null }, "200 · persons[]");
      if (d.more) { UI.replace("pform", p); UI.toast(`Đã thêm ${UI.esc(r.draft.name)}. Nhập người tiếp theo.`); }
      else { UI.back(); UI.toast(`Đã thêm ${UI.esc(r.draft.name)}.`); }
    },
    pUnlinkSpouse: (d) => {
      Mut.unlinkSpouse(famMap(), d.a, d.b);
      S.api("POST", "/v1/family/relations/unlink-spouse", { aId: d.a, bId: d.b }, "200");
      UI.toast("Đã gỡ quan hệ vợ chồng ở cả hai phía.");
    },
    askDelete: (d) => UI.open("confirmDelete", { id: d.id }),
    doDelete: (d) => {
      const st = S.get(), ps = famMap(), name = ps[d.id].name;
      if (st.events[d.id]) Object.assign(st.events[d.id], { orphanName: name, lunarDeath: ps[d.id].lunarDeath });
      const detached = Mut.remove(ps, d.id);
      if (st.fam.selfId === d.id) st.fam.selfId = null;
      delete st.fam.links[d.id];
      S.api("DELETE", `/v1/family/persons/${d.id}`, null, `deleted · detachedFrom ${detached.length}`);
      UI.state.root = null; UI.scroll.tree = null;
      UI.home("tree"); UI.toast(`Đã xoá ${UI.esc(name)}. Con cháu vẫn giữ nguyên.`);
    },
    openGio: (d) => UI.open("gio", { id: d.id }),
    saveGio: (d) => {
      const remind = [0, 1, 3, 7].filter((v) => UI.checked("gr_" + v));
      if (!remind.length) return UI.toast("Chọn ít nhất một mốc nhắc.", "err");
      const st = S.get(), p = famMap()[d.id], isNew = !st.events[d.id];
      st.events[d.id] = { remind, createdAt: Date.now() };
      S.api(isNew ? "POST" : "PATCH", "/v1/events", { name: "Giỗ " + p.name, repeatType: 5, lunar: `${p.lunarDeath.d}/${p.lunarDeath.m}`, remindBefore: remind }, "200");
      if (isNew) S.api("PUT", `/v1/family/persons/${d.id}/gio-event`, { eventId: "evt_…" }, "200");
      UI.close(); UI.toast("Đã đặt nhắc giỗ. Xem trong tab Sự kiện.");
    },
    removeGio: (d) => { delete S.get().events[d.id]; S.api("DELETE", "/v1/events/{id}", null, "204"); UI.close(); UI.toast("Đã tắt nhắc giỗ."); },
    viewInClan: (d) => UI.go("cdetail", { clan: d.clan, id: d.cp }),
    askDetach: (d) => UI.open("confirmDetach", { id: d.id }),
    doDetach: (d) => {
      const st = S.get(), l = linkOf(d.id), cp = st.clans[l.clanId].persons[l.cp], raw = st.fam.persons[d.id];
      SHARED.forEach((k) => { raw[k] = JSON.parse(JSON.stringify(cp[k] == null ? null : cp[k])); });
      delete st.fam.links[d.id];
      S.api("DELETE", `/v1/family/links/${d.id}`, null, "204 · đã chép giá trị hiện tại về cây riêng");
      UI.close(); UI.toast("Đã tách. Người này giờ độc lập với dòng họ.");
    },
  });
})();
