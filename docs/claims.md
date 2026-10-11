# Claims

*Part of the [documentation set](README.md). These are the project's only empirical claims;
the philosophical framing in [design-brief.md](design-brief.md) is narrative, not a claim.*

Every result in this project is stated as a **claim card**, a record that connects a
number to everything a reader must accept before the number means anything:

**Claim → Assumptions → Witness → Result ± se → What this does NOT show → Counterarguments**

The format comes from the toolkit's claim cards (`qollab_project/qk_cards.py`), validated
on the CHSH reference in [reference/chsh/](../reference/chsh/). The Observatory's three
cards are below. The run record (`run_json`) carries the same readings, interval and
explanation text that these cards describe; if a card changes, the explanation copy in
`observatory.py` changes with it, so the document and the program never disagree.

**Simulator rule.** A card's "result" on a simulator is what quantum theory predicts under
the stated noise model. It is not a measurement of nature, and nothing here is evidence
about the physical world. Every simulator card carries this note:

> This is a simulation. It computes what quantum theory predicts, and how the chosen noise
> model degrades it; it is not a test of nature.

**Resolution rule** (fixed in advance, applied by the code, never chosen after the fact).
Capacity's uncertainty is the conservative 95% Hoeffding interval of
[docs/model.md §7](model.md#7-the-hoeffding-interval): e = √(ln 80/(2N_low)) + √(ln 80/(2N_high)),
which is 0.0925 at 1,024 shots per probe.

| Interval for C | Reading |
|---|---|
| excludes zero (\|p̂_high − p̂_low\| > e) | **resolved**: the intentions moved the odds by at least the lower limit |
| includes zero | **"No resolved influence at this shot count."** Never "zero capacity", never "proven agency". |

There is no classical bound to exceed here: these claims are about a *designed* model's
predictions, and the two classical references (fixed output, fair coin) are baselines, not
bounds. Standard errors for single probabilities are binomial, se = √(p̂(1 − p̂)/N), which is
0 at p̂ = 0 or 1 (one reason the Capacity interval is Hoeffding's, not a normal one).

**Common assumptions** (every card): the control family is fixed (phase on the Self, fixed
coupling, the specified equatorial readout); shots are independent and identically
distributed within a probe; the simulator implements the circuit as written (ideal, or its
stated noise model); the orientation canary passed, so the SelfWorld bit order is right.

**How the numbers were measured.** "Built-in simulator" rows are Qiskit `BasicSimulator`
runs under CPython 3.14.4 (qiskit 2.5.2, numpy 2.5.3) with `set_options(seed_simulator=11)`
unless another seed is named, 1,024 shots per probe, `mode=auto` (one 17-qubit tiled
circuit holding the four probes and the canaries), one `backend.run` per row. "Exact" rows
come from `qiskit.quantum_info` (ideal) or the project's density-matrix noise model with
IonQ's published Forte-1 depolarizing rates on our gates ("IonQ-like preset", an
approximation of IonQ's model, not a measurement). The seeds make the rows reproducible;
on Qollab the samples are fresh each run. Platform rows (the judge run on Qollab's built-in
simulator and one IonQ Forte 1 simulator job) are recorded by the captain per
[SUBMIT.md](../SUBMIT.md) §5–6.

---

## Card A: Intentions move the odds across the full range at zero coupling

### Claim

At zero World coupling (w = 0, γ = 0) and any perspective β, the two intent probes of one
job give P(Self = 1) = 0 for φ = β and P(Self = 1) = 1 for φ = β + π, so Capacity C = 1:
opposite intentions move the Self's odds across the entire range. (On a simulator, read
this as: *quantum theory predicts* C = 1 for this circuit family at γ = 0.)

### Assumptions

- The common assumptions above.
- "Opposite intentions" means the two phases φ = β and φ = β + π of the same job; Capacity
  is never assembled from history entries with other settings.
- The interval's guarantee holds at the endpoints 0 and 1 (Hoeffding is distribution-free;
  a normal interval would not be).

### Witness

**Capacity C = |p_high − p_low|** from `intent_low` and `intent_high`, with its 95%
Hoeffding interval. Ideal value: cos γ = **1** at w = 0, for every β (the two probes share
the readout, so Capacity does not depend on the perspective). Direction: higher is more
capacity; 1 is the maximum.

### Result ± se

| Run | p_low / p_high (± se) | C [95% interval] | Resolved? | Notes |
|---|---|---|---|---|
| Exact, no noise | 0 / 1 (exact) | 1.0000 (exact) | n/a | closed form; agrees with the statevector to 1.1×10⁻¹⁶ over the 819-point grid (README → Validation) |
| Exact, IonQ-like preset | 0.0056 / 0.9944 | 0.9888 | n/a | the published Forte-1 rates on our gates (the scale-1 row of `data/fwo_noise.json` at w = 0); an approximation of IonQ's model |
| Built-in simulator, seed 11, 1,024 shots per probe, one job (Act 1: φ = π/2, β = 0) | 0.0000 ± 0 (0/1024) / 1.0000 ± 0 (1024/1024) | **1.0000 [0.9075, 1.0000]** | **yes** | display P(Self = 1) = 0.485 (497/1024, ideal 0.5), O = 0.999 bits, I = 0.000 bits; orientation canary passed; flip rates 0.0 / 0.0; 0.03 s |
| Built-in simulator, seed 11, one job (Act 2: φ = π, β = 0) | 0.0000 / 1.0000 | 1.0000 [0.9075, 1.0000] | yes | display P(Self = 1) = 1.000 (1024/1024), O = 0.000 bits: predictability and capacity coexist |
| Qollab built-in simulator in the browser, one job, 1,024 shots per probe (φ = 140°, w = 0.52, β = 99°; 2026-10-10) | p_low / p_high not shown separately on the page | **0.667 [0.574, 0.760]** (ideal cos γ = 0.685) | **yes** | display P(Self = 1) = 0.234 (240/1024; Demon forecast 0.242), O = 0.786 bits, I = 0.328 bits; 0.1 s; a different setting from Act 1, so the ideal capacity is 0.685, not 1 |
| IonQ Forte 1 simulator (noise model forte-1), one remote job of 17 qubits, 1,024 shots per probe (φ = 222°, w = 0.20, β = 86°; 2026-10-10) | not shown separately on the page | **0.94 [0.84, 1.00]** (ideal cos γ = 0.951) | **yes** | O = 0.618 bits, I = 0.032 bits; job id `01a1296d-229a-70da-8d9b-2b90d19715e6`, wall time 11.46 s; shots seen 1,024 per probe (no rounding shortfall); canary passed, readout flip rates 0.00% / 0.00% (the published model has no readout term); in-browser versions python 3.14.2, qiskit 2.5.2, numpy 2.4.6, qiskit_ionq 1.0.2 |

The interval's lower limit 0.9075 = 1 − e is the conservative bound's price: at 1,024 shots
per probe nothing can be resolved more finely than e = 0.0925 even when every shot agrees.

### What this does NOT show

- That the Self "has" intentions or chooses anything: the phase is set by the user. Version
  one has no autonomous learning or goals.
- Anything a classical system could not do. A responsive classical model, a bit whose value
  is set by a switch, also has C = 1. The content of this card is the contrast with Card B.
- Anything about nature: this is a simulation of the circuit under the stated noise model.
- A neuroscience result, or evidence that quantum systems alone can be agents.
- Validity beyond the chosen controls: phase on the Self, fixed coupling, this readout.
- Agreement between one simulator and the closed form checks the implementation, not the
  world.

### Counterarguments

- **"Capacity measures the controller, not the Self."** True: C is a property of the
  control family and the state together, and the word *intention* is a designed label for
  a gate. The model says so on its explanation page; it claims an inspectable
  correspondence, not a discovery.
- **"Trivial by construction."** At γ = 0 the Self is a single qubit whose phase is dialled
  in, so C = 1 is guaranteed. Agreed; the interesting claim is that the *same* 50/50
  outcome can carry C = 1 here and C = 0 at full coupling (Card B).
- **"The readout decides the answer."** Changing β changes the observable, but both intent
  probes use the same readout, so Capacity is comparable across perspectives and the ideal
  value does not depend on β. Measured: at w = 0.5, β = 0 and β = 1.0 rad give display
  P(Self = 1) = 0.516 and 0.229 (ideal 0.500 and 0.202) with the same Capacity 0.7158
  [0.6233, 0.8083] (ideal 0.7071).

---

## Card B: At full coupling the Self is 50/50 for every intention and Capacity vanishes

### Claim

At full World coupling (w = 1, γ = π/2) the display probability P(Self = 1) is 1/2 for
every intention φ and every perspective β, and the two intent probes give the same
distribution, so Capacity C = 0: in this control family no intention reshapes the Self's
odds. (On a simulator: *quantum theory predicts* C = 0 at γ = π/2; a sampled run shows an
interval that includes zero.)

### Assumptions

- The common assumptions above.
- Only Self-phase control is allowed. The World is prepared and coupled but never
  controlled or post-selected, and the display readout measures the Self marginal.
- The shot count is finite, so "includes zero" is the strongest statement a sample can
  make; the estimate is never forced to zero.

### Witness

**Capacity's 95% Hoeffding interval includes zero** (the resolution rule above), with
Openness O ≈ 1 bit from the display probe showing that the outcome is still uncertain, and
the Demon's forecast p = 1/2 for every φ. Ideal values: C = cos(π/2) = **0**, O = **1 bit**,
and (Card C) Connection I = **1 bit**.

### Result ± se

| Run | p_low / p_high (± se) | C [95% interval] | Resolved? | O (bits) | Notes |
|---|---|---|---|---|---|
| Exact, no noise | 0.5 / 0.5 (exact) | 0.0000 (exact) | n/a | 1.000 | closed form |
| Exact, IonQ-like preset | 0.5 / 0.5 | 0.0000 | n/a | 1.000 | depolarizing noise cannot move a marginal that is already 1/2; it shows up in Connection instead (Card C: 0.953 bits) |
| Built-in simulator, seed 11, 1,024 shots per probe, one job (Act 3: φ = π/2, β = 0) | 0.5156 ± 0.0156 / 0.4854 ± 0.0156 | **0.0303 [0.0000, 0.1228]** | **no** | 0.998 | display P(Self = 1) = 0.525; I = 0.999 bits; the page says *No resolved influence at this shot count* |
| Built-in simulator, seeds 1 / 2 / 3, same settings | 0.4854 / 0.4873; 0.5215 / 0.5303; 0.5000 / 0.5127 | 0.0020 [0, 0.0945]; 0.0088 [0, 0.1013]; 0.0127 [0, 0.1052] | no / no / no | 1.000 / 0.998 / 1.000 | three more samples: the estimate wanders by a few hundredths and is never forced to zero |
| Platform runs at w = 1 | not run at w = 1 on the platform yet (optional) | | | | the two platform runs so far used w = 0.52 (built-in) and w = 0.20 (IonQ Forte 1); see Card A |

At 1,024 shots per probe the interval's upper limit is |d̂| + e, so it is at least 0.0925
wide whatever the sample. **Calibration** (`lab/experiments.fwo_coverage`, 2,000 seeded
runs per point at 1,024 shots per probe, `--seed 1`, shipped as `data/fwo_coverage.json`):
the interval contained the exact Capacity in 100.0% of runs at w = 0, 0.25, 0.5, 0.75
and 1; at w = 1 it reported "resolved" in **0 of 2,000** runs (no false influence; the bound
allows up to 5%); mean widths 0.093 / 0.169 / 0.185 / 0.185 / 0.111. An extra in-session
point at w = 0.9 (exact C = 0.156, just above e), same experiment and seed rule, not in the
shipped file: coverage 100.0%, resolved in 1,998 of 2,000 runs.

### What this does NOT show

- That the Self is "unfree" in any real sense, or that anything was lost. The information
  is in the World (Card C); coupling to an unmeasured partner is decoherence seen from the
  Self, and the model relabels that as constraint by choice.
- That no control could restore Capacity. **Joint control of Self and World** (a World
  dial, a disentangling step before readout, or conditioning on a World measurement) could
  undo the coupling; the result is specific to the chosen controls.
- That C = 0. An interval including zero is absence of evidence at this shot count: an
  effect smaller than about e = 0.09 is invisible at 1,024 shots per probe.
- Anything a classical system could not do: the intention-independent fair-coin baseline
  also has C = 0 and O = 1. "Uncertainty alone is not freedom" is a statement about this
  model's definitions, not about classical or quantum systems in general.
- Anything about nature, neuroscience, or quantum systems as agents. One simulator.

### Counterarguments

- **"Hidden, not destroyed."** A demon with access to both qubits could still steer the
  Self. True, and the model agrees: Capacity is relative to the allowed controls, which is
  why the explanation says *these* intention controls no longer reshape the odds.
- **"This is just decoherence with a story on top."** It is coherent coupling to a second
  qubit, which from the Self's side is indistinguishable from dephasing. The story is the
  point of the project and is declared as artistic construction; the physics underneath is
  standard and reproducible.
- **"Finite shots prove nothing."** Correct, and the card never claims C = 0 from a sample.
  The resolution rule exists so that a small estimate is reported with its interval and
  nothing more; the calibration above shows the rule keeping its promise.

---

## Card C: Coupling writes information into the World

### Claim

In the reference basis (Z on both qubits, no readout rotation), the classical mutual
information between the Self and World outcomes rises from 0 bits at w = 0 to 1 bit at
w = 1, following I = h(sin²γ/2) − ½·h(sin²γ) (0.3113 bits at w = 0.5), independently of the
intention φ. (On a simulator: *quantum theory predicts* this curve for the connection
probe.)

### Assumptions

- The common assumptions above.
- Connection uses the **connection probe's counts only**, in the fixed reference basis; the
  display basis can hide correlations and is never used for I.
- The plug-in (empirical) mutual information from counts is used as the estimator; it is
  biased upward at finite shots (see "What this does NOT show").

### Witness

**Connection I = Σ p(s,w)·log₂[p(s,w) / (p(s)·p(w))]** over the connection probe (zero terms
skipped). Ideal joint distribution (SelfWorld keys): p(00) = 1/2, p(01) = 0,
p(10) = cos²γ/2, p(11) = sin²γ/2. Ideal values: **0 / 0.3113 / 1.0000 bits** at
w = 0 / 0.5 / 1. Direction: higher means more shared information in this basis.

### Result ± se

| Run | I (bits) at w = 0 / 0.5 / 1 | Notes |
|---|---|---|
| Exact, no noise | 0.0000 / 0.3113 / 1.0000 (exact) | closed form; agrees with the statevector to 3.3×10⁻¹⁶ over the 819-point grid; `data/fwo_theory.json` carries the curve |
| Exact, IonQ-like preset | 0.0000 / 0.2919 / 0.9531 | w = 0 and 0.5 from the scale-1 rows of `data/fwo_noise.json`, w = 1 from `predict_json`'s live IonQ-like forecast; depolarizing noise erodes the correlation at full coupling even though it cannot move a marginal that is already 1/2 (Card B) |
| Built-in simulator, seed 11, 1,024 shots, one job per w | 0.0000 / 0.2895 / 0.9989 | w = 0: counts 00/10 = 532/492, World never 1; w = 0.5: 00/10/11 = 532/262/230; w = 1: 00/11 = 532/492, matching pairs only (Acts 1 and 3 and the w = 0.5 run of the README) |
| Qollab built-in simulator in the browser, one job (w = 0.52) | 0.328 bits at w = 0.52 (ideal 0.33) | 2026-10-10; same run as Card A |
| IonQ Forte 1 simulator, one remote job (w = 0.20) | 0.032 bits at w = 0.20 (ideal 0.03) | 2026-10-10; job id `01a1296d-229a-70da-8d9b-2b90d19715e6`, 11.46 s, 1,024 shots per probe |

### What this does NOT show

- **Not an entanglement certification.** Mutual information in one fixed basis is a
  correlation witness: a classical copy of the Self bit into the World gives I = 1 bit too.
  Certifying entanglement would need incompatible measurement settings (a CHSH-type probe,
  which the toolkit has and this project does not claim).
- Not that "the World knows" anything: it is a second qubit whose Z outcome is correlated
  with the Self's.
- Not visible in the display basis, which is why Connection has its own probe.
- At finite shots the plug-in estimate is biased upward by at most roughly
  (K − 1)/(2N ln 2) = 0.0021 bits for K = 4 outcomes and N = 1,024 (the Miller–Madow
  correction, not applied): a sampled I of 0.002 at w = 0 is noise, not information. (The
  seed-11 run at w = 0 read exactly 0.0000 because the World outcome never varied.)
- Anything about nature, neuroscience, or agency. One simulator.

### Counterarguments

- **"Classical correlation suffices, so the quantum part is decoration."** For this card,
  yes: Connection does not distinguish entangled from classically correlated. The quantum
  content of the project is in the *interference* that Cards A and B read out, where the
  same coupling that raises I lowers C through cos γ, and both come from one state.
- **"The estimator is biased."** Agreed, by at most a few thousandths of a bit at the
  default shots; the ideal curve is shown beside the estimate so the reader can see it.
- **"Why this basis?"** Any fixed basis is a choice. Z on both is the basis in which the
  coupling's which-alternative record is written, and it is declared in the drawer as the
  probe's basis rather than hidden.

This effort is supported by Qollab & IonQ
