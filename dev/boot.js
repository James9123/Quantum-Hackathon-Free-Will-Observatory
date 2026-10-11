// Stub-mode boot: mimic how Qollab starts a JS project, then start main.js unchanged.
//   - globalThis.backend: a stand-in object (Qollab injects a PyProxy instead)
//   - main.js starts first; index.html is injected with innerHTML a little later,
//     so main.js's whenMounted() polling is exercised
// Query parameters: ?backend=basic|ionq|error|none  &mount=ms  &slow=N  &axe=1  &reduce=1  &nowebgl=1
// (none: no global `backend` at all, to exercise main.js's missing-backend path;
//  reduce=1 makes matchMedia report prefers-reduced-motion: reduce, so the no-animation
//  path can be checked in a browser that cannot emulate the preference;
//  nowebgl=1 makes every canvas refuse a WebGL context, so the text-only fallback runs)

const params = new URLSearchParams(location.search);
const kind = params.get("backend") || "basic";
const mountDelay = Number(params.get("mount") || 300);
const NAMES = {
  basic: "basic_simulator",
  ionq: "ionq_simulator (stand-in: local ideal simulator)",
  error: "basic_simulator (stand-in that fails)",
};
if (kind !== "none") globalThis.backend = { name: NAMES[kind] || NAMES.basic, stubKind: kind };

if (params.get("reduce") === "1") {
  const real = globalThis.matchMedia.bind(globalThis);
  globalThis.matchMedia = (q) => (/prefers-reduced-motion/.test(q)
    ? { matches: true, media: q, addEventListener() {}, removeEventListener() {} }
    : real(q));
}

if (params.get("nowebgl") === "1") {
  const realGetContext = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (type, ...rest) {
    return /webgl/i.test(String(type)) ? null : realGetContext.call(this, type, ...rest);
  };
}

for (const a of document.querySelectorAll("[data-scenario]")) {
  if (a.dataset.scenario === kind) a.setAttribute("aria-current", "page");
}

// main.js never settles (it ends with `await new Promise(() => {})`), so do not await it.
import("../qollab_project/main.js").catch((err) => console.error("main.js failed: " + err));

const html = await (await fetch("../qollab_project/index.html", { cache: "no-store" })).text();
setTimeout(() => {
  document.getElementById("qollab-root").innerHTML = html;
}, mountDelay);

if (params.get("axe") === "1") {
  // Dev only: axe-core from the one CDN Qollab allows. Never loaded by qollab_project/.
  const s = document.createElement("script");
  s.src = "https://cdn.jsdelivr.net/npm/axe-core@4.10.2/axe.min.js";
  s.onload = () => setTimeout(async () => {
    const res = await globalThis.axe.run(document.getElementById("fwo-app"));
    const lines = res.violations.map((v) => v.id + " (" + v.impact + "): " + v.help + " -- " +
      v.nodes.map((n) => n.target.join(" ")).join(" | "));
    const out = document.getElementById("axe-out");
    out.hidden = false;
    out.textContent = "axe-core " + globalThis.axe.version + ": " + res.violations.length + " violation(s), " +
      res.passes.length + " passing rules, " + res.incomplete.length + " needing review\n" + lines.join("\n");
    console.log(out.textContent);
  }, 3000);
  document.head.appendChild(s);
}
