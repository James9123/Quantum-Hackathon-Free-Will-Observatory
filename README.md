# The Free Will Observatory

> **This effort is supported by Qollab & IonQ**

*A fictional instrument for exploring the capacity to reshape possible futures.*

**The build in one sentence:** a single-page, brain-shaped graph where three personas
investigate one two-qubit Self through fresh simulator experiments, visible changes in
probability, and a transparent model of agency.

You set an **Intention**, press **Run experiment**, and watch the distribution of the
Self's two possible futures move. Turn up the **World coupling** and the future stays just
as uncertain, but your intention stops moving it. The model calls the first situation
*high-capacity* and the second *low-capacity*, and three personas (The Self, Laplace's
Demon, The Observer) argue about what that means. Every number on the page comes from
one freshly submitted simulator job of four two-qubit circuits, and every reading has an
exact definition, a closed-form prediction and an error bar.

> **Honesty, first.** The correspondence between controls and words is *designed, not
> discovered*. Simulators compute what quantum theory predicts (and how a noise model
> degrades it); they do not test nature. The readings are a fictional model, not a
> measurement of free will, and a responsive classical model can score just as high.
> See [Honesty](#honesty-what-this-is-and-is-not).

| Judging trait | Where to look |
|---|---|
| Novelty & creativity | [What it does](#what-it-does), [The question](#the-question), [docs/claims.md](docs/claims.md) |
| Technical execution | [How to run on Qollab](#how-to-run-on-qollab), [The model](#the-model), [Validation](#validation), 500+ tests ([Replicate & extend](#replicate--extend)) |
| Impact potential | [Beyond the tutorial](#beyond-the-tutorial), [Replicate & extend](#replicate--extend) |
| Documentation quality | This page, [docs/model.md](docs/model.md), [docs/claims.md](docs/claims.md), [BUILDLOG.md](BUILDLOG.md), [CREDITS.md](CREDITS.md) |

**Links:** Qollab project: TODO(captain). Demo video (2–3 min): TODO(captain). Source: TODO(captain).

---

## What it does

**The scene.** A dark brain-shaped graph (two fixed ellipsoid lobes, decorative nodes that
are *not* qubits) holds one fictional Self. Two branches leave it: **Future 0** and
**Future 1**, sized by the measured probabilities of the last run. A **World bridge** joins
the Self to a second qubit; its weight follows the measured Connection reading. The
previous run stays as a muted ghost so a change is a comparison, never a flourish. Nothing
moves until a fresh job has returned.

**Three personas, one data set.** Switching persona changes the explanation, never the data.

| Persona | What they do | What it reveals |
|---|---|---|
| **The Self** | Changes the Intention and presses *Run experiment*. | The current future distribution, plus the Capacity available under opposite intentions. |
| **Laplace's Demon** | Runs a forecast for the chosen settings before the job returns. | The closed-form prediction next to the fresh sampled result, plus two labelled classical baselines (a fixed-output model: Capacity 0, Openness 0; a fair coin: Capacity 0, Openness 1). |
| **The Observer** | Changes the Perspective and reruns. | A different observable for the same prepared state. Capacity stays comparable because its two probes share the readout. |

**Three controls** (all angles in radians; see [The model](#the-model)):

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
plus one poetic line in the persona's voice, and a **How this works** drawer with the
circuit, the four probes' counts, the job record and the exact formulas.

## The question

Is uncertainty the same thing as freedom? This project gives the fiction a precise rule and
lets you test it. *Free will, here, is defined as the capacity to reshape possible futures:*
the Self has a distribution of outcomes, an intention is a control input that can redirect
that distribution, and freedom within the model is the **range of redistribution** available
to that input. One surprising outcome is never enough; the model asks whether an
intervention changes the odds across repeated experiments.

**The central dramatic result.** Two situations both look 50/50:

| Setting | P(Self = 1) | Openness | Capacity (ideal) | The model's verdict |
|---|---|---|---|---|
| no coupling (w = 0), intention π/2 | 0.5 | 1 bit | **1.0** (intentions sweep 0% → 100%) | high-capacity |
| full coupling (w = 1), *any* intention | 0.5 | 1 bit | **0.0** (every allowed intention gives 50/50) | low-capacity |

In the model, uncertainty alone is not freedom. The ideal capacity is cos γ: it falls from 1
to 0 as the World learns which alternative the Self took, while the Self's own odds never
leave 50/50. That contrast is the whole show, and it is reproducible to 15 decimal places
([Validation](#validation)).

## How to run on Qollab

Open the project on Qollab, pick a backend in the Run dialog, press **Run**, then use the
page: choose a persona, move the three sliders, press **Run experiment**.

| Entry | Files | What you get |
|---|---|---|
| **JS (the submission)** | `index.html` + `main.js` + `main.css` + `ui/*.js` + `observatory_api.py` + `qk_*.py` + `data/*.json` | The Observatory page. Qollab runs this entry whenever both top-level `index.html` and `main.js` exist. It uses only the injected `backend`, our Python modules, and three.js from Qollab's import map. Nothing runs outside the browser: no separate service, no polling API, no API keys. |
| **Python (fallback)** | `main.py` + `observatory_api.py` + `qk_*.py` + `data/*.json` | Console output: backend profile, the prediction, one run's four count tables, the three readings with the interval, and the explanation. Its parameters appear in Qollab's Run-settings form. |

Build one or the other with `tools/pack_for_qollab.py --entry js` (keeps the page) or
`--entry python` (leaves the JS entry files out, so Qollab runs `main.py`); see
[SUBMIT.md](SUBMIT.md).

**Backends** (Qollab's Run dialog):

| Backend | Kind | Notes |
|---|---|---|
| Built-in simulator | ideal, local | Qiskit `BasicSimulator`, 24 qubits. **Free and local: the backend judges press Run on.** |
| AWS Braket local | ideal, local | 25 qubits |
| IBM noise models | noisy, local (in the browser) | circuits are transpiled first; `mode=auto` sends the four probes as one list job |
| IonQ Forte 1 / Forte Enterprise 1 (simulator) | noisy, remote | 29 qubits, **one job per run**; IonQ results neither add nor subtract points |

**One job per run.** Each press of *Run experiment* submits exactly one `backend.run(...)`
holding all four probes (`display`, `intent_low`, `intent_high`, `connection`) plus two
canary blocks: an orientation check (prepared `110`, a key that is not a palindrome, so a
reversed bit order is diagnosed rather than absorbed) and a readout calibration (flip rates
P(1|0) and P(0|1)). With `mode=auto` the probes are tiled side by side on disjoint qubits
of one circuit on one-job backends (17 qubits: 8 for the probes, 9 for the canaries) and
sent as one list job on the in-browser noise models. A guard in `qk_runtime.run_once`
raises rather than let a second job reach a one-job provider.

**Shots.** 1,024 per probe by default (4,096 sampled circuit executions per click), capped
at 4,096 per probe. The metrics use the shots actually seen per probe (IonQ's noisy
simulators report counts as round(probability × shots), so totals can differ slightly).

**Run settings** (JS page and Python entry alike): `intention_rad` [0, 2π], `world_coupling`
[0, 1], `perspective_rad` [0, π], `shots_per_probe` [1, 4096], `persona` (`self` /
`demon` / `observer`), `mode` (`auto` / `tile` / `list`), `canary` (bool). Invalid values
return a visible *failed* result; nothing is clamped silently, and old counts are never
substituted for a live run.

## The model

Self = q0, World = q1, both start in |0⟩. The circuit, in order:

```
prepare |00>
H(Self)                                   # creates the alternatives
RZ(phi, Self)                             # Intention: how the alternatives recombine
controlled-RY(2*gamma, Self -> World)     # World coupling: RY(g) CX RY(-g) CX on the target
RZ(-beta, Self); H(Self)                  # Perspective: an equatorial readout direction
measure Self and World                    # omitted for the connection probe (Z on both)
```

Before readout, up to a global phase and with the ket order Self, World:

```
[ |00> + e^{i phi} cos(gamma) |10> + e^{i phi} sin(gamma) |11> ] / sqrt(2)
```

The World can keep which-alternative information, which reduces the interference visible in
the Self alone. This is coherent coupling, not a noise slider.

**Ideal display probability:** `P(Self = 1) = [1 − cos(γ) · cos(φ − β)] / 2`, so the
intent probes (φ = β and φ = β + π) give p_low = (1 − cos γ)/2 and p_high = (1 + cos γ)/2,
and the **ideal Capacity is C = cos γ**: 1 at w = 0, 0.7071 at w = 0.5 (p_low/p_high =
0.1464/0.8536), 0 at w = 1.

| Probe | Settings | Purpose |
|---|---|---|
| `display` | user φ, γ, β; full circuit | drives the visible future distribution and Openness |
| `intent_low` | φ = β; same γ, β | one end of the accessible probability range |
| `intent_high` | φ = β + π; same γ, β | the opposite end |
| `connection` | user φ, γ; no final `RZ(−β)`/`H`; Z on both qubits | shared information in a fixed reference basis (Connection) |

**Readings.** C = |p_high − p_low| (the total variation distance between the two binary Self
distributions). O = −p·log₂p − (1−p)·log₂(1−p) with 0·log₂0 = 0, on the display p. I =
Σ p(s,w)·log₂[p(s,w) / (p(s)·p(w))] over the connection probe's counts only (classical
mutual information in one basis, not an entanglement witness). Capacity is never estimated
from history entries with different coupling or readout.

**Uncertainty (Hoeffding + union bound).** For N_low and N_high shots, the signed difference
d = p_high − p_low has the conservative 95% interval d ± e, clipped to [−1, 1], with
e = √(ln 80 / (2·N_low)) + √(ln 80 / (2·N_high)). Mapped through |·| it gives the interval
for C: if it spans zero, the lower limit is 0 and the upper limit is the largest endpoint
magnitude. At 1,024 shots per probe, e ≈ 0.0925. A result is **resolved** only when the
interval excludes zero; otherwise the page says *"No resolved influence at this shot
count"* and never describes a small positive estimate as proven agency.

**Bit order.** The app uses **SelfWorld**: `10` means Self = 1, World = 0. Qiskit writes
clbit 0 rightmost, so a probe measured as [Self = q0, World = q1] comes back as WorldSelf
and is reversed **once**, at the adapter boundary. The test: flip q0 only and the app
outcome must be `10` with certainty.

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
  interference; coupling is called *World influence* because it correlates the Self with a
  second system; the readout angle is called *perspective* because it changes the measured
  observable. Each metaphor points to an inspectable operation.
- **Users supply the intention.** Version one has no autonomous learning or goals.
- **Specific to the chosen controls:** phase changes on the Self, fixed coupling, the
  specified readout. Joint control of Self and World could undo their coupling.
- **Not a universal property of the state, not a neuroscience model, and not evidence that
  quantum systems alone can be agents.** A responsive classical model can also score highly.
- **Simulators compute predictions.** A simulator computes what quantum theory predicts and
  how a noise model degrades it; it does not test nature. No result here is evidence about
  the physical world.
- **The readings stay separate.** They are never averaged into a "free will percentage". A
  Capacity shown as a percentage is labelled *Capacity in this model*.
- **Connection** is measured information in a reference basis, not an entanglement
  certification; a classical copy of the Self bit into the World scores the same.

## Validation

**The toolkit** (`qk_*.py`: one-job packing with canaries, the exact noise model, the
estimators, claim cards, dataset provenance) was built and validated end to end on CHSH
before the Observatory existed; that reference lives in [reference/chsh/](reference/chsh/)
and is not uploaded. Recorded there: the classical bound S ≤ 2 by enumerating all 16
deterministic strategies (and by a linear program in `lab/bounds_lp.py`); the exact noise
model against qiskit-aer's density-matrix simulator to 8.9×10⁻¹⁶ over 15 settings; and
error-bar calibration over 2,000 seeded runs at each of four noise levels (66.7–69.2% of
runs within 1 se against 68.3% expected, 94.2–95.7% within 2 se against 95.4%).

**The Observatory's own checks** (`tests/`):

| Check | Expected | Result |
|---|---|---|
| Closed form vs exact statevector over a (φ, w, β) grid | P(Self = 1) = [1 − cos γ cos(φ − β)]/2 to floating-point rounding | TODO(measure): grid size and max \|error\| (the team's design note reports 819 combinations below 1.1×10⁻¹⁵ with Qiskit 2.5.2 / Aer 0.17.2) |
| No-coupling endpoints | φ = β: Self always 0; φ = β + π: Self always 1 | TODO(measure) |
| Half coupling, β = 0 | p_low / p_high ≈ 0.1464 / 0.8536 | TODO(measure) |
| Full coupling | P(Self = 1) = 0.5 for every φ; the Capacity interval includes zero (the estimate is not forced to zero) | TODO(measure) |
| Connection at w = 0 / 1 | I = 0 / 1 bit | TODO(measure) |
| Bit order: flip q0 only | app outcome `10` with certainty | TODO(measure) |
| Perspective | ideal Capacity stays cos γ for two β values at fixed φ, w | TODO(measure) |
| Hoeffding coverage sweep (`data/fwo_coverage.json`) | at least 95% of seeded runs' intervals contain the true d, at every grid point | TODO(measure) |
| Built-in simulator, 1,024 shots per probe, one job | three acts of [VIDEO.md](VIDEO.md): C ≈ 1 resolved, then C interval including 0 | TODO(measure) |
| IonQ Forte 1 simulator, one job | same structure; job id, date, shots seen | TODO(measure) |

## Beyond the tutorial

All three of the rules' routes, in this order of weight:

1. **A novel application and problem context.** A precise, falsifiable toy model of "the
   capacity to reshape possible futures", staged as an instrument with three personas, where
   the same 50/50 outcome is high-capacity in one setting and zero-capacity in another.
   Nobody's tutorial asks whether uncertainty is freedom.
2. **An original analytical and educational contribution.** The capacity law C = cos γ for
   this control family; a Hoeffding-bounded Capacity interval with a fixed "no resolved
   influence" rule; the Demon's forecast against the sample; two labelled classical
   baselines; claim cards that say what each number does *not* show.
3. **A technical extension.** Four probes and two canary blocks packed into one job (IonQ's
   one-job-per-run rule), an exact in-browser noise model with an IonQ-like preset shown
   next to the ideal prediction, and a coverage sweep that measures whether the error bars
   keep their promise.

## Accessibility

The page follows the shell patterns validated on the CHSH reference
([reference/chsh/UI.md](reference/chsh/UI.md)): semantic headings and landmarks; every
control a real `<label>`ed form element with help text; real `<button>` elements that work
from the keyboard with a visible focus ring; status and readings announced through
`aria-live` regions (one sentence after a slider settles, not one per keystroke); the
graph as a decorative `aria-hidden` scene next to a text reading, with the counts table in
the drawer; no signal carried by colour alone (teal for Self and amber for World are always
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
| `data/fwo_theory.json` | the ideal curves against w: capacity, p_low, p_high, connection bits |
| `data/fwo_noise.json` | the same readings under the exact noise model with the IonQ-like preset, so the Demon can show how far noise moves them |
| `data/fwo_coverage.json` | the Hoeffding interval's measured coverage over seeded runs |

Each file records its schema, generator, git commit, UTC time, library versions and the
class of machine that computed it: **a 48-thread x86 workstation** (Python 3.14, qiskit
2.5.2, qiskit-aer 0.17.2 for cross-checks). All of it is simulator output.

## Replicate & extend

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q                    # the whole suite
.venv/bin/python -m pytest -o addopts= -q tests/test_project_data.py   # one file (any under tests/)

# Run the Python entry locally the way Qollab does (injected `backend`, appended main(...))
.venv/bin/python tools/run_smoke_local.py --project qollab_project --mode auto

# Regenerate the shipped datasets. The grids used for the shipped files are recorded in
# each file's provenance (`params`); if these lines and the provenance disagree, the
# provenance wins.
.venv/bin/python lab/sweep.py --experiment fwo_theory   --grid w=0:1:101 --shots 0 \
    --out qollab_project/data/fwo_theory.json
.venv/bin/python lab/sweep.py --experiment fwo_noise    --grid w=0:1:101 --shots 0 \
    --out qollab_project/data/fwo_noise.json
.venv/bin/python lab/sweep.py --experiment fwo_coverage --grid w=0,0.5,0.9,1 \
    --fixed repeats=2000 --shots 1024 --workers 4 --out qollab_project/data/fwo_coverage.json
```

**Extend:**

- **Change the circuit:** the four probes are built in `qollab_project/observatory_api.py`
  from the circuit order above; a new control is a new gate plus a new line in the
  prediction (`predict_json`) and a new test against the statevector. Keep standard gates
  (`h`, `rz`, `ry`, `cx`) so IonQ compiles it unchanged.
- **Give the Self joint control** (a World dial, or a disentangling step before readout) and
  watch Capacity return at full coupling: the model predicts it, and the claim cards say so.
- **Upgrade Connection** from a reference-basis correlation to an entanglement witness by
  adding the CHSH probe from `reference/chsh/` to the World bridge.
- **A new sweep:** add a function to `lab/experiments.py`, run `lab/sweep.py`, and load the
  output by a literal path such as `"data/my_sweep.json"`.
- **Check before uploading:** `tools/pack_for_qollab.py --entry js` (the platform rules) and
  `tools/scrub_check.py` (public-repo hygiene; its pattern list is private and lives outside
  the repository, so the check fails closed without it).

## Built during the window

Everything in this repository was created during the hackathon window (Fri 2026-10-09
17:00 MDT to Sun 2026-10-11 17:00 MDT); the repository was started at 22:53 MDT on Friday.
**[BUILDLOG.md](BUILDLOG.md)** records what was built and when. The team's design note and
build guide for the Observatory are dated 10 October 2026, inside the window. No
pre-existing project code is included; see [CREDITS.md](CREDITS.md).

## Credits & AI disclosure

The circuit and its philosophical mapping are the team's original design. The code, tests
and documentation were written with substantial help from an AI coding assistant (Claude
Code), directed and reviewed by the team. Who did what, the references, the libraries and
their licenses are in **[CREDITS.md](CREDITS.md)**.

## License

[MIT](LICENSE). The libraries this project relies on are under MIT-compatible open
licenses (Apache-2.0, BSD-3-Clause, MIT); see [CREDITS.md](CREDITS.md).

This effort is supported by Qollab & IonQ
