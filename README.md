# The Free Will Observatory

> **This effort is supported by Qollab & IonQ**

*A fictional instrument for exploring the capacity to reshape possible futures.*

**In one sentence:** a single-page, brain-shaped graph where three personas investigate one
two-qubit Self through fresh simulator experiments, visible changes in probability, and a
transparent model of agency.

You set an **Intention**, press **Run experiment**, and watch the distribution of the Self's
two possible futures move. Turn up the **World coupling** and the future stays just as
uncertain, but your intention stops moving it. **The same 50/50 outcome is high-capacity in
one setting and zero-capacity in another.** Three personas (The Self, Laplace's Demon, The
Observer) read the same data differently. Every number on the page comes from one freshly
submitted simulator job of four two-qubit Qiskit circuits, and every reading has an exact
definition, a closed-form prediction and a conservative error bar.

> **Honesty, first.** The correspondence between controls and words is *designed, not
> discovered*. Simulators compute what quantum theory predicts (and how a noise model
> degrades it); they do not test nature. The readings are a fictional model, not a
> measurement of free will, not neuroscience, and not proof of agency: a responsive
> classical model scores just as high. See [Honesty](#honesty-what-this-is-and-is-not).

| Judging trait | Where to look |
|---|---|
| Novelty & creativity | [What it does](#what-it-does), [The question](#the-question), [Beyond the tutorial](#beyond-the-tutorial) |
| Technical execution | [How to run on Qollab](#how-to-run-on-qollab), [The model](#the-model), [Validation](#validation-measured), the test suite ([Replicate & extend](#replicate--extend)) |
| Impact potential | [Beyond the tutorial](#beyond-the-tutorial), [Replicate & extend](#replicate--extend) |
| Documentation quality | This page, [docs/model.md](docs/model.md), [docs/claims.md](docs/claims.md), [BUILDLOG.md](BUILDLOG.md), [CREDITS.md](CREDITS.md) |

**Links:** Qollab project: TODO(captain). Demo video (2–3 min, public link): TODO(captain).
Source: TODO(captain).

---

## What it does

**The scene.** A brain-shaped graph (two fixed lobes; the decorative nodes are *not* qubits)
holds one fictional Self. Two branches leave it, **Future 0** and **Future 1**, sized by the
measured probabilities of the last run. A **World bridge** rises from a second qubit, the
World, into the Self; its width and opacity follow the measured Connection reading. The
previous run stays as a dashed outline, so a change is a comparison, never a flourish. The
picture's sizes and weights change only when a fresh job returns; the slow drift, the particle
flow and the bridge's shimmer are decoration, off under reduced motion or with the Motion box
unticked.

**Four page styles.** The page opens in style D (blueprint, light); the Style button at the end
of the hackathon line opens a side panel to switch to A (night observatory), B (instrument
console) or C (luminous anatomy). Each style draws the same data in its own way.

**Three personas, one data set.** Switching persona changes the explanation, never the data.
Each guide speaks in an RPG-style dialogue box, and only about what it can see; a short
opening scene introduces them.

| Persona | What they do | What it reveals |
|---|---|---|
| **The Self** | Changes the Intention and presses *Run experiment*. | The current future distribution, plus the Capacity available under opposite intentions. |
| **Laplace's Demon** | Forecasts the chosen settings before the job returns. | The closed-form prediction next to the fresh sample, plus two labelled classical baselines (fixed output: Capacity 0, Openness 0; fair coin: Capacity 0, Openness 1). |
| **The Observer** | Changes the Perspective and reruns. | A different observable for the same prepared state. Capacity stays comparable because its two probes share the readout. |

**Three controls** (angles in radians; see [The model](#the-model)):

| Control | What it is in the circuit | Range (default) |
|---|---|---|
| Intention | a phase φ on the Self: `RZ(φ)` | 0 to 2π (π/2) |
| World coupling | a slider w; γ = w·π/2; a controlled-`RY(2γ)` from Self to World | 0 to 1 (0) |
| Perspective | the equatorial readout angle β: `RZ(−β)`, `H`, measure Z | 0 to π (0) |

**Three readings**, each computed from raw counts, never from the animation:

| Reading | Question it answers | Definition | Range |
|---|---|---|---|
| **Capacity C** | How far can opposite intentions move P(Self = 1)? | \|p_high − p_low\| from the two intent probes, with a conservative 95% interval | 0 to 1 |
| **Openness O** | How uncertain is the current Self outcome? | binary entropy of the display P(Self = 1) | 0 to 1 bit |
| **Connection I** | How much does a reference World measurement reveal about the Self? | mutual information of the separate connection probe | 0 to 1 bit |

Under the scene: the three readings, a before/after probability chart, one factual sentence
plus one line in the persona's voice, and a **How this works** drawer with the circuit, the
four probes' counts, the job record and the formulas.

## The question

Is uncertainty the same thing as freedom? This project gives the fiction a precise rule and
lets you test it. *Free will, here, is defined as the capacity to reshape possible futures:*
the Self has a distribution of outcomes, an intention is a control input that can redirect
that distribution, and freedom within the model is the **range of redistribution** available
to that input. One surprising outcome is never enough; the model asks whether an
intervention changes the odds across repeated experiments.

**The central result.** Two situations both look 50/50:

| Setting | P(Self = 1) | Openness | Capacity (ideal) | The model's verdict |
|---|---|---|---|---|
| no coupling (w = 0), intention π/2 | 0.5 | 1 bit | **1.0** (intentions sweep 0% → 100%) | high-capacity |
| full coupling (w = 1), *any* intention | 0.5 | 1 bit | **0.0** (every allowed intention gives 50/50) | low-capacity |

In the model, uncertainty alone is not freedom. The ideal Capacity is cos γ: it falls from 1
to 0 as the World records which alternative the Self took, while the Self's own odds never
leave 50/50. That contrast is the whole show, and it reproduces to floating-point rounding
([Validation](#validation-measured)).

## How to run on Qollab

Open the project on Qollab, keep the **built-in simulator** in the Run dialog, press
**Run**, then use the page: choose a persona, move the three sliders, press **Run
experiment**. The first run on the defaults (Intention π/2, coupling 0, perspective 0,
1,024 shots per probe) is Act 1 of the demo.

| Entry | Files | What you get |
|---|---|---|
| **JS page (the submission)** | top-level `index.html` (a body fragment) + `main.js` + `main.css` + `ui/*.js`, with `observatory.py`, `observatory_api.py`, the `qk_*.py` toolkit and `data/*.json` | Qollab runs the JS entry whenever both top-level `index.html` and `main.js` exist. The page uses only the injected `backend`, our Python modules (`import * as api from "observatory_api"`, JSON strings both ways) and three.js from Qollab's import map. Nothing runs outside the browser: no server, no polling API, no API keys, no bundler. |
| **Python console (fallback)** | `main.py` + the same Python modules and data | Used only when the JS entry files are absent (`tools/pack_for_qollab.py --entry python` leaves them out). Qollab's Run-settings form shows `main()`'s parameters: `intention_deg` (90), `world_coupling` (0), `perspective_deg` (0), `shots_per_probe` (1024), `persona` (`self`). Output: backend profile, the Demon's forecast, one run's four count tables, the three readings with the interval, the explanation, the baselines. |

Build either upload with `tools/pack_for_qollab.py --entry js` or `--entry python`; see
[SUBMIT.md](SUBMIT.md).

**Backends** (Qollab's Run dialog):

| Backend | Kind | Notes |
|---|---|---|
| Built-in simulator | ideal, local | Qiskit `BasicSimulator`, 24 qubits. **Free and local: the backend judges press Run on.** |
| AWS Braket local | ideal, local | 25 qubits |
| IBM noise models | noisy, local (in the browser) | circuits are transpiled first; `mode=auto` sends the three canary blocks and four probes as one list job of 7 small circuits |
| IonQ Forte 1 / Forte Enterprise 1 (simulator) | noisy, remote | 29 qubits, **one job per run**; the four probes and the canaries travel in that one job |

**One job per run.** Each press of *Run experiment* submits exactly one `backend.run(...)`
holding all four probes (`display`, `intent_low`, `intent_high`, `connection`) plus two
canary checks: an orientation block (prepared `110`, a key that is not a palindrome, so a
reversed bit order is diagnosed rather than absorbed) and a readout calibration (flip rates
P(1|0) and P(0|1), reported, not corrected). With `mode=auto` the probes are tiled side by
side on disjoint qubits of **one 17-qubit circuit** (8 qubits for the probes, 9 for the
canaries) on one-job backends and on the built-in simulator, and sent as one list job on the
in-browser noise models. A guard in `qk_runtime.run_once` refuses a second submission on a
one-job backend before anything reaches the provider (verified: the second call returns
`status: failed` with the guard's message and the job count stays at 1).

**Shots.** 1,024 per probe by default (4,096 sampled circuit executions per click), capped
at 4,096 per probe. The metrics use the shots actually seen per probe (IonQ's noisy
simulators report counts as round(probability × shots), so totals can differ slightly).

**Run settings** (JS page and Python entry alike): `intention_rad` [0, 2π],
`world_coupling` [0, 1], `perspective_rad` [0, π], `shots_per_probe` [1, 4096], `persona`
(`self` / `demon` / `observer`), `mode` (`auto` / `tile` / `list`), `canary` (bool).
Out-of-range or ill-typed values (beyond a 10⁻⁹ rounding allowance at the upper limits)
return a visible *failed* result before any job is submitted; old counts are never
substituted for a live run.

## The model

Self = q0, World = q1, both start in |0⟩. The circuit, in order:

```
prepare |00>
H(Self)                                   # creates the alternatives
RZ(phi, Self)                             # Intention: how the alternatives recombine
controlled-RY(2*gamma, Self -> World)     # World coupling: RY(g) CX RY(-g) CX on the target
RZ(-beta, Self); H(Self)                  # Perspective: an equatorial readout direction
measure Self and World                    # the connection probe skips RZ(-beta)/H: Z on both
```

Before readout, up to a global phase and with the ket order Self, World:

```
[ |00> + e^{i phi} cos(gamma) |10> + e^{i phi} sin(gamma) |11> ] / sqrt(2)
```

The World can keep which-alternative information, which reduces the interference visible
in the Self alone. This is coherent coupling, not a noise slider.

**Ideal display probability:** `P(Self = 1) = [1 − cos(γ) · cos(φ − β)] / 2`, so the intent
probes (φ = β and φ = β + π) give p_low = (1 − cos γ)/2 and p_high = (1 + cos γ)/2, and the
**ideal Capacity is C = cos γ**: 1 at w = 0, 0.7071 at w = 0.5 (p_low/p_high =
0.1464/0.8536), 0 at w = 1. The controlled rotation uses the standard `RY`/`CX`/`RY`/`CX`
decomposition of Qiskit's `CRYGate` (see its API reference), so IonQ's compiler takes it
unchanged.

| Probe | Settings | Purpose |
|---|---|---|
| `display` | user φ, γ, β; full circuit | drives the visible future distribution and Openness |
| `intent_low` | φ = β; same γ, β | one end of the accessible probability range |
| `intent_high` | φ = β + π; same γ, β | the opposite end |
| `connection` | user φ, γ; no final `RZ(−β)`/`H`; Z on both qubits | shared information in a fixed reference basis (Connection) |

**Readings.** C = |p_high − p_low| (the total variation distance between the two binary
Self distributions). O = −p·log₂p − (1−p)·log₂(1−p) with 0·log₂0 = 0, on the display p.
I = Σ p(s,w)·log₂[p(s,w) / (p(s)·p(w))] over the connection probe's counts only (classical
mutual information in one basis, not an entanglement witness). Capacity is never estimated
from history entries with different coupling or readout.

**Uncertainty (Hoeffding 1963 + a union bound).** For N_low and N_high shots, the signed
difference d = p_high − p_low has the conservative 95% interval d ± e, clipped to [−1, 1],
with e = √(ln 80 / (2·N_low)) + √(ln 80 / (2·N_high)). Mapped through |·| it gives the
interval for C: if it spans zero, the lower limit is 0 and the upper limit is the largest
endpoint magnitude. At 1,024 shots per probe, **e = 0.0925**. A result is **resolved** only
when the interval excludes zero; otherwise the page says *"No resolved influence at this
shot count"* and never describes a small positive estimate as proven agency.

**Bit order.** The app uses **SelfWorld**: `10` means Self = 1, World = 0. Qiskit writes
clbit 0 rightmost, so a probe measured as [Self = q0, World = q1] comes back as WorldSelf
and is reversed **once**, at the adapter boundary (`observatory.canonical_counts`). The
test: flip q0 only and the app outcome must be `10` with certainty.

The derivation, the probe and reading tables, the Hoeffding argument and the limits are in
**[docs/model.md](docs/model.md)**. Every claim is a card in **[docs/claims.md](docs/claims.md)**.

## Honesty: what this is and is not

From the explanation drawer, in the team's own words:

> We define free will here as the capacity to reshape possible futures. In this fictional
> observatory, an intention becomes a quantum phase, the World becomes a coupled system, and
> a perspective becomes a measurement choice. Live simulations reveal how these controls
> change a distribution of outcomes. The measurements are real outputs of the simulator; the
> Self and its philosophical meaning are our artistic construction.

- **Designed, not discovered.** Phase is called *intention* because varying it changes
  interference; coupling is called *World coupling* because it wires the Self to a second
  qubit that records which alternative it took (the World never pushes the Self toward a
  future; its record only reduces the interference the Self can use); the readout angle is
  called *perspective* because it changes the measured observable. Each metaphor points to
  an inspectable operation. In the ideal state Capacity = cos γ is the Self's interference
  visibility and the World's distinguishability is sin γ, with C² + D² = 1: the slider rides
  the wave–particle duality relation ([docs/model.md](docs/model.md) §2).
- **Users supply the intention.** Version one has no autonomous learning or goals.
- **Specific to the chosen controls:** phase changes on the Self, fixed coupling, the
  specified readout. Joint control of Self and World could undo their coupling.
- **Not a universal property of the state, not a neuroscience model, and not evidence that
  quantum systems alone can be agents.** A responsive classical model (a bit set by a
  switch) also scores Capacity 1.
- **Simulators compute predictions.** A simulator computes what quantum theory predicts and
  how a noise model degrades it; it does not test nature. No result here is evidence about
  the physical world.
- **The readings stay separate.** They are never averaged into a "free will percentage". A
  Capacity shown as a percentage is labelled *Capacity in this model*.
- **Connection** is measured information in a reference basis, not an entanglement
  certification; a classical copy of the Self bit into the World scores the same.
- **"Not resolved" is not "zero".** An interval that includes zero is absence of evidence at
  this shot count.

## Validation (measured)

All numbers below were produced by the code in this repository under CPython 3.14.4 with
qiskit 2.5.2 and numpy 2.5.3. Sampled runs use Qiskit's `BasicSimulator` with
`set_options(seed_simulator=11)` unless another seed is named; 1,024 shots per probe,
`mode=auto` (one 17-qubit tiled circuit), canaries on. Seeds make the tables reproducible;
on Qollab the samples are fresh each run.

**Exact checks** (`qiskit.quantum_info`, no sampling):

| Check | Result |
|---|---|
| Closed form vs exact statevector over a grid of 13 φ × 9 w × 7 β = 819 settings | max \|error\| in P(Self = 1): 3.3×10⁻¹⁶; in p_low / p_high: 1.1×10⁻¹⁶; in Capacity vs cos γ: 1.7×10⁻¹⁶; in Connection vs h(sin²γ/2) − ½h(sin²γ): 3.3×10⁻¹⁶ |
| State before readout vs the expression above (connection circuit, up to a global phase, 35 (φ, w) points) | max \|amplitude difference\| 1.6×10⁻¹⁶ |
| `RY(γ)·CX·RY(−γ)·CX` block vs Qiskit's `CRYGate(2γ)` (25 values of γ) | max \|matrix element difference\| 1.6×10⁻¹⁶ |
| Bit order: flip q0 only, through the real packing and `canonical_counts` path (256 shots) | Qiskit key `01` → app outcome `10` for 256/256 shots; orientation canary passed |
| Perspective: β = 0 vs β = 1.0 rad at φ = π/2, w = 0.5 | ideal P(Self = 1) 0.5000 vs 0.2025; ideal Capacity cos γ = 0.7071 for both |

**Sampled runs** (one job each):

| Run | P(Self = 1) | p_low / p_high | Capacity [95% interval] | Resolved | Openness | Connection |
|---|---|---|---|---|---|---|
| Act 1: w = 0, φ = π/2, β = 0 | 0.485 (ideal 0.5) | 0/1024 / 1024/1024 | **1.0000 [0.9075, 1.0000]** | yes | 0.999 bits | 0.000 bits |
| Act 2: w = 0, φ = π, β = 0 | 1.000 | 0.0000 / 1.0000 | 1.0000 [0.9075, 1.0000] | yes | 0.000 bits | 0.000 bits |
| Act 3: w = 1, φ = π/2, β = 0 | 0.525 | 0.5156 / 0.4854 | **0.0303 [0.0000, 0.1228]** | **no** → *No resolved influence at this shot count* | 0.998 bits | 0.999 bits |
| Act 3 again, seeds 1 / 2 / 3 | 0.507 / 0.474 / 0.512 | | 0.0020 [0, 0.0945] / 0.0088 [0, 0.1013] / 0.0127 [0, 0.1052] | no / no / no | 1.000 / 0.998 / 1.000 | 1.000 / 1.000 / 1.000 |
| w = 0.5, φ = π/2, β = 0 | 0.516 | 0.1494 / 0.8652 (ideal 0.1464 / 0.8536) | 0.7158 [0.6233, 0.8083] (ideal 0.7071) | yes | 0.999 bits | 0.290 bits (ideal 0.311) |
| Observer: w = 0.5, φ = π/2, β = 1.0 | 0.229 (ideal 0.202) | same probes | 0.7158 [0.6233, 0.8083] | yes | 0.777 bits | 0.290 bits |

Every run: orientation canary passed, readout flip rates 0.0 / 0.0, Hoeffding e = 0.0925,
one `backend.run` call, 0.02–0.04 s wall time under CPython (the browser's Pyodide build is
slower). The Demon's forecast was within 2σ of the sample in every run above except the
Observer run (0.229 vs 0.202, 2.15σ), which the Demon's line reports as "outside the shot
noise I expected": a sample, not a defect.

**Error-bar calibration** (`data/fwo_coverage.json`, from `lab/experiments.fwo_coverage`:
2,000 seeded runs per point sampled from the exact distributions, 1,024 shots per probe,
`--seed 1`): the 95% interval contained the exact Capacity in **100.0%** of runs at
w = 0, 0.25, 0.5, 0.75 and 1; mean width 0.093 / 0.169 / 0.185 / 0.185 / 0.111; fraction
reporting "resolved" 1.000 / 1.000 / 1.000 / 1.000 / **0.000** (at w = 1 no run claimed an
influence). An extra in-session point at w = 0.9 (exact C = 0.156, just above e): coverage
100.0%, resolved in 1,998 of 2,000 runs. The bound is conservative on purpose: a normal
interval would be about half as wide and would fail at the endpoints 0 and 1.

**IonQ-like noise (exact, modelled, not measured).** With IonQ's published Forte-1
depolarizing rates on our gates: Capacity 0.9888 at w = 0 (p_low/p_high 0.0056/0.9944),
0.6992 at w = 0.5, 0 at w = 1; Connection 0.9531 bits at w = 1. An approximation of IonQ's
model, shown by the Demon beside the ideal values.

**Platform runs (2026-10-10).** On Qollab's built-in simulator in the browser, one job
of four probes plus the canary at 1,024 shots per probe (φ = 140°, w = 0.52, β = 99°) finished
in 0.1 s: P(Self = 1) = 0.234 against a forecast of 0.242, Capacity 0.667 [0.574, 0.760]
(ideal 0.685), Openness 0.786 bits, Connection 0.328 bits. On the IonQ Forte 1 noise-model
simulator, one remote 17-qubit job at 1,024 shots per probe (φ = 222°, w = 0.20, β = 86°)
finished in 11.46 s (job id `01a1296d-229a-70da-8d9b-2b90d19715e6`): Capacity 0.94 [0.84, 1.00]
(ideal 0.951), Openness 0.618 bits, Connection 0.032 bits, 1,024 shots seen per probe, canary
passed with 0.00% readout flips (the published model has no readout term). Details in
[docs/claims.md](docs/claims.md).

**The toolkit** (`qk_*.py`: one-job packing with canaries, the exact noise model, the
estimators, claim cards, dataset provenance) was built and validated end to end on CHSH
before the Observatory existed; that reference lives in [reference/chsh/](reference/chsh/)
and is not uploaded. Recorded there: the classical bound S ≤ 2 by enumerating all 16
deterministic strategies (and by a linear program in `lab/bounds_lp.py`); the exact noise
model against qiskit-aer's density-matrix simulator to 8.9×10⁻¹⁶ over 15 settings; and
error-bar calibration over 2,000 seeded runs at each of four noise levels (66.7–69.2% of
runs within 1 se against 68.3% expected, 94.2–95.7% within 2 se against 95.4%).

## Beyond the tutorial

All three of the rules' routes, in this order of weight:

1. **A novel application and problem context.** A precise, falsifiable toy model of "the
   capacity to reshape possible futures", staged as an instrument with three personas, where
   the same 50/50 outcome is high-capacity in one setting and zero-capacity in another.
   Nobody's tutorial asks whether uncertainty is freedom.
2. **An original analytical and educational contribution.** The capacity law C = cos γ for
   this control family; a Hoeffding-bounded Capacity interval with a fixed "no resolved
   influence" rule and a measured coverage check; the Demon's forecast against the sample;
   two labelled classical baselines; claim cards that say what each number does *not* show.
3. **A technical extension.** Four probes and two canary checks packed into one 17-qubit
   job (IonQ's one-job-per-run rule), an exact in-browser noise model with an IonQ-like
   preset shown next to the ideal prediction, and a one-job guard that is tested.

**Who might use it:** educators teaching interference versus decoherence with one dial;
philosophy-of-mind classes that want a model precise enough to argue with; science
communicators; other Qollab projects reusing the one-job packer and canaries.

## Accessibility

The page follows the shell patterns validated on the CHSH reference
([reference/chsh/UI.md](reference/chsh/UI.md)): semantic headings and landmarks; every
control a real `<label>`ed form element with help text; real `<button>` elements that work
from the keyboard with a visible focus ring; status and readings announced through
`aria-live` regions (one sentence after a slider settles, not one per keystroke); the graph
as a decorative `aria-hidden` scene next to a text reading, with the counts table in the
drawer; no signal carried by colour alone (teal for Self and amber for World are always
labelled); reduced motion honoured; text contrast ≥ 4.5:1; usable at 320 px and 200% zoom.
The video has captions and a transcript ([VIDEO.md](VIDEO.md)). Checks on the Observatory
page itself: TODO(team) (keyboard-only walk, screen reader, 200% zoom, contrast, axe-core;
see [SUBMIT.md](SUBMIT.md)).

## Precomputed data

Three small JSON datasets ship with the project and are loaded by literal path (that is how
Qollab decides which files to bundle); if a file is missing, the page computes the exact
curve in the session and says so.

| File | Content |
|---|---|
| `data/fwo_theory.json` | the ideal curves against w (101 points): Capacity, p_low, p_high, Connection, Openness, P(Self = 1) |
| `data/fwo_noise.json` | the readings under the exact noise model with the IonQ-like preset scaled from 0× to 80× its published rates (20 steps) at w = 0 and w = 0.5 (40 rows): at 1× Capacity is 0.9888 and 0.6992, at 80× it is 0.328 and 0.232, so the Demon can show how far noise moves the readings |
| `data/fwo_coverage.json` | the Hoeffding interval's measured coverage over 2,000 seeded runs at each of w = 0, 0.25, 0.5, 0.75, 1 (the numbers in [Validation](#validation-measured)) |

Each file records its schema, generator, git commit, UTC time, library versions and the
class of machine that computed it: **a 48-thread x86 workstation** (Python 3.14, qiskit
2.5.2; qiskit-aer 0.17.2 for cross-checks). All of it is simulator output.

## Replicate & extend

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q                                   # the whole suite (800+ tests, about 45 s)
.venv/bin/python -m pytest -o addopts= -q tests/test_project_data.py   # one file (any under tests/)

# Run the Python entry the way Qollab does: a `backend` global, main.py, then main(...)
# (arguments: intention_deg, world_coupling, perspective_deg, shots_per_probe, persona)
cd qollab_project && ../.venv/bin/python -c 'from qiskit.providers.basic_provider import BasicSimulator
backend = BasicSimulator(); backend.set_options(seed_simulator=11)
exec(open("main.py").read()); main(90.0, 0.0, 0.0, 1024, "self")' && cd ..

# Regenerate the shipped datasets (exact except the coverage sweep, which is seeded; the
# default --seed 1 reproduces the numbers quoted above: a rerun on a different CPU
# architecture gave identical coverage and resolved fractions and mean widths within
# 2e-4, since numpy's sampler is not bit-identical across platforms). Each file's
# provenance (`params`) records the grid actually used; if these lines and the provenance
# disagree, the provenance wins.
.venv/bin/python lab/sweep.py --experiment fwo_theory   --grid w=0:1:101 --shots 0 \
    --out qollab_project/data/fwo_theory.json
.venv/bin/python lab/sweep.py --experiment fwo_noise --shots 0 \
    --grid scale=0,0.5,1,1.5,2,3,4,5,6,8,10,12,15,20,25,30,40,50,60,80 --grid w=0,0.5 \
    --fixed p1=0.0002666666666666667 --fixed p2=0.004949333333333333 \
    --out qollab_project/data/fwo_noise.json
.venv/bin/python lab/sweep.py --experiment fwo_coverage --grid w=0:1:5 \
    --fixed repeats=2000 --shots 1024 --workers 5 --out qollab_project/data/fwo_coverage.json
```

**Extend:**

- **Change the circuit:** the four probes are built in `qollab_project/observatory.py`
  (`make_circuit`, `_probe_angles`) from the circuit order above; a new control is a new
  gate plus a new line in the exact prediction (`prediction`) and a new check against the
  statevector. Keep standard gates (`h`, `rz`, `ry`, `cx`) so IonQ compiles it unchanged.
- **Give the Self joint control** (a World dial, or a disentangling step before readout) and
  watch Capacity return at full coupling: the model predicts it, and the claim cards say so.
- **Upgrade Connection** from a reference-basis correlation to an entanglement witness by
  adding the CHSH probe from `reference/chsh/` to the World bridge.
- **A new sweep:** add a function to `lab/experiments.py`, run `lab/sweep.py`, and load the
  output by a literal path such as `"data/my_sweep.json"` in `observatory_api.py`.
- **Check before uploading:** `tools/pack_for_qollab.py --entry js` (the platform rules) and
  `tools/scrub_check.py` (public-repo hygiene; its pattern list is private and lives outside
  the repository, so the check fails closed without it).

## Built during the window

Everything in this repository was created during the hackathon window (Fri 2026-10-09
17:00 MDT to Sun 2026-10-11 17:00 MDT); the repository was started at 22:53 MDT on Friday
and its first commit is from 23:04. **[BUILDLOG.md](BUILDLOG.md)** records what was built
and when. The team's design note and build guide for the Observatory are dated 10 October
2026, inside the window. No pre-existing project code is included; see
[CREDITS.md](CREDITS.md).

## Credits & AI disclosure

The circuit and its philosophical mapping are the team's original design. The code, tests
and documentation were written with substantial help from an AI coding assistant (Claude
Code), directed and reviewed by the team. Who did what, the references, the libraries and
their licenses are in **[CREDITS.md](CREDITS.md)**.

## License

[MIT](LICENSE). The libraries this project relies on are under MIT-compatible open
licenses (Apache-2.0, BSD-3-Clause, MIT); see [CREDITS.md](CREDITS.md).

This effort is supported by Qollab & IonQ
