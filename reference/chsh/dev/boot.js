// Stub-mode boot: mimic how Qollab starts a JS project, then start main.js unchanged.
//   - globalThis.backend: a stand-in object (Qollab injects a PyProxy instead)
//   - main.js starts first; index.html is injected with innerHTML a little later,
//     so main.js's whenMounted() polling is exercised
// Query parameters: ?backend=basic|readout|ionq|error|none  &mount=ms  &slow=N  &axe=1
// (none: no global `backend` at all, to exercise main.js's missing-backend path)

const params = new URLSearchParams(location.search);
const kind = params.get("backend") || "basic";
const mountDelay = Number(params.get("mount") || 300);
const NAMES = {
  basic: "basic_simulator",
  readout: "basic_simulator+readout_flips (stand-in)",
  ionq: "ionq_simulator (stand-in: local ideal simulator)",
  error: "basic_simulator (stand-in that fails)",
};
if (kind !== "none") globalThis.backend = { name: NAMES[kind] || NAMES.basic, stubKind: kind };

for (const a of document.querySelectorAll("[data-scenario]")) {
  if (a.dataset.scenario === kind) a.setAttribute("aria-current", "page");
}

// main.js never settles (it ends with `await new Promise(() => {})`), so do not await it.
import("../main.js").catch((err) => console.error("main.js failed: " + err));

const html = await (await fetch("../index.html", { cache: "no-store" })).text();
setTimeout(() => {
  document.getElementById("qollab-root").innerHTML = html;
}, mountDelay);

if (params.get("axe") === "1") {
  // Dev only: axe-core from the one CDN Qollab allows. Never loaded by qollab_project/.
  const s = document.createElement("script");
  s.src = "https://cdn.jsdelivr.net/npm/axe-core@4.10.2/axe.min.js";
  s.onload = () => setTimeout(async () => {
    const res = await globalThis.axe.run(document.getElementById("qh-app"));
    const lines = res.violations.map((v) => v.id + " (" + v.impact + "): " + v.help + " -- " +
      v.nodes.map((n) => n.target.join(" ")).join(" | "));
    const out = document.getElementById("axe-out");
    out.hidden = false;
    out.textContent = "axe-core " + globalThis.axe.version + ": " + res.violations.length + " violation(s), " +
      res.passes.length + " passing rules, " + res.incomplete.length + " needing review\n" + lines.join("\n");
    console.log(out.textContent);
  }, 2500);
  document.head.appendChild(s);
}
