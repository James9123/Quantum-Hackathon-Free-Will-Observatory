// Hand-rolled SVG line chart (no external libraries): one series, horizontal
// reference lines, one labelled marker and an optional "current setting" point.
// Drawn at the container's pixel width so 12 px text stays 12 px on a phone.
// Lines differ by dash pattern and markers by shape, never by color alone; the
// legend and the caller's text summary + data table carry the same information.

function niceStep(span, target) {
  const raw = span / Math.max(1, target);
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  for (const m of [1, 2, 2.5, 5, 10]) if (m * mag >= raw) return m * mag;
  return 10 * mag;
}

function ticks(lo, hi, target) {
  const step = niceStep(hi - lo, target);
  const out = [];
  for (let v = Math.ceil(lo / step - 1e-9) * step; v <= hi + 1e-9; v += step) out.push(Number(v.toFixed(10)));
  return { values: out, step };
}

// Decimals that show every tick exactly: a 0.25 step needs 2 (else 2.75 prints as 2.8).
export function decimalsFor(step) {
  let d = 0;
  while (d < 6 && Math.abs(step * Math.pow(10, d) - Math.round(step * Math.pow(10, d))) > 1e-6) d++;
  return d;
}

const DASH = { bound: "7 4", ideal: "2 3", marker: "8 3 2 3" };

export function renderChart(lib, container, cfg) {
  const { svg, replace, fmt } = lib;
  const width = Math.max(260, Math.round(container.clientWidth || 600));
  const height = Math.round(Math.min(360, Math.max(220, width * 0.6)));
  const m = { left: 48, right: 14, top: 14, bottom: 46 };
  const iw = width - m.left - m.right;
  const ih = height - m.top - m.bottom;
  const xs = cfg.xs;
  const ys = cfg.ys;
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const refYs = (cfg.hLines || []).map((l) => l.y);
  const yLo = Math.min(...ys, ...refYs);
  const yHi = Math.max(...ys, ...refYs);
  const pad = 0.06 * (yHi - yLo || 1);
  const yt = ticks(yLo - pad, yHi + pad, Math.max(3, Math.round(ih / 45)));
  const yMin = Math.min(yt.values[0], yLo - pad);
  const yMax = Math.max(yt.values[yt.values.length - 1], yHi + pad);
  const xt = ticks(xMin, xMax, Math.max(3, Math.round(iw / 60)));
  const X = (x) => m.left + ((x - xMin) / (xMax - xMin || 1)) * iw;
  const Y = (y) => m.top + (1 - (y - yMin) / (yMax - yMin || 1)) * ih;
  const uid = cfg.id || "qh-chart";

  const root = svg("svg", {
    viewBox: "0 0 " + width + " " + height, width, height, role: "img",
    "aria-labelledby": uid + "-title " + uid + "-desc", focusable: "false",
  },
  svg("title", { id: uid + "-title" }, cfg.title),
  svg("desc", { id: uid + "-desc" }, cfg.desc || ""));

  const grid = svg("g", { class: "qh-c-grid", "aria-hidden": "true" });
  for (const v of yt.values) {
    if (v < yMin - 1e-9 || v > yMax + 1e-9) continue;
    grid.appendChild(svg("line", { x1: m.left, x2: m.left + iw, y1: Y(v), y2: Y(v) }));
    grid.appendChild(svg("text", { x: m.left - 6, y: Y(v) + 4, "text-anchor": "end" }, fmt(v, decimalsFor(yt.step))));
  }
  for (const v of xt.values) {
    grid.appendChild(svg("line", { x1: X(v), x2: X(v), y1: m.top + ih, y2: m.top + ih + 5, class: "qh-c-axis" }));
    grid.appendChild(svg("text", { x: X(v), y: m.top + ih + 18, "text-anchor": "middle" }, fmt(v, decimalsFor(xt.step))));
  }
  grid.appendChild(svg("line", { x1: m.left, x2: m.left + iw, y1: m.top + ih, y2: m.top + ih, class: "qh-c-axis" }));
  grid.appendChild(svg("line", { x1: m.left, x2: m.left, y1: m.top, y2: m.top + ih, class: "qh-c-axis" }));
  grid.appendChild(svg("text", { x: m.left + iw / 2, y: height - 6, "text-anchor": "middle", class: "qh-axis-label" }, cfg.xLabel));
  grid.appendChild(svg("text", { x: 12, y: m.top + ih / 2, "text-anchor": "middle", class: "qh-axis-label",
    transform: "rotate(-90 12 " + (m.top + ih / 2) + ")" }, cfg.yLabel || "S"));
  root.appendChild(grid);

  const plot = svg("g", { "aria-hidden": "true" });
  for (const line of cfg.hLines || []) {
    plot.appendChild(svg("line", { x1: m.left, x2: m.left + iw, y1: Y(line.y), y2: Y(line.y),
      class: "qh-c-" + line.kind, "stroke-dasharray": DASH[line.kind] || "4 4" }));
    // Label the end where the curve is farther from this line, so the label never
    // sits on the curve or on the crossing marker (on a narrow chart they collide).
    const gapLeft = Math.abs(Y(ys[0]) - Y(line.y));
    const gapRight = Math.abs(Y(ys[ys.length - 1]) - Y(line.y));
    const left = gapLeft > gapRight;
    plot.appendChild(svg("text", { x: left ? m.left + 6 : m.left + iw - 4, y: Y(line.y) - 5,
      "text-anchor": left ? "start" : "end", class: "qh-c-label" }, line.short));
  }
  const pts = xs.map((x, i) => X(x).toFixed(1) + "," + Y(ys[i]).toFixed(1)).join(" ");
  plot.appendChild(svg("polyline", { points: pts, class: "qh-c-curve" }));
  if (cfg.marker && Number.isFinite(cfg.marker.x)) {
    const mx = X(cfg.marker.x);
    plot.appendChild(svg("line", { x1: mx, x2: mx, y1: m.top + ih, y2: Y(cfg.marker.y),
      class: "qh-c-marker", "stroke-dasharray": DASH.marker }));
    plot.appendChild(svg("circle", { cx: mx, cy: Y(cfg.marker.y), r: 5, class: "qh-c-marker-dot" }));
    plot.appendChild(svg("text", { x: mx - 8, y: Y(cfg.marker.y) + 18, "text-anchor": "end", class: "qh-c-label" }, cfg.marker.short || ""));
  }
  if (cfg.point && Number.isFinite(cfg.point.x) && Number.isFinite(cfg.point.y)) {
    const px = X(Math.min(xMax, Math.max(xMin, cfg.point.x)));
    const py = Y(Math.min(yMax, Math.max(yMin, cfg.point.y)));
    plot.appendChild(svg("path", { d: "M" + px + " " + (py - 7) + " L" + (px + 7) + " " + py + " L" + px + " " + (py + 7) +
      " L" + (px - 7) + " " + py + " Z", class: "qh-c-point" }));
  }
  root.appendChild(plot);
  replace(container, root);
}

// Legend entries with tiny inline swatches (decorative) and full text labels.
export function renderLegend(lib, listEl, cfg) {
  const { h, svg, replace } = lib;
  const sw = (...children) => svg("svg", { width: 28, height: 14, viewBox: "0 0 28 14", "aria-hidden": "true", focusable: "false" }, ...children);
  const items = [h("li", {}, sw(svg("line", { x1: 1, x2: 27, y1: 7, y2: 7, class: "qh-c-curve" })), cfg.seriesLabel || "exact S")];
  for (const line of cfg.hLines || []) {
    items.push(h("li", {}, sw(svg("line", { x1: 1, x2: 27, y1: 7, y2: 7, class: "qh-c-" + line.kind, "stroke-dasharray": DASH[line.kind] || "4 4" })), line.label));
  }
  if (cfg.marker && Number.isFinite(cfg.marker.x)) {
    items.push(h("li", {}, sw(svg("circle", { cx: 14, cy: 7, r: 5, class: "qh-c-marker-dot" })), cfg.marker.label));
  }
  items.push(h("li", {}, sw(svg("path", { d: "M14 0 L21 7 L14 14 L7 7 Z", class: "qh-c-point" })),
    cfg.point ? cfg.point.label : "your dial setting: not on this curve (the dial uses the other noise model)"));
  replace(listEl, items);
}
