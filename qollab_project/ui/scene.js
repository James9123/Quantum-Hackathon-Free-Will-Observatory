// The Observatory scene: a brain-shaped graph (the fictional Self), two future
// regions, a World sphere and its bridge, drawn with three.js.
//
// Visual mappings (build guide p.10), applied from the completed display run only:
//   future sphere radius   = RMAX * cbrt(p)              (volume follows probability)
//   branch thickness       = 2 + 10 p  pixels            (converted to world units at
//                                                          the branch depth, so it is
//                                                          really that many pixels)
//   World bridge           thickness 2 + 10 I px, opacity 0.15 + 0.85 I  (I in bits,
//                                                          from the separate connection probe)
//   previous distribution  muted wireframe ghost labelled "previous" until the next
//                          result arrives; the live geometry then animates over ~1 s
//   particles              a FIXED number of points routed to the two branches in
//                          proportions p0 / p1; decoration, never shot chronology
// The brain graph (two ellipsoid lobes, 100 nodes, 3 nearest-neighbour links each) is
// generated once from a seeded PRNG and never moves with the data: a change in the
// picture always means a change in the numbers. No imports: main.js passes in the
// three.js module (THREE) and the dom helpers (lib).

const N_NODES = 100;
const LINKS_PER_NODE = 3;
const N_PARTICLES = 520;
const RMAX = 0.62;                 // sphere radius at p = 1 (world units)
const FOV = 38;
const BASE_COLORS = {   // defaults; main.js may override any key from CSS variables (themes)
  bg: 0x0b1326, self: 0x2dd4bf, selfLight: 0x99f6e4, selfDeep: 0x0f766e,
  world: 0xf59e0b, worldLight: 0xfcd34d, worldDeep: 0x92400e, ghost: 0x9fb3cf, link: 0x2dd4bf,
};
const P = {
  brain: [-1.35, 0.12, 0],
  lobeOffset: 0.52, lobeRadii: [0.98, 0.78, 0.66],
  f1: [2.25, 1.02, 0], f0: [2.25, -1.05, 0],
  world: [-1.35, -1.95, -0.3], worldR: 0.4,
  center: [0.35, -0.2, 0],
};

// Small, fast, seeded PRNG (mulberry32): the brain's geometry must be the same on
// every load, so nothing here uses the browser's unseeded random source.
export function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function ease(s) {
  return s < 0.5 ? 2 * s * s : 1 - Math.pow(-2 * s + 2, 2) / 2;
}

function clamp01(x) {
  return Math.max(0, Math.min(1, Number.isFinite(x) ? x : 0));
}

// Node positions for two ellipsoid lobes, biased toward the surface (a cortex), and
// the 3-nearest-neighbour link list. Pure function of the seed.
export function brainGraph(seed, nNodes = N_NODES, perNode = LINKS_PER_NODE) {
  const rand = mulberry32(seed);
  const nodes = [];
  const half = Math.floor(nNodes / 2);
  for (let i = 0; i < nNodes; i++) {
    const side = i < half ? -1 : 1;
    const u = rand() * 2 - 1;
    const th = rand() * 2 * Math.PI;
    const s = Math.sqrt(1 - u * u);
    const r = Math.cbrt(0.4 + 0.6 * rand());
    let x = s * Math.cos(th) * P.lobeRadii[0] * r;
    const y = s * Math.sin(th) * P.lobeRadii[1] * r;
    const z = u * P.lobeRadii[2] * r;
    // keep a visible fissure between the lobes
    if (side < 0 && x > -0.08) x = -0.08 - (x + 0.08) * 0.5;
    if (side > 0 && x < 0.08) x = 0.08 + (0.08 - x) * 0.5;
    nodes.push([x + side * P.lobeOffset, y, z]);
  }
  const pairs = new Set();
  const links = [];
  for (let i = 0; i < nodes.length; i++) {
    const d = [];
    for (let j = 0; j < nodes.length; j++) {
      if (j === i) continue;
      const dx = nodes[i][0] - nodes[j][0];
      const dy = nodes[i][1] - nodes[j][1];
      const dz = nodes[i][2] - nodes[j][2];
      d.push([dx * dx + dy * dy + dz * dz, j]);
    }
    d.sort((a, b) => a[0] - b[0]);
    for (let k = 0; k < perNode && k < d.length; k++) {
      const j = d[k][1];
      const key = i < j ? i + ":" + j : j + ":" + i;
      if (!pairs.has(key)) {
        pairs.add(key);
        links.push([i, j]);
      }
    }
  }
  return { nodes, links };
}

export function createScene(THREE, lib, host, opts) {
  const COLORS = Object.assign({}, BASE_COLORS, (opts && opts.colors) || {});
  const o = Object.assign({ reducedMotion: false, seed: 20261010 }, opts || {});
  const { h, replace } = lib;
  const api = { available: false };

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "low-power" });
  } catch (err) {
    replace(host, h("p", { class: "fwo-scene-fallback" },
      "The 3D view could not start in this browser (" + String(err && err.message ? err.message : err) +
      "). Every number it would show is in the text, readings and tables below."));
    return api;
  }
  api.available = true;
  renderer.setClearColor(COLORS.bg, 1);
  renderer.setPixelRatio(Math.min(2, (typeof devicePixelRatio === "number" && devicePixelRatio) || 1));
  const canvas = renderer.domElement;
  canvas.setAttribute("role", "img");
  canvas.setAttribute("aria-label", "Observatory scene (loading)");
  canvas.className = "fwo-canvas";
  const labelLayer = h("div", { class: "fwo-scene-labels", "aria-hidden": "true" });
  replace(host, canvas, labelLayer);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(FOV, 1.6, 0.1, 100);
  scene.add(new THREE.AmbientLight(0xffffff, 0.75));
  const key = new THREE.DirectionalLight(0xffffff, 1.4);
  key.position.set(3, 4, 6);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0x99f6e4, 0.5);
  rim.position.set(-4, -2, -3);
  scene.add(rim);

  // ---------------------------------------------------------------- the Self (brain)
  const brain = new THREE.Group();
  brain.position.set(P.brain[0], P.brain[1], P.brain[2]);
  brain.rotation.set(0.12, -0.42, 0.04);
  const baseRotY = brain.rotation.y;
  scene.add(brain);
  const graph = brainGraph(o.seed);
  const nodeGeom = new THREE.SphereGeometry(0.046, 8, 6);
  const nodeMat = new THREE.MeshStandardMaterial({ color: COLORS.selfLight, emissive: COLORS.selfDeep, emissiveIntensity: 0.6, roughness: 0.5 });
  const nodes = new THREE.InstancedMesh(nodeGeom, nodeMat, graph.nodes.length);
  const m4 = new THREE.Matrix4();
  graph.nodes.forEach((p, i) => { m4.makeTranslation(p[0], p[1], p[2]); nodes.setMatrixAt(i, m4); });
  nodes.instanceMatrix.needsUpdate = true;
  brain.add(nodes);
  const linkPos = new Float32Array(graph.links.length * 6);
  graph.links.forEach(([a, b], i) => {
    linkPos.set(graph.nodes[a], i * 6);
    linkPos.set(graph.nodes[b], i * 6 + 3);
  });
  const linkGeom = new THREE.BufferGeometry();
  linkGeom.setAttribute("position", new THREE.BufferAttribute(linkPos, 3));
  brain.add(new THREE.LineSegments(linkGeom, new THREE.LineBasicMaterial({ color: COLORS.link, transparent: true, opacity: 0.5 })));
  for (const side of [-1, 1]) {
    const lobe = new THREE.Mesh(new THREE.SphereGeometry(1, 28, 20),
      new THREE.MeshStandardMaterial({ color: COLORS.self, transparent: true, opacity: 0.08, roughness: 0.9, depthWrite: false }));
    lobe.scale.set(P.lobeRadii[0] * 1.04, P.lobeRadii[1] * 1.04, P.lobeRadii[2] * 1.04);
    lobe.position.x = side * P.lobeOffset;
    brain.add(lobe);
  }

  // ---------------------------------------------------------------- futures, World, tubes
  const sphereGeom = new THREE.SphereGeometry(1, 32, 24);
  const futureMat = new THREE.MeshStandardMaterial({ color: COLORS.self, emissive: COLORS.selfDeep, emissiveIntensity: 0.35, roughness: 0.4, metalness: 0.05 });
  const ghostMat = new THREE.MeshBasicMaterial({ color: COLORS.ghost, wireframe: true, transparent: true, opacity: 0.38 });
  const placeholderMat = new THREE.MeshBasicMaterial({ color: COLORS.self, wireframe: true, transparent: true, opacity: 0.28 });
  const f1 = new THREE.Mesh(sphereGeom, futureMat);
  const f0 = new THREE.Mesh(sphereGeom, futureMat);
  const g1 = new THREE.Mesh(sphereGeom, ghostMat);
  const g0 = new THREE.Mesh(sphereGeom, ghostMat);
  f1.position.set(...P.f1); g1.position.set(...P.f1);
  f0.position.set(...P.f0); g0.position.set(...P.f0);
  scene.add(f1, f0, g1, g0);
  const world = new THREE.Mesh(sphereGeom, new THREE.MeshStandardMaterial({ color: COLORS.world, emissive: COLORS.worldDeep, emissiveIntensity: 0.4, roughness: 0.45 }));
  world.position.set(...P.world);
  world.scale.setScalar(P.worldR);
  scene.add(world);

  const v = (a) => new THREE.Vector3(a[0], a[1], a[2]);
  const bx = P.brain[0] + P.lobeOffset + P.lobeRadii[0] * 0.75;   // right edge of the brain
  const curves = {
    b1: new THREE.CatmullRomCurve3([v([bx - 0.25, P.brain[1] + 0.3, 0.05]), v([0.75, 0.95, 0.1]), v(P.f1)]),
    b0: new THREE.CatmullRomCurve3([v([bx - 0.25, P.brain[1] - 0.15, 0.05]), v([0.75, -0.85, 0.1]), v(P.f0)]),
    bridge: new THREE.CatmullRomCurve3([v([P.brain[0], P.brain[1] - 0.55, 0]), v([P.brain[0] - 0.1, -1.25, -0.15]), v(P.world)]),
  };
  const tubeMat = new THREE.MeshStandardMaterial({ color: COLORS.self, emissive: COLORS.selfDeep, emissiveIntensity: 0.4, roughness: 0.5, transparent: true, opacity: 0.92 });
  const ghostTubeMat = new THREE.MeshBasicMaterial({ color: COLORS.ghost, transparent: true, opacity: 0.22, depthWrite: false });
  const bridgeMat = new THREE.MeshStandardMaterial({ color: COLORS.worldLight, emissive: COLORS.worldDeep, emissiveIntensity: 0.5, roughness: 0.5, transparent: true, opacity: 0.5, depthWrite: false });
  const tubes = {
    b1: new THREE.Mesh(new THREE.BufferGeometry(), tubeMat),
    b0: new THREE.Mesh(new THREE.BufferGeometry(), tubeMat),
    gb1: new THREE.Mesh(new THREE.BufferGeometry(), ghostTubeMat),
    gb0: new THREE.Mesh(new THREE.BufferGeometry(), ghostTubeMat),
    bridge: new THREE.Mesh(new THREE.BufferGeometry(), bridgeMat),
  };
  for (const t of Object.values(tubes)) scene.add(t);

  // ---------------------------------------------------------------- particles
  const rand = mulberry32(o.seed + 1);
  const samples = { b1: curves.b1.getSpacedPoints(64), b0: curves.b0.getSpacedPoints(64) };
  const part = { phase: new Float32Array(N_PARTICLES), speed: new Float32Array(N_PARTICLES),
    jitter: new Float32Array(N_PARTICLES * 3), branch: new Uint8Array(N_PARTICLES) };
  for (let i = 0; i < N_PARTICLES; i++) {
    part.phase[i] = rand();
    part.speed[i] = 0.06 + 0.1 * rand();
    const u = rand() * 2 - 1, th = rand() * 2 * Math.PI, s = Math.sqrt(1 - u * u);
    const mag = 1.6 + 1.4 * rand();
    part.jitter[i * 3] = s * Math.cos(th) * mag;
    part.jitter[i * 3 + 1] = s * Math.sin(th) * mag;
    part.jitter[i * 3 + 2] = u * mag;
  }
  const partPos = new Float32Array(N_PARTICLES * 3);
  const partGeom = new THREE.BufferGeometry();
  partGeom.setAttribute("position", new THREE.BufferAttribute(partPos, 3));
  const particles = new THREE.Points(partGeom, new THREE.PointsMaterial({ color: COLORS.selfLight, size: 0.055, transparent: true, opacity: 0.85, depthWrite: false, sizeAttenuation: true }));
  scene.add(particles);

  // ---------------------------------------------------------------- labels (overlay)
  const labels = {};
  for (const name of ["self", "f1", "f0", "world", "g1", "g0"]) {
    labels[name] = h("span", { class: "fwo-scene-label fwo-scene-label--" + name });
    labelLayer.appendChild(labels[name]);
  }
  labels.self.textContent = "Self (fictional, decorative graph)";
  labels.world.textContent = "World";

  // ---------------------------------------------------------------- state
  const state = { p1: 0.5, I: 0, placeholder: true };
  let ghost = null;                   // {p1, I} of the previous completed run
  let ghostText = ["", ""];
  let liveText = { f1: "Future 1: no run yet", f0: "Future 0: no run yet" };
  let anim = null;                    // {from, to, t0}
  let motion = !o.reducedMotion;
  let reduced = !!o.reducedMotion;
  let width = 0, height = 0, unitsPerPx = 0.01;
  let lastFrame = 0;
  let running = false;

  function pxToRadius(px) {
    return Math.max(0.004, 0.5 * px * unitsPerPx);
  }

  // Rebuilt only when the pixel width or the scale changed (the old buffers are
  // released), so an idle frame allocates nothing.
  function setTube(mesh, curve, px) {
    const key = px.toFixed(3) + "@" + unitsPerPx.toExponential(5);
    if (mesh.userData.tubeKey === key) return;
    mesh.userData.tubeKey = key;
    const old = mesh.geometry;
    mesh.geometry = new THREE.TubeGeometry(curve, 36, pxToRadius(px), 10, false);
    if (old && old.dispose) old.dispose();
  }

  function applyLive(p1, I, placeholder) {
    const p0 = 1 - p1;
    f1.visible = !placeholder; f0.visible = !placeholder;
    f1.scale.setScalar(Math.max(0.001, RMAX * Math.cbrt(p1)));
    f0.scale.setScalar(Math.max(0.001, RMAX * Math.cbrt(p0)));
    setTube(tubes.b1, curves.b1, placeholder ? 2 : 2 + 10 * p1);
    setTube(tubes.b0, curves.b0, placeholder ? 2 : 2 + 10 * p0);
    tubeMat.opacity = placeholder ? 0.35 : 0.92;
    setTube(tubes.bridge, curves.bridge, placeholder ? 2 : 2 + 10 * I);
    bridgeMat.opacity = placeholder ? 0.15 : 0.15 + 0.85 * I;
  }

  function applyGhost() {
    const show = ghost !== null;
    g1.visible = show || state.placeholder;
    g0.visible = show || state.placeholder;
    tubes.gb1.visible = show; tubes.gb0.visible = show;
    if (state.placeholder && !show) {
      g1.material = placeholderMat; g0.material = placeholderMat;
      g1.scale.setScalar(RMAX * Math.cbrt(0.5)); g0.scale.setScalar(RMAX * Math.cbrt(0.5));
      return;
    }
    g1.material = ghostMat; g0.material = ghostMat;
    if (show) {
      g1.scale.setScalar(Math.max(0.001, RMAX * Math.cbrt(ghost.p1)));
      g0.scale.setScalar(Math.max(0.001, RMAX * Math.cbrt(1 - ghost.p1)));
      setTube(tubes.gb1, curves.b1, 2 + 10 * ghost.p1);
      setTube(tubes.gb0, curves.b0, 2 + 10 * (1 - ghost.p1));
    }
  }

  function routeParticles(p1) {
    const n1 = Math.round(clamp01(p1) * N_PARTICLES);
    for (let i = 0; i < N_PARTICLES; i++) part.branch[i] = i < n1 ? 1 : 0;
    placeParticles();
  }

  function placeParticles() {
    const r1 = pxToRadius(2 + 10 * state.p1), r0 = pxToRadius(2 + 10 * (1 - state.p1));
    for (let i = 0; i < N_PARTICLES; i++) {
      const pts = part.branch[i] ? samples.b1 : samples.b0;
      const r = part.branch[i] ? r1 : r0;
      const t = part.phase[i] * (pts.length - 1);
      const k = Math.min(pts.length - 2, Math.floor(t));
      const f = t - k;
      const a = pts[k], b = pts[k + 1];
      partPos[i * 3] = a.x + (b.x - a.x) * f + part.jitter[i * 3] * r;
      partPos[i * 3 + 1] = a.y + (b.y - a.y) * f + part.jitter[i * 3 + 1] * r;
      partPos[i * 3 + 2] = a.z + (b.z - a.z) * f + part.jitter[i * 3 + 2] * r;
    }
    partGeom.attributes.position.needsUpdate = true;
  }

  function project(a) {
    const p = v(a).project(camera);
    return [(p.x + 1) / 2 * width, (1 - p.y) / 2 * height];
  }

  // Labels are centred on their anchor (the World label ends at it) and kept inside
  // the canvas, so nothing is clipped at 360 px.
  function place(label, a, dx, dy, anchorEnd) {
    const [x, y] = project(a);
    const lw = label.offsetWidth || 0;
    let left = x + dx;
    if (anchorEnd) left = Math.min(width - 4, Math.max(lw + 4, left));
    else left = Math.min(width - lw / 2 - 4, Math.max(lw / 2 + 4, left));
    label.style.left = left.toFixed(0) + "px";
    label.style.top = Math.min(height - 12, Math.max(12, y + dy)).toFixed(0) + "px";
  }

  function layoutLabels() {
    labels.self.textContent = width < 480 ? "Self (decorative graph)" : "Self (fictional, decorative graph)";
    labels.f1.textContent = liveText.f1;
    labels.f0.textContent = liveText.f0;
    labels.g1.textContent = ghostText[1];
    labels.g0.textContent = ghostText[0];
    labels.g1.hidden = !ghostText[1];
    labels.g0.hidden = !ghostText[0];
    place(labels.self, [P.brain[0], P.brain[1] + P.lobeRadii[1] + 0.25, 0], 0, 0);
    place(labels.f1, [P.f1[0], P.f1[1] + RMAX + 0.12, 0], 0, -6);
    place(labels.g1, [P.f1[0], P.f1[1] - RMAX - 0.1, 0], 0, 6);
    place(labels.f0, [P.f0[0], P.f0[1] - RMAX - 0.1, 0], 0, 6);
    place(labels.g0, [P.f0[0], P.f0[1] + RMAX + 0.12, 0], 0, -6);
    place(labels.world, [P.world[0] - P.worldR - 0.15, P.world[1], P.world[2]], 0, 0, true);
  }

  function resize() {
    const w = Math.max(200, Math.round(host.clientWidth || 600));
    const hh = Math.max(240, Math.round(host.clientHeight || 360));
    if (w === width && hh === height) return false;
    width = w; height = hh;
    const aspect = w / hh;
    camera.aspect = aspect;
    const camZ = Math.max(7.6, 9.9 / aspect);
    camera.position.set(P.center[0], P.center[1] + 0.25, camZ);
    camera.lookAt(P.center[0], P.center[1], 0);
    camera.updateProjectionMatrix();
    unitsPerPx = (2 * camZ * Math.tan((FOV / 2) * Math.PI / 180)) / hh;
    renderer.setSize(w, hh, false);
    applyLive(state.p1, state.I, state.placeholder);
    applyGhost();
    placeParticles();
    layoutLabels();
    return true;
  }

  function render() {
    renderer.render(scene, camera);
  }

  function step(now) {
    const dt = lastFrame ? Math.min(0.1, (now - lastFrame) / 1000) : 0;
    lastFrame = now;
    let busy = false;
    if (anim) {
      const s = Math.min(1, (now - anim.t0) / 1000);
      const e = ease(s);
      state.p1 = anim.from.p1 + (anim.to.p1 - anim.from.p1) * e;
      state.I = anim.from.I + (anim.to.I - anim.from.I) * e;
      applyLive(state.p1, state.I, false);
      if (s >= 1) anim = null; else busy = true;
    }
    if (motion) {
      for (let i = 0; i < N_PARTICLES; i++) part.phase[i] = (part.phase[i] + part.speed[i] * dt) % 1;
      brain.rotation.y = baseRotY + 0.07 * Math.sin(now / 2600);
      busy = true;
    }
    placeParticles();
    render();
    return busy;
  }

  function raf(fn) {
    if (typeof requestAnimationFrame === "function") requestAnimationFrame(fn);
    else o.setTimeoutFn(() => fn(Date.now()), 16);
  }

  // Release every GPU buffer and the context: used when the canvas leaves the
  // document (the host page replaced the fragment) or on an explicit dispose().
  function dispose() {
    running = false;
    api.available = false;
    try {
      scene.traverse((obj) => {
        if (obj.geometry && obj.geometry.dispose) obj.geometry.dispose();
        if (obj.material && obj.material.dispose) obj.material.dispose();
      });
      renderer.dispose();
      renderer.forceContextLoss();
    } catch (err) { /* the context is already gone */ }
  }

  function showLost() {
    running = false;
    api.available = false;
    replace(host, h("p", { class: "fwo-scene-fallback" },
      "The 3D view stopped because the browser lost its WebGL context. Every number it showed is in the futures, readings and tables below."));
  }

  function loop(now) {
    if (!running) return;
    if (!canvas.isConnected) { dispose(); return; }
    const busy = step(typeof now === "number" ? now : Date.now());
    if (busy) raf(loop); else { running = false; lastFrame = 0; }
  }

  function kick() {
    if (running) return;
    running = true;
    lastFrame = 0;
    raf(loop);
  }

  canvas.addEventListener("webglcontextlost", (ev) => {
    ev.preventDefault();
    showLost();
  });

  // ---------------------------------------------------------------- public API
  // Show a completed run. `prev` (the previous completed run) becomes the ghost.
  api.setResult = (run, prev, text) => {
    const m = run && run.metrics ? run.metrics : {};
    const to = { p1: clamp01(m.p_self_1), I: clamp01(m.connection_bits) };
    if (prev && prev.metrics) {
      ghost = { p1: clamp01(prev.metrics.p_self_1), I: clamp01(prev.metrics.connection_bits) };
      ghostText = [text.prev0, text.prev1];
    } else {
      ghost = null;
      ghostText = ["", ""];
    }
    liveText = { f1: text.f1, f0: text.f0 };
    const from = state.placeholder ? { p1: 0.5, I: 0 } : { p1: state.p1, I: state.I };
    state.placeholder = false;
    applyGhost();
    routeParticles(to.p1);
    if (reduced) {
      anim = null;
      state.p1 = to.p1; state.I = to.I;
      applyLive(to.p1, to.I, false);
    } else {
      anim = { from, to, t0: (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now() };
    }
    layoutLabels();
    kick();
  };

  api.setLabel = (text) => { canvas.setAttribute("aria-label", text); };
  api.setMotion = (on) => { motion = !!on; brain.rotation.y = baseRotY; kick(); };
  api.setReducedMotion = (flag) => { reduced = !!flag; if (reduced) { motion = false; anim = null; } kick(); };
  api.motion = () => motion;
  api.resize = () => { if (resize()) kick(); };
  api.dispose = dispose;
  api.canvas = canvas;

  resize();
  applyLive(0.5, 0, true);
  applyGhost();
  routeParticles(0.5);
  layoutLabels();
  kick();
  return api;
}
