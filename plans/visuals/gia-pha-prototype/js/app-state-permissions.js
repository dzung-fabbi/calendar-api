/* App state (persisted per viewer in localStorage), API call log, personal↔clan overlay, clan permissions.
   Permissions implement plan 260919-shared-clan-tree-collaboration phases 1, 2, 6. */
(function (g) {
  const KEY = "giapha-prototype-v1";
  let st;

  const S = {
    load() {
      try { const raw = localStorage.getItem(KEY); if (raw) { const v = JSON.parse(raw); if (v && v.fam && v.clans) { st = v; return; } } } catch (e) { /* storage blocked: use seed */ }
      st = SEED();
    },
    save() { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) { /* ignore */ } },
    reset() { st = SEED(); S.save(); },
    get: () => st,
    /** Record the API call the real app would make for this action (shown in the side panel). */
    api(method, path, body, result) {
      st.log.unshift({ t: Date.now(), method, path, body: body ? JSON.stringify(body) : "", result: result || "" });
      st.log = st.log.slice(0, 40);
    },
  };

  // ---------- Personal tree with linked overlay (plan phase 4: read shared fields from the clan) ----------
  const SHARED = ["name", "gender", "deceased", "birth", "lunarDeath"];
  const linkOf = (pid) => st.fam.links[pid] || null;
  const clanPersonOf = (pid) => { const l = linkOf(pid); const c = l && st.clans[l.clanId]; return c ? c.persons[l.cp] || null : null; };
  function overlay(pid) {
    const p = st.fam.persons[pid];
    const cp = p && clanPersonOf(pid);
    if (!cp) return p;
    return new Proxy(p, { get: (t, k) => (k === "_linked" ? true : (SHARED.includes(k) ? cp[k] : t[k])) });
  }
  /** Map view where each person exposes clan values for shared fields; writes go to the personal record. */
  const famMap = () => new Proxy(st.fam.persons, {
    get: (t, k) => (typeof k === "string" && t[k] && t[k].id ? overlay(k) : t[k]),
  });

  // ---------- Clan permissions ----------
  const ROLE = { owner: "Trưởng họ", manager: "Ban quản lý", editor: "Biên tập", viewer: "Thành viên" };
  const member = (clan, uid) => clan.members.find((m) => m.uid === uid) || null;
  const roleLabel = (m) => (!m ? "Chưa tham gia" : (m.role === "editor" && m.scopeRoot ? "Trưởng chi" : ROLE[m.role]));

  function familyScope(clan, pid) {
    const ps = clan.persons, s = new Set([pid]);
    G.spouses(ps, pid).forEach((x) => s.add(x.id));
    G.parents(ps, pid).forEach((x) => s.add(x));
    G.descendants(ps, pid).forEach((d) => { s.add(d); G.spouses(ps, d).forEach((x) => s.add(x.id)); });
    // Siblings only while nobody verified has claimed them (decision 2026-09-19).
    const claimed = new Set(clan.members.filter((m) => m.verified && m.person).map((m) => m.person));
    G.siblings(ps, pid).forEach((q) => { if (!claimed.has(q.id)) s.add(q.id); });
    return s;
  }
  function branchScope(clan, root) {
    const ps = clan.persons, s = new Set([root, ...G.descendants(ps, root)]);
    [...s].forEach((d) => G.spouses(ps, d).forEach((x) => s.add(x.id)));
    return s;
  }
  const P = {
    member, roleLabel, familyScope, branchScope,
    /** null = whole clan; otherwise the Set of person ids the user may edit directly. */
    writable(clan, uid) {
      const m = member(clan, uid);
      if (!m) return new Set();
      if (m.role === "owner" || m.role === "manager") return null;
      const fam = m.verified && m.person && clan.persons[m.person] ? familyScope(clan, m.person) : new Set();
      if (m.role === "editor") {
        if (!m.scopeRoot) return null;
        const s = branchScope(clan, m.scopeRoot); fam.forEach((x) => s.add(x)); return s;
      }
      return fam;
    },
    canEdit(clan, uid, pid) { const w = P.writable(clan, uid); return w === null || w.has(pid); },
    canReview(clan, uid, cr) {
      const m = member(clan, uid);
      if (!m || m.role === "viewer") return false;
      if (m.role === "editor" && m.scopeRoot) {
        const t = cr.target || (cr.payload && (cr.payload.fatherId || cr.payload.motherId));
        return branchScope(clan, m.scopeRoot).has(t);
      }
      return true;
    },
    canVerify(clan, uid, target) {
      const m = member(clan, uid);
      if (!m) return false;
      if (m.role === "owner" || m.role === "manager") return true;
      return m.role === "editor" && !!m.scopeRoot && branchScope(clan, m.scopeRoot).has(target.person);
    },
    canApproveInvite(clan, uid, inv) {
      const m = member(clan, uid);
      return !!m && (m.role === "owner" || (m.role === "manager" && inv.role === "viewer"));
    },
    canInvite(clan, uid) { const m = member(clan, uid); return !!m && (m.role !== "viewer" || m.verified); },
    /** 'active' = link now; 'pending' = needs owner/manager approval (phase 1). */
    inviteStatus(clan, uid, personId, role) {
      const m = member(clan, uid);
      if (m.role === "owner") return "active";
      if (role === "editor") return "pending";
      if (m.role === "manager") return "active";
      return personId && P.canEdit(clan, uid, personId) ? "active" : "pending";
    },
    isOwner: (clan, uid) => { const m = member(clan, uid); return !!m && m.role === "owner"; },
  };

  g.S = S; g.Perm = P; g.famMap = famMap; g.overlay = overlay; g.linkOf = linkOf; g.clanPersonOf = clanPersonOf; g.SHARED = SHARED;
})(window);
