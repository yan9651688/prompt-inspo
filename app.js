(() => {
  const $ = s => document.querySelector(s);
  const state = { days: [], loaded: {}, next: 0, model: "全部", q: "" };
  const feed = $("#feed"), sentinel = $("#sentinel");
  const esc = s => String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const toast = msg => { const t = $("#toast"); t.textContent = msg; t.classList.add("show"); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("show"), 1500); };

  async function copy(text) {
    try { await navigator.clipboard.writeText(text); }
    catch { const ta = document.createElement("textarea"); ta.value = text; document.body.appendChild(ta); ta.select(); document.execCommand("copy"); ta.remove(); }
    toast("提示词已复制 ✓");
  }

  const match = e => (state.model === "全部" || e.models.includes(state.model)) &&
    (!state.q || (e.prompt + e.title + e.author + e.author_name).toLowerCase().includes(state.q));

  function card(e) {
    const imgs = e.images.map((src, i) => `<img loading="lazy" src="${esc(src)}" data-full="${esc(e.remote_images[i] || src)}" alt="${esc(e.title)}">`).join("");
    return `<article class="card">
      <div class="imgs n${e.images.length}">${imgs}</div>
      <div class="body">
        <div class="tags">${e.models.map(m => `<span class="tag">${esc(m)}</span>`).join("")}</div>
        <p class="title">${esc(e.title)}</p>
        <div class="prompt" title="点击展开">${esc(e.prompt)}</div>
        <div class="meta"><a href="${esc(e.url)}" target="_blank" rel="noopener">@${esc(e.author)} · 原帖 ↗</a>
        <button class="copy" data-id="${esc(e.id)}">复制提示词</button></div>
      </div></article>`;
  }

  function renderDay(day) {
    const list = (state.loaded[day.date] || []).filter(match);
    if (!list.length) return "";
    return `<section class="day"><h2>${day.date}<small>${list.length} 条</small></h2><div class="grid">${list.map(card).join("")}</div></section>`;
  }

  function rerender() {
    const html = state.days.slice(0, state.next).map(renderDay).join("");
    feed.innerHTML = html || (state.next >= state.days.length ? `<div class="empty">没有匹配的提示词</div>` : "");
  }

  async function loadNext() {
    if (state.next >= state.days.length) { sentinel.textContent = "— 已经到底啦 —"; return; }
    const day = state.days[state.next++];
    if (!state.loaded[day.date]) {
      try { state.loaded[day.date] = await (await fetch(`data/${day.date}.json`)).json(); } catch { state.loaded[day.date] = []; }
    }
    feed.insertAdjacentHTML("beforeend", renderDay(day));
    if (sentinel.getBoundingClientRect().top < innerHeight + 400) loadNext();
  }

  async function init() {
    const idx = await (await fetch("data/index.json", { cache: "no-cache" })).json();
    state.days = idx.days;
    const total = idx.days.reduce((a, d) => a + d.count, 0);
    const models = ["全部", ...new Set(idx.days.flatMap(d => d.models))];
    $("#models").innerHTML = models.map(m => `<button class="chip${m === "全部" ? " on" : ""}" data-m="${esc(m)}">${esc(m)}</button>`).join("");
    $("#stats").textContent = `共 ${total} 条提示词 · ${idx.days.length} 天 · 更新于 ${new Date(idx.updated).toLocaleString("zh-CN")}`;
    new IntersectionObserver(es => es[0].isIntersecting && loadNext(), { rootMargin: "400px" }).observe(sentinel);
  }

  async function loadAll() { while (state.next < state.days.length) { const d = state.days[state.next++]; if (!state.loaded[d.date]) state.loaded[d.date] = await (await fetch(`data/${d.date}.json`)).json(); } rerender(); sentinel.textContent = "— 已经到底啦 —"; }

  $("#models").addEventListener("click", ev => {
    const b = ev.target.closest(".chip"); if (!b) return;
    document.querySelectorAll(".chip").forEach(c => c.classList.toggle("on", c === b));
    state.model = b.dataset.m; loadAll();
  });
  let t; $("#q").addEventListener("input", ev => { clearTimeout(t); t = setTimeout(() => { state.q = ev.target.value.trim().toLowerCase(); loadAll(); }, 200); });

  feed.addEventListener("click", ev => {
    const btn = ev.target.closest(".copy");
    if (btn) { for (const l of Object.values(state.loaded)) { const e = l.find(x => x.id === btn.dataset.id); if (e) return copy(e.prompt); } }
    const p = ev.target.closest(".prompt"); if (p) return p.classList.toggle("open");
    const img = ev.target.closest(".imgs img");
    if (img) { const v = $("#viewer"); v.querySelector("img").src = img.dataset.full; v.hidden = false; }
  });
  $("#viewer").addEventListener("click", () => { $("#viewer").hidden = true; });
  document.addEventListener("keydown", e => { if (e.key === "Escape") $("#viewer").hidden = true; });
  init();
})();
