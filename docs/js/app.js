/* Provenance: a daily desk of rare deals to broker. Vanilla JS, no tracking; statuses and notes live in localStorage. */
(() => {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const TABS = {
    all: "Every lead from the four desks, best first. Luxury, craft and heritage leads are ranked a little higher.",
    revival: "Sleeping beauties: lapsed heritage trade marks, dissolved houses with no successor, and much-loved projects whose makers walked away. You broker the revival.",
    import: "Luxury, craft and hospitality brands with hundreds of locations abroad and none mapped in the UK. You bring them here as agent.",
    closing: "UK companies entering insolvency this month whose kit is unusual or valuable: distilleries, hotels, jewellers, ateliers, boatyards, studios. You find the buyer.",
    twins: "People in different countries building the same rare thing, with no sign they know each other. You make the introduction, with consent.",
  };
  const STATUSES = [["new", "New"], ["contacted", "Contacted"], ["talks", "In talks"], ["done", "Done"], ["dropped", "Dropped"]];
  const KEY = "provenance.v1";
  let store = {};
  try { store = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch { store = {}; }
  const saveStore = () => { try { localStorage.setItem(KEY, JSON.stringify(store)); } catch {} };
  const st = (id) => (store[id] && store[id].status) || "new";

  let DATA = null, LEADS = [], BY = {}, view = "desk", tab = "all", cursor = -1, shown = [], map = null, mapReady = false, SOURCES = null;
  let limit = 60;
  const state = { q: "", cat: "", kind: "", status: "", sort: "score", lux: false };

  function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.add("on"); clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove("on"), 1800); }
  const fmtDate = (d) => { try { return new Date(d).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "Europe/London" }); } catch { return d; } };
  const fmtTime = (d) => { try { return new Date(d).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" }) + " London time"; } catch { return d; } };
  const bars = (lvl, title) => `<span class="bars l${lvl}" title="${esc(title)}" aria-label="${esc(title)}"><i></i><i></i><i></i></span>`;

  async function boot() {
    try {
      const r = await fetch("data/desk.json", { cache: "no-cache" });
      if (!r.ok) throw new Error(r.status);
      DATA = await r.json();
    } catch (e) {
      $("#five").innerHTML = ""; $("#leads").innerHTML = "";
      $("#count").textContent = "Couldn't load today's leads. Please refresh in a moment.";
      return;
    }
    LEADS = DATA.leads; LEADS.forEach((l) => (BY[l.id] = l));
    const now = new Date();
    $("#dateline").textContent = now.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "Europe/London" }) + " · desk refreshed " + fmtTime(DATA.generatedAt);
    $("#foot-gen").textContent = `Data generated ${fmtTime(DATA.generatedAt)}. ${LEADS.length} leads.`;
    for (const b of $$("#tabs button")) {
      const t = b.dataset.tab; $(".n", b).textContent = t === "all" ? LEADS.length : LEADS.filter((l) => l.tab === t).length;
    }
    renderFive(); fillFilters(); readHash(); render(); bind();
  }

  function renderFive() {
    $("#five").innerHTML = DATA.today.map((id) => BY[id]).filter(Boolean).map((l) => `
      <li tabindex="0" data-id="${esc(l.id)}" aria-label="${esc(l.title)}">
        <span class="k"><i class="dot ${l.tab}"></i>${esc(l.tabName)}</span>
        <h3>${esc(l.title)}</h3><p>${esc(l.worth)}</p>
        <span class="s">Score ${l.score} · ${esc(l.category || l.kind || "")}</span>
      </li>`).join("");
  }

  function fillFilters() {
    const pool = LEADS.filter((l) => tab === "all" || l.tab === tab);
    const uniq = (f) => [...new Set(pool.map(f).filter(Boolean))].sort();
    const fill = (sel, vals, label) => { const cur = sel.value; sel.innerHTML = `<option value="">${label}</option>` + vals.map((v) => `<option${v === cur ? " selected" : ""}>${esc(v)}</option>`).join(""); if (!vals.includes(cur)) state[sel.id] = ""; };
    fill($("#cat"), uniq((l) => l.category), "All categories");
    fill($("#kind"), uniq((l) => l.kind), "All types");
  }

  function filtered() {
    const q = state.q.trim().toLowerCase();
    let out = LEADS.filter((l) => (tab === "all" || l.tab === tab)
      && (!state.cat || l.category === state.cat) && (!state.kind || l.kind === state.kind)
      && (!state.status || st(l.id) === state.status) && (!state.lux || l.luxury || l.craft)
      && (!q || (l._s ||= [l.title, l.subtitle, l.category, l.kind, l.worth, l.stalled, (l.facts || []).map((f) => f.join(" ")).join(" "), (l.company || {}).nature].join(" ").toLowerCase()).includes(q)));
    if (state.sort === "date") out.sort((a, b) => String(b.date || "").localeCompare(String(a.date || "")));
    else if (state.sort === "title") out.sort((a, b) => a.title.localeCompare(b.title));
    else out.sort((a, b) => b.score - a.score);
    return out;
  }

  function card(l, i) {
    const s = st(l.id);
    return `<li class="lead" tabindex="0" data-id="${esc(l.id)}" data-i="${i}" style="animation-delay:${Math.min(i, 12) * 18}ms">
      <div class="top"><div><span class="k"><i class="dot ${l.tab}"></i>${esc(l.kind || l.tabName)}${l.luxury ? ' <span class="lux" title="Luxury, heritage or craft">◆</span>' : ""}</span>
      <h3>${esc(l.title)}</h3></div><div class="score" title="Score: value, freshness and fit"><b>${l.score}</b><span>score</span></div></div>
      <p class="sub">${esc(l.subtitle)}</p>
      <p class="worth">${esc(l.worth)}</p>
      <div class="meta"><span class="pill">${bars(l.trust.level, "Trust: " + l.trust.label)} ${esc(l.trust.label)}</span>
      <span class="pill">${bars(l.freshness.level, "Freshness: " + l.freshness.label)} ${esc(l.freshness.label)}</span>
      ${s !== "new" ? `<span class="st ${s}">${esc(STATUSES.find((x) => x[0] === s)[1])}</span>` : ""}${store[l.id]?.notes ? '<span title="Has notes">✎ notes</span>' : ""}</div>
    </li>`;
  }

  function render(keep) {
    if (!keep) limit = 60;
    $$("#tabs button").forEach((b) => b.setAttribute("aria-selected", b.dataset.tab === tab));
    $("#tab-blurb").textContent = TABS[tab];
    shown = filtered();
    const max = limit;
    $("#leads").innerHTML = shown.slice(0, max).map(card).join("");
    $("#more").hidden = shown.length <= max;
    $("#more").textContent = `Show more (${shown.length - max} left)`;
    $("#empty").hidden = shown.length > 0;
    const t = tab === "all" ? "" : ` in ${DATA.tabs[tab].name}`;
    const stx = DATA.tabs[tab]?.status;
    const warn = stx && stx.ok === false ? ` · Today's refresh for this desk failed (${esc(stx.error || stx.note || "source unavailable")}); showing the last good copy.` : "";
    $("#count").textContent = `${shown.length} lead${shown.length === 1 ? "" : "s"}${t}${shown.length > max ? `, showing ${max}` : ""}${warn}`;
    cursor = -1;
    if (view === "map" && mapReady) drawMap();
  }

  function openLead(id, push = true) {
    const l = BY[id]; if (!l) return;
    const rec = store[id] || {};
    const facts = (l.facts || []).filter((f) => f[1]).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${/^https?:/.test(v) ? `<a href="${esc(v)}" target="_blank" rel="noopener">${esc(v.replace(/^https?:\/\//, ""))}</a>` : esc(v)}</dd>`).join("");
    let middle = "";
    if (l.tab === "revival") middle = `<h4>Why it stalled</h4><p class="quote ${l.stalledQuoted ? "q" : ""}">${esc(l.stalled)}</p>${l.stalledQuoted ? '<p class="hint">Quoted from the original record.</p>' : ""}`;
    if (l.tab === "import") middle = `<h4>Evidence it works</h4><p class="quote">${esc(l.evidence)}</p><h4>UK gap check</h4><p class="quote">${esc(l.gap)}</p>`;
    if (l.tab === "closing") middle = `<h4>Likely assets</h4><p class="quote">${esc(l.assets)} <br><span class="hint">Asset appeal: ${esc(l.appealLabel)}, judged from the sector only. No valuation is implied.</span></p>
      <h4>From the notice</h4><p class="quote">${esc(l.excerpt)}</p><p class="hint">Sector match: ${esc(l.matchConfidence)}.</p>
      ${(l.ips || []).length ? `<h4>Office-holder named in the notice</h4><ul class="who">${l.ips.map((p) => `<li>${esc((p.name || "").replace(/\b\w/g, (c) => c.toUpperCase()))}${p.hasIPnum ? ` (IP no. ${esc(p.hasIPnum)})` : ""}${p.email ? ` · <a href="mailto:${esc(p.email)}">${esc(p.email)}</a>` : ""}${p.telephone ? ` · ${esc(p.telephone)}` : ""}</li>`).join("")}</ul><p class="hint">Professional contact as published in the public notice.</p>` : ""}
      ${l.nearby && l.nearby.length ? `<h4>Possible buyers nearby (OpenStreetMap)</h4><ul class="nearby">${l.nearby.map((n) => `<li><a href="${esc(n.osm)}" target="_blank" rel="noopener">${esc(n.name)}</a> · ${esc(n.kind)}${n.km != null ? ` · ${n.km} km` : ""}${n.web ? ` · <a href="${esc(n.web)}" target="_blank" rel="noopener">site</a>` : ""}</li>`).join("")}</ul>` : `<h4>Possible buyers nearby</h4><p class="hint">The OpenStreetMap lookup for nearby ${esc(l.buyers)} didn't respond today, so none are listed. It retries on every daily refresh.</p>`}`;
    if (l.tab === "twins") middle = `<h4>The two sides</h4><div class="sides">${l.sides.map((s) => `<div class="side"><b><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title)}</a></b>${esc(s.by || "")}<br><span class="hint">${esc([(s.place || {}).city, (s.place || {}).countryName || (s.place || {}).country].filter(Boolean).join(", "))} · ${esc(s.source)} · ${esc(s.created || "")}${s.stars != null ? ` · ★${s.stars}` : ""}</span>${s.desc ? `<p style="margin:6px 0 0">${esc(s.desc)}</p>` : ""}</div>`).join("")}</div>
      <h4>Why an intro is valuable</h4><p class="quote">${esc(l.why)}</p><p class="hint">Found by: ${esc(l.origin)}.</p>`;
    const who = (l.who || []).map((w) => `<li>${esc(w)}</li>`).join("");
    $("#detail").innerHTML = `<article class="d">
      <span class="d-k"><i class="dot ${l.tab}"></i>${esc(l.tabName)} · ${esc(l.kind || "")} · score ${l.score}</span>
      <h2 class="d-title" id="d-title">${esc(l.title)}</h2>
      <p class="d-sub">${esc(l.subtitle)}</p>
      <p class="d-worth">${esc(l.worth)}</p>
      <h4>Your status</h4>
      <div class="tracker" role="group" aria-label="Status">${STATUSES.map(([k, v]) => `<button type="button" data-st="${k}" aria-pressed="${st(id) === k}">${v}</button>`).join("")}</div>
      <textarea class="notes" placeholder="Notes (stay in this browser)…" aria-label="Notes">${esc(rec.notes || "")}</textarea>
      <h4>First move</h4><p class="move">${esc(l.firstMove)}</p>
      ${middle}
      <h4>The facts</h4><dl class="facts">${facts}</dl>
      ${l.place || l.place2 ? `<div class="minimap" id="minimap"></div>` : ""}
      <h4>Who might want it</h4><ul class="who">${who}</ul>
      <h4>Suggested deal</h4><p class="move">${esc(l.deal)}</p>
      ${l.warning ? `<p class="warn">${esc(l.warning)}</p>` : ""}
      <h4>Outreach draft <span class="hint" style="text-transform:none;letter-spacing:0">(copy, edit and send yourself. Nothing is sent from here)</span></h4>
      <div class="draft"><textarea aria-label="Outreach draft">${esc(l.outreach)}</textarea><button class="ghost copy" type="button">Copy</button></div>
      <h4>Content angle</h4><p class="move">${esc(l.angle)}</p>
      <h4>Sources</h4><ul class="srcs">${l.sources.map((s) => `<li><span><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.name)}</a><br><small>${esc(s.licence || "")}</small></span><small>${esc({ official: "Official record", academic: "Scholarly", platform: "Platform data", community: "Community data", "official-stale": "Official, stale" }[s.trust] || s.trust || "")}</small></li>`).join("")}</ul>
      <p class="hint" style="margin-top:12px">Trust: ${esc(l.trust.label)} · Freshness: ${esc(l.freshness.label)}${l.trust.deadLinks.length ? " · a source link failed today's check" : ""}</p>
      <p class="hint">Referral fees must be disclosed to both sides. <a href="#rules" data-goto="rules">Read the rules</a> before outreach.</p>
    </article>`;
    const d = $("#drawer"); d.classList.add("open"); d.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    $(".drawer-panel").scrollTop = 0; $(".drawer-panel").focus();
    $$(".tracker button", d).forEach((b) => b.onclick = () => {
      store[id] = { ...(store[id] || {}), status: b.dataset.st, at: new Date().toISOString() }; saveStore();
      $$(".tracker button", d).forEach((x) => x.setAttribute("aria-pressed", x === b)); toast("Status saved"); refreshCard(id);
    });
    const n = $(".notes", d); n.oninput = () => { store[id] = { ...(store[id] || {}), notes: n.value }; saveStore(); clearTimeout(n.t); n.t = setTimeout(() => refreshCard(id), 600); };
    $(".copy", d).onclick = async () => { const t = $(".draft textarea", d); try { await navigator.clipboard.writeText(t.value); } catch { t.select(); document.execCommand("copy"); } toast("Draft copied"); };
    const gl = $('[data-goto="rules"]', d); if (gl) gl.onclick = (e) => { e.preventDefault(); closeLead(); setView("rules"); };
    if (push) history.replaceState(null, "", "#lead=" + encodeURIComponent(id));
    if ((l.place || l.place2) && window.maplibregl) setTimeout(() => miniMap(l), 30);
  }

  function refreshCard(id) { const el = $(`.lead[data-id="${CSS.escape(id)}"]`); if (el) { const i = +el.dataset.i; el.outerHTML = card(BY[id], i); } }
  function closeLead() { const d = $("#drawer"); d.classList.remove("open"); d.setAttribute("aria-hidden", "true"); document.body.style.overflow = ""; if (location.hash.startsWith("#lead=")) history.replaceState(null, "", view === "desk" ? "#" + (tab === "all" ? "" : tab) : "#" + view); }

  /* ---------- map ---------- */
  function baseStyle() {
    return { version: 8, sources: { c: { type: "geojson", data: "data/countries.geojson" } },
      layers: [{ id: "bg", type: "background", paint: { "background-color": "#e9f0f0" } },
        { id: "land", type: "fill", source: "c", paint: { "fill-color": "#f8f4ec" } },
        { id: "edge", type: "line", source: "c", paint: { "line-color": "#d6ccb9", "line-width": 0.6 } }] };
  }
  const COL = { revival: "#7d2f3b", import: "#2f5d50", closing: "#2c4a6e", twins: "#8a6a2f" };
  function points(list) {
    const f = [], lines = [];
    for (const l of list) {
      for (const p of [l.place, l.place2]) if (p && isFinite(p.lat) && isFinite(p.lon)) f.push({ type: "Feature", geometry: { type: "Point", coordinates: [p.lon, p.lat] }, properties: { id: l.id, tab: l.tab, title: l.title, sub: l.subtitle, score: l.score, prec: p.precision || "" } });
      if (l.place && l.place2) lines.push({ type: "Feature", geometry: { type: "LineString", coordinates: arc([l.place.lon, l.place.lat], [l.place2.lon, l.place2.lat]) }, properties: { tab: l.tab } });
    }
    return { pts: { type: "FeatureCollection", features: f }, lines: { type: "FeatureCollection", features: lines } };
  }
  function arc(a, b) { const out = []; const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2 + Math.min(25, Math.hypot(b[0] - a[0], b[1] - a[1]) * 0.18); for (let t = 0; t <= 1.0001; t += 0.05) { const x = (1 - t) * (1 - t) * a[0] + 2 * (1 - t) * t * mx + t * t * b[0]; const y = (1 - t) * (1 - t) * a[1] + 2 * (1 - t) * t * my + t * t * b[1]; out.push([x, y]); } return out; }
  function initMap() {
    if (map || !window.maplibregl) return;
    map = new maplibregl.Map({ container: "map", style: baseStyle(), center: [-1.5, 52.8], zoom: 4.6, attributionControl: { compact: true, customAttribution: "Natural Earth · data: Gazette, IPO, Wikidata, OSM, GitHub" } });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    map.on("load", () => {
      map.addSource("pts", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addSource("lines", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({ id: "arcs", type: "line", source: "lines", paint: { "line-color": "#a8843a", "line-width": 1.2, "line-opacity": 0.55, "line-dasharray": [2, 2] } });
      map.addLayer({ id: "halo", type: "circle", source: "pts", paint: { "circle-radius": ["interpolate", ["linear"], ["get", "score"], 30, 7, 90, 13], "circle-color": ["match", ["get", "tab"], "revival", COL.revival, "import", COL.import, "closing", COL.closing, COL.twins], "circle-opacity": 0.14 } });
      map.addLayer({ id: "dots", type: "circle", source: "pts", paint: { "circle-radius": ["interpolate", ["linear"], ["get", "score"], 30, 3.5, 90, 6.5], "circle-color": ["match", ["get", "tab"], "revival", COL.revival, "import", COL.import, "closing", COL.closing, COL.twins], "circle-stroke-color": "#fffdf9", "circle-stroke-width": 1.2 } });
      map.on("mouseenter", "dots", () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", "dots", () => (map.getCanvas().style.cursor = ""));
      map.on("click", "dots", (e) => {
        const p = e.features[0].properties;
        const el = document.createElement("div");
        el.innerHTML = `<b>${esc(p.title)}</b>${esc(p.sub)}<br><span style="color:#7a7266">score ${p.score}${p.prec ? " · placed by " + esc(p.prec) : ""}</span><br><button type="button">Open lead</button>`;
        $("button", el).onclick = () => openLead(p.id);
        new maplibregl.Popup({ offset: 10, maxWidth: "280px" }).setLngLat(e.lngLat).setDOMContent(el).addTo(map);
      });
      mapReady = true; drawMap();
    });
  }
  function drawMap() {
    const on = new Set($$(".map-legend input:checked").map((i) => i.dataset.layer));
    const list = filtered().filter((l) => on.has(l.tab));
    const { pts, lines } = points(list);
    map.getSource("pts").setData(pts); map.getSource("lines").setData(lines);
    const withLoc = list.filter((l) => l.place).length;
    $("#map-note").textContent = `${withLoc} of ${list.length} filtered leads have a location. Import leads sit at the brand's home country; trade marks have no reliable location and aren't drawn.`;
  }
  function miniMap(l) {
    const el = $("#minimap"); if (!el) return;
    const m = new maplibregl.Map({ container: el, style: baseStyle(), center: [l.place.lon, l.place.lat], zoom: l.place.precision === "country" ? 3 : 6, interactive: true, attributionControl: false });
    m.on("load", () => {
      const { pts, lines } = points([l]);
      m.addSource("p", { type: "geojson", data: pts }); m.addSource("l", { type: "geojson", data: lines });
      m.addLayer({ id: "l", type: "line", source: "l", paint: { "line-color": "#a8843a", "line-width": 1.4, "line-dasharray": [2, 2] } });
      m.addLayer({ id: "p", type: "circle", source: "p", paint: { "circle-radius": 6, "circle-color": COL[l.tab], "circle-stroke-color": "#fff", "circle-stroke-width": 1.5 } });
      if (l.place2) { const b = new maplibregl.LngLatBounds(); pts.features.forEach((f) => b.extend(f.geometry.coordinates)); m.fitBounds(b, { padding: 30, maxZoom: 5, duration: 0 }); }
    });
  }

  /* ---------- prose pages ---------- */
  async function renderSources() {
    if (SOURCES) return;
    try { SOURCES = await (await fetch("data/sources.json", { cache: "no-cache" })).json(); } catch { $("#sources").innerHTML = "<p>Couldn't load the source audit.</p>"; return; }
    const a = DATA.audit || {};
    const spot = (a.spotChecks || []);
    $("#sources").innerHTML = `<h1>Sources &amp; trust</h1>
      <p>Every lead links to its original record. Each source below is rated for who publishes it, how it's licensed, how fresh it is and how accurate it tends to be. A daily audit validates the data, spot-checks real records against the original pages, and checks source links. Anything that fails is flagged on the card, or held back.</p>
      <p class="hint">Last audit: ${a.generatedAt ? esc(fmtTime(a.generatedAt)) : "not yet run"}${a.summary ? " · " + esc(a.summary) : ""}</p>
      <h2>Today's checks</h2>
      <table class="audit"><thead><tr><th>Check</th><th>Tool</th><th>Result</th></tr></thead><tbody>
      ${a.schema ? `<tr><td>Data schema and types</td><td>frictionless-py</td><td>${esc(a.schema.result)}</td></tr>` : ""}
      ${a.linkCheck ? `<tr><td>Source links (sample)</td><td>${esc(a.linkCheck.tool)}</td><td>${esc(a.linkCheck.result)}</td></tr>` : ""}
      ${spot.map((s) => `<tr><td>Spot-check: ${esc(s.source)}</td><td>re-read original page</td><td>${s.passed}/${s.checked} matched${s.note ? " · " + esc(s.note) : ""}</td></tr>`).join("")}
      </tbody></table>
      <h2>Ratings</h2><div class="srcgrid">${SOURCES.sources.map((s) => `<div class="srccard"><h3>${esc(s.name)} <span class="grade ${esc(s.grade[0])}">${esc(s.grade)}</span></h3><p style="margin:0">${esc(s.verdict)}</p>
        <dl><dt>Publisher</dt><dd>${esc(s.publisher)}</dd><dt>Type</dt><dd>${esc(s.type)}</dd><dt>Licence</dt><dd>${esc(s.licence)}</dd><dt>Updates</dt><dd>${esc(s.updates)}</dd><dt>Stability</dt><dd>${esc(s.stability)}</dd><dt>Known issues</dt><dd>${esc(s.issues)}</dd><dt>Used for</dt><dd>${esc(s.usedFor)}</dd><dt>Link</dt><dd><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url.replace(/^https?:\/\//, ""))}</a></dd></dl></div>`).join("")}</div>
      <h2>Considered and left out</h2><ul>${SOURCES.skipped.map((s) => `<li><strong>${esc(s.name)}</strong>: ${esc(s.why)}</li>`).join("")}</ul>
      <h2>Free sign-ups that would add value</h2><ul>${SOURCES.signups.map((s) => `<li><strong>${esc(s.name)}</strong>: ${esc(s.why)} Sign up at <a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url.replace(/^https?:\/\//, ""))}</a>, then add the key as the repository secret <code>${esc(s.secret)}</code>.</li>`).join("")}</ul>`;
  }
  function renderRules() {
    $("#rules").innerHTML = `<h1>The rules</h1>
      <p>This desk finds leads. You decide what to do with them. Nothing here contacts anyone, and every draft is for you to edit and send yourself.</p>
      <h2>Disclose every fee</h2><p>Tell both sides, in writing and up front, that you're paid for the introduction, by whom, and roughly how much. Undisclosed commissions can be treated as secret commissions (bribes) under UK law, and can make a deal voidable.</p>
      <h2>Some referral fees are banned</h2><ul>
        <li><strong>Personal injury:</strong> paying or receiving referral fees for personal injury claims and services is prohibited (LASPO Act 2012, ss.56–60).</li>
        <li><strong>Regulated financial products, investments and credit:</strong> introducing for a fee can itself be a regulated activity (FSMA 2000; FCA rules), so don't broker investments, loans or insurance without authorisation.</li>
        <li><strong>Insolvency assets:</strong> office-holders must get the best price for creditors. Offer buyers to them openly. Don't ask for side payments from an insolvency practitioner.</li>
        <li><strong>Clinical assets:</strong> licensing deals involve regulated data and IP. Use specialist lawyers before anything is signed.</li></ul>
      <h2>GDPR and outreach</h2><ul>
        <li>Contact businesses and people only in a professional capacity, through channels they published for that purpose: a notice's office-holder contact, a company's partnerships page, or a project's issue tracker.</li>
        <li>For individuals (sole traders, makers, researchers), rely on <em>legitimate interest</em>. Keep it relevant and brief, say how you found them, and offer a clear opt-out. Stop if they say no.</li>
        <li>Under PECR, unsolicited marketing email to individual subscribers needs consent, so treat makers' personal addresses carefully and prefer their public project channels.</li>
        <li>Notes you write here stay in this browser only. If you move them into a CRM, keep a record of the lawful basis and delete data you no longer need.</li></ul>
      <h2>Names and trade marks</h2><p>A lapsed registration may still carry goodwill (passing off), and someone may have re-filed. Search the live UK and EU registers and take advice before anyone relaunches a name.</p>
      <h2>Honesty</h2><p>Every lead comes from a real public record and links to it. Scores rank leads and aren't valuations. Asset appeal is judged from the sector, not from inspection. The UK-gap check covers what OpenStreetMap has mapped, not online sales or stockists.</p>`;
  }

  /* ---------- views, routing, keys ---------- */
  function setView(v, push = true) {
    view = v;
    $$(".view").forEach((s) => (s.hidden = s.id !== "view-" + v));
    $$(".topnav button").forEach((b) => b.classList.toggle("on", b.dataset.view === v));
    if (v === "map") { initMap(); if (mapReady) { map.resize(); drawMap(); } }
    if (v === "sources") renderSources();
    if (v === "rules") renderRules();
    if (push) history.replaceState(null, "", v === "desk" ? "#" + (tab === "all" ? "" : tab) : "#" + v);
    window.scrollTo(0, 0);
  }
  function setTab(t) { tab = t; fillFilters(); render(); if (view !== "desk") setView("desk"); else history.replaceState(null, "", "#" + (t === "all" ? "" : t)); }
  function readHash() {
    const h = decodeURIComponent(location.hash.slice(1));
    if (h.startsWith("lead=")) { const id = h.slice(5); if (BY[id]) { tab = "all"; setTimeout(() => openLead(id, false), 0); } return; }
    if (["revival", "import", "closing", "twins"].includes(h)) tab = h;
    if (["map", "sources", "rules"].includes(h)) setTimeout(() => setView(h, false), 0);
  }
  function moveCursor(d) {
    const items = $$("#leads .lead"); if (!items.length) return;
    cursor = Math.max(0, Math.min(items.length - 1, cursor + d));
    items.forEach((x, i) => x.classList.toggle("cursor", i === cursor));
    items[cursor].focus({ preventScroll: true }); items[cursor].scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
  function bind() {
    $$(".topnav button, .brand").forEach((b) => b.addEventListener("click", (e) => { e.preventDefault(); setView(b.dataset.view); }));
    $$("#tabs button").forEach((b) => (b.onclick = () => setTab(b.dataset.tab)));
    const q = $("#q"); let t; q.oninput = () => { clearTimeout(t); t = setTimeout(() => { state.q = q.value; render(); }, 120); };
    for (const id of ["cat", "kind", "status", "sort"]) $("#" + id).onchange = (e) => { state[id] = e.target.value; render(); };
    $("#lux").onchange = (e) => { state.lux = e.target.checked; render(); };
    $("#viewmap").onclick = () => setView("map");
    $("#more").onclick = () => { const n = $$("#leads .lead").length; limit += 60; render(true); $$("#leads .lead")[n]?.focus({ preventScroll: true }); };
    $("#clear").onclick = () => { Object.assign(state, { q: "", cat: "", kind: "", status: "", lux: false }); q.value = ""; $("#lux").checked = false; ["cat", "kind", "status"].forEach((i) => ($("#" + i).value = "")); render(); };
    const openFrom = (e) => { const li = e.target.closest("[data-id]"); if (li && !e.target.closest("a")) openLead(li.dataset.id); };
    $("#leads").onclick = openFrom; $("#five").onclick = openFrom;
    for (const el of [$("#leads"), $("#five")]) el.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.dataset.id) openLead(e.target.dataset.id); });
    $$("[data-close]").forEach((b) => (b.onclick = closeLead));
    $$(".map-legend input").forEach((i) => (i.onchange = () => mapReady && drawMap()));
    document.addEventListener("keydown", (e) => {
      const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName);
      if (e.key === "Escape") { if ($("#drawer").classList.contains("open")) closeLead(); else if (typing) document.activeElement.blur(); return; }
      if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
      if ($("#drawer").classList.contains("open")) return;
      if (e.key === "/") { e.preventDefault(); setView("desk"); q.focus(); }
      else if (e.key === "j") { e.preventDefault(); moveCursor(1); }
      else if (e.key === "k") { e.preventDefault(); moveCursor(-1); }
      else if (/^[1-5]$/.test(e.key)) setTab(["all", "revival", "import", "closing", "twins"][+e.key - 1]);
    });
  }
  boot();
})();
