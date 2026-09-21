/* Navigation stack, overlays, toast, render loop, event delegation and small HTML helpers. */
(function (g) {
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const UI = {
    esc, stack: [{ s: "tree", p: {} }], ov: null, toastMsg: null, Screens: {}, Overlays: {}, Actions: {},
    state: { zoom: 1, q: "", crTab: "pending", matchSel: {}, invPick: undefined },
    scroll: {},
  };
  UI.top = () => UI.stack[UI.stack.length - 1];
  UI.go = (s, p = {}) => { UI.stack.push({ s, p }); UI.ov = null; UI.render(); };
  UI.replace = (s, p = {}) => { UI.stack[UI.stack.length - 1] = { s, p }; UI.ov = null; UI.render(); };
  UI.back = () => { if (UI.stack.length > 1) UI.stack.pop(); UI.ov = null; UI.render(); };
  UI.home = (s, p = {}) => { UI.stack = [{ s, p }]; UI.ov = null; UI.render(); };
  UI.open = (t, p = {}) => { UI.ov = { t, p }; UI.render(); };
  UI.close = () => { UI.ov = null; UI.render(); };
  UI.toast = (msg, kind) => {
    UI.toastMsg = { msg, kind }; clearTimeout(UI._tt);
    UI._tt = setTimeout(() => { UI.toastMsg = null; UI.render(); }, 4200);
    UI.render();
  };

  // ---------- pieces ----------
  const now = () => { const d = new Date(); return `${d.getHours()}:${Lunar.pad(d.getMinutes())}`; };
  UI.status = () => `<div class="status"><span>${now()}</span><span>●●● 5G ▮</span></div>`;
  UI.bar = (title, o = {}) => `<div class="bar">${o.back === false ? "" : `<button class="ic" data-act="back" aria-label="Quay lại">${o.close ? "✕" : "‹"}</button>`}
    <h4>${o.titleAct ? `<button data-act="${o.titleAct}">${title}</button>` : title}</h4>${o.right || ""}</div>`;
  UI.tabs = (on) => `<nav class="tabs">${[["cal", "▦", "Lịch"], ["events", "◷", "Sự kiện"], ["giapha", "❦", "Gia phả"], ["me", "◉", "Cá nhân"]]
    .map(([k, i, l]) => `<button class="${on === k ? "on" : ""}" data-act="tab" data-tab="${k}"><i>${i}</i>${l}</button>`).join("")}</nav>`;
  UI.av = (p) => `<span class="av ${p.deceased ? "dead" : p.gender}">${esc((p.name.split(" ").pop() || "?")[0])}</span>`;
  UI.row = (o) => `<${o.act ? "button" : "div"} class="row" ${o.act ? `data-act="${o.act}"` : ""} ${o.data || ""} ${o.disabled ? "disabled" : ""}>
    ${o.lead || ""}<span class="t">${o.title}${o.sub ? `<small>${o.sub}</small>` : ""}</span>${o.trail || (o.act && !o.disabled ? '<span class="chev">›</span>' : "")}</${o.act ? "button" : "div"}>`;

  // ---------- form helpers ----------
  const $ = (id) => document.getElementById(id);
  UI.val = (id) => ($(id) ? $(id).value : "");
  UI.checked = (id) => !!($(id) && $(id).checked);
  UI.radio = (name) => { const el = document.querySelector(`input[name="${name}"]:checked`); return el ? el.value : ""; };
  UI.field = (label, inner, extra = "") => `<div class="f"><label class="lb">${label}${extra}</label>${inner}</div>`;
  UI.input = (id, v, o = {}) => `<input class="input" id="${id}" value="${esc(v)}" ${o.ph ? `placeholder="${esc(o.ph)}"` : ""} ${o.type ? `type="${o.type}"` : ""} ${o.list ? `list="${o.list}"` : ""} ${o.max ? `maxlength="${o.max}"` : ""} ${o.attrs || ""}>`;
  UI.seg = (name, opts, v) => `<div class="seg" role="radiogroup">${opts.map(([k, l]) => `<label><input type="radio" name="${name}" value="${k}" ${k === v ? "checked" : ""}><span>${l}</span></label>`).join("")}</div>`;
  UI.switch = (id, on, label, sub, attrs = "") => `<label class="tog"><span>${label}${sub ? `<small>${sub}</small>` : ""}</span><input type="checkbox" id="${id}" ${on ? "checked" : ""} ${attrs}><span class="sw2"></span></label>`;
  UI.select = (id, opts, v, attrs = "") => `<select id="${id}" ${attrs}>${opts.map(([k, l]) => `<option value="${esc(k)}" ${k === v ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>`;
  UI.toInputDate = (s) => (s ? s.split("-").reverse().join("-") : "");
  UI.fromInputDate = (s) => (s ? s.split("-").reverse().join("-") : null);

  // ---------- render loop ----------
  UI.render = () => {
    S.save();
    const app = $("app"), top = UI.top();
    const keep = app.querySelector("[data-keep]");
    if (keep) UI.scroll[keep.dataset.keep] = [keep.scrollLeft, keep.scrollTop];
    const focused = document.activeElement && document.activeElement.id;
    const scr = UI.Screens[top.s] || UI.Screens.tree;
    UI.after = null;
    app.innerHTML = UI.status() + scr(top.p || {}) +
      (UI.ov ? `<div class="scrim" data-act="close"></div>${UI.Overlays[UI.ov.t](UI.ov.p || {})}` : "") +
      (UI.toastMsg ? `<div class="toast ${UI.toastMsg.kind || ""}" role="status">${UI.toastMsg.msg}</div>` : "");
    const nk = app.querySelector("[data-keep]");
    if (nk && UI.scroll[nk.dataset.keep]) [nk.scrollLeft, nk.scrollTop] = UI.scroll[nk.dataset.keep];
    if (UI.after) UI.after(app);
    if (focused && $(focused) && $(focused).dataset.refocus) { const el = $(focused); el.focus(); const n = el.value.length; try { el.setSelectionRange(n, n); } catch (e) { /* ignore */ } }
    if (g.Panel) Panel.render();
  };

  // ---------- event delegation (app + side panel) ----------
  document.addEventListener("click", (e) => {
    const el = e.target.closest("[data-act]");
    if (!el || el.disabled || el.hasAttribute("disabled")) return;
    const fn = UI.Actions[el.dataset.act];
    if (fn) { e.preventDefault(); fn(el.dataset, el); }
  });
  document.addEventListener("input", (e) => {
    const fn = e.target.dataset && UI.Actions[e.target.dataset.input];
    if (fn) fn(e.target);
  });
  document.addEventListener("change", (e) => {
    const fn = e.target.dataset && UI.Actions[e.target.dataset.change];
    if (fn) fn(e.target);
  });

  Object.assign(UI.Actions, {
    back: () => UI.back(),
    close: () => UI.close(),
    tab: (d) => UI.home({ cal: "cal", events: "events", giapha: "tree", me: "me" }[d.tab]),
  });
  g.UI = UI;
})(window);
