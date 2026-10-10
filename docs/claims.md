# Claims

Every result in this project is stated as a **claim card**, a record that connects a
number to everything a reader must accept before the number means anything:

**Claim → Assumptions → Witness → Result ± se → What this does NOT show → Counterarguments**

The project prints these cards when it runs. `qollab_project/qk_cards.py` builds them (as
JSON records) and renders them as plain text (`card_text`) or Markdown (`card_markdown`).
The CHSH card's wording lives in `qollab_project/chsh.py`, in `CLAIM`, `ASSUMPTIONS`,
`NOT_SHOWN` and `COUNTERARGUMENTS`. If you edit the card below, edit those constants too,
so the document and the program never disagree.

**Simulator rule.** On a simulator, a card's "result" is what quantum theory predicts under
the stated noise model. It is not a measurement of nature. Every simulator card carries
this note automatically:

> This is a simulation. It computes what quantum theory predicts, and how the chosen noise
> model degrades it; it is not a test of nature.

**Verdict rule** (fixed in advance, applied by the code, never chosen after the fact).
With *direction* "max" (classical models give value ≤ bound),
z = (value − bound) / se. The verdict uses the mitigated value when there is one, and the
raw value otherwise:

| z | Verdict |
|---|---|
| z ≥ 3 | exceeds classical bound |
| z ≤ 0 | consistent with classical bound |
| 0 < z < 3 | inconclusive |

A z-score speaks only to **statistical** error. The assumptions, the "does NOT show" list
and the counterarguments cover everything else.

---

## Card 1: CHSH (reference experiment)

### Claim

Two qubits prepared in |Φ+⟩ and measured at the CHSH angles give S above 2, the largest
value any local hidden-variable model allows.

(On a simulator, read this as: *quantum theory predicts* S above 2 for this preparation and
these angles. Alice measures along 0 or π/2 and Bob along π/4 or −π/4, all in the X–Z
plane, and S = E₀₀ + E₀₁ + E₁₀ − E₁₁.)

### Assumptions

The classical bound S ≤ 2 holds for every model that satisfies all three of these:

- **Locality:** Alice's outcome does not depend on Bob's setting, and vice versa.
- **Realism:** outcomes are fixed by pre-existing (hidden) variables.
- **Measurement independence:** settings are chosen independently of those variables.

### Witness

**CHSH.** Classical bound: S ≤ 2 (Clauser, Horne, Shimony & Holt 1969; checked here by
enumerating all 16 deterministic strategies, and by a linear program in
`lab/bounds_lp.py`). Quantum maximum: 2√2 ≈ 2.828 (Tsirelson 1980).

### Result ± se

| Run | S ± se | z vs 2 | Verdict | Notes |
|---|---|---|---|---|
| Exact, no noise | 2.828427 (exact) | n/a | n/a | density matrix, no sampling |
| Exact, IonQ-like preset | 2.8126 (exact) | n/a | n/a | IonQ's published Forte-1 simulator rates on our gates (an approximation) |
| Built-in simulator, 1000 shots, one job, seed 11 | 2.846 ± 0.044 | +19.0 | exceeds classical bound | ideal simulator; the canary passed and measured zero readout flips, so no mitigation |
| TODO: IonQ Forte simulator, one job | TODO | TODO | TODO | raw and readout-mitigated values, job id, date |

Noise budget (exact model): S = 2√2(1 − λ) under a two-qubit depolarizing channel λ, so S
reaches 2 at λ\* = 1 − 1/√2 ≈ 0.2929. The numerical crossing matches this to 2.5×10⁻¹¹.
With the IonQ-like preset scaled up, S stays above 2 through 53× the published rates. The
error bars' coverage was measured over 2000 seeded runs at each of four noise levels: 66.7–69.2%
of runs fall within 1 se (68.3% expected), and 94.2–95.7% within 2 se (95.4% expected).

### What this does NOT show

- Both qubits sit in one device (or one simulator), with no space-like separation between
  the measurements, so the locality loophole is wide open.
- Settings are fixed by the program, not chosen by independent random sources.
- This is a simulation. It computes what quantum theory predicts, and how the chosen noise
  model degrades it; it is not a test of nature.
- The IonQ-like preset is not IonQ's actual noise model (our gate decomposition, published
  pre-September-2025 rates, no readout term).
- The error bars cover shot noise only, not model error.

### Counterarguments

- **Superdeterminism:** if settings and hidden variables are correlated, any S is possible.
- **Nonlocal hidden-variable theories** (e.g. Bohmian mechanics) reproduce S = 2√2.
- **Many-worlds readings** avoid nonlocality by denying that each run has a single outcome.

---

## Card 2: TODO(idea), the chosen idea

Copy this template and fill in every field. A field that cannot be filled is a finding:
say so in the card rather than dropping the field. Put the same text in the idea module's
`CLAIM`, `ASSUMPTIONS`, `NOT_SHOWN` and `COUNTERARGUMENTS` constants so the printed card
matches.

### Claim

TODO(idea): one sentence, falsifiable, naming the system, the preparation, the measured
quantity and the threshold. On a simulator, phrase it as a prediction of quantum theory.

### Assumptions

TODO(idea): every assumption that the classical (or rival) bound needs, one per bullet.
If a rival model can drop an assumption, say which one.

- TODO
- TODO

### Witness

TODO(idea): the quantity (name and formula), its classical bound with a citation and how
this repo checks it (enumeration, LP or proof), the quantum ideal, and the direction ("max"
or "min").

### Result ± se

| Run | value ± se | z vs bound | Verdict | Notes |
|---|---|---|---|---|
| Exact, no noise | TODO | n/a | n/a | |
| Exact, noise preset | TODO | n/a | n/a | |
| Built-in simulator, N shots, one job | TODO | TODO | TODO | |
| IonQ simulator, one job | TODO | TODO | TODO | job id, date |

TODO(idea): the noise budget (where the witness crosses its bound) and the shots needed for 3σ.

### What this does NOT show

- This is a simulation. It computes what quantum theory predicts, and how the chosen noise
  model degrades it; it is not a test of nature.
- TODO(idea): loopholes, model limits, and what a skeptic would still be free to believe.

### Counterarguments

- TODO(idea): the strongest objections to the claim's *interpretation*, stated fairly.
