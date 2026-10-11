# Credits

This effort is supported by Qollab & IonQ

## Team

| Name | Role |
|---|---|
| TODO(team): name | captain: submission, Qollab upload, IonQ verification run |
| TODO(team): name | quantum owner: circuits, live execution, statistics, validation |
| TODO(team): name | experience owner: scene, personas, interface, video |

## The design

The two-qubit circuit (a Self qubit with a phase control, a coupled World qubit, an
equatorial readout), the four-probe experiment, the three readings (Capacity, Openness,
Connection) and the philosophical mapping ("the capacity to reshape possible futures", the
three personas, the central contrast between uncertainty and capacity) are the **team's
original design**. No paper proposes this model; it was written down in the team's design
note and build guide, both dated 10 October 2026, inside the hackathon window
(TODO(team): decide whether to add the build guide to `docs/`).

The gate definitions and the provider compilation route follow the official Qiskit and
IonQ documentation listed below. The controlled-RY decomposition (`RY(γ)`, `CX`, `RY(−γ)`,
`CX` equals `CRY(2γ)`) is the standard one.

## AI disclosure

The code, tests and documentation in this repository were written with **substantial help
from an AI coding assistant (Claude Code)**, directed and reviewed by the team. The
assistant worked from the team's build guide, which set the model, the probes, the
readings, the honesty language and the acceptance tests.

What the humans did (TODO(team): confirm each line, add names, and fix anything that does
not match what actually happened):

- **Idea and direction:** defined free will for this project as the capacity to reshape
  possible futures, chose the two-qubit model, the three personas and the four probes, and
  wrote the build guide; set the constraints: Qiskit only, one job per IonQ run, standard
  gates, honest simulator language, MIT license.
- **Review:** reviewed the assistant's changes and decided what to keep. TODO(team): say
  which parts a person read line by line.
- **Platform runs:** uploaded the project to Qollab, ran it on the free simulators and on
  IonQ's simulator, and recorded the results. TODO(team): who ran what, and when.
- **Video and submission:** TODO(team): who recorded the demo; the captain's final checks
  and submission.

What the assistant did: wrote most of the code, tests and documentation drafts to the
team's direction; summarized the platform documentation
([docs/platform-notes.md](docs/platform-notes.md)); ran the local tests and the
off-platform sweeps; and ran the independent and adversarial review passes recorded in
[BUILDLOG.md](BUILDLOG.md), as separate assistant sessions that checked each module after
it was written. Those reviews are AI reviews, not human ones.

## Pre-existing work

Everything in this repository was created during the hackathon window (Fri 2026-10-09
17:00 MDT to Sun 2026-10-11 17:00 MDT). The repository was started at 22:53 MDT on Friday,
and [BUILDLOG.md](BUILDLOG.md) records what was built and when. The Observatory's design
note and build guide are dated 10 October 2026, inside the window. The project uses
published results (references below), open-source libraries (installed, not copied) and
public platform documentation. No code was copied from tutorials, courses or other
projects.

TODO(team): confirm this statement before submitting. To be safe, treat anything prepared
before Fri 17:00 MDT as pre-existing work and list it here, including idea shortlists,
research notes and planning documents, even if no code came from them. If there is any,
say what it was and when it was made.

## References

Where each outside idea came from, and where it is used.

| Reference | Used for | Where |
|---|---|---|
| W. Hoeffding, "Probability inequalities for sums of bounded random variables", *J. Am. Stat. Assoc.* **58**, 13–30 (1963) | the conservative 95% interval for Capacity (two-sided bound per probe, union bound over the two intent probes) | `observatory_api.py`, [docs/model.md](docs/model.md) §7 |
| C. E. Shannon, "A mathematical theory of communication", *Bell Syst. Tech. J.* **27**, 379–423 and 623–656 (1948) | binary entropy (Openness) and mutual information (Connection) | `observatory_api.py`, [docs/model.md](docs/model.md) §5 |
| T. M. Cover & J. A. Thomas, *Elements of Information Theory*, 2nd ed., Wiley (2006) | the definitions and conventions used for O and I (0·log 0 = 0; plug-in estimate) | [docs/model.md](docs/model.md), [docs/claims.md](docs/claims.md) |
| IBM Qiskit, *CRYGate* API reference: <https://quantum.cloud.ibm.com/docs/en/api/qiskit/qiskit.circuit.library.CRYGate> | the controlled-Y-rotation definition and qubit (control/target) convention | the coupling gate and its test |
| IonQ, *Getting started with Qiskit*: <https://docs.ionq.com/sdks/qiskit/index> | provider setup, explicit measurement, multiple circuits in one job, result retrieval | `qk_runtime.py` |
| IonQ, *Compilation and native gates with Qiskit*: <https://docs.ionq.com/sdks/qiskit/native-gates-qiskit> | which standard gates are accepted and how IonQ compiles them | standard gates only (`h`, `rz`, `ry`, `cx`) |
| IonQ, *Simulation with noise models*: <https://docs.ionq.com/features/simulation-with-noise-models> | ideal versus noisy simulation, model limitations; the published Forte-1 depolarizing rates behind the IonQ-like preset | `qk_noise.py` |
| Qollab documentation (qollab.xyz/learn/docs): runtime environment, Python and JS projects, compute backends, transpilation, error mitigation | how a project is run, how `backend` is injected, data-file bundling, the one-job rule | [docs/platform-notes.md](docs/platform-notes.md) |
| Qollab, *Global Quantum Hackathon* (qollab.xyz/programs/hackathon) | the rules and judging traits, mirrored in [SUBMIT.md](SUBMIT.md) | |

The URLs were taken from the team's build guide, which checked them on 10 October 2026.
The three bibliographic entries are standard listings; TODO(team): confirm them against the
publisher's pages before submitting.

### Validation references

The toolkit was validated on CHSH before the Observatory existed
([reference/chsh/](reference/chsh/), not uploaded). The references its uploaded modules
still cite (checked against the publisher's or arXiv's listing on 2026-10-09):

| Reference | Used for | Where |
|---|---|---|
| J. F. Clauser, M. A. Horne, A. Shimony & R. A. Holt, "Proposed experiment to test local hidden-variable theories", *Phys. Rev. Lett.* **23**, 880 (1969) | the CHSH inequality S ≤ 2 | `qk_bounds.py`, `reference/chsh/` |
| B. S. Tsirelson (Cirel'son), "Quantum generalizations of Bell's inequality", *Lett. Math. Phys.* **4**, 93 (1980) | the quantum maximum 2√2 | `qk_bounds.py`, `reference/chsh/` |
| A. J. Leggett & A. Garg, *Phys. Rev. Lett.* **54**, 857 (1985); C. Emary, N. Lambert & F. Nori, *Rep. Prog. Phys.* **77**, 016001 (2014) | the Leggett–Garg K₃ witness and its bound | `qk_bounds.py` |
| N. D. Mermin, *Phys. Rev. Lett.* **65**, 3373 (1990); A. Peres, *Phys. Lett. A* **151**, 107 (1990); P. K. Aravind, *Am. J. Phys.* **72**, 1303 (2004); G. Brassard, A. Broadbent & A. Tapp, *Found. Phys.* **35**, 1877 (2005) | the Mermin–Peres magic square and its game form (Peres confirmed only through secondary bibliographies) | `qk_bounds.py` |
| T. Giurgica-Tiron, Y. Hindy, R. LaRose, A. Mari & W. J. Zeng, arXiv:2005.10921 (2020); K. Temme, S. Bravyi & J. M. Gambetta, *Phys. Rev. Lett.* **119**, 180509 (2017) | zero-noise extrapolation by unitary folding (lab and reference only) | `qk_mitigation.py`, `qk_primitives.py` |
| E. B. Wilson, *J. Am. Stat. Assoc.* **22**, 209 (1927) | the Wilson score interval | `qk_estimators.py` |

**Our own toolkit designs** (no outside source claimed): one-job packing (tile, list and
tiles layouts); the canary blocks (the non-palindromic orientation check and the readout
calibration blocks); the exact density-matrix noise model and its IonQ-like preset; claim
cards; the error-bar coverage study; the dataset provenance format; the upload checker and
the hygiene scanner. They build on standard techniques: depolarizing channels,
tensor-product readout-confusion inversion, and linear programming over the local polytope.

## Libraries

All installed from their official packages and used unmodified. None of their code is
copied into this repository.

| Library | Version | License | Used for |
|---|---|---|---|
| Qiskit | 2.5.2 | Apache-2.0 | circuits, transpilation, `BasicSimulator` (the project and the tests) |
| NumPy | 2.5.3 | BSD-3-Clause | the density-matrix noise model, the statevector checks |
| SciPy | 1.18.1 | BSD-3-Clause; its bundled HiGHS solver is MIT | linear programs in `lab/bounds_lp.py` (lab only) |
| three.js | as provided by Qollab's import map | MIT | the brain-shaped scene in the JS entry (the only external script) |
| qiskit-aer | 0.17.2 | Apache-2.0 | **lab cross-checks only**; not uploaded |
| pytest | 9.1.1 | MIT | tests (not uploaded) |
| qiskit-ionq (provided by Qollab) | as on the platform | Apache-2.0 | IonQ backends on Qollab. We never construct a backend; `qk_runtime` imports `ErrorMitigation` only if it is present |

The project is released under the [MIT License](LICENSE). The libraries above are under
permissive open-source licenses (Apache-2.0, BSD-3-Clause, MIT). `tools/pack_for_qollab.py`
flags any script import from a host other than cdn.jsdelivr.net, the only external host
Qollab allows.

## Platform documentation

- Qollab documentation (qollab.xyz/learn/docs). Our summary of what the code relies on is
  in [docs/platform-notes.md](docs/platform-notes.md).
- IonQ, "Simulation with Noise Models": the source of the Forte-1 depolarizing rates
  (r₁q = 2.67×10⁻⁴, r₂q = 4.95×10⁻³, for jobs before mid-September 2025) behind the
  IonQ-like preset; read on 2026-10-09.
- The hackathon rules page (requirements and judging traits), mirrored in
  [SUBMIT.md](SUBMIT.md).

This effort is supported by Qollab & IonQ
