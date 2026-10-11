// Small DOM and formatting helpers shared by the UI modules.
// No imports, no globals beyond `document`: main.js passes in anything else
// (setTimeout is injected by Qollab, so callers hand it over explicitly).

const SVG_NS = "http://www.w3.org/2000/svg";

// Wait until an element with this id exists. Qollab injects index.html with
// innerHTML, which may land after main.js has started.
export function whenMounted(id, setTimeoutFn, timeoutMs = 15000, intervalMs = 25) {
  return new Promise((resolve, reject) => {
    const started = Date.now();
    const poll = () => {
      const node = document.getElementById(id);
      if (node) {
        resolve(node);
      } else if (Date.now() - started > timeoutMs) {
        reject(new Error("element #" + id + " did not appear within " + timeoutMs + " ms"));
      } else {
        setTimeoutFn(poll, intervalMs);
      }
    };
    poll();
  });
}

export function byId(id) {
  const node = document.getElementById(id);
  if (!node) throw new Error("missing element #" + id);
  return node;
}

function setAttrs(node, attrs) {
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "text") node.textContent = String(value);
    else if (key === "class") node.setAttribute("class", value);
    else if (key === "for") node.setAttribute("for", value);
    else node.setAttribute(key, value === true ? "" : String(value));
  }
}

function append(node, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    node.appendChild(typeof child === "object" ? child : document.createTextNode(String(child)));
  }
}

// h("p", {class: "x"}, "text", h("strong", {}, "bold")): text is always set as text,
// never parsed as HTML, so values from Python cannot inject markup.
export function h(tag, attrs, ...children) {
  const node = document.createElement(tag);
  setAttrs(node, attrs);
  append(node, children);
  return node;
}

export function svg(tag, attrs, ...children) {
  const node = document.createElementNS(SVG_NS, tag);
  setAttrs(node, attrs);
  append(node, children);
  return node;
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
}

export function replace(node, ...children) {
  clear(node);
  append(node, children);
  return node;
}

const MINUS = "\u2212";

function isNum(x) {
  return typeof x === "number" && Number.isFinite(x);
}

// Fixed-point number with a real minus sign; null/undefined/NaN -> "n/a".
export function fmt(x, digits = 3) {
  if (!isNum(x)) return "n/a";
  const s = Math.abs(x).toFixed(digits);
  return (x < 0 && Number(s) !== 0 ? MINUS : "") + s;
}

export function fmtSigned(x, digits = 2) {
  if (!isNum(x)) return "n/a";
  const s = Math.abs(x).toFixed(digits);
  return (Number(s) === 0 ? "" : x < 0 ? MINUS : "+") + s;
}

export function fmtInt(n) {
  if (n === null || n === undefined || !Number.isFinite(Number(n))) return "n/a";
  return Math.round(Number(n)).toLocaleString("en-US");
}

export function fmtPct(x, digits = 1) {
  if (!isNum(x)) return "n/a";
  return (100 * x).toFixed(digits) + "%";
}

// Degrees text for an angle in radians: "90 degrees" (the degree sign is \u00b0).
export function fmtDeg(rad, digits = 0) {
  if (!isNum(rad)) return "n/a";
  return fmt((180 / Math.PI) * rad, digits) + "\u00b0";
}

// Radians and degrees together: "1.571 rad (90 degrees)".
export function fmtRad(rad, digits = 3) {
  if (!isNum(rad)) return "n/a";
  return fmt(rad, digits) + " rad (" + fmtDeg(rad) + ")";
}

// Trailing-edge debounce without clearTimeout (only setTimeout is injected):
// every call bumps a generation counter and only the newest timer fires.
export function debounce(fn, ms, setTimeoutFn) {
  let generation = 0;
  return (...args) => {
    const mine = ++generation;
    setTimeoutFn(() => {
      if (mine === generation) fn(...args);
    }, ms);
  };
}

let tableCount = 0;

// A table from a header row and body rows. Cells are strings or {text, scope, class}.
// The title sits in a paragraph above the scroll box (so it wraps on a phone) and
// names both the table and its keyboard-scrollable region via aria-labelledby.
export function table(caption, headers, rows, opts = {}) {
  const cell = (tag, c, extra) => {
    const spec = typeof c === "object" && c !== null ? c : { text: c };
    const attrs = Object.assign({}, extra, spec.class ? { class: spec.class } : {}, spec.scope ? { scope: spec.scope } : {});
    return h(tag, attrs, spec.text === undefined ? "" : String(spec.text));
  };
  const capId = "fwo-tcap-" + ++tableCount;
  const t = h("table", { "aria-labelledby": capId },
    h("thead", {}, h("tr", {}, headers.map((c) => cell("th", c, { scope: "col" })))),
    h("tbody", {}, rows.map((row) => h("tr", {}, row.map((c, i) =>
      i === 0 && opts.rowHeaders !== false ? cell("th", c, { scope: "row" }) : cell("td", c, {}))))));
  // A scrollable region must be reachable by keyboard: tabindex + a name.
  return h("div", { class: "fwo-table" },
    h("p", { id: capId, class: "fwo-table-cap" }, caption || opts.label || "Table"),
    h("div", { class: "fwo-scroll" + (opts.tall ? " fwo-scroll--tall" : ""), role: "region", tabindex: "0",
      "aria-labelledby": capId }, t));
}
