// The Observatory scene drawn flat, as an SVG plate, in the styles of the four design
// directions: "a" night observatory (gold orbs under a starfield, a ringed World), "b"
// instrument console (wireframe reticles on an engineering grid), "c" luminous anatomy (a
// glowing violet organism) and "d" blueprint (ink on graph paper, hatching, dimension lines).
// A theme asks for one with the CSS variable --fwo-scene-plate (read by main.js); without it
// the 3D view in ui/scene.js runs. The plate needs no WebGL.
//
// The same visual mappings as the 3D view (build guide p.10), from the completed display run:
//   future radius        = 52 * cbrt(p) scene units            (volume follows probability)
//   branch thickness     = 2 + 10 p screen pixels              (non-scaling strokes)
//   World bridge         = 4 + 6 I px (at most 10), opacity 0.15 + 0.85 I   (I in bits,
//                          connection probe); it rises from the World into the Self, under
//                          the Self's body, as if entering the mind
//   shimmer              = 1 to 4 pulses climbing the bridge from the World into the Self,
//                          more and brighter with more connection; none at zero, none when still
//   previous run         = dashed outlines labelled "previous" until the next result
//   particles            = a FIXED 40 dots routed to the two branches in proportions p1 / p0;
//                          decoration, never shot chronology
// The brain (the 3D view's two-lobe graph, projected) and the stars are fixed constants, so a change in the picture always means a change in the numbers.
// Annotated values (t = ... px, I = ... bits) always show the run's own numbers, never the
// in-between frames of the one-second transition. No imports: main.js passes in the dom
// helpers (lib).

const W = 660;
const H = 420;
const RMAX = 52;                                   // future radius at p = 1 (scene units)
const FC = [[512, 300], [512, 112]];               // Future 0 lower right, Future 1 upper right
const GHOST_OFF = [10, -12];
const WORLD = [150, 322];
const WORLD_R = 22;
// Branch curves (cubic): the last point is the sphere's left edge, so it follows the radius.
const BRANCH = [[[271, 212], [384, 216], [430, 300]], [[275, 152], [384, 150], [430, 112]]];
// The World bridge, drawn from the top of the World up into the Self's lower middle (through
// the fissure, clear of nodes and links), where the Self's body is layered over it: it enters
// the mind. The shimmer climbs it from the World into the Self.
const BRIDGE = "M 156,300 C 172,272 185,250 185,226 L 185,206";
const SHIMMER_S = 2.2;                             // seconds for one pulse to climb the bridge
const SELF_X = 184;                                // centre of the Self (label, glow)
const N_PART = 40;
const FLOW = 0.05;                                 // particle speed: branch lengths per second
const NARROW = 480;                                // px: shorter labels below this width
const BG = { x: -330, y: -210, width: 1320, height: 840 };   // covers any letterbox margin

// The Self: the 3D view's own brain (ui/scene.js brainGraph, seed 20261010: two ellipsoid lobes
// with a fissure, 100 nodes, three nearest-neighbour links each), turned by the 3D view's tilt
// (0.12, -0.42, 0.04 rad) and projected flat. NODES holds x, y and a ball radius per node,
// far to near (nearer nodes are larger and drawn on top); LOBES holds each lobe shell's
// projected ellipse (cx, cy, rx, ry, rotation in degrees). Then 110 stars (x, y, r, opacity).
const NODES = [
  137.6, 161.7, 3.4, 154.1, 198.5, 3.44, 171.1, 175.5, 3.45, 157.7, 169.2, 3.48, 154.5, 171.5, 3.48, 156.6, 170.9, 3.51,
  155.4, 169.2, 3.51, 149, 218.7, 3.53, 114.7, 193.8, 3.54, 151.7, 132.5, 3.54, 163, 176.7, 3.55, 167.4, 156.1, 3.55,
  133.4, 194.9, 3.55, 120, 140.5, 3.57, 127.8, 202.9, 3.57, 118.4, 201.8, 3.58, 152.3, 225.4, 3.65, 120.2, 189.8, 3.67,
  139.1, 143.6, 3.67, 125.3, 158.4, 3.67, 128.2, 193.4, 3.68, 125.6, 135.4, 3.73, 126.2, 219.5, 3.75, 140.5, 228.8, 3.8,
  123.7, 238.9, 3.81, 101.7, 217.5, 3.83, 153.4, 240.4, 3.85, 96.8, 207.8, 3.88, 152.1, 119.7, 3.88, 112.2, 158.6, 3.89,
  120.7, 228.3, 3.9, 246.7, 169, 3.93, 86.8, 186, 3.95, 109.3, 180.2, 3.97, 140, 118.3, 3.98, 253.2, 181.7, 3.99,
  91.3, 181.3, 4.03, 104.1, 184.8, 4.04, 254.8, 178.4, 4.07, 258.8, 198.5, 4.07, 245.5, 207.4, 4.08, 93.2, 145.9, 4.08,
  249.9, 196.1, 4.09, 245.4, 131, 4.09, 110.5, 138.6, 4.1, 108.8, 142, 4.1, 123.9, 125.1, 4.16, 105.6, 178, 4.2,
  272, 152, 4.24, 241.2, 234.4, 4.24, 133.7, 115.8, 4.25, 118.1, 198.7, 4.27, 115.2, 132.2, 4.3, 260.5, 209.8, 4.32,
  100.2, 180.1, 4.32, 232.5, 235.2, 4.33, 118.6, 132.4, 4.34, 111, 163.6, 4.36, 229.8, 231.4, 4.37, 123.3, 208.2, 4.39,
  128.2, 172.2, 4.4, 130.7, 189.5, 4.41, 250.1, 227.5, 4.42, 236.5, 113.5, 4.44, 251.1, 232, 4.45, 277.8, 166.3, 4.46,
  275.2, 169.5, 4.5, 231.4, 118.2, 4.51, 221.3, 111.7, 4.53, 254.9, 176.7, 4.54, 253.6, 224.4, 4.55, 271.9, 211.7, 4.57,
  253.8, 162, 4.57, 260.1, 125.6, 4.58, 253.9, 155.6, 4.59, 267.3, 201.2, 4.6, 207.6, 222.8, 4.68, 239.5, 234.7, 4.69,
  235, 122, 4.69, 253.5, 147.2, 4.69, 244.2, 197.4, 4.74, 235, 124.2, 4.79, 224.3, 231.2, 4.8, 236.2, 221.8, 4.8,
  205.4, 126.8, 4.83, 251.9, 151.2, 4.83, 220.4, 225.8, 4.84, 264.3, 205, 4.84, 215.8, 143.9, 4.85, 216, 199.7, 4.85,
  277.3, 156.3, 4.86, 198.8, 202.3, 4.87, 203.9, 171.6, 4.91, 211, 131.4, 4.92, 243.3, 148.6, 4.96, 229.8, 177.2, 4.97,
  224.4, 177.5, 4.97, 251.3, 169.7, 4.99, 267.4, 164.5, 4.99, 244.4, 143.2, 5,
];
const LINKS = [
  30, 24, 30, 22, 30, 23, 1, 7, 1, 12, 1, 10, 8, 15, 8, 17, 8, 14, 10, 5, 10, 6, 10, 3,
  45, 44, 45, 41, 45, 52, 29, 33, 29, 19, 29, 45, 13, 21, 13, 19, 13, 18, 50, 46, 50, 56, 50, 52,
  33, 37, 33, 36, 33, 32, 24, 23, 24, 22, 51, 59, 51, 61, 51, 47, 25, 27, 25, 30, 25, 22, 17, 20,
  17, 15, 15, 14, 57, 60, 57, 54, 57, 47, 32, 36, 32, 37, 14, 12, 14, 20, 2, 10, 2, 3, 2, 5,
  52, 56, 52, 46, 52, 44, 11, 3, 11, 6, 11, 5, 28, 34, 28, 21, 28, 18, 26, 23, 26, 16, 26, 24,
  37, 36, 37, 47, 34, 46, 34, 50, 27, 32, 27, 37, 3, 5, 3, 4, 3, 6, 21, 18, 21, 19, 20, 12,
  54, 47, 54, 51, 19, 18, 22, 23, 18, 9, 7, 16, 7, 14, 46, 44, 4, 5, 4, 6, 61, 60, 61, 59,
  16, 23, 5, 6, 41, 44, 41, 29, 12, 15, 59, 60, 9, 11, 9, 21, 56, 46, 0, 4, 0, 6, 0, 3,
  60, 54, 75, 71, 75, 87, 75, 80, 92, 96, 92, 95, 92, 88, 97, 98, 97, 94, 97, 95, 91, 89, 91, 76,
  91, 92, 64, 62, 64, 70, 64, 55, 74, 72, 74, 79, 74, 69, 99, 94, 99, 85, 99, 97, 82, 86, 82, 83,
  82, 77, 76, 86, 76, 82, 66, 65, 66, 69, 66, 72, 69, 72, 42, 39, 42, 40, 42, 35, 87, 80, 87, 71,
  49, 55, 49, 58, 49, 62, 79, 85, 79, 72, 65, 69, 65, 48, 35, 38, 35, 31, 90, 98, 90, 85, 90, 79,
  58, 55, 58, 62, 94, 85, 31, 38, 31, 42, 84, 93, 84, 88, 84, 81, 39, 40, 39, 35, 89, 86, 89, 96,
  88, 93, 88, 81, 38, 42, 43, 48, 43, 63, 43, 31, 96, 95, 78, 81, 78, 67, 78, 68, 68, 67, 68, 63,
  40, 35, 73, 79, 73, 78, 73, 63, 83, 86, 83, 77, 70, 62, 70, 77, 98, 85, 63, 67, 63, 78, 80, 83,
  55, 62, 53, 62, 53, 39, 53, 71, 81, 93, 71, 70, 48, 66, 48, 38,
];
const LOBES = [[157.4, 175.6, 89.4, 74.5, -177.7], [210.6, 176.4, 89.4, 74.5, -177.7]];
const STARS = [
  173.6, 274.3, 0.86, 0.64, 261.1, 72.9, 0.69, 0.4, 594.7, 208.8, 0.76, 0.88, 653.7, 189.4, 0.67, 0.38,
  63.1, 144.9, 0.61, 0.42, 172.4, 238.7, 1.56, 0.77, 273.1, 174.5, 1.13, 0.51, 224.5, 29.6, 0.83, 0.93,
  86.1, 211.4, 1.26, 0.85, 144.8, 115.7, 0.8, 0.53, 294.7, 397, 1.52, 0.86, 18.2, 17.3, 1.35, 0.88,
  312.6, 245.9, 0.5, 0.52, 608.3, 344.1, 1.53, 0.93, 166, 48.9, 0.69, 0.62, 448.7, 391.9, 1.37, 0.7,
  502.6, 192.4, 1.16, 0.28, 514.1, 99.8, 1.6, 0.7, 202.1, 56.7, 0.8, 0.7, 459.5, 50.2, 0.58, 0.62,
  384, 163.9, 0.77, 0.67, 10.8, 128.2, 1.05, 0.92, 424.3, 368.1, 1.07, 0.41, 165.1, 399.8, 1.35, 0.47,
  18.2, 209.3, 1.31, 0.54, 171.7, 279, 1.61, 0.41, 26.2, 143.3, 1, 0.73, 133.1, 332.4, 1.39, 0.6,
  137.8, 403.6, 0.87, 0.82, 154.5, 95.2, 1.41, 0.46, 624.7, 208.3, 0.72, 0.41, 275.9, 278.1, 1.64, 0.35,
  260.5, 91.7, 1.67, 0.35, 37.8, 28.8, 0.97, 0.88, 580.1, 305.9, 1.7, 0.9, 218.7, 80.4, 1.62, 0.77,
  24.8, 277.7, 0.95, 0.51, 220.3, 73.7, 0.5, 0.45, 233.2, 397.7, 0.65, 0.92, 139.2, 150.9, 1.49, 0.83,
  286, 24.3, 1.07, 0.51, 603.5, 83.5, 0.94, 0.88, 23.7, 173.3, 1.47, 0.79, 30.5, 18.4, 0.58, 0.89,
  171.6, 311.9, 1.58, 0.49, 181.5, 398.6, 1.24, 0.43, 471.2, 134.4, 0.83, 0.25, 496.7, 381.6, 1.26, 0.91,
  19.8, 100.4, 1.07, 0.92, 625.9, 163.2, 0.8, 0.55, 325.7, 386.4, 0.72, 0.81, 485.5, 343, 1.43, 0.68,
  217.7, 135.7, 0.93, 0.8, 55.5, 85.3, 1.4, 0.42, 46.2, 18, 1.16, 0.48, 643.1, 368, 1.69, 0.44,
  58.8, 43.7, 1.1, 0.75, 295.4, 100.5, 1, 0.68, 443.5, 312.2, 1.52, 0.72, 83, 350.4, 0.85, 0.65,
  247.2, 308.1, 0.74, 0.42, 164, 67.2, 1.56, 0.65, 216.8, 167.2, 1.69, 0.61, 154.9, 337.1, 1.28, 0.94,
  70.7, 199.6, 1.48, 0.84, 600.2, 20.6, 0.85, 0.33, 127.6, 404.9, 1.2, 0.9, 246.7, 360.8, 1.04, 0.43,
  511.1, 393.6, 0.63, 0.67, 408.2, 93.7, 0.94, 0.35, 137, 109, 1.22, 0.71, 136.6, 8.7, 0.89, 0.72,
  124.7, 132.6, 0.74, 0.81, 361.3, 30.1, 0.62, 0.53, 362.7, 267.3, 0.61, 0.36, 457.4, 172.8, 0.84, 0.47,
  625.5, 132.7, 1.18, 0.5, 275.5, 360.1, 1.7, 0.5, 132.6, 303.9, 0.74, 0.25, 591.9, 178.6, 1.48, 0.53,
  579.6, 193.9, 0.7, 0.26, 363.6, 268, 1.59, 0.31, 409.7, 156.8, 1.11, 0.35, 188.7, 218.7, 1.61, 0.33,
  323.8, 335.6, 1.66, 0.39, 86.6, 392.5, 1.67, 0.59, 38.8, 385.6, 0.97, 0.88, 408.5, 343.7, 0.69, 0.8,
  148.8, 170.6, 1.52, 0.83, 123.3, 93.9, 0.98, 0.61, 254.1, 54.7, 0.8, 0.76, 589, 20.9, 1.17, 0.78,
  28.9, 349.3, 0.64, 0.67, 362.6, 262.3, 0.87, 0.54, 383.9, 179.4, 1.29, 0.56, 289.8, 13.6, 1.24, 0.59,
  157.4, 318.6, 1.44, 0.57, 121.1, 199, 0.63, 0.34, 284.8, 41.8, 1.03, 0.61, 30.6, 266.2, 0.6, 0.76,
  511, 214.7, 0.57, 0.6, 250.4, 395.8, 0.66, 0.85, 653.5, 305.6, 1.48, 0.39, 644.1, 206.7, 1.65, 0.89,
  111.7, 328.8, 1.62, 0.3, 232.8, 315.5, 0.69, 0.88, 183.3, 340, 0.67, 0.6, 603.8, 89.8, 0.82, 0.6,
  212, 19.2, 0.72, 0.36, 614.5, 284, 1.57, 0.37,
];

function clamp01(x) {
  return Math.max(0, Math.min(1, Number.isFinite(x) ? x : 0));
}

function ease(s) {
  return s < 0.5 ? 2 * s * s : 1 - Math.pow(-2 * s + 2, 2) / 2;
}

function frac(x) {
  return x - Math.floor(x);
}

function n1(x) {
  return String(Math.round(x * 10) / 10);
}

function radius(p) {
  return Math.max(0.5, RMAX * Math.cbrt(clamp01(p)));
}

function bezier(c, t) {
  const m = 1 - t;
  const a = m * m * m, b = 3 * m * m * t, d = 3 * m * t * t, e = t * t * t;
  return [a * c[0][0] + b * c[1][0] + d * c[2][0] + e * c[3][0], a * c[0][1] + b * c[1][1] + d * c[2][1] + e * c[3][1]];
}

function branchCurve(i, r) {
  return BRANCH[i].concat([[FC[i][0] - r, FC[i][1]]]);
}

function curvePath(c) {
  return "M " + c[0].join(",") + " C " + c.slice(1).map((p) => n1(p[0]) + "," + n1(p[1])).join(" ");
}

// A dimension line with an arrowhead at each end, pointing outward along the line.
function dimension(x1, y1, x2, y2) {
  const len = Math.hypot(x2 - x1, y2 - y1) || 1;
  const ux = (x2 - x1) / len, uy = (y2 - y1) / len;
  const head = (x, y, sx, sy) => "M " + n1(x) + "," + n1(y) + " L " + n1(x + 7 * sx - 2.6 * sy) + "," +
    n1(y + 7 * sy + 2.6 * sx) + " L " + n1(x + 7 * sx + 2.6 * sy) + "," + n1(y + 7 * sy - 2.6 * sx) + " Z";
  return { line: "M " + n1(x1) + "," + n1(y1) + " L " + n1(x2) + "," + n1(y2), heads: head(x1, y1, ux, uy) + " " + head(x2, y2, -ux, -uy) };
}

function set(node, attrs) {
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, typeof v === "number" ? n1(v) : String(v));
}

const TEXT = {
  self: "Self (fictional, decorative graph)",
  selfNarrow: "Self (decorative graph)",
  world: "World",
  previous: "previous",
};

function tTag(p, long) {
  return "t = " + (long ? "2 + 10 p = " : "") + (2 + 10 * p).toFixed(2) + " px";
}

// ------------------------------------------------------------------ the four drawn styles
// Each builder draws its layers in order and registers the parts that follow the data
// through the context (c): branches, particles, ghosts, futures, labels and annotations.

const STYLES = {
  a(c) {
    c.gradient("sky", [[0, "#101d44"], [0.55, "#0a1330"], [1, "#070d1f"]],
      { gradientUnits: "userSpaceOnUse", cx: 0, cy: 0, r: 1, gradientTransform: "translate(330 117.6) scale(528 336)" });
    c.gradient("orb", [[0, "#f9e2ae"], [0.45, "#e5b45a"], [1, "#7a5a20"]], { cx: "38%", cy: "34%", r: "75%" });
    c.gradient("halo", [[0, "#e5b45a", 0.34], [0.6, "#e5b45a", 0.1], [1, "#e5b45a", 0]], {});
    c.gradient("world", [[0, "#d9fbf3"], [0.45, "#8fd8cb"], [1, "#1f5a50"]], { cx: "38%", cy: "34%", r: "75%" });
    c.gradient("brainhalo", [[0, "#3d5aa8", 0.5], [1, "#3d5aa8", 0]], {});
    c.add("rect", Object.assign({ fill: c.ref("sky") }, BG));
    const stars = c.add("g", { fill: "#dce6ff" });
    const twinkle = c.add("g", { fill: "#dce6ff", class: "fwo-plate-twinkle" });
    for (let i = 0; i < STARS.length; i += 4) {
      c.add("circle", { cx: STARS[i], cy: STARS[i + 1], r: STARS[i + 2], opacity: STARS[i + 3] }, i % 12 === 0 ? twinkle : stars);
    }
    c.bridge({ stroke: "#8fd8cb" }, "#f0fffb");
    c.brain({ body: ["#0c1636", 0.4], glow: { cx: SELF_X, cy: 176, rx: 150, ry: 112, fill: c.ref("brainhalo") },
      shell: { fill: "#e5b45a", "fill-opacity": 0.07 }, link: { stroke: "#e5b45a", "stroke-opacity": 0.5, "stroke-width": 0.9 },
      ball: [[0, "#fdf0cc"], [0.5, "#e8bd6a"], [1, "#8a6424"]] });
    c.selfLabel(72, 12.5, { fill: "#c8d2ec", "font-weight": 500 });
    c.add("circle", { cx: WORLD[0], cy: WORLD[1], r: WORLD_R + 10, fill: c.ref("halo"), opacity: 0.35 });
    c.add("circle", { cx: WORLD[0], cy: WORLD[1], r: WORLD_R, fill: c.ref("world") });
    c.add("ellipse", { cx: WORLD[0], cy: WORLD[1], rx: 36, ry: 9, fill: "none", stroke: "#8fd8cb", "stroke-width": 1.6,
      opacity: 0.8, transform: "rotate(-16 150 322)" });
    c.worldLabel(34, 12.5, { fill: "#8fd8cb", "font-weight": 500 });
    c.branches({ stroke: "#e5b45a", opacity: 0.14 }, (t) => 2 * t, { stroke: "#efc87e", opacity: 0.92 });
    c.particles("circle", { fill: "#f9e2ae", opacity: 0.9 }, 1.7);
    c.ghosts({ stroke: "#8090b8", "stroke-width": 1.4, "stroke-dasharray": "4 4", opacity: 0.38 }, 11.5,
      { fill: "#93a3cc", "font-weight": 500 });
    for (const i of [1, 0]) {
      const g = c.futureGroup(i);
      const halo = c.add("circle", { fill: c.ref("halo") }, g);
      const orb = c.add("circle", { fill: c.ref("orb") }, g);
      c.future(i, (cx, cy, r) => { set(halo, { cx, cy, r: r + 14 }); set(orb, { cx, cy, r }); });
    }
    c.futureLabels(12.5, { fill: "#c8d2ec", "font-weight": 500 }, 12, (fs) => 10 + 0.95 * fs);
  },

  b(c) {
    c.pattern("grid", 20, "M 20,0 L 0,0 0,20", "#22272d");
    c.pattern("major", 100, "M 100,0 L 0,0 0,100", "#2b3138");
    c.add("rect", Object.assign({ fill: "#16191e" }, BG));
    c.add("rect", Object.assign({ fill: c.ref("grid") }, BG));
    c.add("rect", Object.assign({ fill: c.ref("major") }, BG));
    c.bridge({ stroke: "#f0a44a", "stroke-dasharray": "3 4" }, "#ffe6c2");
    c.brain({ body: ["#16191e", 0.41], shell: { fill: "#45c8e0", "fill-opacity": 0.06 }, link: { stroke: "#45c8e0", "stroke-opacity": 0.5, "stroke-width": 0.9 },
      ball: [[0, "#d2f6fc"], [0.5, "#5fd0e6"], [1, "#17606e"]] });
    c.selfLabel(72, 11, { fill: "#b9c0c7", "font-weight": 500 });
    const bridgeTag = c.text("fwo-s-tag", 204, 314, 10, 9, { fill: "#8b96a1" });
    c.tag((v, narrow) => {
      bridgeTag.textContent = "I = " + v.I.toFixed(3) + " bits" + (narrow ? "" : " \u2192 " +
        (v.I < 0.0005 ? "bridge at floor" : "bridge " + (4 + 6 * v.I).toFixed(1) + " px"));
    }, [bridgeTag]);
    const wg = c.add("g", { stroke: "#f0a44a", fill: "none" });
    c.add("circle", { cx: WORLD[0], cy: WORLD[1], r: WORLD_R, "stroke-width": 1.6 }, wg);
    c.add("circle", { cx: WORLD[0], cy: WORLD[1], r: WORLD_R - 6, "stroke-width": 0.8, "stroke-dasharray": "2 3" }, wg);
    c.add("path", { d: "M 116,322 H 184 M 150,288 V 356", "stroke-width": 0.8 }, wg);
    c.worldLabel(39, 11, { fill: "#f0a44a", "font-weight": 500 });
    c.branches({ stroke: "#0e3a44", opacity: 1 }, (t) => t + 3, { stroke: "#45c8e0", opacity: 1 });
    c.particles("rect", { fill: "#45c8e0", opacity: 0.75 }, 1.4);
    const t1 = c.text("fwo-s-tag", 296, 122, 10, 9, { fill: "#8b96a1" });
    const t0 = c.text("fwo-s-tag", 288, 282, 10, 9, { fill: "#8b96a1" });
    c.tag((v) => { t1.textContent = tTag(v.p1, false); t0.textContent = tTag(1 - v.p1, false); }, [t1, t0]);
    c.ghosts({ stroke: "#8b96a1", "stroke-width": 1.3, "stroke-dasharray": "5 4", opacity: 0.45 }, 10.5,
      { fill: "#8b96a1", "font-weight": 500 });
    for (const i of [1, 0]) {
      const g = c.futureGroup(i, { stroke: "#45c8e0", fill: "none" });
      const ring = c.add("circle", { "stroke-width": 1.6 }, g);
      const inner = c.add("circle", { "stroke-width": 0.8, "stroke-dasharray": "2 3" }, g);
      const cross = c.add("path", { "stroke-width": 0.8 }, g);
      const ticks = c.add("path", { "stroke-width": 1 }, g);
      c.future(i, (cx, cy, r) => {
        set(ring, { cx, cy, r });
        set(inner, { cx, cy, r: Math.max(0.5, r - 6) });
        cross.setAttribute("d", "M " + n1(cx - r - 12) + "," + n1(cy) + " H " + n1(cx + r + 12) + " M " + n1(cx) + "," +
          n1(cy - r - 12) + " V " + n1(cy + r + 12));
        let d = "";
        for (let k = 0; k < 24; k++) {
          const a = Math.PI * k / 12, ca = Math.cos(a), sa = Math.sin(a), r2 = r + (k % 6 === 0 ? 9 : 7);
          d += "M " + n1(cx + (r + 4) * ca) + "," + n1(cy + (r + 4) * sa) + " L " + n1(cx + r2 * ca) + "," + n1(cy + r2 * sa) + " ";
        }
        ticks.setAttribute("d", d);
      });
    }
    c.futureLabels(11, { fill: "#b9c0c7", "font-weight": 500 }, 18, (fs) => 14 + 1.1 * fs);
  },

  c(c) {
    c.gradient("bg", [[0, "#14101f"], [0.55, "#0a0a10"], [1, "#050507"]],
      { gradientUnits: "userSpaceOnUse", cx: 0, cy: 0, r: 1, gradientTransform: "translate(277.2 168) scale(561 357)" });
    c.gradient("tissue", [[0, "#b79cff", 0.3], [0.55, "#8e6fe8", 0.13], [1, "#8e6fe8", 0]], {});
    c.gradient("orb", [[0, "#f0e9ff"], [0.38, "#c4acff"], [0.78, "#6d4fc2"], [1, "#332361"]], { cx: "42%", cy: "38%", r: "70%" });
    c.gradient("orbglow", [[0, "#b79cff", 0.5], [0.7, "#b79cff", 0.12], [1, "#b79cff", 0]], {});
    c.gradient("world", [[0, "#d9fff4"], [0.4, "#63e6c4"], [1, "#144d40"]], { cx: "42%", cy: "38%", r: "70%" });
    c.add("rect", Object.assign({ fill: c.ref("bg") }, BG));
    c.bridge({ stroke: "#63e6c4" }, "#eafff9");
    c.brain({ body: ["#110f1b", 0.4], glow: { cx: SELF_X, cy: 176, rx: 150, ry: 112, fill: c.ref("tissue") },
      shell: { fill: "#b79cff", "fill-opacity": 0.08 }, link: { stroke: "#b79cff", "stroke-opacity": 0.5, "stroke-width": 0.9 },
      ball: [[0, "#f5f0ff"], [0.5, "#c9b4ff"], [1, "#6d4fc2"]] });
    c.selfLabel(70, 12.5, { fill: "#c6c3ce", "font-weight": 500 });
    c.add("circle", { cx: WORLD[0], cy: WORLD[1], r: WORLD_R + 16, fill: c.ref("orbglow"), opacity: 0.35 });
    c.add("circle", { cx: WORLD[0], cy: WORLD[1], r: WORLD_R, fill: c.ref("world"), opacity: 0.92 });
    c.add("circle", { cx: WORLD[0], cy: WORLD[1], r: WORLD_R + 7, fill: "none", stroke: "#63e6c4", "stroke-width": 1, opacity: 0.45 });
    c.worldLabel(38, 12.5, { fill: "#63e6c4", "font-weight": 500 });
    c.branches({ stroke: "#8e6fe8", opacity: 0.16 }, (t) => 2 * t + 1.4, { stroke: "#c4acff", opacity: 0.9 });
    c.particles("circle", { fill: "#e4d9ff", opacity: 0.85 }, 1.9);
    c.ghosts({ stroke: "#948fa6", "stroke-width": 1.4, "stroke-dasharray": "3 5", opacity: 0.34 }, 11.5,
      { fill: "#948fa6", "font-weight": 500 });
    for (const i of [1, 0]) {
      const g = c.futureGroup(i);
      const glow = c.add("circle", { fill: c.ref("orbglow") }, g);
      const orb = c.add("circle", { fill: c.ref("orb") }, g);
      c.future(i, (cx, cy, r) => { set(glow, { cx, cy, r: r + 20 }); set(orb, { cx, cy, r }); });
    }
    c.futureLabels(12.5, { fill: "#c6c3ce", "font-weight": 500 }, 14, (fs) => 12 + 0.95 * fs);
  },

  d(c) {
    c.hatch("hatch", "#17355e");
    c.pattern("grid", 24, "M 24,0 L 0,0 0,24", "#d9e3ef");
    c.add("rect", Object.assign({ fill: "#f8fafc" }, BG));
    c.add("rect", Object.assign({ fill: c.ref("grid") }, BG));
    c.bridge({ stroke: "#0e6e8c", "stroke-dasharray": "4 3" }, "#7fe3ff");
    c.brain({ body: ["#f8fafc", 0.43], shell: { fill: "#b23a1f", "fill-opacity": 0.08 }, link: { stroke: "#17355e", "stroke-opacity": 0.5, "stroke-width": 0.8 },
      ball: [[0, "#f0a08a"], [0.5, "#bf4a2c"], [1, "#6b1f0f"]] });
    c.selfLabel(64, 11, { fill: "#17355e", "font-weight": 600 });
    c.add("line", { x1: SELF_X, y1: 70, x2: SELF_X, y2: 88, stroke: "#17355e", "stroke-width": 1 });
    const bd = dimension(206, 324, 170, 290);
    const bdim = c.add("g", { class: "fwo-s-dim" });
    c.add("path", { d: bd.line, stroke: "#44597a", "stroke-width": 1, fill: "none" }, bdim);
    c.add("path", { d: bd.heads, fill: "#44597a" }, bdim);
    const bridgeTag = c.text("fwo-s-tag", 210, 334, 9.5, 9, { fill: "#44597a" });
    c.tag((v, narrow) => {
      bridgeTag.textContent = "bridge " + (4 + 6 * v.I).toFixed(1) + " px" + (narrow ? "" : " \u00b7 op. " +
        (0.15 + 0.85 * v.I).toFixed(2) + " (I = " + v.I.toFixed(3) + ")");
    }, [bridgeTag, bdim]);
    c.add("circle", { cx: WORLD[0], cy: WORLD[1], r: WORLD_R, fill: "#0e6e8c", stroke: "#17355e", "stroke-width": 1.6 });
    c.add("path", { d: "M 150,344 A 22,22 0 0 0 128,322 L 150,322 Z", fill: c.ref("hatch") });
    c.add("ellipse", { cx: WORLD[0], cy: WORLD[1], rx: 36, ry: 9, fill: "none", stroke: "#17355e", "stroke-width": 1,
      transform: "rotate(-16 150 322)" });
    c.worldLabel(41, 11, { fill: "#17355e", "font-weight": 600 });
    c.branches(null, null, { stroke: "#17355e", opacity: 1 });
    c.particles("circle", { fill: "#17355e", opacity: 0.55 }, 1.8);
    const t1 = c.text("fwo-s-tag", 296, 116, 9.5, 9, { fill: "#44597a" });
    const t0 = c.text("fwo-s-tag", 288, 282, 9.5, 9, { fill: "#44597a" });
    c.tag((v, narrow) => { t1.textContent = tTag(v.p1, !narrow); t0.textContent = tTag(1 - v.p1, !narrow); }, [t1, t0]);
    c.ghosts({ stroke: "#17355e", "stroke-width": 1.2, "stroke-dasharray": "5 4", opacity: 0.5 }, 10.5,
      { fill: "#44597a", "font-weight": 500 });
    for (const i of [1, 0]) {
      const g = c.futureGroup(i);
      const disc = c.add("circle", { fill: "#b23a1f", stroke: "#17355e", "stroke-width": 1.6 }, g);
      const quad = c.add("path", { fill: c.ref("hatch") }, g);
      const axes = c.add("path", { class: "fwo-s-cl", fill: "none", stroke: "#17355e", "stroke-width": 0.7,
        "stroke-dasharray": "8 3 2 3", opacity: 0.6 }, g);
      let dim = null, dimHeads = null, dimTag = null;
      if (i === 1) {
        const dg = c.add("g", { class: "fwo-s-dim" }, g);
        dim = c.add("path", { stroke: "#44597a", "stroke-width": 1, fill: "none" }, dg);
        dimHeads = c.add("path", { fill: "#44597a" }, dg);
        dimTag = c.text("fwo-s-tag", 512, 185, 9.5, 9, { fill: "#44597a" }, dg);
        dimTag.textContent = "\u00d8 = 52 \u00b7 \u221bp";
      }
      c.future(i, (cx, cy, r) => {
        set(disc, { cx, cy, r });
        quad.setAttribute("d", "M " + n1(cx) + "," + n1(cy + r) + " A " + n1(r) + "," + n1(r) + " 0 0 0 " + n1(cx - r) + "," +
          n1(cy) + " L " + n1(cx) + "," + n1(cy) + " Z");
        axes.setAttribute("d", "M " + n1(cx - r - 8) + "," + n1(cy) + " H " + n1(cx + r + 8) + " M " + n1(cx) + "," +
          n1(cy - r - 8) + " V " + n1(cy + r + 8));
        if (dim) {
          const dd = dimension(cx - r, cy + r + 10, cx + r, cy + r + 10);
          dim.setAttribute("d", dd.line);
          dimHeads.setAttribute("d", dd.heads);
          set(dimTag, { x: cx, y: cy + r + 22 + c.fontSize(dimTag) });
        }
      });
    }
    c.futureLabels(11, { fill: "#17355e", "font-weight": 600 }, 12, (fs) => 10 + 0.95 * fs);
  },
};

export const PLATE_STYLES = Object.keys(STYLES);

export function createPlate(lib, host, opts) {
  const o = Object.assign({ style: "a", reducedMotion: false }, opts || {});
  const style = STYLES[o.style] ? o.style : "a";
  const { svg, replace } = lib;
  const api = { available: true };
  const uid = "fwo-plate-" + style + "-";
  const root = svg("svg", { class: "fwo-plate fwo-plate--" + style, viewBox: "0 0 " + W + " " + H,
    preserveAspectRatio: "xMidYMid meet", role: "img", "aria-label": "Observatory scene (loading)", focusable: "false" });
  const defs = svg("defs", {});
  root.appendChild(defs);

  // ---------------------------------------------------------------- parts that follow the data
  const dyn = { under: [null, null], underWidth: null, branch: [null, null], bridge: null, parts: [], partKind: "circle",
    partSize: 1.8, ghost: [null, null], ghostLabel: null, groups: [null, null], future: [null, null], label: [null, null],
    labelTop: 12, labelBottom: (fs) => 10 + 0.95 * fs, self: null, world: null, worldGap: 34, tags: [], tagNodes: [],
    fonts: [] };

  const c = {
    ref: (name) => "url(#" + uid + name + ")",
    add(tag, attrs, parent) {
      const node = svg(tag, attrs || {});
      (parent || root).appendChild(node);
      return node;
    },
    gradient(name, stops, attrs) {
      const gr = svg("radialGradient", Object.assign({ id: uid + name }, attrs));
      for (const s of stops) gr.appendChild(svg("stop", { offset: s[0], "stop-color": s[1], "stop-opacity": s.length > 2 ? s[2] : null }));
      defs.appendChild(gr);
    },
    pattern(name, size, d, stroke) {
      const pt = svg("pattern", { id: uid + name, width: size, height: size, patternUnits: "userSpaceOnUse" },
        svg("path", { d, fill: "none", stroke, "stroke-width": 1 }));
      defs.appendChild(pt);
    },
    hatch(name, stroke) {
      const pt = svg("pattern", { id: uid + name, width: 6, height: 6, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" },
        svg("line", { x1: 0, y1: 0, x2: 0, y2: 6, stroke, "stroke-width": 1.1 }));
      defs.appendChild(pt);
    },
    text(cls, x, y, base, min, attrs, parent) {
      const t = c.add("text", Object.assign({ class: cls, x, y, "font-size": base }, attrs || {}), parent);
      dyn.fonts.push([t, base, min]);
      return t;
    },
    fontSize: (node) => Number(node.getAttribute("font-size")) || 11,
    links(attrs) {
      let d = "";
      for (let k = 0; k < LINKS.length; k += 2) {
        const a = LINKS[k] * 3, b = LINKS[k + 1] * 3;
        d += "M " + NODES[a] + "," + NODES[a + 1] + " L " + NODES[b] + "," + NODES[b + 1] + " ";
      }
      c.add("path", Object.assign({ d, fill: "none" }, attrs));
    },
    // The Self as in the 3D view: first its body (the two lobe outlines filled with the scene's
    // own background colour, laid over the World bridge so the bridge enters the mind), an
    // optional glow, the two translucent lobe shells (overlapping in the middle), the links,
    // then the nodes as shaded balls, far to near: two graphs with a narrow fissure.
    brain(o) {
      c.gradient("ball", o.ball, { cx: "36%", cy: "32%", r: "72%" });
      const lobe = (L, attrs) => Object.assign({ cx: L[0], cy: L[1], rx: L[2], ry: L[3],
        transform: "rotate(" + L[4] + " " + L[0] + " " + L[1] + ")" }, attrs);
      const body = c.add("g", { opacity: o.body[1] });            // one opacity for the union
      for (const L of LOBES) c.add("ellipse", lobe(L, { fill: o.body[0] }), body);
      if (o.glow) c.add("ellipse", o.glow);
      for (const L of LOBES) c.add("ellipse", lobe(L, o.shell));
      c.links(o.link);
      const g = c.add("g", { fill: c.ref("ball") });
      for (let k = 0; k < NODES.length; k += 3) c.add("circle", { cx: NODES[k], cy: NODES[k + 1], r: NODES[k + 2] }, g);
    },
    selfLabel(y, base, attrs) {
      dyn.self = c.text("fwo-s-lab fwo-s-lab--self", SELF_X, y, base, 10.5, Object.assign({ "text-anchor": "middle" }, attrs));
      dyn.self.textContent = TEXT.self;
    },
    worldLabel(gap, base, attrs) {
      dyn.worldGap = gap;
      dyn.world = c.text("fwo-s-lab fwo-s-lab--world", WORLD[0], WORLD[1] + gap + base, base, 10.5,
        Object.assign({ "text-anchor": "middle" }, attrs));
      dyn.world.textContent = TEXT.world;
    },
    // The World bridge, and over it the shimmer: soft bright pulses that climb from the World
    // into the Self while motion is on, as many and as bright as the connection is strong.
    bridge(attrs, glow) {
      dyn.bridge = c.add("path", Object.assign({ d: BRIDGE, fill: "none", "vector-effect": "non-scaling-stroke",
        "stroke-linecap": "round" }, attrs));
      defs.appendChild(svg("filter", { id: uid + "shimmer", x: "-60%", y: "-20%", width: "220%", height: "140%" },
        svg("feGaussianBlur", { stdDeviation: 1.4 })));
      dyn.shimmer = c.add("path", { d: BRIDGE, fill: "none", stroke: glow, "stroke-linecap": "round",
        filter: c.ref("shimmer"), display: "none" });
    },
    branches(under, underWidth, main) {
      for (const i of [1, 0]) {
        if (under) dyn.under[i] = c.add("path", Object.assign({ fill: "none", "vector-effect": "non-scaling-stroke" }, under));
      }
      dyn.underWidth = underWidth;
      for (const i of [1, 0]) dyn.branch[i] = c.add("path", Object.assign({ fill: "none", "vector-effect": "non-scaling-stroke" }, main));
    },
    particles(kind, attrs, size) {
      dyn.partKind = kind;
      dyn.partSize = size;
      const g = c.add("g", attrs);
      for (let k = 0; k < N_PART; k++) {
        dyn.parts.push(c.add(kind, kind === "rect" ? { width: 2 * size, height: 2 * size } : { r: size }, g));
      }
    },
    ghosts(attrs, base, labelAttrs) {
      const g = c.add("g", Object.assign({ fill: "none" }, attrs));
      dyn.ghostGroup = g;
      for (const i of [1, 0]) dyn.ghost[i] = c.add("circle", {}, g);
      dyn.ghostLabel = c.text("fwo-s-ghost", 0, 0, base, 9.5, labelAttrs);
      dyn.ghostLabel.textContent = TEXT.previous;
    },
    futureGroup(i, attrs) {
      dyn.groups[i] = c.add("g", Object.assign({ class: "fwo-plate-future fwo-plate-future--" + i }, attrs || {}));
      return dyn.groups[i];
    },
    future(i, fn) {
      dyn.future[i] = fn;
    },
    futureLabels(base, attrs, top, bottom) {
      dyn.labelTop = top;
      dyn.labelBottom = bottom;
      for (const i of [1, 0]) {
        dyn.label[i] = c.text("fwo-s-lab fwo-s-lab--f" + i, FC[i][0], FC[i][1], base, 10.5, Object.assign({ "text-anchor": "middle" }, attrs));
      }
    },
    tag(fn, nodes) {
      dyn.tags.push(fn);
      for (const n of nodes) dyn.tagNodes.push(n);
    },
  };
  STYLES[style](c);
  host.classList.add("fwo-scene-host--plate");
  replace(host, root);

  // ---------------------------------------------------------------- state
  const state = { p1: 0.5, I: 0, placeholder: true };   // what is drawn (moves during the transition)
  let target = { p1: 0.5, I: 0 };                        // the run's numbers (annotations use these)
  let ghost = null;
  let liveText = ["Future 0: no run yet", "Future 1: no run yet"];
  let anim = null;
  let motion = !o.reducedMotion;
  let reduced = !!o.reducedMotion;
  let width = 0, height = 0, scale = 1, narrow = false;
  let running = false, last = 0;
  let shimmerLen = 0, shimmerAt = 0;                     // bridge length (scene units), dash offset
  let split = N_PART / 2;                                // particles on Future 1's branch
  const u = new Float64Array(N_PART);                    // position along the branch, 0..1

  // The still layout: evenly spaced along each branch, as in the design drawings.
  function evenParticles() {
    const n1c = split, n0c = N_PART - split;
    for (let k = 0; k < N_PART; k++) {
      const onOne = k < n1c;
      const idx = onOne ? k : k - n1c;
      const n = onOne ? n1c : n0c;
      u[k] = n > 0 ? (idx + 0.5) / n : 0;
    }
  }

  function placeParticles(r) {
    for (let k = 0; k < N_PART; k++) {
      const i = k < split ? 1 : 0;
      const [x, y] = bezier(r[i].curve, 0.06 + 0.9 * u[k]);
      const node = dyn.parts[k];
      if (dyn.partKind === "rect") set(node, { x: x - dyn.partSize, y: y - dyn.partSize });
      else set(node, { cx: x, cy: y });
    }
  }

  function fitText() {
    for (const [node, base, min] of dyn.fonts) node.setAttribute("font-size", n1(Math.max(base, min / scale)));
    if (dyn.self) dyn.self.textContent = narrow ? TEXT.selfNarrow : TEXT.self;
    if (dyn.world) dyn.world.setAttribute("y", n1(WORLD[1] + dyn.worldGap + c.fontSize(dyn.world)));
  }

  function apply() {
    const p = [1 - state.p1, state.p1];
    const r = [0, 1].map((i) => {
      const rad = state.placeholder ? radius(0.5) : radius(p[i]);
      return { rad, curve: branchCurve(i, rad) };
    });
    for (const i of [0, 1]) {
      const t = state.placeholder ? 2 : 2 + 10 * p[i];
      const d = curvePath(r[i].curve);
      set(dyn.branch[i], { d, "stroke-width": t.toFixed(2) });
      dyn.branch[i].style.opacity = state.placeholder ? "0.35" : "";
      if (dyn.under[i]) set(dyn.under[i], { d, "stroke-width": dyn.underWidth(t).toFixed(2) });
      if (dyn.future[i]) dyn.future[i](FC[i][0], FC[i][1], r[i].rad);
      if (dyn.groups[i]) dyn.groups[i].style.opacity = state.placeholder ? "0.35" : "";
      const lab = dyn.label[i];
      if (lab) {
        lab.textContent = liveText[i];
        const fs = c.fontSize(lab);
        lab.setAttribute("y", n1(i === 1 ? FC[i][1] - r[i].rad - dyn.labelTop : FC[i][1] + r[i].rad + dyn.labelBottom(fs)));
      }
    }
    const I = state.placeholder ? 0 : state.I;
    const bw = 4 + 6 * I;
    set(dyn.bridge, { "stroke-width": bw.toFixed(2), opacity: (0.15 + 0.85 * I).toFixed(3) });
    shimmer(I, bw);
    placeParticles(r);
    // previous run: dashed outlines, labelled once beside Future 0's
    const show = ghost !== null;
    dyn.ghostGroup.setAttribute("display", show ? "inline" : "none");
    dyn.ghostLabel.setAttribute("display", show ? "inline" : "none");
    if (show) {
      const gp = [1 - ghost.p1, ghost.p1];
      for (const i of [0, 1]) set(dyn.ghost[i], { cx: FC[i][0] + GHOST_OFF[0], cy: FC[i][1] + GHOST_OFF[1], r: radius(gp[i]) });
      const g0 = radius(gp[0]);
      let len = 0;
      try { len = dyn.ghostLabel.getComputedTextLength(); } catch (err) { len = 0; }
      if (!len) len = 0.6 * c.fontSize(dyn.ghostLabel) * TEXT.previous.length;
      const gx = Math.min(FC[0][0] + GHOST_OFF[0] + g0 + 8, W - 6 - len);
      set(dyn.ghostLabel, { x: gx, y: FC[0][1] + GHOST_OFF[1] + 4 });
    }
  }

  // The shimmer: 1 to 4 pulses (more with more connection) spaced evenly along the bridge at
  // brightness 0.9 I, climbing from the World into the Self while motion is on. No connection,
  // no shimmer; still or reduced motion, no shimmer (the bridge's width and opacity still show I).
  function shimmer(I, bw) {
    const on = motion && !state.placeholder && I > 0.02;
    dyn.shimmer.setAttribute("display", on ? "inline" : "none");
    if (!on) return;
    if (!shimmerLen) {
      try { shimmerLen = dyn.shimmer.getTotalLength(); } catch (err) { shimmerLen = 0; }
      if (!shimmerLen) shimmerLen = 196;
    }
    const n = 1 + Math.round(3 * I);
    const period = shimmerLen / n;
    const pulse = Math.min(24, period * 0.45);
    set(dyn.shimmer, { "stroke-width": (0.85 * bw / Math.max(0.2, scale)).toFixed(2),
      "stroke-dasharray": n1(pulse) + " " + n1(period - pulse), "stroke-dashoffset": n1(shimmerAt), opacity: (0.9 * I).toFixed(3) });
  }

  function applyTags() {
    for (const n of dyn.tagNodes) n.setAttribute("display", state.placeholder ? "none" : "inline");
    if (!state.placeholder) for (const fn of dyn.tags) fn(target, narrow);
  }

  function resize() {
    const w = Math.round(host.clientWidth || 0), hh = Math.round(host.clientHeight || 0);
    if (!w || !hh || (w === width && hh === height)) return false;
    width = w; height = hh;
    scale = Math.min(w / W, hh / H);
    narrow = w < NARROW;
    fitText();
    applyTags();
    return true;
  }

  function step(now) {
    const dt = last ? Math.min(0.1, (now - last) / 1000) : 0;
    last = now;
    let busy = false;
    if (anim) {
      const s = Math.min(1, (now - anim.t0) / 1000);
      const e = ease(s);
      state.p1 = anim.from.p1 + (anim.to.p1 - anim.from.p1) * e;
      state.I = anim.from.I + (anim.to.I - anim.from.I) * e;
      if (s >= 1) anim = null; else busy = true;
    }
    if (motion) {
      for (let k = 0; k < N_PART; k++) u[k] = frac(u[k] + FLOW * dt);
      // a falling dash offset moves the pulses forward along the bridge: World to Self
      shimmerAt = (shimmerAt - ((shimmerLen || 196) / SHIMMER_S) * dt) % 100000;
      busy = true;
    }
    apply();
    return busy;
  }

  function raf(fn) {
    if (typeof requestAnimationFrame === "function") requestAnimationFrame(fn);
    else if (o.setTimeoutFn) o.setTimeoutFn(() => fn(Date.now()), 16);
  }

  function loop(now) {
    if (!running) return;
    if (!root.isConnected) { running = false; return; }
    const busy = step(typeof now === "number" ? now : Date.now());
    if (busy) raf(loop); else { running = false; last = 0; }
  }

  function kick() {
    if (running) return;
    running = true;
    last = 0;
    raf(loop);
  }

  function still(flag) {
    root.classList.toggle("fwo-plate--still", flag);
  }

  // ---------------------------------------------------------------- public API (as ui/scene.js)
  api.setResult = (run, prev, text) => {
    const m = run && run.metrics ? run.metrics : {};
    const to = { p1: clamp01(m.p_self_1), I: clamp01(m.connection_bits) };
    ghost = prev && prev.metrics ? { p1: clamp01(prev.metrics.p_self_1), I: clamp01(prev.metrics.connection_bits) } : null;
    liveText = [text.f0, text.f1];
    const from = state.placeholder ? { p1: 0.5, I: 0 } : { p1: state.p1, I: state.I };
    state.placeholder = false;
    target = to;
    split = Math.round(to.p1 * N_PART);
    evenParticles();
    if (reduced) {
      anim = null;
      state.p1 = to.p1; state.I = to.I;
    } else {
      anim = { from, to, t0: (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now() };
    }
    applyTags();
    apply();
    kick();
  };
  api.setLabel = (label) => { root.setAttribute("aria-label", label); };
  api.setMotion = (on) => { motion = !!on; still(!motion); kick(); };
  api.setReducedMotion = (flag) => {
    reduced = !!flag;
    if (reduced) { motion = false; anim = null; state.p1 = target.p1; state.I = target.I; still(true); }
    kick();
  };
  api.motion = () => motion;
  api.resize = () => { if (resize()) { apply(); kick(); } };
  api.dispose = () => { running = false; api.available = false; };
  api.canvas = root;
  api.style = style;

  still(!motion);
  evenParticles();
  resize();
  apply();
  applyTags();
  kick();
  return api;
}
