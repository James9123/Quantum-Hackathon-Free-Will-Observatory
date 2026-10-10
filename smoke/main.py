"""Qollab platform smoke test.

Settles platform unknowns before any experiment depends on them:
versions, the injected backend, package vs flat imports, data-file loading,
Run-settings form types, count-key format and bit order (canary blocks),
one-job packing (tile vs list), IonQ debiasing, density-matrix speed.

Run it once per backend. It submits exactly ONE job per press of Run.
Paste the whole console output back, especially the SMOKE SUMMARY block.
"""

import json
import math
import os
import sys
import time
import traceback

# Top-level imports so Qollab's pre-run import scanner fetches our modules and loads
# the bundled scipy/matplotlib. Failures are recorded and reported, never fatal.
_IMPORT_ERRORS = {}
try:
    import qk_runtime
    import qk_packer
except Exception as _exc:          # reported in section 2
    qk_runtime = qk_packer = None
    _IMPORT_ERRORS["flat"] = _exc
try:
    import pkgtest
except Exception as _exc:
    pkgtest = None
    _IMPORT_ERRORS["package"] = _exc
try:
    import scipy
except Exception as _exc:
    scipy = None
    _IMPORT_ERRORS["scipy"] = _exc
try:
    import matplotlib
except Exception as _exc:
    matplotlib = None
    _IMPORT_ERRORS["matplotlib"] = _exc

SMOKE_VERSION = "smoke-3"
_RUN_COUNTER = [0]          # survives only if the interpreter is reused between runs
_MARKER = "/tmp/qollab_smoke_marker.txt"
SUMMARY = []


def _note(key, value):
    SUMMARY.append((key, value))


def _section(title):
    print("\n== %s ==" % title)


def _fail(label, exc):
    print("  %s: FAILED %s: %s" % (label, type(exc).__name__, exc))
    tb = traceback.format_exc().strip().splitlines()
    for line in tb[-6:]:
        print("    | " + line)


def _version(modname):
    try:
        mod = __import__(modname)
        return getattr(mod, "__version__", "present(no __version__)")
    except Exception as exc:
        return "MISSING(%s)" % type(exc).__name__


def _as_bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on", "y", "t")
    return bool(v)


def _find_backend():
    g = globals()
    if g.get("backend") is not None:
        return g["backend"], "main.py globals"
    import builtins
    if getattr(builtins, "backend", None) is not None:
        return builtins.backend, "builtins"
    try:
        import __main__
        if getattr(__main__, "backend", None) is not None:
            return __main__.backend, "__main__"
    except Exception:
        pass
    return None, "not found"


# ---------------------------------------------------------------- density matrix bench

def _bench_circuit(n):
    from qiskit import QuantumCircuit
    qc = QuantumCircuit(n)
    qc.h(0)
    for q in range(n - 1):
        qc.cx(q, q + 1)
    for q in range(n):
        qc.ry(0.3 + 0.1 * q, q)
    for q in reversed(range(n - 1)):
        qc.cx(q, q + 1)
    return qc


def _np_apply_unitary(rho, u, qs, n):
    import numpy as np
    k = len(qs)
    ut = np.asarray(u).reshape([2] * (2 * k))
    rows = [n - 1 - q for q in reversed(qs)]
    cols = [2 * n - 1 - q for q in reversed(qs)]
    rho = np.tensordot(ut, rho, axes=(list(range(k, 2 * k)), rows))
    rho = np.moveaxis(rho, list(range(k)), rows)
    rho = np.tensordot(rho, ut.conj(), axes=(cols, list(range(k, 2 * k))))
    rho = np.moveaxis(rho, list(range(2 * n - k, 2 * n)), cols)
    return rho


_LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _np_depolarize(rho, lam, qs, n):
    """(1-lam) rho + lam * (I/d on qs) (x) Tr_qs(rho), on the (2,)*2n tensor."""
    import numpy as np
    if lam == 0:
        return rho
    k = len(qs)
    rows = [n - 1 - q for q in reversed(qs)]
    cols = [2 * n - 1 - q for q in reversed(qs)]
    full = list(_LETTERS[: 2 * n])
    traced = list(full)
    for r, c in zip(rows, cols):
        traced[c] = traced[r]
    rest = [a for a in range(2 * n) if a not in rows and a not in cols]
    reduced = np.einsum("".join(traced) + "->" + "".join(full[a] for a in rest), rho)
    eye = np.eye(2 ** k).reshape([2] * (2 * k)) / 2 ** k
    spec = ("".join(full[a] for a in rows + cols) + "," + "".join(full[a] for a in rest)
            + "->" + "".join(full))
    return (1 - lam) * rho + lam * np.einsum(spec, eye, reduced)


def _np_noisy_dm(qc, lam1, lam2):
    import numpy as np
    from qiskit.quantum_info import Operator
    n = qc.num_qubits
    rho = np.zeros([2] * (2 * n), dtype=complex)
    rho[(0,) * (2 * n)] = 1.0
    for inst in qc.data:
        qs = [qc.find_bit(q).index for q in inst.qubits]
        rho = _np_apply_unitary(rho, Operator(inst.operation).data, qs, n)
        rho = _np_depolarize(rho, lam1 if len(qs) == 1 else lam2, qs, n)
    return rho.reshape(2 ** n, 2 ** n)


def _qiskit_noisy_dm(qc, lam1, lam2):
    import numpy as np
    from qiskit.quantum_info import DensityMatrix, Kraus, Operator, Pauli

    def depol(k, lam):
        labels = [""]
        for _ in range(k):
            labels = [a + b for a in labels for b in "IXYZ"]
        d2 = 4 ** k
        ops = []
        for lab in labels:
            w = (1 - lam + lam / d2) if set(lab) == {"I"} else lam / d2
            ops.append(np.sqrt(w) * Pauli(lab).to_matrix())
        return Kraus(ops)

    k1, k2 = depol(1, lam1), depol(2, lam2)
    dm = DensityMatrix.from_label("0" * qc.num_qubits)
    for inst in qc.data:
        qs = [qc.find_bit(q).index for q in inst.qubits]
        dm = dm.evolve(Operator(inst.operation), qargs=qs)
        dm = dm.evolve(k1 if len(qs) == 1 else k2, qargs=qs)
    return dm.data


def _density_bench():
    import numpy as np
    results = {}
    for n, budget_s in ((6, None), (8, 0.75), (10, 0.75)):
        if budget_s is not None:
            prev = results.get(n - 2)
            if prev is None or prev["numpy_s"] > budget_s:
                break
        qc = _bench_circuit(n)
        t0 = time.perf_counter()
        a = _qiskit_noisy_dm(qc, 0.01, 0.05) if n <= 8 else None   # cross-check only at small n
        t1 = time.perf_counter()
        b = _np_noisy_dm(qc, 0.01, 0.05)
        t2 = time.perf_counter()
        results[n] = {
            "gates": len(qc.data),
            "qiskit_kraus_s": round(t1 - t0, 4) if a is not None else -1.0,
            "numpy_s": round(t2 - t1, 4),
            "max_abs_diff": float(np.max(np.abs(a - b))) if a is not None else -1.0,
            "trace": round(float(np.real(np.trace(b))), 9),
        }
        if a is None:
            print("  DM n=%d gates=%d qiskit+Kraus skipped  numpy %.3fs  max|diff| n/a"
                  % (n, results[n]["gates"], t2 - t1))
        else:
            print("  DM n=%d gates=%d qiskit+Kraus %.3fs  numpy %.3fs  max|diff| %.2e"
                  % (n, results[n]["gates"], t1 - t0, t2 - t1, results[n]["max_abs_diff"]))
    return results


# ---------------------------------------------------------------- CHSH blocks

CHSH_SETTINGS = [  # (name, theta_A, theta_B, sign in S)
    ("chsh_a0b0", 0.0, 0.7853981633974483, +1),
    ("chsh_a0b1", 0.0, -0.7853981633974483, +1),
    ("chsh_a1b0", 1.5707963267948966, 0.7853981633974483, +1),
    ("chsh_a1b1", 1.5707963267948966, -0.7853981633974483, -1),
]


def _chsh_blocks(Block):
    from qiskit import QuantumCircuit
    blocks = []
    for name, ta, tb, sign in CHSH_SETTINGS:
        qc = QuantumCircuit(2, name=name)
        qc.h(0)
        qc.cx(0, 1)
        qc.ry(-ta, 0)      # measure along theta in the X-Z plane: ry(-theta) then Z
        qc.ry(-tb, 1)
        blocks.append(Block(name, qc, [0, 1], {"theta_a": ta, "theta_b": tb, "sign": sign}))
    return blocks


def _parity(counts):
    n = sum(counts.values())
    if not n:
        return float("nan"), float("nan"), 0
    even = sum(c for k, c in counts.items() if k.count("1") % 2 == 0)
    e = (2 * even - n) / n
    se = ((1 - e * e) / n) ** 0.5
    return e, se, n


# ---------------------------------------------------------------- main

def _bench_note(bench):
    parts = []
    for n, r in bench.items():
        qk = "skip" if r["qiskit_kraus_s"] < 0 else "%.3fs" % r["qiskit_kraus_s"]
        diff = "skip" if r["max_abs_diff"] < 0 else "%.1e" % r["max_abs_diff"]
        parts.append("n%d:qk=%s/np=%.3fs/diff=%s" % (n, qk, r["numpy_s"], diff))
    return ";".join(parts)


def _print_layout(packed, circs):
    """After transpiling (IBM), show which physical qubits each canary block landed on:
    per-bit flip rates are then per physical qubit, and cal0/cal1 use different ones."""
    try:
        if not getattr(circs[0], "layout", None):
            return
        phys = {}
        for s in packed.slots:
            if not s.name.startswith("_canary"):
                continue
            idx = circs[s.circuit_index].layout.final_index_layout()
            phys[s.name] = [idx[q] for q in s.qubits]
        print("  physical qubits of canary blocks: %s" % phys)
        _note("canary_physical_qubits", phys)
    except Exception as exc:
        print("  physical layout: n/a (%s)" % type(exc).__name__)


def _section_imports():
    _section("2. Imports and data files")
    try:
        if "flat" in _IMPORT_ERRORS:
            exc = _IMPORT_ERRORS["flat"]
            print("  flat import of qk_runtime/qk_packer: FAILED %s: %s" % (type(exc).__name__, exc))
            _note("flat_import", "FAILED %s" % type(exc).__name__)
        else:
            print("  flat imports (qk_runtime, qk_packer): OK")
            _note("flat_import", "ok")
        if pkgtest is None:
            exc = _IMPORT_ERRORS.get("package")
            print("  import pkgtest: FAILED %s: %s" % (type(exc).__name__, exc))
            _note("package_import", "FAILED %s" % type(exc).__name__)
        else:
            value, sub = getattr(pkgtest, "VALUE", None), getattr(pkgtest, "SUB", None)
            kind = "ok" if value and sub else "namespace-or-partial(file=%s)" % getattr(
                pkgtest, "__file__", None)
            print("  import pkgtest: %s value=%r sub=%r" % (kind, value, sub))
            _note("package_import", kind)
    except Exception as exc:
        _fail("import probes", exc)
        _note("package_import", "FAILED %s" % type(exc).__name__)
    try:
        with open("data/probe.json") as fh:
            probe = json.load(fh)
        print("  open('data/probe.json'): OK %r" % (probe,))
        _note("data_literal_path", "ok")
    except Exception as exc:
        _fail("open('data/probe.json')", exc)
        _note("data_literal_path", "FAILED %s" % type(exc).__name__)
    try:
        print("  cwd=%s" % os.getcwd())
        print("  listdir('.')=%s" % sorted(os.listdir("."))[:30])
        if os.path.isdir("data"):
            print("  listdir('data')=%s" % sorted(os.listdir("data"))[:30])
        print("  __file__=%s  __name__=%s" % (globals().get("__file__", "<undefined>"), __name__))
        print("  sys.path[:6]=%s" % sys.path[:6])
        _note("__name__", __name__)
    except Exception as exc:
        _fail("filesystem listing", exc)


def _section_backend():
    """Backend identity (printed directly, so it survives a failed flat import) and
    the qk_runtime profile. Returns (backend, profile) or (backend_or_None, None)."""
    _section("3. Backend")
    be, where = _find_backend()
    print("  backend found in: %s" % where)
    _note("backend_found_in", where)
    if be is None:
        return None, None
    try:
        name = getattr(be, "name", None)
        if callable(name):
            name = name()
        print("  type=%s.%s  name=%r" % (type(be).__module__, type(be).__name__, name))
        _note("backend_module", type(be).__module__)
        _note("backend_class", type(be).__name__)
        _note("backend_name", name)
    except Exception as exc:
        _fail("backend identity", exc)
    try:
        ops = sorted(be.target.operation_names)
        print("  target ops (%d): %s" % (len(ops), ops[:40]))
    except Exception as exc:
        print("  target ops: n/a (%s)" % type(exc).__name__)
    try:
        opts = getattr(be, "options", None)
        if opts is None:
            items = {}
        elif hasattr(opts, "items"):
            items = dict(opts.items())
        else:
            items = dict(getattr(opts, "_fields", {}) or {})
        safe = {k: repr(v)[:60] for k, v in items.items()
                if not any(w in k.lower() for w in ("token", "key", "secret", "auth", "password"))}
        print("  options: %s" % json.dumps(safe)[:600])
    except Exception as exc:
        print("  options: n/a (%s)" % type(exc).__name__)
    if qk_runtime is None:
        return be, None
    try:
        profile = qk_runtime.backend_profile(be)
    except Exception as exc:
        _fail("backend_profile", exc)
        profile = {"family": "unknown", "name": str(type(be).__name__), "module": "",
                   "class": type(be).__name__, "reported_qubits": None, "noise_model": None,
                   "max_qubits": 20, "remote": False, "noisy": False, "one_job": True,
                   "transpile": False}
    print("  profile: %s" % json.dumps(profile))
    for key in ("family", "reported_qubits", "max_qubits", "noise_model", "one_job"):
        _note(key, profile.get(key))
    return be, profile


def main(shots: int = 1000, mode: str = "auto", debias: bool = True):
    SUMMARY.clear()
    _RUN_COUNTER[0] += 1
    t_start = time.perf_counter()
    print("Qollab smoke test %s" % SMOKE_VERSION)

    # ------------------------------------------------ 0. form types + persistence
    _section("0. Run-settings form and persistence")
    print("  shots=%r (%s)  mode=%r (%s)  debias=%r (%s)"
          % (shots, type(shots).__name__, mode, type(mode).__name__, debias, type(debias).__name__))
    _note("form_received", "shots=%r:%s mode=%r:%s debias=%r:%s" % (
        shots, type(shots).__name__, mode, type(mode).__name__, debias, type(debias).__name__))
    try:
        shots = int(shots)
    except Exception:
        print("  shots not int-like; using 1000")
        shots = 1000
    mode = str(mode).strip().lower()
    if mode not in ("auto", "tile", "list"):
        print("  mode %r unknown; using 'auto'" % mode)
        mode = "auto"
    debias = _as_bool(debias)
    _note("runs_in_this_interpreter", _RUN_COUNTER[0])
    marker_seen = os.path.exists(_MARKER)
    try:
        with open(_MARKER, "w") as fh:
            fh.write(str(time.time()))
    except Exception as exc:
        marker_seen = "unwritable(%s)" % type(exc).__name__
    _note("tmp_marker_from_previous_run", marker_seen)
    print("  module-state run counter=%d  /tmp marker from a previous run: %s"
          % (_RUN_COUNTER[0], marker_seen))

    # ------------------------------------------------ 1. environment
    _section("1. Environment")
    print("  python %s" % sys.version.replace("\n", " "))
    print("  platform=%s implementation=%s" % (sys.platform, sys.implementation.name))
    vers = {m: _version(m) for m in (
        "pyodide", "qiskit", "numpy", "scipy", "matplotlib", "qiskit_aer",
        "qiskit_ionq", "qiskit_braket_provider", "qiskit_ibm_runtime")}
    for m in ("scipy", "matplotlib"):
        if m in _IMPORT_ERRORS:
            vers[m] = "MISSING(%s)" % type(_IMPORT_ERRORS[m]).__name__
    for m, v in vers.items():
        print("  %-24s %s" % (m, v))
    _note("python", sys.version.split()[0])
    _note("platform", sys.platform)
    for m, v in vers.items():
        _note(m, v)
    try:
        from qiskit_ionq import ErrorMitigation
        members = [m for m in dir(ErrorMitigation) if not m.startswith("_")]
        print("  from qiskit_ionq import ErrorMitigation: OK members=%s" % members)
        _note("ionq_ErrorMitigation_import", "ok")
    except Exception as exc:
        print("  from qiskit_ionq import ErrorMitigation: unavailable (%s)" % type(exc).__name__)
        _note("ionq_ErrorMitigation_import", "unavailable %s" % type(exc).__name__)
    try:
        _note("dm_bench", _bench_note(_density_bench()))
    except Exception as exc:
        _fail("density-matrix bench", exc)
        _note("dm_bench", "FAILED %s" % type(exc).__name__)

    # ------------------------------------------------ 2. imports + data files
    _section_imports()

    # ------------------------------------------------ 3. backend
    be, profile = _section_backend()
    if be is None or profile is None:
        print("  No usable backend/profile (backend=%s, qk_runtime=%s). Stopping before any job."
              % (be is not None, qk_runtime is not None))
        _print_summary(t_start)
        return
    qk_runtime.begin_run()
    requested = mode
    mode = qk_runtime.preferred_mode(profile, mode)
    if requested == "auto":
        print("  mode auto -> %s (tile for one-job backends, list for local noisy simulators)" % mode)
    _note("mode", "%s (requested %s)" % (mode, requested))

    # ------------------------------------------------ 4. one job
    _section("4. One job: canary + 4 CHSH tiles (mode=%s, shots=%d)" % (mode, shots))
    counts = None
    packed = None
    run_kwargs = {}
    try:
        blocks = _chsh_blocks(qk_packer.Block)
        packed = qk_packer.pack(blocks, max_qubits=profile["max_qubits"], mode=mode, canary=True)
        summ = packed.summary()
        print("  packed: %d circuit(s), qubits per circuit %s"
              % (summ["n_circuits"], summ["qubits_per_circuit"]))
        _note("packed", "mode=%s circuits=%d qubits=%s" % (mode, summ["n_circuits"], summ["qubits_per_circuit"]))
        t0 = time.perf_counter()
        circs = qk_runtime.prepare(packed.circuits, be, profile)
        print("  prepare: %s (%.2fs)" % (qk_runtime.LAST_RUN.get("prepare"), time.perf_counter() - t0))
        _note("prepare", qk_runtime.LAST_RUN.get("prepare"))
        if profile["family"].startswith("ionq"):
            run_kwargs = qk_runtime.ionq_run_kwargs(debias)
            if debias and shots < 500:
                print("  note: debiasing needs >= 500 shots (and never runs on IonQ simulators)")
        else:
            print("  debias=%r ignored (not an IonQ backend)" % debias)
        _note("run_kwargs_sent", {k: repr(v) for k, v in run_kwargs.items()})
        print("  submitting ONE job: run kwargs %s" % {k: repr(v) for k, v in run_kwargs.items()})
        _print_layout(packed, circs)
        counts = qk_runtime.run_once(be, circs, shots, profile, allow_partial=True, **run_kwargs)
    except Exception as exc:
        _fail("one-job run", exc)
        _note("job", "FAILED %s: %s" % (type(exc).__name__, str(exc)[:300]))
    lr = qk_runtime.LAST_RUN
    _note("backend_run_calls", qk_runtime.jobs_submitted())
    for key in ("job_returned", "job_id", "submitted_as", "result_retry", "debias_note",
                "failed_circuits",
                "raw_key_lengths", "raw_value_types", "wall_s", "job_class"):
        if key in lr:
            _note(key, lr.get(key))
    print("  backend.run calls this run: %d" % qk_runtime.jobs_submitted())

    # ------------------------------------------------ 5. results
    _section("5. Results")
    if "raw_head" in lr:
        print("  raw counts (first 10 per circuit): %s" % json.dumps(lr["raw_head"], default=str)[:1500])
        _note("raw_keys", lr.get("raw_key_sample"))
    if counts is not None and packed is not None:
        try:
            print("  normalized key sample: %s" % [list(c)[:3] for c in counts])
            print("  shots seen per circuit: %s" % [sum(c.values()) for c in counts])
            _note("norm_keys", [list(c)[:2] for c in counts])
            _note("shots_seen", [sum(c.values()) for c in counts])
            un = qk_packer.unpack(packed, counts)
            rep = qk_packer.canary_report(un)
            diag = qk_packer.diagnose_orientation(packed, counts)
            print("  orientation: ok=%s expected=%s majority=%s fraction=%.3f"
                  % (rep["orientation_ok"], rep["orientation_expected"],
                     rep["orientation_majority"], rep["orientation_fraction"]))
            print("  orientation hypotheses (fraction matching): %s" % diag)
            print("  readout P(1|0) per bit: %s" % ["%.4f" % p for p in rep["p_flip_0to1"]])
            print("  readout P(0|1) per bit: %s" % ["%.4f" % p for p in rep["p_flip_1to0"]])
            _note("orientation_ok", rep["orientation_ok"])
            _note("orientation_hypotheses", diag)
            _note("p01", ["%.4f" % p for p in rep["p_flip_0to1"]])
            _note("p10", ["%.4f" % p for p in rep["p_flip_1to0"]])
            s_val, s_var = 0.0, 0.0
            for name, ta, tb, sign in CHSH_SETTINGS:
                e, se, n = _parity(un[name])
                s_val += sign * e
                s_var += se * se
                print("  %s: E=%+.4f +/- %.4f (n=%d, ideal %+.4f)" % (name, e, se, n, math.cos(ta - tb)))
            s_se = s_var ** 0.5
            if s_se > 0 and s_se == s_se:
                z_txt = "%+.2f" % ((s_val - 2.0) / s_se)
            else:
                z_txt = "n/a"
            print("  CHSH S = %.4f +/- %.4f   (classical bound 2, ideal 2.8284)  z vs 2 = %s"
                  % (s_val, s_se, z_txt))
            _note("S", "%.4f+/-%.4f z=%s" % (s_val, s_se, z_txt))
        except Exception as exc:
            _fail("result analysis", exc)
            _note("analysis", "FAILED %s: %s" % (type(exc).__name__, str(exc)[:200]))
    meta = {k: lr.get(k) for k in ("n_circuits", "submitted_as", "shots_requested", "run_kwargs",
                                   "job_id", "job_class", "submit_s", "result_s", "wall_s",
                                   "debias_note", "result_retry")}
    print("  job: %s" % json.dumps(meta, default=str))
    print("  result metadata: %s" % json.dumps(lr.get("result"), default=str)[:1500])
    _print_summary(t_start)


def _one_line(v, limit=400):
    text = str(v).replace("\r", " ").replace("\n", " | ")
    return text if len(text) <= limit else text[:limit] + "...(cut)"


def _print_summary(t_start):
    _note("total_s", round(time.perf_counter() - t_start, 2))
    print("\n=== SMOKE SUMMARY %s ===" % SMOKE_VERSION)
    for k, v in SUMMARY:
        print("%s=%s" % (k, _one_line(v)))
    print("=== END SMOKE SUMMARY ===")
