# Build log

All times are MDT (UTC-6). The hackathon window opened Fri 2026-10-09 17:00 MDT.
This log records what was built and when; it is the "built during the window" record.

| When (MDT) | What |
|---|---|
| Fri 2026-10-09 22:53 | Repo created (`git init`, MIT `LICENSE`, layout). Python 3.14 venv: qiskit 2.5.2, numpy 2.5.3, scipy 1.18.1, pytest; qiskit-aer 0.17.2 for cross-checks only. |
| Fri 2026-10-09 23:00 | `qk_runtime.py` (backend profile, one-job run wrapper with guard, count normalization) and `qk_packer.py` (tile / list / multi-tile packing, canary orientation + readout-calibration blocks, unpacker with orientation diagnostics). |
| Fri 2026-10-09 23:03 | `smoke/` platform smoke-test project; local runner `tools/run_smoke_local.py`. Local BasicSimulator run: CHSH S = 2.846 ± 0.044, one job, 0.2 s. |
| Fri 2026-10-09 23:04 | Tests: 43 passing (count normalization, backend profiles, one-job guard, packed-vs-separate agreement within 3σ, exact-marginal checks, canary diagnostics, smoke end to end). |
