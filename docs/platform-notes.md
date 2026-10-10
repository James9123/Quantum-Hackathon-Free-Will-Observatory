# Qollab platform notes (for contributors)

What the code in this repo relies on about the Qollab runtime. Sources: Qollab docs
(qollab.xyz/learn/docs: runtime-environment, python-qiskit-projects, js-qiskit-projects,
compute-backends, primitives, transpilation, error-mitigation), the hackathon rules page,
IonQ's noise-model guide, and the qiskit-ionq / qiskit-braket-provider sources.
Read 2026-10-09; items marked *(smoke)* are confirmed or refuted by `smoke/` runs.

## Python projects
- Entry `main.py`. The runner executes one source string: its own prologue (creates the
  global `backend`), then `main.py`, then an appended call `main(<positional literals>)`.
  It runs in `__main__`'s namespace, so **never call `main()` yourself and never add an
  `if __name__ == "__main__":` block**: either would run `main()` twice.
- The Run-settings form exists only if `def main(` starts at column 0, the whole signature
  is on one line, and every parameter is annotated with a bare `int`, `float`, `str` or
  `bool` and has a literal, non-negative default. Otherwise main() is silently not called.
- `backend` is a global in `main.py` only. Pass it to other modules as an argument.
  Never construct a backend.
- `main()`'s return value is discarded; print what you want to show.
- Local imports: flat modules and packages both work (an import scanner prefetches them).
  Bundled packages (numpy, scipy, matplotlib) load when an import statement names them.
- Data files load only when a **literal relative path string** names them somewhere in the
  scanned Python (e.g. `open("data/chsh_noise.json")`). f-strings, `+` and `os.path.join`
  are not picked up. ≤100 files per project, ≤2 MB each. Loaders here take text, not paths.
- Each run is a fresh interpreter: no module state or files survive between runs.
- `input()` does not work. Network: GET/OPTIONS only (`pyodide.http.pyfetch`).

## JS projects (top-level `index.html` + `main.js` win over `main.py`)
- `index.html` is a body fragment injected with `innerHTML`: inline `<script>` and `on*`
  attributes never run. `main.css` is the only stylesheet loaded.
- `main.js` is transformed to CommonJS and run as an async function body; top-level
  `await` works; avoid `import.meta` and dynamic `import()`. It gets injected `backend`,
  `console` (log/info/warn/error/debug only) and `setTimeout`.
- Import Python by dotted module name: `import * as api from "ui_api"` or named imports;
  a default import gives `undefined`. JS files: `./` or `../` paths only.
- Call your Python with `.callPromising(...)` / `.callPromisingKwargs(...)` (mandatory for
  anything that submits to IonQ). Passing JSON strings both ways is the robust pattern.
  `print()` inside Python called from JS does not reach the console.
- Remote (IonQ) requests only route while `main.js` is still running: end it with
  `await new Promise(() => {})` if buttons submit jobs later.
- Sandbox: `allow-scripts` only (no popups, downloads, modals, storage). External JS only
  from cdn.jsdelivr.net. No Workers or WebSockets.

## Backends
| Dialog entry | Object | Notes |
|---|---|---|
| Built-in simulator | `BasicSimulator()` | ideal, 24 qubits |
| AWS Braket local | `BraketLocalBackend()` | ideal, 25; count keys not zero-padded |
| IBM noise models (8) | `qiskit_ibm_runtime` Fake backends on Aer | noisy, in browser; transpile first |
| IonQ Forte 1 / Forte Enterprise 1 (sim) | qiskit-ionq simulator + noise model | remote, 29, **one job per run** |
| IonQ Forte QPUs | qiskit-ionq QPU | credits; not used by this project |

- IonQ: one job per run. One `backend.run([c1, c2, ...])` is a single multi-circuit job
  *(smoke: list mode)*. Counts from noisy simulation are `round(prob × shots)`, so totals can
  differ slightly from `shots`.
- IonQ's cloud simulators never apply debiasing (QPU-only feature).
- IonQ strips barriers and recompiles server side, so gate folding for ZNE is likely undone
  there. Folding-based ZNE is used only with local simulators and our density-matrix model.
- `BackendSamplerV2` returns all zeros on IonQ; this project uses `backend.run` + `get_counts()`.

## IonQ noise model
IonQ documents its (pre-September-2025) Forte-1 simulator noise as one depolarizing channel
after each native gate, ρ → (1−r)ρ + r·I/d, with r₁q ≈ 2.67×10⁻⁴ and r₂q ≈ 4.95×10⁻³ (the
same convention as `qiskit_aer.noise.depolarizing_error`). No readout term is published, and
the current Forte models are documented as more complex. Our `IONQ_FORTE_LIKE` preset uses
these published rates on our own (non-native) gate decomposition, so it is an approximation.
