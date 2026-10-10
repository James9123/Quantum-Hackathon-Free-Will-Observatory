"""Qollab runtime harness: backend profile, one-job run wrapper, count normalization.

Works under CPython on a laptop and under Pyodide on Qollab. Dependencies: qiskit + stdlib.

Rules this module enforces:
- Never create a backend. The caller passes in the `backend` that Qollab injects.
- One `backend.run` per `run_once` call. When the profile says the backend is
  one-job-per-run (IonQ, or anything unrecognized), a second submission in the
  same run raises instead of reaching the provider. Call `begin_run()` at the
  top of `main()` so a reused interpreter starts each run with a clean guard.
- Counts come back as Qiskit bitstrings: one key per outcome, no spaces,
  zero-padded to the circuit's clbit count, clbit 0 rightmost.
"""

import time

__all__ = [
    "backend_profile", "prepare", "run_once", "normalize_counts",
    "begin_run", "jobs_submitted", "ionq_run_kwargs", "LAST_RUN",
]

# Qollab's published ceilings (qollab.xyz compute-backends). "Ceilings, not guarantees".
_FAMILY_DEFAULTS = {
    #               max_qubits remote  noisy  one_job transpile
    "basic":        (24,       False,  False, False,  True),
    "braket_local": (25,       False,  False, False,  True),
    # IBM noise models report 156/120 device qubits, but the simulation runs in the
    # browser, so a practical cap applies to the *active* qubits we use.
    "ibm_noise":    (24,       False,  True,  False,  True),
    "ionq_sim":     (29,       True,   True,  True,   False),
    "ionq_qpu":     (36,       True,   True,  True,   False),
    "unknown":      (20,       False,  False, True,   True),
}

_IBM_DEVICE_HINTS = (
    "fez", "torino", "marrakesh", "kingston", "aachen", "brisbane", "sherbrooke",
    "kyiv", "quebec", "brussels", "strasbourg", "nazca", "cusco", "rensselaer",
    "pittsburgh", "boston", "miami", "heron", "eagle", "osaka", "kyoto",
)

# IonQ noise-model simulators: qubit ceiling by model family (Qollab compute-backends).
_IONQ_MODEL_QUBITS = (("aria", 25), ("forte", 29))
# qiskit-ionq falls back to reporting 4 qubits when its backend lookup fails; treat
# implausibly small IonQ counts as unknown rather than refusing a 17-qubit job.
_IONQ_MIN_PLAUSIBLE = 8

_STATE = {"jobs": 0}
LAST_RUN = {}


def begin_run():
    """Reset the one-job guard. Call once at the start of each user-visible run."""
    _STATE["jobs"] = 0
    LAST_RUN.clear()


def jobs_submitted():
    return _STATE["jobs"]


def _reported_qubits(backend):
    for getter in (
        lambda b: b.num_qubits,
        lambda b: b.target.num_qubits,
        lambda b: b.configuration().n_qubits,
    ):
        try:
            n = getter(backend)
        except Exception:
            continue
        if isinstance(n, int) and n > 0:
            return n
    return None


def _backend_name(backend):
    name = getattr(backend, "name", None)
    if callable(name):  # BackendV1 style
        try:
            name = name()
        except Exception:
            name = None
    return str(name) if name is not None else type(backend).__name__


def _classify(module, name, cls):
    m, n, c = module.lower(), name.lower(), cls.lower()
    hay = " ".join((m, n, c))
    if "ionq" in hay or "forte" in n or "aria" in n:
        if "qpu" in n or "qpu" in c:
            return "ionq_qpu"
        return "ionq_sim"
    if "braket" in hay:
        return "braket_local"
    if "basic_provider" in m or n == "basic_simulator":
        return "basic"
    if ("qiskit_ibm_runtime" in m or "fake_provider" in m or n.startswith("fake_")
            or "ibm" in n or any(h in n for h in _IBM_DEVICE_HINTS)):
        return "ibm_noise"
    return "unknown"


def backend_profile(backend):
    """Describe the injected backend. Unknown backends stay usable but conservative."""
    module = type(backend).__module__ or ""
    cls = type(backend).__name__
    name = _backend_name(backend)
    family = _classify(module, name, cls)
    cap, remote, noisy, one_job, transpile_ = _FAMILY_DEFAULTS[family]
    reported = _reported_qubits(backend)
    noise_model = _option(backend, "noise_model")
    usable = reported
    if family.startswith("ionq"):
        if family == "ionq_sim" and noise_model:
            for key, n in _IONQ_MODEL_QUBITS:
                if key in str(noise_model).lower():
                    cap = n
        if reported is not None and reported < _IONQ_MIN_PLAUSIBLE:
            usable = None
    max_qubits = min(cap, usable) if usable else cap
    return {
        "family": family,
        "name": name,
        "module": module,
        "class": cls,
        "reported_qubits": reported,
        "noise_model": None if noise_model is None else str(noise_model),
        "max_qubits": int(max_qubits),
        "remote": remote,
        "noisy": noisy,
        "one_job": one_job,
        "transpile": transpile_,
    }


def _option(backend, key):
    opts = getattr(backend, "options", None)
    if opts is None:
        return None
    try:
        return opts.get(key)
    except Exception:
        return getattr(opts, key, None)


def prepare(circuits, backend, profile, optimization_level=1):
    """Make circuits runnable on `backend`.

    Local simulators: transpile against the backend (unrolls anything they reject,
    maps onto device coupling for IBM noise models). Use optimization_level=0 for
    folded (ZNE) circuits so U U^dagger pairs survive.
    IonQ: submitted as written; IonQ compiles to its native gates server side.
    Falls back to the original circuits if transpilation fails, and records why.
    """
    single = not isinstance(circuits, (list, tuple))
    circs = [circuits] if single else list(circuits)
    info = {"transpiled": False, "optimization_level": None, "error": None}
    if profile.get("transpile"):
        try:
            from qiskit import transpile
            circs = transpile(circs, backend=backend, optimization_level=optimization_level)
            if not isinstance(circs, list):
                circs = [circs]
            info.update(transpiled=True, optimization_level=optimization_level)
        except Exception as exc:  # keep going with the untranspiled circuits
            info["error"] = "%s: %s" % (type(exc).__name__, exc)
    LAST_RUN["prepare"] = info
    return circs


def ionq_run_kwargs(debias):
    """backend.run kwargs for IonQ debiasing. Empty dict means "provider default".

    Debiasing is on by default for jobs of >= 500 shots and impossible below 500.
    Turning it off needs qiskit_ionq.ErrorMitigation; if that import fails we can
    only use the default, and say so in LAST_RUN.
    """
    if debias:
        return {}
    try:
        from qiskit_ionq import ErrorMitigation
    except Exception as exc:
        LAST_RUN["debias_note"] = "qiskit_ionq.ErrorMitigation unavailable (%s); provider default used" % (
            type(exc).__name__)
        return {}
    return {"error_mitigation": ErrorMitigation.NO_DEBIASING}


def _num_clbits(circuit):
    try:
        return int(circuit.num_clbits)
    except Exception:
        return 0


def _counts_for(result, i, n_experiments):
    try:
        return result.get_counts(i)
    except Exception:
        allc = result.get_counts()
        if isinstance(allc, list):
            return allc[i]
        if n_experiments == 1:
            return allc
        raise


def run_once(backend, circuits, shots, profile, **run_kwargs):
    """Submit exactly ONE job and return normalized counts, one dict per circuit.

    `circuits` may be one circuit or a list. A list of one is submitted as a bare
    circuit. Metadata about the job lands in LAST_RUN.
    """
    if profile.get("one_job") and _STATE["jobs"] >= 1:
        raise RuntimeError(
            "one-job guard: backend %r accepts one job per run and a job was already "
            "submitted in this run" % profile.get("name"))
    single = not isinstance(circuits, (list, tuple))
    circs = [circuits] if single else list(circuits)
    if not circs:
        raise ValueError("run_once: no circuits")
    payload = circs[0] if len(circs) == 1 else circs
    _STATE["jobs"] += 1
    t0 = time.perf_counter()
    job = backend.run(payload, shots=int(shots), **run_kwargs)
    t_submit = time.perf_counter()
    result = job.result()
    t_done = time.perf_counter()
    raw = [_counts_for(result, i, len(circs)) for i in range(len(circs))]
    counts = [normalize_counts(r, _num_clbits(c), shots=shots) for r, c in zip(raw, circs)]
    job_id = None
    try:
        job_id = job.job_id()
    except Exception:
        pass
    LAST_RUN.update({
        "n_circuits": len(circs),
        "submitted_as": "circuit" if len(circs) == 1 else "list",
        "shots_requested": int(shots),
        "run_kwargs": {k: repr(v) for k, v in run_kwargs.items()},
        "job_id": job_id,
        "job_class": type(job).__module__ + "." + type(job).__name__,
        "submit_s": round(t_submit - t0, 3),
        "result_s": round(t_done - t_submit, 3),
        "wall_s": round(t_done - t0, 3),
        "raw_key_sample": [list(r)[:3] for r in raw],
        "raw_value_types": sorted({type(v).__name__ for r in raw for v in r.values()}),
        "result": _result_meta(result),
    })
    return counts


def _result_meta(result):
    """Small, JSON-safe summary of a Result (no counts)."""
    meta = {}
    for key in ("backend_name", "backend_version", "job_id", "success", "status", "date"):
        val = getattr(result, key, None)
        if val is not None and not callable(val):
            meta[key] = str(val)
    try:
        md = getattr(result, "metadata", None)
        if md:
            meta["metadata"] = {str(k): str(v)[:120] for k, v in dict(md).items()}
    except Exception:
        pass
    try:
        exps = []
        for r in result.results[:4]:
            exps.append({
                "shots": str(getattr(r, "shots", None)),
                "success": str(getattr(r, "success", None)),
                "header": str(getattr(r, "header", ""))[:160],
            })
        meta["experiments"] = exps
    except Exception:
        pass
    return meta


def _key_to_bits(key, key_format):
    if isinstance(key, int):
        if key < 0:
            raise ValueError("negative count key %r" % key)
        return format(key, "b")
    s = str(key).strip().replace(" ", "").replace("_", "")
    low = s.lower()
    if key_format == "hex" or low.startswith("0x"):
        return format(int(low, 16), "b")
    if low.startswith("0b"):
        s = low[2:]
    if key_format == "dec":
        return format(int(s, 10), "b")
    if s and set(s) <= {"0", "1"}:
        return s
    if key_format == "auto" and s.isdigit():
        return format(int(s, 10), "b")
    raise ValueError("unrecognized count key %r" % (key,))


def normalize_counts(raw, num_clbits, shots=None, key_format="auto"):
    """Raw provider counts -> {bitstring: int}, clbit 0 rightmost.

    Accepts space-separated register keys, hex ('0x5'), '0b' prefixes, int keys and
    decimal-string keys (key_format='dec', or 'auto' when the key has digits 2-9).
    Pads to num_clbits. Keys longer than num_clbits are trimmed only when the extra
    leading bits are zero. Probability-valued dicts (floats summing to ~1) are
    scaled by `shots` when given. Colliding keys are summed.
    """
    items = list(dict(raw).items())
    vals = [v for _, v in items]
    as_probs = (
        shots is not None and vals
        and any(isinstance(v, float) and not float(v).is_integer() for v in vals)
        and abs(sum(float(v) for v in vals) - 1.0) < 1e-6
    )
    out = {}
    for k, v in items:
        bits = _key_to_bits(k, key_format)
        if num_clbits:
            if len(bits) > num_clbits:
                extra = bits[: len(bits) - num_clbits]
                if set(extra) - {"0"}:
                    raise ValueError(
                        "count key %r has %d bits, circuit has %d clbits" % (k, len(bits), num_clbits))
                bits = bits[len(bits) - num_clbits:]
            bits = bits.zfill(num_clbits)
        n = int(round(float(v) * shots)) if as_probs else int(round(float(v)))
        if n:
            out[bits] = out.get(bits, 0) + n
    return dict(sorted(out.items()))
