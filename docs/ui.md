# The Observatory page (JS UI)

**Layout (friendly version, 2026-10-11).** The page reads top to bottom as three steps, then
the results in plain words, then optional detail panels:

1. **Hero:** title, a one-sentence hook, and the three steps.
2. **Pick a guide:** three persona cards (`role="tab"`). Under them, the RPG dialogue box with a
   portrait to the side. The portrait is a labelled placeholder (`.fwo-portrait`) until the
   sprite sheets land. The one dialogue box moves into the selected guide's tab panel. Before a
   run each guide greets the visitor (`txt.INTRO`, placeholder lines for the team to replace);
   after a run it speaks the engine's persona line. Each guide's panel also carries a one-line
   tip: the Self's dials in plain words, the Demon's forecast, the Observer's point of view.
3. **Set the dials:** "Your choice" (intention), "Ties to the world" (World coupling), "Point of
   view" (perspective), each with one plain sentence; the technical name is small print.
   Degrees on the surface; radians and gamma live in the aria-valuetext and the panels.
4. **Run the experiment:** one big button, a plain policy line, the status line. Shots,
   packing and the self-check circuits sit in "Advanced run settings".
5. **Two possible futures:** the 3D scene with two big percentage cards (sticky beside the
   left column on wide screens).
6. **What happened:** three plain cards with a 0-1 meter each: how much your choice can change
   the odds (with the 95% range drawn as a band), how open the future is, how much the World
   knows. The exact sentence "No resolved influence at this shot count." appears when the range
   includes zero.
7. **Want more detail?** Closed drop-downs: the full numbers (factual sentence, count tables,
   job record), the before/after chart, the Demon's prediction, how it works step by step (plain
   steps, circuit diagram, the four circuits, the math), how sure we can be (the range, theory
   curves, calibration and noise tables), the classical comparison, where this runs (backend
   chips), and what this does NOT show.

The sections below describe the components; ids and contracts are unchanged.


The browser side of The Free Will Observatory: a Qollab-native JS project (top-level
`index.html` + `main.js` + `main.css` + `ui/*.js`) that calls the Python engine
(`observatory_api.py`) in the same browser tab and draws the scene with three.js from
Qollab's import map. No server, no polling API, no keys, no React, no bundler.

Simulators compute what quantum theory predicts and how a noise model degrades it;
they do not test nature. The readings are a designed, fictional model of agency, and the
page says so next to the results.

This effort is supported by Qollab & IonQ

## Files

| File | Uploaded? | Role |
|---|---|---|
| `qollab_project/index.html` | yes | Body fragment (no scripts, no `on*` attributes, no inline styles): header + backend badge, status line, persona tabs, controls, scene host, futures, readings, chart, explanation, baselines, the "How this works" drawer, footer with the attribution line. |
| `qollab_project/main.css` | yes | The only stylesheet. Scoped under `#fwo-app`; colours are CSS variables. Carries the four page styles (A night observatory, B instrument console, C luminous anatomy, D blueprint), each scoped by `data-theme` on `#fwo-app`, and one Google Fonts import for their typefaces. Every style's text and control colours are contrast-tested. |
| `qollab_project/main.js` | yes | Entry: waits for the DOM, wires everything, calls Python, ends with `await new Promise(() => {})`. |
| `qollab_project/ui/dom.js` | yes | `whenMounted`, `h`/`svg` builders (text only, never `innerHTML`), number formatting, a `setTimeout`-only debounce, accessible tables. |
| `qollab_project/ui/text.js` | yes | Every sentence the page shows or announces (honesty note, probe texts, capacity sentence, scene label, chart and curve summaries). |
| `qollab_project/ui/tabs.js` | yes | Persona tabs (WAI-ARIA tabs, roving tabindex, arrow keys). |
| `qollab_project/ui/badge.js` | yes | Backend badge. |
| `qollab_project/ui/scene.js` | yes | The three.js scene (below). Exports `mulberry32` and `brainGraph` so the geometry is testable. |
| `qollab_project/ui/plate.js` | yes | The scene drawn flat as SVG in the four design directions' styles (below). A theme selects it with `--fwo-scene-plate`; it needs no WebGL. |
| `qollab_project/ui/chart.js` | yes | Hand-rolled SVG bar chart (previous / current / forecast) and line chart (theory curves). |
| `qollab_project/ui/readings.js` | yes | Futures, the three readings, Demon forecast and comparison, baselines, run-failure view, the drawer (circuit text, count tables, job record, honesty), coverage and noise tables. |
| `dev/index.html`, `dev/boot.js`, `dev/stub_api.js`, `dev/stub_data.js` | no | Stub mode for local testing (below). |
| `tools/make_ui_stubs.py` | no | Regenerates `dev/stub_data.js` from the real `observatory_api` functions. |
| `tests/test_ui_static.py` | no | Static checks: platform rules, labels, live regions, contrast, hygiene, stub contract, node parse. |

`ui/` modules import nothing; `main.js` imports them and passes in the helpers (and the
`THREE` module), so they behave the same under Qollab's CommonJS transform and as native
ES modules in stub mode.

## Structure and flow

1. `whenMounted("fwo-app")` polls for the injected fragment, then `profile_json(backend, true)`
   is called exactly once (a fresh one-job budget for this page load) and the badge is drawn.
2. The sliders edit a **draft**; every change recomputes the Demon's forecast
   (`predict_json`, debounced 150 ms), the Self/Observer sentences and the forecast bars.
3. **Run experiment** submits the whole draft as ONE job (`run_json`). While it is awaited the
   button is `aria-disabled` (local backends) or locked for good (one-job backends, with a
   visible note that receives focus), the status line says what was submitted, and a
   "Live simulator: waiting for the job… N s" line counts the elapsed time. The guards run
   before the handler's first `await`, so a double-click cannot submit twice.
4. On completion the previous run becomes the ghost; futures, readings, chart, factual
   sentence, persona line, Demon comparison, baselines, drawer and the scene update; the
   canvas `aria-label` is rewritten. On failure the error and the job evidence are shown and
   nothing is substituted.
5. Persona tabs change which interpretation is shown (and the `persona` field of the next
   draft); they never touch data.
6. Size changes (a `ResizeObserver` on the scene host and both chart containers, plus the
   window `resize` event) schedule one redraw 150 ms later, a throttle with a trailing run so
   a burst can never starve it; a chart is rebuilt only when its container width changed.

## Visual mappings (from the build guide, applied from the completed display run only)

| Element | Mapping |
|---|---|
| Future 1 / Future 0 spheres | radius = `RMAX · cbrt(p)`, p = P(Self = 1) and 1 − p from the display probe (volume follows probability) |
| Branch tubes | thickness 2 + 10 p **pixels**, converted to world units at the branch depth (`unitsPerPx`), so it is really that many pixels |
| World bridge | thickness 4 + 4.5 I px (at most 8.5 px) and opacity 0.15 + 0.85 I, I = connection bits from the separate connection probe |
| Ghost | the previous completed distribution as wireframe spheres and faint tubes labelled "previous"; the live geometry animates from it over about 1 s (eased); replaced when the next result arrives |
| Particles | 520 points, a fixed number, routed to the two branches in proportions p0 / p1; they drift along the branches when motion is on; never shot chronology |
| Brain graph | two ellipsoid lobes, 100 nodes, 3 nearest-neighbour links each, generated once from a seeded PRNG (`mulberry32`, seed 20261010); it never changes with the data |
| Before/after chart | bars: previous (hatched), current (solid), Demon forecast (outlined, dashed) |
| Theory chart (drawer) | ideal capacity (solid), P_low / P_high (dashed), connection (dash-dot) against w, with the draft's w as a diamond |

Colour is never the only signal: labels, hatching, dash patterns and text carry everything.

## Drawn scenes for the design themes (`ui/plate.js`)

Each page style (A to D, shipped in `main.css`, D by default; the Style menu on the kicker line changes it, and `?theme=a|b|c|d|none` picks one in stub mode) sets `--fwo-scene-plate`
to its letter, and `main.js` then draws the scene with `ui/plate.js` instead of the three.js
view. Without the variable the 3D view runs, unchanged.

| Style | Look |
|---|---|
| a, night observatory | starfield sky, gold shaded orbs with halos, dotted light along the branches, ringed teal World |
| b, instrument console | engineering grid, wireframe reticles with tick rings and centre marks, annotated `t = ... px` and `I = ... bits` |
| c, luminous anatomy | violet glow behind the brain, glowing orbs, mint World |
| d, blueprint | graph paper, ink lines, brick-red discs with a hatched quadrant and centre lines, dimension line `Ø = 52 · ∛p`, annotated widths |

The plate keeps the 3D view's mappings: radius `52 · cbrt(p)` scene units, branch width
2 + 10 p screen pixels (non-scaling strokes), bridge 4 + 4.5 I px (at most 8.5) at opacity 0.15 + 0.85 I, rising from the World into the Self, where the Self's body (the lobes filled with the scene's background) is layered over it, as if it enters the mind,
dashed outlines for the previous run, and a fixed 40 particles split p1 / p0 that flow evenly
when motion is on. Annotations always show the run's own numbers, never the in-between frames
of the one-second transition. The Self is the 3D view's own brain (the same seed: two lobes with a fissure, 100 nodes, three nearest-neighbour links each), turned by the 3D view's tilt and projected flat, inside two overlapping translucent lobe shells, the two graphs a narrow fissure apart. The nodes use each design direction's own style as a glowing point cloud (a point with a soft glow at every node, thin links), and with motion on the constellation drifts: the 3D view's slow sway, re-projected with real depth, nearer nodes a little larger and brighter. The brain layout and the stars are fixed constants, so a change
in the picture always means a change in the numbers. The frame keeps the drawing's 660 x 420
proportions; labels are kept at a readable size on phones and switch to shorter wording below
480 px. While motion is on, a shimmer of soft pulses climbs the bridge from the World into the Self: one pulse
at low connection, up to four at 1 bit, brightness 0.9 I, none at zero connection.
Reduced motion (or the Motion box unticked) stops the flow, the transition, the
shimmer and the star twinkle.

## Stub mode (local testing)

Stub mode runs the unchanged `main.js` in an ordinary browser with `observatory_api` replaced
by `dev/stub_api.js` (import map) and `backend` replaced by a stand-in object. `dev/boot.js`
starts `main.js` first and injects `index.html` 300 ms later, as Qollab would.

1. `.venv/bin/python tools/make_ui_stubs.py` regenerates the canned data: profiles for an
   ideal local simulator, an IonQ-shaped stand-in (one job per run) and a failing backend;
   `predict_json` + `run_json` on a seeded BasicSimulator for the three demo settings of the
   guide, w = 0.5, and two Observer settings; the IonQ refusal; the failing run; `curves_json()`.
2. Serve the repository root on your machine's loopback interface only, e.g.
   `.venv/bin/python -m http.server 8761 --bind <loopback address>`, and open `/dev/index.html`
   on that server.
3. Query parameters: `?backend=basic|ionq|error|none`, `&mount=1500` (late injection),
   `&slow=4` (slower stub calls, to watch the progress line), `&reduce=1` (report
   `prefers-reduced-motion: reduce` to the JS; the CSS media query still follows the real
   preference), `&nowebgl=1` (every canvas refuses a WebGL context, so the text-only
   fallback runs), `&axe=1` (axe-core report under the page).

Settings without a canned run are synthesized in JS from the closed-form distributions with a
seeded sampler; the backend name then says `[stub: JS closed-form sampler]` and the persona
lines are borrowed from the nearest canned run, marked `[stub]`. A test checks that the JS
closed form agrees with `observatory.prediction` to 1e-9.

## Sprite portraits (`ui/sprites.js`, `ui/dialogue.js`)

The portrait beside the dialogue line is an animated pixel-art sprite per guide, keyed to the
page's state. Sheets are horizontal strips of square cells: 128 px for wide screens and a
64 px strip for phones (derived by area-averaging the 128 px art, never CSS-scaled; the element
is drawn at a whole-number scale with `image-rendering: pixelated`). `tools/build_sprites.py`
embeds the team's SpriteGen exports as data URIs (JavaScript on Qollab cannot fetch project
files) and copies each sheet's timing from its sidecar and frame names.

| State of the page | The Self | Laplace's Demon | The Observer |
|---|---|---|---|
| at rest | idle | idle | idle (stare while the point-of-view dial is being turned) |
| a job is running | idle | gesture (works the orb) | stare |
| result: the choice measurably moved the odds | happy | gesture if the sample fell within the forecast's shot noise, anger if it fell outside | dance |
| result: no resolved influence | angry: frames 1–4 once, then hold on frame 4 until the dials change or a new run starts | same rule as above | dance |
| the run failed | angry (same hold) | anger | idle |

Timing rules: each sheet plays at its own fps; a sheet with per-frame `ticks` holds frames
for that many ticks (the Observer's stare holds its first image for 61 ticks, about 7.6 s,
then plays the 7 movement frames: a long pause, then a glance); a sheet with `play`/`hold`
plays those frames once and stays on the hold frame. Under `prefers-reduced-motion` the
portrait shows one still key frame (the hold frame where one exists, else the first) and
never advances. Only the shown guide's portrait animates; switching guides restarts the
animation for the new guide in the current state. When a guide has no sheet, the labelled
placeholder box is shown instead.

## Accessibility checklist

Checked in a Chromium-based browser in stub mode on Sat 2026-10-10 (evening, MDT), then
again after an adversarial review the same night, which fixed the items marked "fixed".

| Check | Result | How |
|---|---|---|
| No console errors | Pass | Console read after load, three runs (the three demo acts), tab switches, and the ionq / error / none / reduce scenarios; the only error-level messages are the deliberate ones from the failing stand-in and the missing-backend path, which the page also shows. |
| Scene renders and follows the data | Pass | Screenshots after act 1 (49.7 / 50.3 %), act 2 (100 / 0 % with the ghost labelled "previous 49.7 %"), act 3 (w = 1: thick bright bridge, capacity 0.007, interval 0.000–0.099, "No resolved influence at this shot count."). |
| Everything on the canvas exists as text | Pass | Futures cards (p and counts), the three readings, the scene caption, the canvas `aria-label` (rewritten per run), the chart summary + data table, the four count tables. |
| Persona tabs by keyboard | Pass | Focus on "The Self", ArrowRight moves focus and selection to the Demon (comparison table shown), ArrowRight again to the Observer; Home/End supported. The persona line is rewritten 600 ms after the last change, so arrowing announces one line. |
| One job, clicked three times | Pass | IonQ-shaped stand-in: three programmatic clicks in one tick gave one job; the lock note received focus and says the job was used. |
| Failure path | Pass | Failing stand-in: visible error note with the job evidence; Run stays usable; readings still say "No run yet". |
| Missing backend | Pass | `?backend=none`: badge says profile unavailable, forecast and curves still work, Run allows one press. |
| Every control has a label | Pass | `<label for>` on every input/select (also a test); range inputs carry `aria-valuetext` in radians and degrees. |
| Live regions | Pass | Only the status line and the persona line are live (also a test). |
| Visible focus | Pass (by inspection) | 3 px yellow `:focus-visible` outline on every interactive element (12:1 on navy). |
| Text contrast ≥ 4.5:1 | Pass | Computed from the CSS variables in `tests/test_ui_static.py`: body text 16:1, muted 9:1+, teal and amber 11:1+ on every surface, dark text on the teal button 9:1, note colours 8:1+. Non-text (focus ring, borders, chart strokes) ≥ 3:1. |
| Reduced motion | Pass | `?reduce=1`: the Motion box starts unchecked with an explanation; after a run the canvas pixels were identical 0.7 s apart (no transition, no particle flow). The CSS rule that removes transitions under the media query is verified by inspection only (the JS switch cannot change what CSS sees). Fixed: when the OS preference changes back to "no preference" the checkbox and the scene now agree. |
| WebGL unavailable | Pass (fixed) | `?nowebgl=1`: a text note replaces the canvas, the Motion box is disabled and says why, Run still works and the futures, readings, chart and caption ("it would show ...") populate. A lost context later (`WEBGL_lose_context`) also falls back to text. |
| Canvas text alternative is accurate | Pass (fixed) | The canvas `aria-label` used to call Future 0 the left sphere and Future 1 the right one; both sit on the right (Future 1 upper, Future 0 lower) and the label now says so. |
| Narrow chart labels | Pass (fixed) | At 360 px the value labels of neighbouring bars touched ("50.7%50.0%"); they now alternate in height on narrow charts. |
| Failure evidence | Pass (fixed) | The error view said "a submission may have been attempted" whenever `job_id` was null, even when nothing reached the backend. It now reads the submission markers (`n_circuits` / `submitted_as`, written just before the call; `job_returned` just after) and, after an earlier successful run, recognises stale job evidence instead of attributing it to the failed attempt. |
| 360 px wide | Pass | Viewport 360 × 780 with every `details` open after a run: `scrollWidth` = 360, no element past the right edge except table cells inside their keyboard-focusable scroll regions; all six scene labels measured inside the canvas. |
| Keyboard walk | Pass | From the Self tab, Tab visits the panel, the three sliders, Job settings, Run, Motion and the two details summaries in visual order; every stop matched `:focus-visible` with the 3 px outline (computed style read at each stop). Arrow keys move the sliders; Home/End/arrows move the persona tabs. |
| Performance | Pass | 100 instanced nodes, 188 link segments, 520 points, five tubes: about 60 frames/s with motion on; the per-frame loop allocates nothing (tube geometry is rebuilt only when its pixel width or the scale changes, and the old buffers are released); the JS heap did not grow over a 5 s sample. The loop idles when motion is off and nothing animates, and disposes the renderer if the canvas leaves the document. |
| 200 % zoom | Pass | Emulated as a 640 × 400 viewport: single column, no horizontal scroll. |
| axe-core 4.10.2 | 0 violations | Run on `#fwo-app` after a run with every `details` open; 1 item "needs review" (a contrast cell axe could not resolve). Not re-run after the review (the changes were text, chart label positions and scene plumbing). |
| Contract conformance | Pass | `tests/test_ui_static.py` calls the live `profile_json`, `predict_json`, `run_json` and `curves_json` and asserts every field path the JS reads (and the evidence fields of a failed run) exists with that exact name. |
| Nothing hover-only | Pass (by inspection) | No tooltips; every label is always visible. |

Not verified: screen readers (VoiceOver, NVDA), the page inside Qollab itself (Pyodide, the
CommonJS transform, three.js from Qollab's import map), and a real IonQ job.

## Known limits

- Not yet run inside Qollab. A test parses `main.js` as an async function body with imports
  rewritten to `await require(...)`, which is how Qollab runs it, but the import map entry
  for `three` (0.186.1) is taken from the platform notes, not observed.
- WebGL is required for the scene; without it the page shows a text fallback and every
  number is still in the readings and tables.
- The scene's thickness-in-pixels mapping is exact at the depth of the branches (z = 0);
  perspective makes parts of a tube nearer or farther by a few per cent.
- The overlay labels on the canvas are `aria-hidden` (the data lives in the futures cards and
  the canvas label), so a screen reader hears each number once.
- The persona line (`aria-live="polite"`) is written once per completed run and also, debounced
  600 ms, when the persona tab changes, so the line on screen never names the wrong persona and
  a keyboard user arrowing through the tabs hears one line. Drop `schedulePoetic()` from the tab
  `onChange` in `main.js` to announce strictly once per run.
- The brain sways gently (±4°) only while Motion is on; it is the same sway on every run and never
  follows the data. The ghost tubes share the live tubes' path, so a ghost branch is visible only
  where the previous run's branch was thicker than the current one.
- In stub mode, settings without canned data are synthesized in JS; the persona lines are then
  borrowed from the nearest canned run and marked as such.
