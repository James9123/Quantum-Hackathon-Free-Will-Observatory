// Hand-rolled SVG charts (no libraries). Bars and lines differ by fill pattern and
// dash, never by colour alone; every chart has a <title> and <desc>, and the caller
// shows the same numbers as text and as a table. No imports: main.js passes `lib`.

const BAR_DASH = "5 3";
const LINE_DASH = { solid: "", dashed: "7 4", dotted: "2 3", dashdot: "8 3 2 3" };

function num(x) {
  return typeof x === "number" && Number.isFinite(x) ? x : null;
}

// Before/after probability chart: Future 0 and Future 1, each with up to three bars:
// previous run (hatched), current run (solid), Demon forecast (outlined, dashed).
// cfg = {id, title, desc, groups: [{label, bars: [{kind: "previous"|"current"|"forecast", value, text}]}]}
export function renderBars(lib, container, cfg) {
  const { svg, replace, fmtPct } = lib;
  const width = Math.max(260, Math.round(container.clientWidth || 520));
  const height = Math.round(Math.min(300, Math.max(200, width * 0.5)));
  const groups = cfg.groups || [];
  const m = { left: 50, right: 12, top: 18, bottom: 34 };
  const iw = width - m.left - m.right;
  const gw = iw / Math.max(1, groups.length);
  // On a narrow chart neighbouring value labels would touch: alternate their height
  // (and leave room above the plot for the raised ones).
  const maxBars = Math.max(1, ...groups.map((g) => g.bars.filter((b) => num(b.value) !== null).length));
  const stagger = Math.min(56, (gw - 24) / maxBars) < 54 && maxBars > 1;
  if (stagger) m.top = 30;
  const ih = height - m.top - m.bottom;
  const uid = cfg.id || "fwo-bars";
  const Y = (p) => m.top + (1 - p) * ih;
  const root = svg("svg", { viewBox: "0 0 " + width + " " + height, width, height, role: "img",
    "aria-labelledby": uid + "-title " + uid + "-desc", focusable: "false", class: "fwo-svg" },
  svg("title", { id: uid + "-title" }, cfg.title),
  svg("desc", { id: uid + "-desc" }, cfg.desc || ""),
  svg("defs", {}, svg("pattern", { id: uid + "-hatch", patternUnits: "userSpaceOnUse", width: 6, height: 6, patternTransform: "rotate(45)" },
    svg("line", { x1: 0, y1: 0, x2: 0, y2: 6, class: "fwo-c-hatch" }))));
  const grid = svg("g", { class: "fwo-c-grid", "aria-hidden": "true" });
  for (const p of [0, 0.25, 0.5, 0.75, 1]) {
    grid.appendChild(svg("line", { x1: m.left, x2: m.left + iw, y1: Y(p), y2: Y(p) }));
    grid.appendChild(svg("text", { x: m.left - 6, y: Y(p) + 4, "text-anchor": "end" }, fmtPct(p, 0)));
  }
  grid.appendChild(svg("line", { x1: m.left, x2: m.left + iw, y1: Y(0), y2: Y(0), class: "fwo-c-axis" }));
  root.appendChild(grid);
  const plot = svg("g", { "aria-hidden": "true" });
  groups.forEach((g, gi) => {
    const bars = g.bars.filter((b) => num(b.value) !== null);
    const slot = Math.min(56, (gw - 24) / Math.max(1, bars.length));
    const x0 = m.left + gi * gw + (gw - slot * bars.length) / 2;
    bars.forEach((b, bi) => {
      const x = x0 + bi * slot + 4;
      const w = slot - 8;
      const y = Y(b.value);
      const attrs = { x, y, width: w, height: Math.max(0, Y(0) - y), class: "fwo-c-bar fwo-c-bar--" + b.kind };
      if (b.kind === "previous") attrs.fill = "url(#" + uid + "-hatch)";
      if (b.kind === "forecast") attrs["stroke-dasharray"] = BAR_DASH;
      plot.appendChild(svg("rect", attrs));
      const lift = stagger && bi % 2 === 1 ? 12 : 0;
      plot.appendChild(svg("text", { x: x + w / 2, y: Math.max(m.top - 4 - lift, y - 4 - lift), "text-anchor": "middle", class: "fwo-c-value" }, b.text || fmtPct(b.value)));
    });
    plot.appendChild(svg("text", { x: m.left + gi * gw + gw / 2, y: height - 10, "text-anchor": "middle", class: "fwo-c-cat" }, g.label));
  });
  root.appendChild(plot);
  replace(container, root);
}

// Legend for the bar chart: swatches are decorative; the text carries the meaning.
export function renderBarLegend(lib, listEl, items) {
  const { h, svg, replace } = lib;
  const sw = (kind) => {
    const attrs = { x: 1, y: 1, width: 26, height: 12, class: "fwo-c-bar fwo-c-bar--" + kind };
    if (kind === "forecast") attrs["stroke-dasharray"] = BAR_DASH;
    const s = svg("svg", { width: 28, height: 14, viewBox: "0 0 28 14", "aria-hidden": "true", focusable: "false" });
    if (kind === "previous") {
      s.appendChild(svg("defs", {}, svg("pattern", { id: "fwo-legend-hatch", patternUnits: "userSpaceOnUse", width: 6, height: 6, patternTransform: "rotate(45)" },
        svg("line", { x1: 0, y1: 0, x2: 0, y2: 6, class: "fwo-c-hatch" }))));
      attrs.fill = "url(#fwo-legend-hatch)";
    }
    s.appendChild(svg("rect", attrs));
    return s;
  };
  replace(listEl, items.map((it) => h("li", {}, sw(it.kind), it.label)));
}

// Multi-series line chart on a shared x grid, y fixed to [0, 1].
// cfg = {id, title, desc, xLabel, yLabel, xs, series: [{label, ys, dash, cls}], point: {x, y, label}|null}
export function renderLines(lib, container, cfg) {
  const { svg, replace, fmt } = lib;
  const width = Math.max(260, Math.round(container.clientWidth || 520));
  const height = Math.round(Math.min(320, Math.max(200, width * 0.55)));
  const m = { left: 46, right: 14, top: 14, bottom: 44 };
  const iw = width - m.left - m.right;
  const ih = height - m.top - m.bottom;
  const xs = cfg.xs || [];
  const xMin = Math.min(...xs), xMax = Math.max(...xs);
  const X = (x) => m.left + ((x - xMin) / (xMax - xMin || 1)) * iw;
  const Y = (y) => m.top + (1 - Math.max(0, Math.min(1, y))) * ih;
  const uid = cfg.id || "fwo-lines";
  const root = svg("svg", { viewBox: "0 0 " + width + " " + height, width, height, role: "img",
    "aria-labelledby": uid + "-title " + uid + "-desc", focusable: "false", class: "fwo-svg" },
  svg("title", { id: uid + "-title" }, cfg.title),
  svg("desc", { id: uid + "-desc" }, cfg.desc || ""));
  const grid = svg("g", { class: "fwo-c-grid", "aria-hidden": "true" });
  for (const p of [0, 0.25, 0.5, 0.75, 1]) {
    grid.appendChild(svg("line", { x1: m.left, x2: m.left + iw, y1: Y(p), y2: Y(p) }));
    grid.appendChild(svg("text", { x: m.left - 6, y: Y(p) + 4, "text-anchor": "end" }, fmt(p, 2)));
  }
  const nx = Math.max(2, Math.min(6, Math.round(iw / 70)));
  for (let i = 0; i <= nx; i++) {
    const x = xMin + (xMax - xMin) * i / nx;
    grid.appendChild(svg("line", { x1: X(x), x2: X(x), y1: m.top + ih, y2: m.top + ih + 5, class: "fwo-c-axis" }));
    grid.appendChild(svg("text", { x: X(x), y: m.top + ih + 18, "text-anchor": "middle" }, fmt(x, 2)));
  }
  grid.appendChild(svg("line", { x1: m.left, x2: m.left + iw, y1: m.top + ih, y2: m.top + ih, class: "fwo-c-axis" }));
  grid.appendChild(svg("line", { x1: m.left, x2: m.left, y1: m.top, y2: m.top + ih, class: "fwo-c-axis" }));
  grid.appendChild(svg("text", { x: m.left + iw / 2, y: height - 6, "text-anchor": "middle", class: "fwo-axis-label" }, cfg.xLabel || ""));
  grid.appendChild(svg("text", { x: 12, y: m.top + ih / 2, "text-anchor": "middle", class: "fwo-axis-label",
    transform: "rotate(-90 12 " + (m.top + ih / 2) + ")" }, cfg.yLabel || ""));
  root.appendChild(grid);
  const plot = svg("g", { "aria-hidden": "true" });
  for (const s of cfg.series || []) {
    if (!s.ys || s.ys.length !== xs.length) continue;
    const pts = xs.map((x, i) => X(x).toFixed(1) + "," + Y(s.ys[i]).toFixed(1)).join(" ");
    const attrs = { points: pts, class: "fwo-c-line " + (s.cls || "") };
    if (LINE_DASH[s.dash]) attrs["stroke-dasharray"] = LINE_DASH[s.dash];
    plot.appendChild(svg("polyline", attrs));
  }
  if (cfg.point && num(cfg.point.x) !== null && num(cfg.point.y) !== null) {
    const px = X(cfg.point.x), py = Y(cfg.point.y);
    plot.appendChild(svg("path", { d: "M" + px + " " + (py - 7) + " L" + (px + 7) + " " + py + " L" + px + " " + (py + 7) +
      " L" + (px - 7) + " " + py + " Z", class: "fwo-c-point" }));
  }
  root.appendChild(plot);
  replace(container, root);
}

export function renderLineLegend(lib, listEl, cfg) {
  const { h, svg, replace } = lib;
  const items = (cfg.series || []).map((s) => {
    const attrs = { x1: 1, x2: 27, y1: 7, y2: 7, class: "fwo-c-line " + (s.cls || "") };
    if (LINE_DASH[s.dash]) attrs["stroke-dasharray"] = LINE_DASH[s.dash];
    return h("li", {}, svg("svg", { width: 28, height: 14, viewBox: "0 0 28 14", "aria-hidden": "true", focusable: "false" }, svg("line", attrs)), s.label);
  });
  if (cfg.point) {
    items.push(h("li", {}, svg("svg", { width: 28, height: 14, viewBox: "0 0 28 14", "aria-hidden": "true", focusable: "false" },
      svg("path", { d: "M14 0 L21 7 L14 14 L7 7 Z", class: "fwo-c-point" })), cfg.point.label));
  }
  replace(listEl, items);
}
