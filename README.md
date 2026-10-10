# TODO(idea): Project title

> **This effort is supported by Qollab & IonQ**

TODO(idea): one-paragraph summary of the chosen idea, starting from the question it asks.
Until the idea is chosen, this repository ships a complete **reference experiment (CHSH)**
that runs end to end on Qollab: press Run and **one** job measures the four CHSH settings
next to "canary" blocks that check bit order and calibrate readout error. Then a **claim card**
spells out what the number does and does not show, and **precomputed noise sweeps** (each
with its provenance) show how far noise can go before quantum correlations drop to the level
any classical model can produce. The idea's experiment will reuse the same parts.

> **Simulator honesty.** Everything here runs on simulators. A simulator computes what
> quantum theory *predicts*, plus how the chosen noise model degrades that prediction. It
> does **not** test nature. When this project says "S exceeds 2", it means "quantum theory,
> as simulated, predicts S above 2". It is not evidence about the physical world. Every
> claim card printed by the project says this too.

| Judging trait | Where to look |
|---|---|
| Novelty & creativity | [What it does](#what-it-does), [The problem](#the-problem) (TODO(idea)) |
| Technical execution | [How it works](#how-it-works), [Results](#results), 400+ tests ([Replicate & extend](#replicate--extend)) |
| Impact potential | TODO(idea); a reusable one-job + claim-card toolkit ([How it works](#how-it-works)) |
| Documentation quality | This page, [docs/claims.md](docs/claims.md), [BUILDLOG.md](BUILDLOG.md), [CREDITS.md](CREDITS.md) |

**Beyond the tutorial:** a *technical extension* (an exact noise dial, readout mitigation,
zero-noise extrapolation, and benchmarking against qiskit-aer) plus an *original
educational contribution* (claim cards, error bars whose coverage is measured, and the shot
counts needed to resolve a violation). TODO(idea): add the idea's novel application here.

---

## What it does

TODO(idea): what a judge sees and learns, in 3 to 5 bullets.

Reference experiment (CHSH), as shipped:

- Runs the four CHSH measurement settings on a shared Bell pair |Φ+⟩ in **one job** on any
  Qollab backend, including IonQ's one-job-per-run simulators.
- Checks the backend's bit order and measures its readout error in the same job (canary
  blocks), then corrects the readout bias.
- Prints a **claim card**: claim → assumptions → witness → result ± standard error →
  verdict → what this does NOT show → counterarguments.
- Shows a precomputed curve: S against noise strength, where S crosses the classical bound
  of 2, how many shots it takes to resolve the violation, and how far to trust the error bars.

## The problem

TODO(idea): the question, who cares, and why a simulator is the right first tool for it.

For the reference experiment: Bell-type inequalities bound the correlations that any
local hidden-variable model can produce (CHSH: |S| ≤ 2). Quantum theory predicts up to
2√2 ≈ 2.828 (Tsirelson's bound). Noise pulls quantum predictions back toward the classical
region. The questions a learner can answer with this project: *how much* noise does it take,
*how many shots* resolve the gap, and *what exactly* a violation would and would not establish.

## How to run on Qollab

Upload the project folder (built by `tools/pack_for_qollab.py`, see [SUBMIT.md](SUBMIT.md)),
pick a backend in the Run dialog, and press **Run**.

| Entry | Files | What you get |
|---|---|---|
| **Python** | `main.py` (+ modules, `data/`) | Console output: backend profile, claim card, noise curve, validation numbers. Run settings: `shots` (int, default 1000), `mode` (`auto`/`tile`/`list`/`tiles`), `mitigate` (bool, default True). |
| **JS** | `index.html` + `main.js` (+ `main.css`, `ui/*.js`, `ui_api.py`) | An interactive page. Qollab runs this entry instead of `main.py` whenever both top-level files exist. TODO(idea): confirm which entry is submitted. |

Build one or the other: `tools/pack_for_qollab.py --entry python` leaves the JS entry files
out, and `--entry js` keeps them.

**Backends** (Qollab's Run dialog):

| Backend | Kind | Notes |
|---|---|---|
| Built-in simulator | ideal, local | Qiskit `BasicSimulator`, up to 24 qubits. **Free and local: the kind of backend judges press Run on.** |
| AWS Braket local | ideal, local | 25 qubits |
| IBM noise models | noisy, local (in the browser) | Circuits are transpiled first; `mode=auto` sends small circuits as one list job |
| IonQ Forte 1 / Forte Enterprise 1 (simulator) | noisy, remote | 29 qubits, **one job per run**; IonQ results neither add nor subtract points |

**The one-job rule.** IonQ's simulators accept one job per run, so the project never
submits twice. Everything (canaries plus every measurement setting) is packed into a
single `backend.run(...)`. A guard in `qk_runtime.run_once` raises an error rather than
let a second job reach the provider.

## How it works

| Piece | File | What it does |
|---|---|---|
| One-job packing | `qk_packer.py` | `tile`: every block side by side on disjoint qubits of one circuit (CHSH: 17 qubits); `list`: one circuit per block, submitted as one list job; `tiles`: first-fit into as few circuits as fit. |
| Canary blocks | `qk_packer.py` | *Orientation*: qubits prepared as (1, 1, 0) and measured in the order [2, 0, 1]. The expected key `110` is not a palindrome, so reversed keys or an ignored qubit→clbit map are diagnosed, not silently absorbed. *Calibration*: three qubits left in \|0⟩ and three flipped to \|1⟩ give per-bit readout flip rates P(1\|0) and P(0\|1). |
| Exact noise dial | `qk_noise.py` | Full density-matrix evolution (no sampling): depolarizing noise after every 1- and 2-qubit gate (qiskit-aer's parameter convention), classical readout flips, and one `scale` knob. For CHSH, S = 2√2(1 − λ), which reaches 2 at λ\* = 1 − 1/√2 ≈ 0.2929. |
| IonQ-like preset | `qk_noise.py` | IonQ's published Forte-1 simulator depolarizing rates (r₁q ≈ 2.67×10⁻⁴, r₂q ≈ 4.95×10⁻³). We apply them to our own gate decomposition, not IonQ's native gates, so the preset is an **approximation**. |
| Readout mitigation | `qk_mitigation.py`, `chsh.py` | Tensor-product confusion-matrix inversion using the canary's flip rates. It removes the predicted bias, not shot noise: the corrected error bar is wider, by 1/(1 − p₀₁ − p₁₀)². |
| Zero-noise extrapolation | `qk_mitigation.py`, `qk_primitives.py` | Global unitary folding (U → U (U†U)ᵏ, the same unitary with 2k + 1 times the gates) at fold factors 1, 3, 5, then linear, Richardson or exponential extrapolation to zero noise. **IonQ caveat:** IonQ strips barriers and recompiles circuits on its servers, which likely undoes the folding, so ZNE is used only on local simulators and on our exact model. |
| Claim cards | `qk_cards.py` | One JSON record per claim plus text and Markdown renderings. Verdict rule on z = (value − bound)/se: z ≥ 3 *exceeds*, z ≤ 0 *consistent*, otherwise *inconclusive*. Simulator cards always carry the simulator note. |
| Precomputed sweeps | `lab/sweep.py`, `qk_data.py` | Off-platform sweeps write small JSON datasets. Each records its schema, generator, git commit, UTC time, library versions and machine class. The project loads them by literal path, because that is how Qollab decides which data files to ship. |
| Classical bounds | `qk_bounds.py`, `lab/bounds_lp.py` | Brute-force enumeration of deterministic strategies (in the project), and a linear program over the local polytope (lab only, SciPy/HiGHS). |

TODO(idea): add the idea's own module(s) to this table.

## Results

Reference experiment (CHSH). Numbers come from `qollab_project/data/*.json`, computed
off-platform by `lab/sweep.py` at commit `851fd4c` on
a 48-thread x86 workstation (Python 3.14, qiskit 2.5.2, qiskit-aer 0.17.2).
All of them are **simulator outputs**.

| Quantity | Value | Source |
|---|---|---|
| Ideal S | 2√2 = 2.828427… | `chsh_noise.json`, p₂ = 0 |
| Crossing λ\* (S = 2) | numeric 0.2928932188 vs theory 1 − 1/√2; \|difference\| = 2.5×10⁻¹¹ (under 1×10⁻¹⁰) | `chsh_noise.json` |
| Error-bar coverage (2000 seeded 1000-shot runs at each of p₂ = 0, 0.1, 0.2, 0.29) | within 1 se: 66.7–69.2% (68.3% expected); within 2 se: 94.2–95.7% (95.4% expected) | `chsh_coverage.json` |
| Noise dial vs qiskit-aer density matrix | max \|ΔS\| = 8.9×10⁻¹⁶ over 15 settings (p₁ = 0.01, p₂ = 0 … 0.35) | `chsh_aer_check.json` |
| IonQ-like preset | S = 2.813. S stays above 2 up to 53× the published rates and first falls below it at 54× (S = 1.999), a **~54× margin** | `chsh_ionq_like.json` |
| Shots per setting for the expected gap S − 2 to reach 3 se | 27 at p₂ = 0; 355 at p₂ = 0.2; 20,054 at p₂ = 0.28 | `chsh_noise.json` |
| ZNE under p₁ = 0.01, p₂ = 0.05 (exact model) | S at folds 1/3/5 = 2.620 / 2.249 / 1.931 → linear 2.784, Richardson 2.826, exponential 2.828 (ideal 2.828) | `chsh.zne_exact` |
| LP self-check | local maximum of CHSH = 2 (16 deterministic vertices); critical visibility of the Tsirelson point = 0.7071 = 1/√2 | `lab/bounds_lp.py` |

The exponential ZNE fit is almost exact here **because of the model**: with depolarizing
noise on every gate, S decays exponentially in the fold factor, which is the shape that fit
assumes. That is a property of this noise model, not a general result.

One local run of the Python entry (built-in simulator, 1000 shots, seed 11, one job, 17
qubits): S = 2.846 ± 0.044 (z = +19.0 against the bound 2), and the canary's bit-order check
passed.

TODO(idea): IonQ simulator run, one job: backend, shots, raw and mitigated S ± se, job id, date.

## Claims

Every result is stated as a claim card: claim → assumption → witness → result ± se → what
this does NOT show → counterarguments. See **[docs/claims.md](docs/claims.md)** for the CHSH
card and the blank template for the chosen idea.

## What this does NOT show

- **Nothing about nature.** These are simulations of quantum theory under stated noise
  models.
- **No loophole-free Bell test.** Both qubits sit in one device or simulator with no
  space-like separation (the locality loophole is wide open), and the program fixes the
  settings instead of drawing them from independent random sources.
- **Not IonQ's exact noise.** The IonQ-like preset applies IonQ's published (pre-September
  2025) Forte-1 depolarizing rates to our own gate decomposition. IonQ documents its current
  Forte models as more complex than that. No readout term is published, so the preset uses
  none unless asked.
- **A limited noise model.** The noise dial has depolarizing and readout noise only: no idle,
  crosstalk, leakage or coherent errors.
- **Error-bar coverage covers shot noise only.** It does not cover model error.
- TODO(idea): the idea's own limits.

## Accessibility

- **Python entry:** the console output is plain ASCII text with no color, so it reads
  in a screen reader and survives copy and paste. The claim card is wrapped at 100 columns
  and states its verdict in words. The text bar chart prints each value and "above 2" or
  "at/below 2" next to every bar, so nothing depends on the bars alone.
- **JS entry:** the page uses semantic headings and labelled sections, form controls with
  labels and help text (`aria-describedby`), and real `<button>` elements that work from
  the keyboard. Status messages and readings are announced through `aria-live` regions,
  and graphics that are only decorative are hidden from screen readers next to a text
  reading. TODO(idea): before submitting, test keyboard-only use, a screen reader, 200%
  zoom and contrast (see [SUBMIT.md](SUBMIT.md)).
- **Video:** captions and a transcript (see [VIDEO.md](VIDEO.md)).

## Replicate & extend

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q                       # the whole suite, about 30 seconds

# Run the Python entry locally the way Qollab does (injects `backend`, appends main(...))
.venv/bin/python tools/run_smoke_local.py --project qollab_project --mode auto

# Regenerate the shipped datasets (add --git-commit to stamp a commit by hand)
.venv/bin/python lab/sweep.py --experiment chsh --grid p2=0:0.35:71 --shots 0 \
    --out qollab_project/data/chsh_noise.json
.venv/bin/python lab/sweep.py --experiment chsh --grid scale=0:80:81 \
    --fixed p1=0.0002666666666666667 --fixed p2=0.004949333333333333 \
    --out qollab_project/data/chsh_ionq_like.json
.venv/bin/python lab/sweep.py --experiment chsh_coverage --grid p2=0,0.1,0.2,0.29 \
    --fixed repeats=2000 --shots 1000 --workers 4 --out qollab_project/data/chsh_coverage.json
.venv/bin/python lab/sweep.py --experiment chsh_aer --grid p2=0:0.35:15 --fixed p1=0.01 \
    --out qollab_project/data/chsh_aer_check.json

# Classical bounds by linear programming (SciPy's HiGHS)
.venv/bin/python lab/bounds_lp.py
```

Re-running these four sweeps reproduces the shipped results to within 4.4×10⁻¹⁶
(floating-point rounding), and the coverage counts come out identical.

**Extend:**

- **A new experiment:** follow `qollab_project/chsh.py`. Build circuits as
  `qk_packer.Block`s, then call `pack` → `qk_runtime.prepare` → `run_once` (one job) →
  `unpack` → `canary_report`, and finish with a `qk_cards.claim_card` that carries
  `CLAIM`, `ASSUMPTIONS`, `NOT_SHOWN` and `COUNTERARGUMENTS`.
- **A new witness or bound:** add it to `qk_bounds.WITNESSES`. Its classical bound is
  checked by enumeration, and `lab/bounds_lp.py` shows how to check one by LP.
- **A new sweep:** add a function to `EXPERIMENTS` in `lab/experiments.py`, run
  `lab/sweep.py`, and load the output in the project by a literal path such as
  `"data/my_sweep.json"`.
- **Check before uploading:** `tools/pack_for_qollab.py` (the platform rules) and
  `tools/scrub_check.py` (public-repo hygiene; its pattern list is private and lives
  outside the repository, so the check fails closed without it).

## Built during the event

Everything in this repository was created during the hackathon window (Fri 2026-10-09
17:00 MDT to Sun 2026-10-11 17:00 MDT). The repository was started at 22:53 MDT on Friday.
**[BUILDLOG.md](BUILDLOG.md)** records what was built and when. No pre-existing project
code is included. See [CREDITS.md](CREDITS.md) for the papers, libraries and documentation
we relied on.

## Credits & AI disclosure

The code, tests and documentation were written with substantial help from an AI coding
assistant (Claude Code, by Anthropic), directed and reviewed by the team. Who did what,
the papers, the libraries and their licenses are listed in **[CREDITS.md](CREDITS.md)**.

## License

[MIT](LICENSE). The libraries this project relies on are under MIT-compatible open
licenses (Apache-2.0, BSD-3-Clause, MIT); see [CREDITS.md](CREDITS.md).

This effort is supported by Qollab & IonQ
