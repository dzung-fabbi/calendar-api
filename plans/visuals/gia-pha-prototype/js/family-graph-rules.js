/* Graph derivations + relation rules, shared by the personal tree and clan trees.
   Mirrors docs/gia-pha-api-spec.md §2 (only upward edges + spouses are stored), §4 (rules), §5 (derivations). */
(function (g) {
  const all = (ps) => Object.values(ps);
  const byCreated = (a, b) => (a.createdAt - b.createdAt) || (a.id < b.id ? -1 : 1);
  const uniq = (xs) => [...new Set(xs)];

  const G = {
    all, byCreated,
    parents: (ps, id) => [ps[id].fatherId, ps[id].motherId].filter((x) => x && ps[x]),
    children: (ps, id) => all(ps).filter((p) => p.fatherId === id || p.motherId === id).sort(byCreated),
    spouses: (ps, id) => (ps[id] ? ps[id].spouses.filter((s) => ps[s.id]) : []),
    /** People sharing a child with `id` without a spouse edge ("có con chung ≠ đã cưới"). */
    coParents(ps, id) {
      const sp = new Set(G.spouses(ps, id).map((s) => s.id));
      return uniq(G.children(ps, id).map((c) => (c.fatherId === id ? c.motherId : c.fatherId))
        .filter((x) => x && ps[x] && !sp.has(x)));
    },
    partners: (ps, id) => uniq([...G.spouses(ps, id).map((s) => s.id), ...G.coParents(ps, id)]),
    siblings(ps, id) {
      const p = ps[id];
      return all(ps).filter((q) => q.id !== id &&
        ((p.fatherId && q.fatherId === p.fatherId) || (p.motherId && q.motherId === p.motherId))).sort(byCreated);
    },
    ancestors(ps, id) {
      const out = new Set(), stack = G.parents(ps, id);
      while (stack.length) { const x = stack.pop(); if (!out.has(x)) { out.add(x); stack.push(...G.parents(ps, x)); } }
      return out;
    },
    descendants(ps, id) {
      const out = new Set(), stack = G.children(ps, id).map((c) => c.id);
      while (stack.length) { const x = stack.pop(); if (!out.has(x)) { out.add(x); stack.push(...G.children(ps, x).map((c) => c.id)); } }
      return out;
    },
    isUnlinked: (ps, id) => !G.parents(ps, id).length && !G.spouses(ps, id).length && !G.children(ps, id).length,
    /** Lineage root: climb father first, then mother (spec §2.2). */
    lineageRoot(ps, id) {
      let cur = id; const seen = new Set([id]);
      for (;;) {
        const p = ps[cur], up = (p.fatherId && ps[p.fatherId]) ? p.fatherId : ((p.motherId && ps[p.motherId]) ? p.motherId : null);
        if (!up || seen.has(up)) return cur;
        seen.add(up); cur = up;
      }
    },
    hasGio: (p) => p.deceased && p.lunarDeath && p.lunarDeath.d >= 1 && p.lunarDeath.d <= 30 && p.lunarDeath.m >= 1 && p.lunarDeath.m <= 12,
    gio: (p) => (G.hasGio(p) ? Lunar.nextGio(p.lunarDeath.d, p.lunarDeath.m) : null),
    years(p) {
      const b = p.birth ? p.birth.slice(-4) : "";
      const d = p.lunarDeath && p.lunarDeath.y ? String(p.lunarDeath.y) : "?";
      return p.deceased ? `${b || "?"} – ${d}` : b;
    },
  };

  // ---- Rules: return { code, message } on violation, null when allowed ----
  const E = (code, message) => ({ code, message });
  const R = {
    setParent(ps, childId, slot, parentId) {
      if (!parentId) return null;
      if (childId === parentId) return E("SELF_PARENT", "Một người không thể là cha/mẹ của chính mình.");
      if (G.ancestors(ps, parentId).has(childId) || G.descendants(ps, childId).has(parentId))
        return E("PARENT_CYCLE", "Không đặt được: người này đang là con cháu trong nhánh đó, nối vào sẽ tạo vòng lặp.");
      const gd = ps[parentId].gender;
      if (slot === "father" && gd === "female") return E("GENDER_SLOT", "Ô cha không nhận người giới tính nữ.");
      if (slot === "mother" && gd === "male") return E("GENDER_SLOT", "Ô mẹ không nhận người giới tính nam.");
      return null;
    },
    slotTaken(ps, childId, slot) {
      const cur = ps[childId][slot + "Id"];
      if (!cur || !ps[cur]) return null;
      return slot === "father"
        ? E("PARENT_SLOT_TAKEN", "Người này đã có cha. Cha dượng nên nhập là vợ/chồng của mẹ.")
        : E("PARENT_SLOT_TAKEN", "Người này đã có mẹ. Mẹ kế nên nhập là vợ/chồng của cha.");
    },
    spouse(ps, a, b) {
      if (a === b) return E("SELF_SPOUSE", "Không thể nối vợ/chồng với chính mình.");
      return null;
    },
    spouseWarning(ps, a, b) {
      return (G.ancestors(ps, a).has(b) || G.ancestors(ps, b).has(a))
        ? E("SPOUSE_IS_ANCESTOR", "Hai người này có quan hệ trực hệ. Vẫn lưu, nhưng hãy kiểm tra lại.") : null;
    },
    /** Why an "add <kind>" menu item is disabled (spec §4.7), or null. */
    addBlock(ps, anchorId, kind) {
      if (kind === "father" || kind === "mother") return R.slotTaken(ps, anchorId, kind);
      if (kind === "sibling" && !G.parents(ps, anchorId).length)
        return E("SIBLING_NO_PARENT", "Chưa có cha hoặc mẹ nên chưa thêm được anh chị em.");
      return null;
    },
  };

  // ---- Mutations on a persons map (caller persists + logs the API call) ----
  const slotFor = (gender) => (gender === "female" ? "mother" : "father");
  const fitsSlot = (gender, slot) => !((slot === "father" && gender === "female") || (slot === "mother" && gender === "male"));
  const M = {
    create(ps, draft, prefix) {
      const id = prefix + Math.random().toString(36).slice(2, 8);
      ps[id] = Object.assign({ id, fatherId: null, motherId: null, spouses: [], createdAt: Date.now(), version: 1 }, draft);
      return ps[id];
    },
    setParent(ps, childId, slot, parentId) { ps[childId][slot + "Id"] = parentId || null; },
    /** Link both sides; fill empty parent slots of existing children only for the FIRST partner (spec §4.4). */
    linkSpouse(ps, a, b, type) {
      const firstA = !G.partners(ps, a).length, firstB = !G.partners(ps, b).length;
      const up = (x, y) => { const s = ps[x].spouses.find((s) => s.id === y); if (s) s.type = type || "married"; else ps[x].spouses.push({ id: y, type: type || "married" }); };
      up(a, b); up(b, a);
      [[a, b, firstA], [b, a, firstB]].forEach(([x, y, first]) => {
        if (!first) return;
        G.children(ps, x).forEach((c) => {
          const other = c.fatherId === x ? "mother" : "father";
          if (!c[other + "Id"] && fitsSlot(ps[y].gender, other)) c[other + "Id"] = y;
        });
      });
    },
    unlinkSpouse(ps, a, b) {
      ps[a].spouses = ps[a].spouses.filter((s) => s.id !== b);
      ps[b].spouses = ps[b].spouses.filter((s) => s.id !== a);
    },
    /** Partners of `parentId` that fit the other slot of a new child (spec §4.6). */
    otherParentCandidates(ps, parentId) {
      const other = slotFor(ps[parentId].gender) === "father" ? "mother" : "father";
      return G.partners(ps, parentId).filter((id) => fitsSlot(ps[id].gender, other));
    },
    /** Create + connect in one step (spec §4.7). Returns { person } or { error }. */
    addRelative(ps, anchorId, kind, draft, otherParentId, prefix) {
      const block = R.addBlock(ps, anchorId, kind);
      if (block) return { error: block };
      const p = M.create(ps, draft, prefix);
      const a = ps[anchorId];
      if (kind === "father" || kind === "mother") {
        const err = R.setParent(ps, anchorId, kind, p.id);
        if (err) { delete ps[p.id]; return { error: err }; }
        a[kind + "Id"] = p.id;
      } else if (kind === "spouse") {
        M.linkSpouse(ps, anchorId, p.id, "married");
      } else if (kind === "child") {
        const slot = slotFor(a.gender), other = slot === "father" ? "mother" : "father";
        p[slot + "Id"] = anchorId;
        const cands = M.otherParentCandidates(ps, anchorId);
        const pick = otherParentId && cands.includes(otherParentId) ? otherParentId : (cands.length === 1 ? cands[0] : null);
        if (pick) p[other + "Id"] = pick;
      } else if (kind === "sibling") {
        p.fatherId = a.fatherId; p.motherId = a.motherId;
      }
      return { person: p };
    },
    /** Delete without cascade (spec §2.6). Returns ids that lost an edge. */
    remove(ps, id) {
      const detached = [];
      all(ps).forEach((q) => {
        let hit = false;
        if (q.fatherId === id) { q.fatherId = null; hit = true; }
        if (q.motherId === id) { q.motherId = null; hit = true; }
        if (q.spouses.some((s) => s.id === id)) { q.spouses = q.spouses.filter((s) => s.id !== id); hit = true; }
        if (hit) detached.push(q.id);
      });
      delete ps[id];
      return detached;
    },
  };

  /** Standalone "Thêm người" auto-link by label relative to "tôi" (spec §4.8). Returns a hint or null. */
  function autoLinkByLabel(ps, selfId, p) {
    const me = selfId && ps[selfId];
    const label = p.relationship;
    if (!me || !label) return "Chưa nối vào cây: chưa có “tôi” hoặc chưa chọn quan hệ.";
    const setUp = (childId, slot) => {
      if (!childId) return false;
      const err = R.slotTaken(ps, childId, slot) || R.setParent(ps, childId, slot, p.id);
      if (err) return false;
      ps[childId][slot + "Id"] = p.id; return true;
    };
    const ok = {
      "Cha": () => setUp(selfId, "father"), "Mẹ": () => setUp(selfId, "mother"),
      "Ông nội": () => setUp(me.fatherId, "father"), "Bà nội": () => setUp(me.fatherId, "mother"),
      "Ông ngoại": () => setUp(me.motherId, "father"), "Bà ngoại": () => setUp(me.motherId, "mother"),
      "Vợ": () => (M.linkSpouse(ps, selfId, p.id), true), "Chồng": () => (M.linkSpouse(ps, selfId, p.id), true),
      "Con": () => { const s = slotFor(me.gender); p[s + "Id"] = selfId; const c = M.otherParentCandidates(ps, selfId); if (c.length === 1) p[(s === "father" ? "mother" : "father") + "Id"] = c[0]; return true; },
      "Anh": null, "Chị": null, "Em": null,
    };
    if (["Anh", "Chị", "Em"].includes(label)) {
      if (!me.fatherId && !me.motherId) return "Chưa nối: bạn chưa có cha hoặc mẹ trong cây.";
      p.fatherId = me.fatherId; p.motherId = me.motherId; return null;
    }
    if (!ok[label]) return `Nhãn “${label}” không chỉ ra đúng một chỗ trong cây nên người này nằm ở nhóm “Chưa nối vào cây”.`;
    return ok[label]() ? null : "Chưa nối được: vai này đã có người hoặc thiếu người trung gian.";
  }

  g.G = G; g.Rules = R; g.Mut = M; g.autoLinkByLabel = autoLinkByLabel;
})(window);
