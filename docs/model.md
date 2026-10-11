# The model

The exact two-qubit experiment behind the Free Will Observatory, every reading's definition,
the bit-order rule, the uncertainty interval, and what none of it shows. The fiction is
intentional; the circuit behaviour underneath it is reproducible, and this page is the
specification the code is tested against (`model_version` = `fwo-1`).

**Conventions.** Self = q0, World = q1, both start in |0⟩. Ket order is **Self, World**
throughout. All internal angles are radians. The user-facing slider w maps to the coupling
angle γ = w·π/2.

## 1. The circuit

| Control | Operation | Range (default) | Why it earns its name |
|---|---|---|---|
| Intention | `RZ(φ)` on the Self | 0 to 2π (π/2) | varying the phase changes how the two alternatives recombine |
| World coupling | controlled-`RY(2γ)`, control Self, target World | w: 0 to 1 (0) | it correlates the Self with a second system |
| Perspective | `RZ(−β)` then `H` on the Self, then measure Z | 0 to π (0) | it changes the measured observable |

Circuit order:

```
prepare |00>
H(Self)
RZ(phi, Self)
controlled-RY(2*gamma, control = Self, target = World)
RZ(-beta, Self)
H(Self)
measure Self and World
```

The controlled rotation is written with standard gates only, so every backend (and IonQ's
compiler) takes it unchanged: `RY(γ)` on the World, `CX(Self → World)`, `RY(−γ)` on the
World, `CX(Self → World)`. That block equals Qiskit's `CRYGate(2γ)` exactly (checked
numerically in the tests). The first `H` creates the alternatives; the phase controls how
they recombine; the coupling writes which-alternative information into the World; the final
`RZ` and `H` pick an equatorial measurement direction and turn interference into ordinary
bit probabilities.

The Self phase and the readout phase are different conceptual controls even though the ideal
probability depends only on their difference; the interface keeps their names distinct.

## 2. The state before readout

Dropping global phases:

1. After `H` and `RZ(φ)` on the Self: (|0⟩ + e^{iφ}|1⟩)/√2 ⊗ |0⟩.
2. The controlled rotation acts only on the Self = 1 branch, where the World becomes
   `RY(2γ)`|0⟩ = cos γ |0⟩ + sin γ |1⟩.

So, before readout,

```
|ψ> = [ |00> + e^{i phi} cos(gamma) |10> + e^{i phi} sin(gamma) |11> ] / sqrt(2)
```

The World's marginal is P(World = 1) = sin²γ / 2 and does not depend on φ or β. The Self's
reduced state has the off-diagonal element e^{iφ} cos γ / 2: the interference visibility
available to any equatorial readout is **cos γ**. This is coherent coupling, not a noise
slider; the information is in the World, not lost.

## 3. The display probability

Write θ = φ − β. `RZ(−β)` turns e^{iφ} into e^{iθ} (up to a global phase). `H` on the Self
maps |0⟩ → (|0⟩ + |1⟩)/√2 and |1⟩ → (|0⟩ − |1⟩)/√2. Collecting the Self = 1 amplitudes:

| Outcome (Self, World) | Amplitude | Probability |
|---|---|---|
| (1, 0) | (1 − e^{iθ} cos γ) / 2 | (1 − 2 cos γ cos θ + cos²γ) / 4 |
| (1, 1) | −e^{iθ} sin γ / 2 | sin²γ / 4 |
| (0, 0) | (1 + e^{iθ} cos γ) / 2 | (1 + 2 cos γ cos θ + cos²γ) / 4 |
| (0, 1) | e^{iθ} sin γ / 2 | sin²γ / 4 |

Adding the first two rows (cos²γ + sin²γ = 1):

```
P(Self = 1) = [ 1 - cos(gamma) * cos(phi - beta) ] / 2
```

At zero coupling (γ = 0) the intention sweeps P(Self = 1) from 0 (θ = 0) to 1 (θ = π). At
full coupling (γ = π/2) the Self marginal is 1/2 for every intention and every perspective.
The closed form is checked against an exact statevector over a grid of (φ, w, β) in the
tests; the team's design note reported 819 combinations agreeing to better than 1.1×10⁻¹⁵.

## 4. The probes

Four two-qubit circuits make one run, submitted together as one job. Their names and
results are kept separate.

| Probe | Settings | Purpose |
|---|---|---|
| `display` | user φ, γ, β; full circuit | drives the visible future distribution; the source of Openness |
| `intent_low` | φ = β; same γ and β | one end of the accessible probability range: ideal p_low = (1 − cos γ)/2 |
| `intent_high` | φ = β + π; same γ and β | the opposite end: ideal p_high = (1 + cos γ)/2 |
| `connection` | user φ and γ; **no** final `RZ(−β)`/`H`; measure both qubits in Z | shared information in a fixed reference basis; the source of Connection |

Default 1,024 shots per probe (4,096 sampled executions per click), capped at 4,096 per
probe. Angles above 2π are equivalent modulo 2π. Capacity is never estimated by comparing
history entries with different coupling or readout settings: both intent probes always come
from the same job as the display probe.

## 5. The readings

Raw counts are stored first; every metric is computed from counts, never from the
animation. p is a probability estimated as counts / shots seen.

| Reading | Exact calculation | Interpretation | Ideal value |
|---|---|---|---|
| **Capacity C** | \|p_high − p_low\| from the two intent probes | total variation distance between the two binary Self distributions; the primary fictional agency measure, 0 to 1 | cos γ |
| **Openness O** | −p·log₂p − (1 − p)·log₂(1 − p) with 0·log₂0 = 0, on the display p = P(Self = 1) | uncertainty of the current Self outcome, 0 to 1 bit. Uncertainty is **not** capacity. | h([1 − cos γ cos θ]/2) |
| **Connection I** | Σ_{s,w} p(s,w)·log₂[p(s,w) / (p(s)·p(w))] over the connection probe's counts only, skipping zero terms | classical mutual information between Self and World in the reference measurement, 0 to 1 bit; not a general entanglement witness | h(sin²γ/2) − ½·h(sin²γ) |

h(x) = −x·log₂x − (1 − x)·log₂(1 − x) is the binary entropy. In the connection probe the
ideal joint distribution (SelfWorld keys) is p(00) = 1/2, p(01) = 0, p(10) = cos²γ/2,
p(11) = sin²γ/2, so the Self marginal is 1/2 whatever the coupling, and I depends on γ only.

Ideal values at the settings used in the demo (β = 0):

| w | γ | p_low / p_high | C | I (bits) | display p at φ = π/2 | O at φ = π/2 |
|---|---|---|---|---|---|---|
| 0 | 0 | 0.0000 / 1.0000 | 1.0000 | 0.0000 | 0.5 | 1 bit |
| 0.5 | π/4 | 0.1464 / 0.8536 | 0.7071 | 0.3113 | 0.5 | 1 bit |
| 1 | π/2 | 0.5000 / 0.5000 | 0.0000 | 1.0000 | 0.5 | 1 bit |

At φ = π (still w = 0) the display p is 1 and O is 0 bits while C stays 1: predictability
and capacity coexist. These numbers are closed-form consequences of the formulas above, not
run results; the shrinking p_low/p_high range is the quantity the capacity probes estimate.

The readings are never averaged into a single "free will percentage". When Capacity is shown
as a percentage it is labelled *Capacity in this model* and defined in the drawer.

## 6. Bit order

The app's canonical order is **SelfWorld**: `10` means Self = 1, World = 0, and
p = [counts[`10`] + counts[`11`]] / N, with absent outcomes filled with zero.

Qiskit writes classical bit 0 at the **right** end of a count key. A probe measured as
[Self = q0 → c0, World = q1 → c1] therefore comes back as c1c0 = **WorldSelf**. The
two-bit strings are reversed **once**, at the adapter boundary between `qk_packer`'s
block-local counts and the Observatory's readings, and nowhere else.

The test that catches a mistake: flip q0 only (`X` on the Self, nothing on the World) and
measure. Qiskit reports the key `01`; the app must report `10` with certainty. A reversed
mapping would report `01`, and a mapping applied twice would report `01` as well.

Independently of that unit test, every job carries two canary blocks from `qk_packer`:
an **orientation** block prepared as `110` (a key that is not a palindrome, so a reversed
or scrambled register is diagnosed rather than absorbed) and a **readout calibration** block
that measures the per-bit flip rates P(1|0) and P(0|1). The run record reports them as
`bit_order_check.orientation_ok`, `p_flip_0to1_mean` and `p_flip_1to0_mean`. The flip rates
are reported, not corrected.

## 7. The Hoeffding interval

Near zero capacity the question is whether a small estimate means anything, so the interval
must be honest there.

**Setup.** For one probe with N independent shots, the indicator of Self = 1 is a bounded
random variable in [0, 1] and p̂ is its mean. Hoeffding's inequality gives, for any t > 0,

```
P( |p_hat - p| >= t ) <= 2 * exp(-2 * N * t^2)
```

**Choice of t.** Set the right-hand side to 1/40: t(N) = √(ln 80 / (2N)).

**Union bound over the two intent probes.** The probability that *either* estimate misses
by its t is at most 1/40 + 1/40 = 1/20. On the complementary event, which has probability
at least 95%,

```
|d_hat - d| <= t(N_low) + t(N_high) = e,   with   d = p_high - p_low
e = sqrt(ln(80) / (2 * N_low)) + sqrt(ln(80) / (2 * N_high))
```

**The intervals.** For the signed difference: [d̂ − e, d̂ + e], clipped to [−1, 1] because
|d| ≤ 1. For C = |d|, map the interval through the absolute value: if it spans zero, the
lower limit is 0 and the upper limit is the largest endpoint magnitude; otherwise both
limits are the endpoint magnitudes in order. A result is **resolved** when the interval
excludes zero, which is exactly |d̂| > e.

**Size.** At 1,024 shots per probe, ln 80 ≈ 4.382 and e ≈ 2 × 0.0463 ≈ **0.0925**. The bound
is distribution-free and therefore conservative: a normal-approximation 95% interval for d
at p ≈ 1/2 would be about half as wide. That is the price of a guarantee that holds at
every p, including the endpoints 0 and 1 where normal intervals fail. N_low and N_high are
the shots actually seen per probe (IonQ's noisy simulators report counts as
round(probability × shots), so totals can differ slightly from the request).

**What the user sees.** "Capacity 0.01; conservative 95% interval 0.00–0.10." If the
interval includes zero: *"No resolved influence at this shot count."* A tiny positive
estimate is never described as proven agency, and the estimate is never forced to zero.

**What the interval assumes.** Independent, identically distributed shots within each probe
(true of the ideal and sampled simulators). It covers shot noise only: not noise-model
error, not readout bias (reported by the canary, not corrected), not the choice of model.

## 8. The Demon's forecast and the baselines

Laplace's Demon displays the derived P(Self = 1), p_low, p_high, Capacity, Openness and
Connection for the chosen settings before any result arrives (`predict_json`), and compares
them with the sampled values afterwards. It understands the probability law; it does not
see the shots in advance. Two theoretical classical references sit beside it, labelled as
such: a **fixed-output** model (Capacity 0, Openness 0) and an intention-independent
**fair coin** (Capacity 0, Openness 1). Their contrast explains the metric. It is not a
proof that classical systems cannot have capacity: a classical bit set by a switch has
Capacity 1.

## 9. Noise

The default experiments run on an ideal simulator; the Qollab backends with noise models
(the in-browser IBM models and IonQ's cloud simulators) degrade the readings according to
*their* models. The Demon also shows an IonQ-like prediction (`noisy_ionq_like`) computed by
the project's exact density-matrix noise model with IonQ's published Forte-1 simulator
depolarizing rates applied to our own gate decomposition. It is an approximation of IonQ's
noise, a modeled degradation, not a hardware measurement; `data/fwo_noise.json` carries the
same preset across the whole coupling range.

## 10. What this does NOT show

- **Nothing about nature.** Simulators compute what quantum theory predicts and how a noise
  model degrades it. The measurements are real outputs of the simulator; the Self and its
  philosophical meaning are the team's artistic construction.
- **Not discovered, designed.** Phase is called intention, coupling is called World
  influence and the readout angle is called perspective because each points to an
  inspectable operation. The words are labels for gates.
- **Specific to this control family:** phase changes on the Self, fixed coupling, the
  specified readout. **Joint control of Self and World could undo their coupling** and
  restore Capacity at w = 1. The score is not a universal property of the state.
- **Not a neuroscience model, and not evidence that quantum systems alone can be agents.**
  Users supply the intention input; version one has no autonomous learning or goals.
- **A responsive classical model can also score highly.** Capacity measures how far an
  external input moves the odds, which a classical switch does perfectly.
- **Connection is not an entanglement certification.** A classical copy of the Self bit
  into the World gives the same mutual information in the reference basis, and the display
  basis can hide correlations, which is why Connection uses its own probe.
- **"Not resolved" is not "zero".** An interval that includes zero means the shot count
  cannot see an effect smaller than about e; it is absence of evidence.
- **The interval covers shot noise only.**
- **One simulator per run.** Agreement between the closed form and a simulator is a check
  of the implementation, not of the world.

## 11. The contract in brief

`qollab_project/observatory_api.py` exposes the model to the page as JSON strings:
`profile_json` (backend profile, preferred packing mode, one-job flag, versions),
`predict_json` (the ideal readings, per-probe distributions with SelfWorld keys, the
IonQ-like noisy prediction, the two baselines), `run_json` (one job, then settings, source
record with job evidence and `shots_seen`, canonical counts, metrics with
`capacity_ci95` and `resolved`, the prediction, and factual plus persona explanations; on
any exception a `failed` status with whatever is known), `explain_json` (one persona's
explanation for a result) and `curves_json` (the three shipped datasets with provenance, or
an exact fallback computed in the session). Invalid settings never raise: they come back as
a `failed` record with the reason.
