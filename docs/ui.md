# The JavaScript UI shell

A browser UI for the Qollab project, built around the CHSH reference experiment.
The components are generic (backend badge, one-job Run button, claim card, noise dial,
precomputed-curve chart), so the team can swap in its chosen experiment later.

Simulators compute what quantum theory predicts, and how a noise model degrades it.
They do not test nature, and the UI says so next to every result.

This effort is supported by Qollab & IonQ

## Files

| File | Uploaded? | Role |
|---|---|---|
| `qollab_project/index.html` | yes | Body fragment: header, backend badge, status line, Run panel, Result, noise dial, chart, footer with the attribution line. No scripts, no `on*` attributes, no inline styles. |
| `qollab_project/main.css` | yes | The only stylesheet. Every selector is scoped under `#qh-app`. Colors are CSS variables on `#qh-app`. |
| `qollab_project/main.js` | yes | Entry point. Waits for the DOM, wires the components, calls Python, ends with `await new Promise(() => {})`. |
| `qollab_project/ui/dom.js` | yes | Helpers: `whenMounted`, `h`/`svg` element builders (text only, never `innerHTML`), number formatting, z-score text, a debounce that needs only `setTimeout`, accessible tables. |
| `qollab_project/ui/experiment.js` | yes | **Everything CHSH-specific**: labels, dial presets, chart descriptions, text summaries, data-table columns. |
| `qollab_project/ui/badge.js` | yes | Backend badge. |
| `qollab_project/ui/card.js` | yes | Claim-card component and run-error view. |
| `qollab_project/ui/dial.js` | yes | Noise dial (preset select, sliders, gauge, plain-language reading). |
| `qollab_project/ui/chart.js` | yes | Hand-rolled SVG line chart and legend (no external libraries). |
| `qollab_project/ui_api.py` | yes | The Python side: JSON strings in, JSON strings out. |
| `dev/index.html`, `dev/boot.js`, `dev/stub_api.js`, `dev/stub_data.js` | no | Stub mode for local testing. |
| `tools/make_ui_stubs.py` | no | Regenerates `dev/stub_data.js` from the real `ui_api` functions. |
| `tests/test_ui_api.py` | no | Tests for `ui_api` and static checks on the JS shell. |

The `ui/` modules import nothing. `main.js` imports them and passes in the helpers
(`makeExperiment(dom)`, `renderCard(dom, ...)`), so they behave the same under Qollab's
CommonJS loader and as native ES modules in stub mode.

## How it fits Qollab's JS runtime

- `index.html` is injected with `innerHTML`, possibly after `main.js` starts:
  `whenMounted("qh-app", setTimeout, 60000)` polls every 25 ms (up to 60 s) before binding.
- `main.js` runs as the body of an async function with `backend`, `console` and
  `setTimeout` injected. It uses only static imports at the top, no `import.meta`, no
  dynamic `import()`, only `console.log`/`console.error` with strings, and only
  `setTimeout` (the debounce never needs `clearTimeout`).
- Python is imported by name, `import * as api from "ui_api"`, and every call is
  `await api.fn.callPromising(...)`; the reply is parsed with `JSON.parse(String(ret))`.
  The injected `backend` is passed straight through as an argument.
- IonQ allows one job per run and routes requests only while `main.js` is alive, so the
  file ends with `await new Promise(() => {})`.
- A missing `backend` (not injected, `null` or `undefined`) is caught in `main.js` before
  any Python call; the badge says the profile is unavailable and Python is never asked to
  run a job. A reply that is not a JSON object becomes `{error}`.
- A failure while loading the dial or the chart is reported in the status line and does
  not leave Run disabled; a failure while drawing a result is reported the same way.
- No external scripts, fonts, popups, alerts, downloads or storage.

## Python bridge (`ui_api.py`)

Every function returns `json.dumps` of a plain dict, strict JSON (NaN and infinity become
`null`). Nothing raises to JavaScript: failures come back as `{"error": "..."}`. A JS `null`
or `undefined` argument (Pyodide's `jsnull` or `None`) counts as missing.

| Function | Returns |
|---|---|
| `profile_json(backend, new_run=False)` | `qk_runtime.backend_profile` plus `preferred_mode`, `simulator`, `run_allowed`, `job_policy` (a sentence for the badge) and `sim_note`. `main.js` passes `new_run=true` once, at page load: that starts a fresh one-job count, so an interpreter reused across Qollab runs cannot refuse the new run's job. Nothing else passes it. |
| `noise_dial_json(params_json)` | Exact CHSH under a `NoiseSpec` from `{"p1","p2","r01","r10","scale","preset"}`; preset is `custom`, `ionq_forte_like` or `ionq_forte_like_spam` (presets use `qk_noise.ionq_forte_like(spam, scale)`). Returns `S`, per-term `E`, per-term outcome distributions, `classical_bound` 2, `quantum_ideal` 2&radic;2, `exceeds`, shots per setting for a 3-standard-error margin, a one-sentence `reading`, the effective rates and `elapsed_ms`. The four circuits are built once and reused; a call takes a few milliseconds under CPython. |
| `run_chsh_json(backend, shots, mode, mitigate)` | ONE job through `chsh.run` (after `qk_runtime.begin_run()`): the claim card, `mitigation_note`, canary report, per-term `E`, layout summary, job evidence. On a one-job backend a second call in the same run is refused before anything is submitted. On failure: `error`, `job_submitted` (a submission was attempted) and `job.job_returned` (the backend returned a job object), so the page never claims more than it knows. |
| `curve_json()` | Compact series from `data/chsh_noise.json` (S vs p2, &lambda;*) and `data/chsh_ionq_like.json` (S vs scale, crossing scale), the error-bar coverage rows from `data/chsh_coverage.json`, the qiskit-aer cross-check from `data/chsh_aer_check.json`, and provenance. Each file is opened by a literal relative path; if a file cannot be read, the curve is computed in the session and labelled as such. |
| `card_text_json(card_json)` | `qk_cards.card_text` (ASCII, also printed to the console) and `card_markdown`. |

## What the page shows

- **Header**: a project-title placeholder (`#qh-title`) and a one-paragraph description.
- **Backend badge**: name, simulator or hardware, ideal or noisy, local or remote,
  one job per run or no job limit, qubit ceiling, and the job policy in words.
- **Status line** (`role="status"`, `aria-live="polite"`): every step, including errors.
- **Run panel**: shots per setting (1 to 100,000), packing mode (auto, tile, list),
  readout mitigation checkbox, and the Run button. On a one-job backend the button is
  disabled after one press for the rest of the page load, and a visible note (which
  receives focus) says why. On local simulators it stays usable; while a job runs it is
  marked `aria-disabled` so keyboard focus is not lost.
- **Result**: the simulator-honesty note, then the claim card: verdict as text with a
  shape symbol, the verdict basis and rule, claim, assumptions, witness and bound,
  quantum ideal, raw and mitigated values with standard error and z, backend and shots,
  "What this does NOT show", counterarguments, a diagnostics section (per-setting
  correlations, canary, layout, job) and the plain-text card.
- **Noise dial**: preset select; custom mode has sliders for the two-qubit depolarizing
  strength p2 (0 to 0.35) and a symmetric readout flip probability (0 to 15%); the
  IonQ-like presets have a scale slider (0 to 80 times the published rates). Calls are
  debounced (120 ms) and only the newest answer is shown. Output: predicted S, a text
  badge (above / at or below the bound), a gauge with ticks at 2 and 2&radic;2, the
  plain-language reading in an `aria-live="polite"` region, effective rates, the preset
  note, and a table of per-setting correlations and outcome probabilities. The number,
  badge and gauge follow the slider at once; the reading is written only after the dial
  has been still for 900 ms, so a screen reader hears one sentence when the user stops,
  not one per arrow-key step. Each slider announces its own value through
  `aria-valuetext`; the visible value next to its label is `aria-hidden` (an `<output>`
  element would be a second, implicit live region).
- **Precomputed curve**: radio buttons choose S vs p2 or S vs IonQ-like scale (changing
  the dial preset switches the chart to the matching curve). The SVG has a title and a
  description; below it are a text summary, a legend, the full data table in a
  `details` element, the validation numbers, and provenance (generator, commit, the
  class of machine, creation time). The dial's current setting is drawn as a diamond.
- **Footer**: "This effort is supported by Qollab & IonQ".

## Stub mode (local testing)

Stub mode runs the unchanged `main.js` in an ordinary browser, with `ui_api` replaced by
`dev/stub_api.js` through an import map and `backend` replaced by a stand-in object.
`dev/boot.js` starts `main.js` first and injects `index.html` with `innerHTML` 300 ms
later, so the `whenMounted` polling is exercised the way Qollab would.

1. Regenerate the canned data whenever `ui_api.py` or the data files change:

   ```
   .venv/bin/python tools/make_ui_stubs.py
   ```

   It calls the real `ui_api` functions under CPython: profiles and one run each on a
   seeded BasicSimulator, a readout-flip wrapper around it (so the card shows a
   mitigated value), an IonQ-shaped wrapper (one job per run, but it runs on the local
   ideal simulator) and a backend whose submission fails; 105 noise-dial points
   (`stub_api.js` interpolates between them and marks interpolated readings
   "[stub: interpolated]"); and `curve_json()`.

2. Serve the repository root on your machine's loopback interface only, for example
   `.venv/bin/python -m http.server 8700 --bind <loopback address>`, and open
   `/dev/index.html` on that server.

3. Query parameters: `?backend=basic|readout|ionq|error|none` picks the stand-in (`none`
   leaves `backend` undefined, to check the missing-backend path),
   `&mount=1500` delays the HTML injection, `&slow=3` slows every stub call, and
   `&axe=1` loads axe-core from cdn.jsdelivr.net (stub mode only, never in
   `qollab_project/`) and prints its report under the page and to the console.

In stub mode the canned run ignores the shots and mode you enter (the console says so).

## Accessibility checklist

Checked in a Chromium-based browser in stub mode on Fri 2026-10-09 (MDT), then again after an
adversarial review on Sat 2026-10-10, which fixed the items marked "fixed".

| Check | Result | How |
|---|---|---|
| No console errors | Pass | Console read after load, dial changes and runs in all four scenarios, including with the HTML injected 1.5 s after `main.js` starts. The only error messages are the deliberate ones from the failing stand-in, which the page also shows. |
| Noise dial updates | Pass | Slider moved by keyboard: p2 = 0.100 gives S = 2.546 (2&radic;2 &times; 0.9). With the IonQ-like + readout preset, End takes the scale to 80&times; and gives S = 0.065, the "at or below" badge and a hatched gauge; the chart switches to the matching curve. |
| Run produces a card | Pass | Ideal, readout-flip (raw 2.390, mitigated 2.822), one-job and failing stand-ins. The failing stand-in's card says a submission was attempted but no job came back (fixed: it used to say a job was submitted). |
| One job, clicked twice quickly | Pass | One-job stand-in: a real double-click, then three more programmatic clicks, then Space pressed three times on a fresh load: one stub job each time. All guards run before the handler's first `await` (also a test). |
| Keyboard-only operation | Pass, with one gap | Tab order follows the visual order (shots, mode, mitigation, Run, preset, sliders, details, curve radios, details). Enter and Space both press Run; arrow keys and End move sliders. The native select's popup could not be driven by synthetic keys in the test browser, so preset changes were tested through the change event; the select is a native control. |
| Visible focus | Pass | 3 px `:focus-visible` outline in the accent color (6.7:1 on white) on every interactive element, including summaries, scrollable regions and the lock note that receives focus. |
| Every control has a label | Pass | `<label for>` or a wrapping label for every input and select (also a test). Range inputs carry `aria-valuetext` (for example "p2 = 0.030"). |
| aria-live behaviour | Pass (fixed) | Only the status line and the dial reading are live (also a test). Before the fix, six arrow-key steps 250 ms apart rewrote the reading six times and each slider's `<output>` (an implicit live region) announced every step. Now the same steps write the reading once, 900 ms after the last step (measured with a MutationObserver, and in a node test of `dial.js` on a virtual clock). |
| Text contrast &ge; 4.5:1 | Pass | Computed from the CSS color variables (also a test): body text 17.8:1, muted text 7.9 to 8.5:1, white on the accent button 6.7:1, verdict and note text 7.6 to 8.1:1 on their tints, chart text 17.8:1. Non-text: control borders 4.5 to 4.8:1, focus ring 6.7:1, chart lines 5.0 to 7.1:1. |
| No color-only signals | Pass | Verdicts are text plus a shape (&#9650; / &#9632; / &#9679;); the dial badge says "above" or "at or below"; the gauge is hatched below the bound; chart lines differ by dash pattern and are named in the legend; markers differ by shape; error states also say so in words. |
| Charts have text alternatives | Pass | SVG `role="img"` with `<title>` and `<desc>`; a visible summary sentence; the full data table in `details`. Fixed: y-axis ticks on a 0.25 step printed 2.75 as "2.8" and 2.25 as "2.3"; ticks now print every value exactly (also a test). |
| Chart labels | Pass (fixed) | On a narrow chart the "S = 2" label sat on the &lambda;* marker. Each reference-line label now goes to the end of the plot where the curve is far from that line (also a test). |
| prefers-reduced-motion | Pass (by inspection) | The only motion is a 180 ms gauge-width transition, removed under `prefers-reduced-motion: reduce` (rule confirmed in the loaded stylesheet; the test browser could not emulate the preference itself). |
| 320 and 360 px wide | Pass | Viewport emulated at 320 &times; 780 (and earlier 360 &times; 780) with every `details` open and a card shown: no horizontal page scroll and no element past the right edge; wide tables scroll inside keyboard-focusable regions; the chart is redrawn at the container's pixel width. |
| 200% zoom | Pass | Emulated as a 640 &times; 400 viewport (a 1280 px window at 200%): one column, no horizontal scroll. |
| axe-core 4.10.2 | 0 violations | Run on `#qh-app` with the readout-flip card shown and every `details` open, after the fixes. "Needs review" items are color-contrast cells whose background axe could not resolve inside scroll boxes (their backgrounds are the white and light-gray colors above). |

Not verified: screen readers (VoiceOver, NVDA) and the page inside Qollab itself.

## Swapping CHSH for another experiment

1. **Python**: write the experiment module (like `chsh.py`: circuits, `exact(noise)`,
   `run(backend, ...)` returning a claim card). In `ui_api.py`, point
   `noise_dial_json` at its exact model (replace `_circuits`/`_exact_terms` and the
   reading sentence), `run_chsh_json` at its `run` (keep the name, or rename it and the
   call in `main.js`), and `curve_json` at its precomputed data files, each opened by a
   literal path. Keep the JSON shapes: `S`/`exceeds`/`reading`/`terms` for the dial,
   `card` plus diagnostics for a run, `x`/`S` series for curves.
2. **`ui/experiment.js`**: change the labels, the bound and ideal, the outcome columns,
   the dial presets (which slider fields each shows and which curve matches), the chart
   titles, axis labels, markers, summaries and table rows.
3. **`index.html`**: change the title, the description, the slider ranges and labels,
   and the gauge ticks (their positions are CSS classes `qh-at-bound`/`qh-at-ideal` in
   `main.css`, as percentages of `gaugeMax`).
4. **Tests and stubs**: update the CHSH numbers in `tests/test_ui_api.py`, then rerun
   `tools/make_ui_stubs.py` and check the page in stub mode.

The badge, Run button, claim card, dial plumbing and chart need no changes: they read only
the card fields, the JSON shapes above and `experiment.js`.

## Known limits

- Not yet run inside Qollab. The runtime facts above come from Qollab's documentation
  and source; stub mode checks the page logic, not Pyodide or the CommonJS transform. A
  test parses `main.js` as an async function body with imports rewritten to
  `await require(...)`, which is how Qollab runs it.
- Whether Qollab ships the data files to a JS project when only `ui_api.py` names them
  is untested; if it does not, `curve_json` computes the two curves in the session and
  says so, and the validation section reports the data as unavailable.
- The IonQ-like preset approximates IonQ's published noise model on this project's gates
  (see `qk_noise.IONQ_PRESET_NOTE`, shown under the dial).
- On a one-job backend, Run stays locked after one press even when Python reports that
  no job reached the backend: the conservative choice. The lock note says which case it was.
- Stub mode only: the readout-flip stand-in profiles as a local basic simulator, so its
  badge says "ideal (no noise)" even though its counts carry readout flips.
