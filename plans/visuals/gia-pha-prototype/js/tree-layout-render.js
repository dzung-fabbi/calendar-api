/* Tree layout: unit = person + partners side by side, children fork centred under the unit.
   Client-side only (spec §10: layout is not the backend's job). Renders absolutely positioned nodes + SVG lines. */
(function (g) {
  const W = 100, H = 56, GX = 14, GY = 56;

  function build(ps, id, depth, placed) {
    const units = [id]; placed.add(id);
    G.partners(ps, id).forEach((s) => { if (!placed.has(s)) { units.push(s); placed.add(s); } });
    const kidIds = [];
    units.forEach((u) => G.children(ps, u).forEach((c) => { if (!kidIds.includes(c.id)) kidIds.push(c.id); }));
    const kids = [];
    kidIds.forEach((k) => { if (!placed.has(k)) kids.push(build(ps, k, depth + 1, placed)); });
    const unitW = units.length * W + (units.length - 1) * GX;
    const kidsW = kids.reduce((a, k) => a + k.w, 0) + Math.max(0, kids.length - 1) * GX * 2;
    return { units, kids, depth, unitW, kidsW, w: Math.max(unitW, kidsW) };
  }

  function place(n, x0, out) {
    const ux = x0 + (n.w - n.unitW) / 2, y = n.depth * (H + GY);
    n.units.forEach((u, i) => {
      const x = ux + i * (W + GX);
      out.nodes.push({ id: u, x, y });
      if (i > 0) out.lines.push(`M${x - GX} ${y + H / 2}H${x}`);
    });
    if (n.kids.length) {
      // Fork starts between the first couple (or under a single parent).
      const mx = n.units.length > 1 ? ux + W + GX / 2 : ux + W / 2;
      const yb = n.units.length > 1 ? y + H / 2 : y + H, ymid = y + H + GY / 2;
      let cx = x0 + (n.w - n.kidsW) / 2;
      const centers = n.kids.map((k) => { const c = place(k, cx, out); cx += k.w + GX * 2; return c; });
      out.lines.push(`M${mx} ${yb}V${ymid}`);
      out.lines.push(`M${Math.min(mx, ...centers)} ${ymid}H${Math.max(mx, ...centers)}`);
      centers.forEach((c) => out.lines.push(`M${c} ${ymid}V${y + H + GY}`));
    }
    return ux + W / 2;
  }

  /** Layout from `rootId`. Returns { nodes:[{id,x,y}], lines:[svg path], w, h, hidden: count not on this branch }. */
  function layout(ps, rootId) {
    const placed = new Set();
    const tree = build(ps, rootId, 0, placed);
    const out = { nodes: [], lines: [] };
    place(tree, 20, out);
    const w = tree.w + 40;
    const h = Math.max(...out.nodes.map((n) => n.y)) + H + 30;
    const hidden = G.all(ps).filter((p) => !placed.has(p.id) && !G.isUnlinked(ps, p.id)).length;
    return Object.assign(out, { w, h, hidden });
  }

  /** Root choices for "Theo dòng": distinct lineage roots of every connected person. */
  function rootOptions(ps) {
    const roots = new Set();
    G.all(ps).forEach((p) => { if (!G.isUnlinked(ps, p.id)) roots.add(G.lineageRoot(ps, p.id)); });
    return [...roots].filter((r) => G.children(ps, r).length || G.partners(ps, r).length);
  }

  /**
   * HTML for a tree. opts: { self, pick, scope:Set|null (null=all editable), marks:{id:"👤"}, showLinks, act }
   */
  function render(ps, rootId, opts = {}) {
    const L = layout(ps, rootId);
    const nodes = L.nodes.map(({ id, x, y }) => {
      const p = ps[id];
      const cls = ["node", p.deceased ? "dead" : p.gender, id === opts.self ? "self" : "",
        id === opts.pick ? "pick" : "", opts.scope && opts.scope.has(id) ? "scope" : ""].join(" ");
      const short = p.name.split(" ").slice(-2).join(" ");
      const mark = opts.marks && opts.marks[id] ? `<i class="acct">${opts.marks[id]}</i>` : "";
      const lk = opts.showLinks && p._linked ? '<i class="lk" title="Đã liên kết dòng họ">🔗</i>' : "";
      return `<button class="${cls}" style="left:${x}px;top:${y}px" data-act="${opts.act || "node"}" data-id="${id}" aria-label="${UI.esc(p.name)}">
        <b>${UI.esc(short)}</b><small>${G.years(p) || "&nbsp;"}</small>${id === opts.self ? '<span class="me">Tôi</span>' : ""}${mark}${lk}</button>`;
    }).join("");
    return {
      html: `<div class="canvas" style="width:${L.w}px;height:${L.h}px"><svg width="${L.w}" height="${L.h}" aria-hidden="true"><path d="${L.lines.join(" ")}" fill="none" stroke="#B9BDB6" stroke-width="1.6"/></svg>${nodes}</div>`,
      layout: L,
    };
  }

  g.TreeView = { render, layout, rootOptions, W, H };
})(window);
