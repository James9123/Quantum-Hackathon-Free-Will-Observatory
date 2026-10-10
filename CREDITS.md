# Credits

This effort is supported by Qollab & IonQ

## Team

| Name | Role |
|---|---|
| TODO(team): name | captain: submission, Qollab upload, IonQ run |
| TODO(team): name | TODO |
| TODO(team): name | TODO |

## AI disclosure

The code, tests and documentation in this repository were written with **substantial help
from an AI coding assistant (Claude Code, by Anthropic)**, directed and reviewed by the team.

What the humans did (TODO(team): confirm each line, add names and fix anything that
does not match what actually happened):

- **Idea and direction:** chose the project idea (TODO(idea)) and the CHSH reference
  experiment, and set the goals and constraints: Qiskit only, one job per IonQ run,
  honest simulator language, MIT license.
- **Review:** reviewed the assistant's changes and decided what to keep. TODO(team): say
  which parts a person read line by line.
- **Platform runs:** upload the project to Qollab, run it on the free simulators and on
  IonQ's simulator, and record the results. TODO(team): who ran what, and when.
- **Submission:** TODO(team): the captain's final checks and submission.

What the assistant did: wrote most of the code, tests and documentation drafts to the
team's direction; summarized the platform documentation
([docs/platform-notes.md](docs/platform-notes.md)); ran the local tests and the
off-platform sweeps; and ran the independent and adversarial review passes recorded in
[BUILDLOG.md](BUILDLOG.md), as separate assistant sessions that checked each module after
it was written. Those reviews are AI reviews, not human ones.

## Pre-existing work

**None.** Everything in this repository was created during the hackathon window (Fri
2026-10-09 17:00 MDT to Sun 2026-10-11 17:00 MDT). The repository was started at 22:53 MDT
on Friday, and [BUILDLOG.md](BUILDLOG.md) records what was built and when. The project uses
published physics results (papers below), open-source libraries (installed, not copied),
and public platform documentation. No code was copied from tutorials, courses or other
projects. TODO(team): confirm this statement before submitting. To be safe, treat anything
prepared before Fri 17:00 MDT as pre-existing work and list it here, including idea
shortlists, research notes, platform notes and planning documents, even if no code came
from them. If there is any, replace "None" with what it was and when it was made.

## Papers

Where each idea came from, and where it is used here. **Verification:** each reference
was checked against the publisher's or arXiv's listing (title, authors, volume, first page,
year) on 2026-10-09, except where marked otherwise. Before the final submission, someone
should still check the references against the original papers.

| Reference | Used for | Where | Checked |
|---|---|---|---|
| J. F. Clauser, M. A. Horne, A. Shimony & R. A. Holt, "Proposed experiment to test local hidden-variable theories", *Phys. Rev. Lett.* **23**, 880 (1969) | the CHSH inequality S ≤ 2 for local hidden-variable models | `chsh.py`, `qk_bounds.py` | yes |
| B. S. Tsirelson (Cirel'son), "Quantum generalizations of Bell's inequality", *Lett. Math. Phys.* **4**, 93 (1980) | the quantum maximum S = 2√2 | `chsh.py`, `qk_bounds.py` | yes |
| A. J. Leggett & A. Garg, "Quantum mechanics versus macroscopic realism: Is the flux there when nobody looks?", *Phys. Rev. Lett.* **54**, 857 (1985) | the Leggett–Garg K₃ witness and its macrorealist bound | `qk_bounds.py` | yes |
| C. Emary, N. Lambert & F. Nori, "Leggett–Garg inequalities", *Rep. Prog. Phys.* **77**, 016001 (2014) | review of Leggett–Garg inequalities, cited with the K₃ witness | `qk_bounds.py` | yes |
| N. D. Mermin, "Simple unified form for the major no-hidden-variables theorems", *Phys. Rev. Lett.* **65**, 3373 (1990) | the Mermin–Peres magic square | `qk_bounds.py` | yes |
| A. Peres, "Incompatible results of quantum measurements", *Phys. Lett. A* **151**, 107 (1990) | the Mermin–Peres magic square | `qk_bounds.py` | **partly:** confirmed only through secondary bibliographies, not the publisher's page |
| P. K. Aravind, "Quantum mysteries revisited again", *Am. J. Phys.* **72**, 1303 (2004) | the magic square as a two-player game | `qk_bounds.py` | yes |
| G. Brassard, A. Broadbent & A. Tapp, "Quantum pseudo-telepathy", *Found. Phys.* **35**, 1877 (2005) | the pseudo-telepathy framing of the magic-square game | `qk_bounds.py` | yes |
| T. Giurgica-Tiron, Y. Hindy, R. LaRose, A. Mari & W. J. Zeng, "Digital zero noise extrapolation for quantum error mitigation" (2020), arXiv:2005.10921 | zero-noise extrapolation by unitary folding | `qk_primitives.fold`, `qk_mitigation.zne`, `chsh.zne_exact` | yes (arXiv listing) |
| K. Temme, S. Bravyi & J. M. Gambetta, "Error mitigation for short-depth quantum circuits", *Phys. Rev. Lett.* **119**, 180509 (2017) | zero-noise (Richardson) extrapolation | `qk_mitigation.zne` | yes (arXiv journal reference) |
| E. B. Wilson, "Probable inference, the law of succession, and statistical inference", *J. Am. Stat. Assoc.* **22**, 209 (1927) | the Wilson score interval for win rates | `qk_estimators.win_rate` | yes |

**Our own designs** (no outside source claimed): one-job packing (tile, list and tiles
layouts); the canary blocks (the non-palindromic orientation check and the readout
calibration blocks); the exact density-matrix noise dial and its IonQ-like preset; claim
cards and their verdict rule; the error-bar coverage study; the dataset provenance format;
the upload checker and the hygiene scanner. They build on standard techniques:
tensor-product readout-confusion inversion, depolarizing channels, and linear programming
over the local polytope.

## Libraries

All installed from their official packages and used unmodified. None of their code is
copied into this repository.

| Library | Version | License | Used for |
|---|---|---|---|
| Qiskit | 2.5.2 | Apache-2.0 | circuits, transpilation, `BasicSimulator` (the project and the tests) |
| NumPy | 2.5.3 | BSD-3-Clause | the density-matrix noise dial and readout mitigation |
| SciPy | 1.18.1 | BSD-3-Clause; its bundled HiGHS solver is MIT | linear programs in `lab/bounds_lp.py` (lab only) |
| qiskit-aer | 0.17.2 | Apache-2.0 | **lab cross-checks only** (`chsh_aer_check.json`); not uploaded |
| pytest | 9.1.1 | MIT | tests (not uploaded) |
| qiskit-ionq (provided by Qollab) | as on the platform | Apache-2.0 | IonQ backends on Qollab. We never construct a backend; `qk_runtime` imports `ErrorMitigation` only if it is present |

The project is released under the [MIT License](LICENSE). The libraries above are under
permissive open-source licenses (Apache-2.0, BSD-3-Clause, MIT). As of this writing the
JS entry loads no external scripts; `tools/pack_for_qollab.py` flags any import from
outside cdn.jsdelivr.net, the only external host Qollab allows.

## Platform documentation

- Qollab documentation (qollab.xyz/learn/docs): runtime environment, Python and JS
  projects, compute backends, primitives, transpilation, error mitigation. Our summary of
  what the code relies on is in [docs/platform-notes.md](docs/platform-notes.md).
- IonQ, "Simulation with Noise Models":
  <https://docs.ionq.com/guides/simulation-with-noise-models>. This is the source of the
  Forte-1 depolarizing rates (r₁q = 2.67×10⁻⁴, r₂q = 4.95×10⁻³, for jobs before
  mid-September 2025) behind our IonQ-like preset; checked on 2026-10-09.
- The hackathon rules page (requirements and judging traits), mirrored in
  [SUBMIT.md](SUBMIT.md).

This effort is supported by Qollab & IonQ
