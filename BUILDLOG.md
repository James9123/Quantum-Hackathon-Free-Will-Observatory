# Build log

All times are MDT (UTC-6). The hackathon window opened Fri 2026-10-09 17:00 MDT.
This log records what was built and when; it is the "built during the window" record.

| When (MDT) | What |
|---|---|
| Fri 2026-10-09 22:53 | Repo created (`git init`, MIT `LICENSE`, layout). Python 3.14 venv: qiskit 2.5.2, numpy 2.5.3, scipy 1.18.1, pytest; qiskit-aer 0.17.2 for cross-checks only. |
| Fri 2026-10-09 23:00 | `qk_runtime.py` (backend profile, one-job run wrapper with guard, count normalization) and `qk_packer.py` (tile / list / multi-tile packing, canary orientation + readout-calibration blocks, unpacker with orientation diagnostics). |
| Fri 2026-10-09 23:03 | `smoke/` platform smoke-test project; local runner `tools/run_smoke_local.py`. Local BasicSimulator run: CHSH S = 2.846 ± 0.044, one job, 0.2 s. |
| Fri 2026-10-09 23:04 | Tests: 43 passing (count normalization, backend profiles, one-job guard, packed-vs-separate agreement within 3σ, exact-marginal checks, canary diagnostics, smoke end to end). |
| Fri 2026-10-09 23:10 | Platform research digest (`docs/platform-notes.md`): how Qollab invokes `main()`, imports, data files, JS projects, backends, IonQ noise-model conventions. Smoke test hardened accordingly (top-level imports for the import scanner; IonQ qubit-count fallback; Qollab-runner emulation in `tools/run_smoke_local.py`). |
| Fri 2026-10-09 23:35 | P1 modules: `qk_primitives` (Bell/GHZ, measure-along, Pauli basis change, parity→ancilla, CNOT copy, unitary folding), `qk_estimators` (parities, witnesses, Wilson intervals, z vs bound, shot power, bootstrap), `qk_bounds` (CHSH, Leggett–Garg K3, CHSH game, magic square; brute-force classical bounds; exact quantum values), `qk_noise` (exact density-matrix noise dial, IonQ-like preset), `qk_mitigation` (readout inversion, ZNE), `qk_cards` (claim cards), `qk_data` (dataset schema with provenance). Each written and then independently reviewed. |
| Fri 2026-10-09 23:45 | CHSH reference experiment (`qollab_project/chsh.py`, `main.py`) end to end: one packed job → canary → readout mitigation → claim card. Noise dial reproduces S = 2√2(1−λ) and λ* = 1 − 1/√2; agrees with qiskit-aer's density-matrix simulator to 1e-15. ZNE (folds 1,3,5) moves S from 2.620 to 2.784 (ideal 2.828) under 1%/5% depolarizing noise. Off-platform tools: `lab/sweep.py`, `lab/experiments.py`, `lab/bounds_lp.py` (LP: CHSH local max 2, Tsirelson critical visibility 1/√2). |
