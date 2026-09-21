/* Clan admin flows: review proposals, members & verification, invites (+ approval), join by code, match personal ↔ clan. */
(function () {
  const ME = "u_anh", DAY = 86400000;
  const rid = () => Math.random().toString(36).slice(2, 7);
  const code = () => "NGV-" + rid().toUpperCase().slice(0, 4) + "-" + rid().toUpperCase().slice(0, 2);
  const clanOf = (p) => S.get().clans[(p && p.clan) || "nguyen"];
  const norm = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D").toLowerCase().trim();
  const btns = (html) => `<div class="btns" style="margin-top:0">${html}</div>`;

  // ---------------- Review proposals (phase 2) ----------------
  UI.Screens.creview = (p) => {
    const clan = clanOf(p), uid = S.get().userId, tab = UI.state.crTab;
    const list = clan.crs.filter((c) => {
      const open = c.status === "pending" && !ClanOps.expired(c);
      if (tab === "mine") return c.by === uid;
      if (tab === "done") return !open && (Perm.canReview(clan, uid, c) || c.by === uid);
      return open && (Perm.canReview(clan, uid, c) || c.by === uid);
    });
    const tabBtn = (k, l) => `<button class="chip ${tab === k ? "on" : ""}" data-act="crTab" data-t="${k}">${l}</button>`;
    return UI.bar("Đề xuất thay đổi") + `<div class="chips">${tabBtn("pending", "Chờ duyệt")}${tabBtn("mine", "Của tôi")}${tabBtn("done", "Đã xử lý / hết hạn")}</div>
      <div class="body"><div class="list" style="display:grid;gap:10px">${list.map((c) => card(clan, uid, c)).join("") || '<div class="empty">Không có đề xuất nào ở đây.</div>'}</div></div>`;
  };
  function card(clan, uid, c) {
    const ps = clan.persons, t = c.target && ps[c.target], age = ClanOps.age(c);
    const who = UI.esc(ClanOps.memberName(clan, c.by));
    let head, body = "";
    if (c.action === "create_person") {
      const par = ps[c.payload.fatherId] || ps[c.payload.motherId];
      head = `<b>${who}</b> đề xuất thêm <b>${UI.esc(c.payload.person.name)}</b>${par ? " làm con của " + UI.esc(par.name) : ""}`;
    } else {
      head = `<b>${who}</b> đề xuất sửa <b>${UI.esc(t ? t.name : "người đã xoá")}</b>`;
      body = `<dl class="kv">${Object.keys(c.payload).map((k) => `<dt>${PersonForm.LABEL[k] || k}</dt><dd><span class="old">${UI.esc(PersonForm.show(k, t ? t[k] : null))}</span> → <span class="new">${UI.esc(PersonForm.show(k, c.payload[k]))}</span></dd>`).join("")}</dl>`;
    }
    const open = c.status === "pending" && !ClanOps.expired(c);
    const stale = open && t && t.version !== c.baseVersion;
    const status = open ? `còn ${30 - age} ngày trước khi hết hạn` : { approved: "Đã duyệt", rejected: "Bị từ chối", withdrawn: "Đã rút", pending: "Hết hạn (30 ngày)" }[c.status];
    const actions = !open ? "" : Perm.canReview(clan, uid, c)
      ? btns(`<button class="btn" data-act="crReject" data-id="${c.id}">Từ chối</button><button class="btn ok" data-act="crApprove" data-id="${c.id}">Duyệt</button>`)
      : c.by === uid ? btns(`<button class="btn" data-act="crWithdraw" data-id="${c.id}">Rút lại</button>`) : "";
    return `<div class="crd"><div>${head}<br><small style="color:#6B736E">${age === 0 ? "Hôm nay" : age + " ngày trước"} · ${status}${c.reviewer ? " · " + UI.esc(ClanOps.memberName(clan, c.reviewer)) : ""}</small></div>
      ${body}${c.note ? `<div class="hintbox">Nguồn: ${UI.esc(c.note)}</div>` : ""}
      ${stale ? `<div class="warnbox">${UI.esc(t.name)} đã được sửa sau khi đề xuất này được gửi. Xem lại trước khi duyệt.</div>` : ""}${actions}</div>`;
  }
  UI.Overlays.confirmStale = ({ id }) => `<div class="dialog" role="dialog"><h5>Đề xuất đã cũ</h5>
    <p>Người này đã được sửa sau khi đề xuất được gửi. Duyệt sẽ ghi đè giá trị mới hơn bằng giá trị trong đề xuất.</p>
    <div class="btns"><button class="btn" data-act="close">Để xem lại</button><button class="btn pri" data-act="crApprove" data-id="${id}" data-force="1">Vẫn duyệt</button></div></div>`;

  // ---------------- Members, verification, invite approval (phases 1, 6) ----------------
  UI.Screens.cmembers = (p) => {
    const clan = clanOf(p), uid = S.get().userId, ps = clan.persons, owner = Perm.isOwner(clan, uid);
    const pendV = clan.members.filter((m) => m.person && !m.verified);
    const pendI = clan.invites.filter((i) => i.status === "pending" && (Perm.canApproveInvite(clan, uid, i) || i.by === uid || Perm.isOwner(clan, uid)));
    const mine = clan.invites.filter((i) => i.by === uid && i.status === "active");
    const pname = (id) => (id && ps[id] ? UI.esc(ps[id].name) : "người chưa gắn");
    return UI.bar("Thành viên", { right: Perm.canInvite(clan, uid) ? '<button class="ic" data-act="goInvite" aria-label="Mời">＋</button>' : "" }) + `<div class="body"><div class="list">
      ${pendV.length ? `<div class="sec">Chờ xác minh · ${pendV.length}</div>${pendV.map((m) => `<div class="crd"><div><b>${UI.esc(m.name)}</b> tự nhận là <b>${pname(m.person)}</b></div>
        ${Perm.canVerify(clan, uid, m) ? btns(`<button class="btn" data-act="mReject" data-uid="${m.uid}">Từ chối</button><button class="btn ok" data-act="mVerify" data-uid="${m.uid}">Xác minh</button>`)
          : '<small style="color:#6B736E">Trưởng họ, Ban quản lý hoặc trưởng chi của người này sẽ xác minh.</small>'}</div>`).join("")}` : ""}
      ${pendI.length ? `<div class="sec">Lời mời chờ duyệt · ${pendI.length}</div>${pendI.map((i) => `<div class="crd"><div><b>${UI.esc(ClanOps.memberName(clan, i.by))}</b> mời <b>${pname(i.person)}</b> · ${i.role === "editor" ? "Biên tập viên" : "Thành viên"}${i.note ? `<br><small style="color:#6B736E">“${UI.esc(i.note)}”</small>` : ""}</div>
        ${Perm.canApproveInvite(clan, uid, i) ? btns(`<button class="btn" data-act="invReject" data-id="${i.id}">Từ chối</button><button class="btn ok" data-act="invApprove" data-id="${i.id}">Duyệt lời mời</button>`)
          : `<small style="color:#6B736E">${i.role === "editor" ? "Chỉ trưởng họ duyệt lời mời Biên tập viên." : "Chờ trưởng họ hoặc Ban quản lý duyệt."}</small>`}</div>`).join("")}` : ""}
      ${mine.length ? `<div class="sec">Lời mời của tôi · còn hiệu lực</div><div class="card">${mine.map((i) => UI.row({ lead: '<span class="g">✉</span>', title: pname(i.person), sub: "Mã " + i.code,
        trail: `<button class="act" data-act="openAsInvitee" data-code="${i.code}">Mở như người nhận</button>` })).join("")}</div>` : ""}
      <div class="sec">Thành viên · ${clan.members.length}</div><div class="card">${clan.members.map((m) => UI.row({ lead: `<span class="av male">${UI.esc(m.name.split(" ").pop()[0])}</span>`,
        title: UI.esc(m.name) + (m.uid === uid ? " (bạn)" : ""),
        sub: (m.person ? "Là " + pname(m.person) + (m.verified ? " ✓" : " · chờ xác minh") : "Chưa chọn mình là ai") + (m.scopeRoot ? " · chi của " + pname(m.scopeRoot) : ""),
        trail: owner && m.uid !== uid && m.role !== "owner"
          ? UI.select("role_" + m.uid, [["manager", "Ban quản lý"], ["editor", "Biên tập"], ["viewer", "Thành viên"]], m.role, `data-change="setRole" data-uid="${m.uid}" aria-label="Vai trò" style="width:auto;padding:4px 6px;font-size:12px"`)
          : `<span class="role ${m.role}">${Perm.roleLabel(m)}</span>` })).join("")}</div>
      ${owner ? '<p class="note">Chỉ trưởng họ đổi được vai trò. Ban quản lý duyệt thay trưởng họ: lời mời thành viên, xác minh, đề xuất.</p>' : ""}
      </div></div>`;
  };

  // ---------------- Invite (phase 1: members invite their family; beyond family needs approval) ----------------
  UI.Screens.cinvite = (p) => {
    const clan = clanOf(p), uid = S.get().userId, ps = clan.persons;
    if (!Perm.canInvite(clan, uid)) return UI.bar("Mời vào họ", { close: true }) + '<div class="body"><div class="empty">Bạn cần được xác minh là ai trong cây trước khi mời người khác.</div></div>';
    const busy = new Set([...clan.members.map((m) => m.person), ...clan.invites.filter((i) => i.status !== "rejected" && i.status !== "used").map((i) => i.person)].filter(Boolean));
    const role = UI.state.invRole || "viewer";
    const cands = Object.values(ps).filter((q) => !q.deceased && !busy.has(q.id))
      .sort((a, b) => (Perm.canEdit(clan, uid, b.id) - Perm.canEdit(clan, uid, a.id)) || G.byCreated(a, b));
    const pick = UI.state.invPick === undefined ? (cands[0] ? cands[0].id : "") : UI.state.invPick;
    const st = (id) => Perm.inviteStatus(clan, uid, id || null, role);
    const tag = (s) => `<span class="conf ${s === "active" ? "hi" : "lo"}">${s === "active" ? "Gửi ngay" : "Cần duyệt"}</span>`;
    const opt = (id, title, sub) => UI.row({ act: "invPick", data: `data-id="${id}"`, lead: `<span class="radio" style="width:18px;height:18px;border-radius:50%;border:${pick === id ? "5px solid #9E2A20" : "2px solid #C4C8C2"};flex:none"></span>`, title, sub, trail: tag(st(id)) });
    const now = st(pick);
    return UI.bar("Mời vào họ", { close: true }) + `<div class="body"><div class="form">
      <div class="f"><label class="lb">Mời ai?</label><div class="card">
        ${cands.map((q) => opt(q.id, UI.esc(q.name), Perm.canEdit(clan, uid, q.id) ? "Trong phạm vi của bạn" : "Ngoài phạm vi của bạn")).join("")}
        ${opt("", "Không gắn người", "Người được mời tự chọn mình trong cây")}</div></div>
      ${UI.field("Quyền", UI.seg("f_role", [["viewer", "Thành viên"], ["editor", "Biên tập viên"]], role).replace(/<input /g, '<input data-change="invRole" '))}
      ${now === "active" ? '<div class="hintbox">Có link ngay. Người nhận bấm link là vào đúng vị trí và được xác minh.</div>'
        : `<div class="warnbox">${role === "editor" ? "Mời làm Biên tập viên: chỉ <b>trưởng họ</b> duyệt." : "Ngoài phạm vi của bạn nên cần <b>trưởng họ hoặc Ban quản lý</b> duyệt."} Chưa có link cho tới khi được duyệt.</div>`}
      ${UI.field(now === "active" ? "Lời nhắn (tuỳ chọn)" : "Lời nhắn cho người duyệt", UI.input("f_invnote", "", { ph: "Ví dụ: chú ở Sài Gòn, chưa ai mời", max: 120 }))}
      </div></div><div class="savebar"><button class="btn pri" data-act="invSend" data-pick="${pick}">${now === "active" ? "Tạo link mời" : "Gửi duyệt"}</button></div>`;
  };
  UI.Overlays.inviteReady = ({ code: c }) => `<div class="sheet"><div class="grab"></div><h5>Link mời đã sẵn sàng</h5>
    <div class="qr" aria-label="Mã QR mẫu"></div><div class="code">${c}</div>
    <div class="btns"><button class="btn" data-act="fakeShare">Sao chép link</button><button class="btn pri" data-act="fakeShare">Gửi qua Zalo</button></div>
    <div class="btns"><button class="btn ok" data-act="openAsInvitee" data-code="${c}">Mở link như người được mời</button></div></div>`;

  // ---------------- Join by code ----------------
  const findInvite = (c) => { for (const clan of Object.values(S.get().clans)) { const i = clan.invites.find((x) => x.code === c && x.status === "active"); if (i) return { clan, i }; } return null; };
  UI.Screens.cjoin = (p) => {
    const hit = p.code ? findInvite(p.code) : null;
    let body = "";
    if (p.code && !hit) body = '<div class="errbox">Mã không đúng, đã dùng, hoặc chưa được duyệt.</div>';
    if (hit) {
      const { clan, i } = hit, q = i.person && clan.persons[i.person];
      const free = Object.values(clan.persons).filter((x) => !x.deceased && !clan.members.some((m) => m.person === x.id));
      body = `<div class="crd" style="background:linear-gradient(160deg,#1F3A33,#2E6B5B);color:#EAF4F0;text-align:center"><small>${UI.esc(ClanOps.memberName(clan, i.by))} mời bạn vào</small>
        <div style="font:700 22px 'Noto Serif',Georgia,serif">${UI.esc(clan.name)}</div><small>${UI.esc(clan.place)} · ${Object.keys(clan.persons).length} người · ${clan.members.length} thành viên</small></div>
        ${q && !p.notMe ? `<div class="sec">Bạn là người này trong cây?</div><div class="card">${UI.row({ lead: UI.av(q), title: `<b>${UI.esc(q.name)}</b>`, sub: G.years(q) })}</div>
          <div class="hintbox">Xác nhận xong bạn được xác minh ngay, sửa trực tiếp được thông tin của mình, vợ/chồng, cha mẹ, con cháu.</div>
          ${btns(`<button class="btn" data-act="joinNotMe">Không phải tôi</button><button class="btn pri" data-act="joinAs" data-code="${i.code}">Đúng, là tôi</button>`)}`
        : `${UI.field("Bạn là ai trong cây?", UI.select("f_claim", [["", "Chưa chọn (chỉ xem)"], ...free.map((x) => [x.id, x.name])], ""))}
          <div class="warnbox">Tự chọn thì cần trưởng họ, Ban quản lý hoặc trưởng chi xác minh trước khi được sửa.</div>
          ${btns(`<button class="btn pri" data-act="joinClaim" data-code="${i.code}">Vào họ</button>`)}`}`;
    }
    return UI.bar("Tham gia dòng họ", { close: true }) + `<div class="body"><div class="form">
      ${UI.field("Mã mời", `<div style="display:flex;gap:8px">${UI.input("f_code", p.code || "", { ph: "NGV-XXXX-XX" })}<button class="btn ok" style="flex:none;padding:10px 14px" data-act="joinLookup">Kiểm tra</button></div>`)}
      ${body}</div></div>`;
  };

  // ---------------- Match personal ↔ clan (phase 4) ----------------
  function matchData(clan) {
    const st = S.get(), fam = st.fam, fp = famMap(), cps = clan.persons;
    const toCp = (pid) => (pid && fam.links[pid] && fam.links[pid].clanId === clan.id ? fam.links[pid].cp : null);
    const linkedCp = new Set(Object.values(fam.links).filter((l) => l.clanId === clan.id).map((l) => l.cp));
    const unP = Object.keys(fam.persons).filter((id) => !fam.links[id]), unC = Object.keys(cps).filter((id) => !linkedCp.has(id));
    const sug = [];
    unP.forEach((pid) => {
      const p = fp[pid];
      let best = null;
      unC.forEach((cid) => {
        const q = cps[cid];
        if (norm(p.name) !== norm(q.name)) return;
        const why = (p.fatherId && toCp(p.fatherId) && toCp(p.fatherId) === q.fatherId) ? "Cùng cha ở cả hai cây"
          : (p.motherId && toCp(p.motherId) && toCp(p.motherId) === q.motherId) ? "Cùng mẹ ở cả hai cây"
          : G.spouses(fp, pid).some((s) => toCp(s.id) && q.spouses.some((x) => x.id === toCp(s.id))) ? "Cùng vợ/chồng ở cả hai cây"
          : G.children(fp, pid).some((c) => toCp(c.id) && [cps[toCp(c.id)].fatherId, cps[toCp(c.id)].motherId].includes(cid)) ? "Cùng con ở cả hai cây" : null;
        if (why) best = { pid, cid, hi: true, why };
        else if (!best && p.birth && q.birth && p.birth.slice(-4) === q.birth.slice(-4)) best = { pid, cid, hi: false, why: "Trùng tên và năm sinh, chưa rõ quan hệ" };
      });
      if (best) sug.push(best);
    });
    const sugP = new Set(sug.map((s) => s.pid)), sugC = new Set(sug.map((s) => s.cid));
    const give = unP.filter((pid) => !sugP.has(pid) && (toCp(fam.persons[pid].fatherId) || toCp(fam.persons[pid].motherId)));
    const take = unC.filter((cid) => !sugC.has(cid) && ([cps[cid].fatherId, cps[cid].motherId].some((x) => linkedCp.has(x)) || cps[cid].spouses.some((s) => linkedCp.has(s.id))));
    return { sug, give, take, toCp, fp, cps };
  }
  UI.Screens.cmatch = (p) => {
    const st = S.get(), clan = clanOf(p), md = matchData(clan), sel = UI.state.matchSel;
    const on = (s) => { const k = s.pid + "|" + s.cid; return k in sel ? sel[k] : s.hi; };
    const nSel = md.sug.filter(on).length;
    const par = (pid) => { const r = st.fam.persons[pid]; return md.toCp(r.fatherId) || md.toCp(r.motherId); };
    return UI.bar("Ghép với " + UI.esc(clan.name), { close: true }) +
      (st.userId !== ME ? '<div class="banner">Gia phả cá nhân trong demo là của Minh Anh; thao tác ở đây dùng quyền của Minh Anh.</div>' : "") +
      `<div class="body"><div class="list">
      <div class="hintbox" style="margin-top:4px">So sánh cây của bạn với ${UI.esc(clan.name)}. Không ghép tự động: bạn xác nhận từng cặp. Chỉ trùng tên thì phải trùng cả năm sinh.</div>
      <div class="sec">Có thể là cùng một người · ${md.sug.length}</div>
      ${md.sug.map((s) => UI.row({ act: "matchToggle", data: `data-k="${s.pid}|${s.cid}" data-v="${on(s) ? 0 : 1}"`,
        lead: `<span class="g">${on(s) ? "☑" : "☐"}</span>`, title: `${UI.esc(md.fp[s.pid].name)} ⇄ ${UI.esc(md.cps[s.cid].name)}`, sub: s.why,
        trail: `<span class="conf ${s.hi ? "hi" : "lo"}">${s.hi ? "Chắc" : "Có thể"}</span>` })).join("") || '<p class="note">Không có gợi ý mới.</p>'}
      ${md.give.length ? `<div class="sec">Bạn có, họ chưa có · ${md.give.length}</div>${md.give.map((pid) => UI.row({ lead: UI.av(md.fp[pid]), title: UI.esc(md.fp[pid].name),
        sub: Perm.canEdit(clan, ME, par(pid)) ? "Trong phạm vi của bạn: thêm thẳng vào họ" : "Ngoài phạm vi: gửi đề xuất",
        trail: `<button class="act" data-act="contribute" data-id="${pid}">Đóng góp</button>` })).join("")}` : ""}
      ${md.take.length ? `<div class="sec">Họ có, bạn chưa có · ${md.take.length}</div>${md.take.map((cid) => UI.row({ lead: UI.av(md.cps[cid]), title: UI.esc(md.cps[cid].name), sub: G.years(md.cps[cid]),
        trail: `<button class="act" data-act="importCp" data-id="${cid}">Nhận về</button>` })).join("")}` : ""}
      </div></div><div class="savebar"><button class="btn pri" data-act="matchLink" ${nSel ? "" : "disabled"}>Liên kết ${nSel} cặp đã chọn</button></div>`;
  };

  // ---------------- Actions ----------------
  const cur = () => clanOf(UI.top().p);
  Object.assign(UI.Actions, {
    crTab: (d) => { UI.state.crTab = d.t; UI.render(); },
    crApprove: (d) => {
      const clan = cur(), c = clan.crs.find((x) => x.id === d.id), t = c.target && clan.persons[c.target];
      if (t && t.version !== c.baseVersion && !d.force) return UI.open("confirmStale", { id: c.id });
      if (c.action === "update_person") ClanOps.applyUpdate(clan, c.target, c.payload);
      if (c.action === "create_person") {
        const np = ClanOps.createPerson(clan, c.payload.person, c.payload.fatherId, c.payload.motherId);
        if (c.familyPersonId && S.get().fam.persons[c.familyPersonId]) S.get().fam.links[c.familyPersonId] = { clanId: clan.id, cp: np.id };
      }
      Object.assign(c, { status: "approved", reviewer: S.get().userId });
      S.api("POST", `/clans/${clan.id}/change-requests/${c.id}/approve`, d.force ? { override_stale: true } : null, "200 · revision ghi người duyệt");
      UI.close(); UI.toast("Đã duyệt và áp dụng. Người gửi nhận thông báo.");
    },
    crReject: (d) => {
      const clan = cur(), c = clan.crs.find((x) => x.id === d.id);
      Object.assign(c, { status: "rejected", reviewer: S.get().userId });
      S.api("POST", `/clans/${clan.id}/change-requests/${c.id}/reject`, { note: "" }, "200"); UI.toast("Đã từ chối. Người gửi nhận thông báo.");
    },
    crWithdraw: (d) => {
      const clan = cur(), c = clan.crs.find((x) => x.id === d.id); c.status = "withdrawn";
      S.api("DELETE", `/clans/${clan.id}/change-requests/${c.id}`, null, "204"); UI.toast("Đã rút đề xuất.");
    },
    mVerify: (d) => {
      const clan = cur(), m = Perm.member(clan, d.uid); m.verified = true;
      S.api("POST", `/clans/${clan.id}/members/${d.uid}/verify`, null, "200"); UI.toast(`Đã xác minh ${UI.esc(m.name)}. Người này sửa được gia đình mình.`);
    },
    mReject: (d) => {
      const clan = cur(), m = Perm.member(clan, d.uid); m.person = null; m.verified = false;
      S.api("DELETE", `/clans/${clan.id}/members/${d.uid}/verify`, null, "204"); UI.toast("Đã từ chối và gỡ việc tự nhận.");
    },
    setRole: (el) => {
      const clan = cur(), m = Perm.member(clan, el.dataset.uid); m.role = el.value; if (m.role !== "editor") delete m.scopeRoot;
      S.api("PATCH", `/clans/${clan.id}/members/${m.uid}`, { role: m.role }, "200"); UI.toast(`${UI.esc(m.name)} giờ là ${Perm.roleLabel(m)}.`);
    },
    invPick: (d) => { UI.state.invPick = d.id; UI.render(); },
    invRole: (el) => { UI.state.invRole = el.value; UI.render(); },
    invSend: (d) => {
      const clan = cur(), uid = S.get().userId, role = UI.state.invRole || "viewer", person = d.pick || null;
      const status = Perm.inviteStatus(clan, uid, person, role);
      const inv = { id: "inv_" + rid(), by: uid, person, role, status, code: status === "active" ? code() : null, note: UI.val("f_invnote").trim(), createdAt: Date.now() };
      clan.invites.push(inv);
      S.api("POST", `/clans/${clan.id}/invites`, { person_id: person, role, request_note: inv.note }, `201 · status ${status === "active" ? "active" : "pending_approval"}`);
      UI.state.invPick = undefined; UI.state.invRole = "viewer";
      UI.back();
      if (status === "active") UI.open("inviteReady", { code: inv.code });
      else UI.toast(role === "editor" ? "Đã gửi. Chờ trưởng họ duyệt." : "Đã gửi. Chờ trưởng họ hoặc Ban quản lý duyệt, bạn sẽ nhận thông báo kèm link.");
    },
    invApprove: (d) => {
      const clan = cur(), i = clan.invites.find((x) => x.id === d.id);
      Object.assign(i, { status: "active", code: code(), approvedBy: S.get().userId });
      S.api("POST", `/clans/${clan.id}/invites/${i.id}/approve`, null, "200 · sinh mã + push cho người mời"); UI.toast("Đã duyệt. Người mời nhận thông báo kèm link.");
    },
    invReject: (d) => {
      const clan = cur(), i = clan.invites.find((x) => x.id === d.id); i.status = "rejected";
      S.api("POST", `/clans/${clan.id}/invites/${i.id}/reject`, null, "200"); UI.toast("Đã từ chối lời mời.");
    },
    fakeShare: () => UI.toast("Bản demo: link đã được sao chép / mở Zalo."),
    openAsInvitee: (d) => { UI.ov = null; UI.go("cjoin", { code: d.code }); },
    joinLookup: () => UI.replace("cjoin", { code: UI.val("f_code").trim().toUpperCase() }),
    joinNotMe: () => UI.replace("cjoin", Object.assign({}, UI.top().p, { notMe: 1 })),
    joinAs: (d) => join(d.code, true),
    joinClaim: (d) => join(d.code, false),
    matchToggle: (d) => { UI.state.matchSel[d.k] = d.v === "1"; UI.render(); },
    matchLink: () => {
      const st = S.get(), clan = cur(), md = matchData(clan), sel = UI.state.matchSel;
      const pairs = md.sug.filter((s) => { const k = s.pid + "|" + s.cid; return k in sel ? sel[k] : s.hi; });
      pairs.forEach((s) => { st.fam.links[s.pid] = { clanId: clan.id, cp: s.cid }; });
      UI.state.matchSel = {};
      S.api("POST", "/v1/family/links", { clanId: clan.id, pairs: pairs.map((s) => ({ personId: s.pid, clanPersonId: s.cid })) }, "201");
      UI.toast(`Đã liên kết ${pairs.length} người. Họ mang dấu 🔗 trong cây của bạn.`);
    },
    contribute: (d) => {
      const st = S.get(), clan = cur(), md = matchData(clan), raw = st.fam.persons[d.id], p = famMap()[d.id];
      const f = md.toCp(raw.fatherId), m = md.toCp(raw.motherId), draft = {};
      SHARED.forEach((k) => { draft[k] = p[k]; });
      if (Perm.canEdit(clan, ME, f || m)) {
        const np = ClanOps.createPerson(clan, draft, f, m);
        st.fam.links[d.id] = { clanId: clan.id, cp: np.id };
        S.api("POST", "/v1/family/links/contribute", { personId: d.id, clanId: clan.id }, "201 · tạo thẳng + liên kết");
        return UI.toast(`Đã thêm ${UI.esc(p.name)} vào ${UI.esc(clan.name)} và liên kết.`);
      }
      ClanOps.createCR(clan, ME, { action: "create_person", payload: { person: draft, fatherId: f, motherId: m }, note: "Đóng góp từ gia phả cá nhân", familyPersonId: d.id });
      UI.toast("Đã gửi đề xuất thêm người. Khi được duyệt, người này tự liên kết.");
    },
    importCp: (d) => {
      const st = S.get(), clan = cur(), q = clan.persons[d.id], fp = famMap();
      const back = {}; Object.entries(st.fam.links).forEach(([pid, l]) => { if (l.clanId === clan.id) back[l.cp] = pid; });
      const draft = {}; SHARED.forEach((k) => { draft[k] = JSON.parse(JSON.stringify(q[k] == null ? null : q[k])); });
      const np = Mut.create(st.fam.persons, draft, "p_");
      ["father", "mother"].forEach((s) => { const pid = back[q[s + "Id"]]; if (pid && !Rules.setParent(fp, np.id, s, pid)) np[s + "Id"] = pid; });
      q.spouses.forEach((s) => { const pid = back[s.id]; if (pid) Mut.linkSpouse(fp, np.id, pid, s.type); });
      st.fam.links[np.id] = { clanId: clan.id, cp: q.id };
      S.api("POST", "/v1/family/links/import", { clanId: clan.id, clanPersonIds: [q.id] }, "201 · skippedEdges 0");
      UI.scroll.tree = null;
      UI.toast(`Đã nhận ${UI.esc(q.name)} về cây của bạn (🔗).`);
    },
  });

  function join(c, asPerson) {
    const st = S.get(), hit = findInvite(c); if (!hit) return UI.toast("Mã không còn hiệu lực.", "err");
    const { clan, i } = hit, claim = asPerson ? i.person : (UI.val("f_claim") || null);
    const q = claim && clan.persons[claim];
    const m = { uid: "u_" + rid(), name: q ? q.name : "Người dùng mới", role: i.role, person: claim, verified: !!(asPerson && i.person) };
    clan.members.push(m);
    if (i.person) i.status = "used";
    S.api("POST", "/join", { code: c }, asPerson ? "200 · đã gắn + xác minh" : "200");
    if (!asPerson && claim) S.api("PUT", `/clans/${clan.id}/toi-la`, { person_id: claim }, "200 · chờ xác minh");
    st.userId = m.uid; UI.scroll = {};
    UI.home("ctree", { clan: clan.id });
    UI.toast(m.verified ? `Chào ${UI.esc(m.name)}! Bạn đã vào họ và được xác minh. Bảng bên phải đã chuyển sang tài khoản này.`
      : "Đã vào họ. " + (claim ? "Chờ trưởng họ, Ban quản lý hoặc trưởng chi xác minh." : "Bạn đang ở quyền xem."));
  }
})();
