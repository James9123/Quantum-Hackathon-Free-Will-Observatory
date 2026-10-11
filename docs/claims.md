# Claims

Every result in this project is stated as a **claim card**, a record that connects a
number to everything a reader must accept before the number means anything:

**Claim → Assumptions → Witness → Result ± se → What this does NOT show → Counterarguments**

The format comes from the toolkit's claim cards (`qollab_project/qk_cards.py`), validated
on the CHSH reference in [reference/chsh/](../reference/chsh/). The Observatory's three
cards are below. The run record (`run_json`) carries the same readings, interval and
explanation text that these cards describe; if a card changes, the explanation copy in
`observatory_api.py` changes with it, so the document and the program never disagree.

**Simulator rule.** A card's "result" on a simulator is what quantum theory predicts under
the stated noise model. It is not a measurement of nature, and nothing here is evidence
about the physical world. Every simulator card carries this note:

> This is a simulation. It computes what quantum theory predicts, and how the chosen noise
> model degrades it; it is not a test of nature.

**Resolution rule** (fixed in advance, applied by the code, never chosen after the fact).
Capacity's uncertainty is the conservative 95% Hoeffding interval of
[docs/model.md §7](model.md#7-the-hoeffding-interval): e = √(ln 80/(2N_low)) + √(ln 80/(2N_high)),
about 0.0925 at 1,024 shots per probe.

| Interval for C | Reading |
|---|---|
| excludes zero (\|p̂_high − p̂_low\| > e) | **resolved**: the intentions moved the odds by at least the lower limit |
| includes zero | **"No resolved influence at this shot count."** Never "zero capacity", never "proven agency". |

There is no classical bound to exceed here: these claims are about a *designed* model's
predictions, and the two classical references (fixed output, fair coin) are baselines, not
bounds. Standard errors for single probabilities are binomial, se = √(p̂(1 − p̂)/N).

**Common assumptions** (every card): the control family is fixed (phase on the Self, fixed
coupling, the specified equatorial readout); shots are independent and identically
distributed within a probe; the simulator implements the circuit as written (ideal, or its
stated noise model); the orientation canary passed, so the SelfWorld bit order is right.

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
| Exact, no noise | 0 / 1 (exact) | 1.0000 (exact) | n/a | closed form; statevector check in the tests |
| Exact, IonQ-like preset | TODO(measure) | TODO(measure) | n/a | `data/fwo_noise.json`: IonQ's published Forte-1 rates on our gates, an approximation |
| Built-in simulator, 1,024 shots per probe, one job | TODO(measure) | TODO(measure) | TODO(measure) | seed, the orientation canary, flip rates |
| IonQ Forte 1 simulator, one job | TODO(measure) | TODO(measure) | TODO(measure) | job id, date, shots seen |

Expected at 1,024/1,024 shots on an ideal simulator: every low shot 0, every high shot 1,
C = 1.0000 with interval [0.9075, 1.0000] (the team's design note's seeded local example gave
exactly that; it is not this project's run).

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
  value does not depend on β.

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
| Exact, IonQ-like preset | TODO(measure) | TODO(measure) | n/a | TODO(measure) | `data/fwo_noise.json` |
| Built-in simulator, 1,024 shots per probe, one job | TODO(measure) | TODO(measure) | expected: no | TODO(measure) | at 1,024 shots the interval is at least [0, 0.0925] wide |
| IonQ Forte 1 simulator, one job | TODO(measure) | TODO(measure) | TODO(measure) | TODO(measure) | job id, date, shots seen |

Expected: an estimate of a few hundredths with an interval such as [0.00, 0.10], read as
*"No resolved influence at this shot count."* (The team's design note's seeded local example:
C = 0.0088, interval 0.0000–0.1013; not this project's run.) The coverage sweep
(`data/fwo_coverage.json`) measures how often such intervals contain the true difference:
TODO(measure).

### What this does NOT show

- That the Self is "unfree" in any real sense, or that anything was lost. The information
  is in the World (Card C); coupling to an unmeasured partner is decoherence seen from the
  Self, and the model relabels that as constraint by choice.
- That no control could restore Capacity. **Joint control of Self and World** (a World
  dial, a disentangling step before readout, or conditioning on a World measurement) could
  undo the coupling; the result is specific to the chosen controls.
- That C = 0. An interval including zero is absence of evidence at this shot count: an
  effect smaller than about e ≈ 0.09 is invisible at 1,024 shots per probe.
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
  nothing more.

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
| Exact, no noise | 0.0000 / 0.3113 / 1.0000 (exact) | closed form; `data/fwo_theory.json` carries the curve |
| Exact, IonQ-like preset | TODO(measure) | `data/fwo_noise.json` |
| Built-in simulator, 1,024 shots, one job | TODO(measure) | three runs (one per w), each one job |
| IonQ Forte 1 simulator, one job | TODO(measure) | one setting; job id, date, shots seen |

### What this does NOT show

- **Not an entanglement certification.** Mutual information in one fixed basis is a
  correlation witness: a classical copy of the Self bit into the World gives I = 1 bit too.
  Certifying entanglement would need incompatible measurement settings (a CHSH-type probe,
  which the toolkit has and this project does not claim).
- Not that "the World knows" anything: it is a second qubit whose Z outcome is correlated
  with the Self's.
- Not visible in the display basis, which is why Connection has its own probe.
- At finite shots the plug-in estimate is biased upward by at most roughly
  (K − 1)/(2N ln 2) ≈ 0.002 bits for K = 4 outcomes and N = 1,024 (the Miller–Madow
  correction, not applied): a sampled I of 0.002 at w = 0 is noise, not information.
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
