"""Generate dev/stub_data.js: canned answers for the UI's stub mode.

Every answer comes from the REAL qollab_project/ui_api.py functions under CPython:
profiles and runs on local stand-in backends (BasicSimulator, a readout-flip
wrapper, an IonQ-shaped wrapper, a failing backend), a grid of noise-dial points
(dev/stub_api.js interpolates between them) and the precomputed curves.

    .venv/bin/python tools/make_ui_stubs.py

Not part of the Qollab upload. Stand-in backends are local wrappers around
BasicSimulator, so every stub number is an ideal-simulator or exact-model number.
"""

import json
import os
import sys

import numpy as np
from qiskit.providers.basic_provider import BasicSimulator

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.join(ROOT, "qollab_project")
if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)

import ui_api  # noqa: E402

OUT = os.path.join(ROOT, "dev", "stub_data.js")
SEED = 7
SHOTS = 1000
P2_GRID = [round(0.025 * i, 3) for i in range(15)]            # 0 .. 0.35
RO_GRID = [0.0, 0.025, 0.05, 0.1, 0.15]
SCALE_GRID = [0, 1, 2, 4, 8, 12, 16, 24, 32, 40, 48, 56, 64, 72, 80]
DIAL_KEEP = ("preset", "noise", "S", "E", "terms", "exceeds", "margin",
             "shots_per_setting_3sigma", "reading", "elapsed_ms")


def _seeded_basic():
    be = BasicSimulator()
    be.set_options(seed_simulator=SEED)
    return be


class _Delegate:
    """Delegates everything except run() to an inner BasicSimulator."""

    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, item):
        return getattr(self._inner, item)


class ReadoutFlipStandIn(_Delegate):
    """BasicSimulator with seeded per-bit readout flips added to its counts, so the
    canary sees readout error and the card shows a mitigated value."""
    __module__ = "qiskit.providers.basic_provider.ui_stub"   # profiles as a local simulator
    name = "basic_simulator+readout_flips (stand-in)"

    def __init__(self, inner, p01=0.03, p10=0.05, seed=SEED):
        super().__init__(inner)
        self.p01, self.p10 = p01, p10
        self._rng = np.random.default_rng(seed)
        self.jobs = 0

    def _flip(self, counts):
        out = {}
        for key, c in counts.items():
            bits = np.array([ch == "1" for ch in key])
            r = self._rng.random((int(c), len(key)))
            flip = np.where(bits, r < self.p10, r < self.p01)
            for row in bits ^ flip:
                k = "".join("1" if b else "0" for b in row)
                out[k] = out.get(k, 0) + 1
        return out

    def run(self, circuits, shots=1024, **kw):
        res = self._inner.run(circuits, shots=shots, **kw).result()
        n = len(circuits) if isinstance(circuits, list) else 1
        flipped = [self._flip(res.get_counts(i)) for i in range(n)]
        self.jobs += 1
        job_id = "stub-readout-flips-%d" % self.jobs

        class _Res:
            results = []

            def get_counts(self_, i=None):
                return flipped if i is None else flipped[i]

        class _Job:
            def result(self_):
                return _Res()

            def job_id(self_):
                return job_id

        return _Job()


class IonQShapedStandIn(_Delegate):
    """Looks like an IonQ simulator to backend_profile (one job per run, remote),
    but runs on a local ideal BasicSimulator and refuses a second job."""
    __module__ = "qiskit_ionq.ionq_backend"
    name = "ionq_simulator (stand-in: local ideal simulator)"
    num_qubits = 29

    def __init__(self, inner):
        super().__init__(inner)
        self.jobs = 0

    def run(self, run_input, shots=1024, **kw):
        self.jobs += 1
        if self.jobs > 1:
            raise RuntimeError("stand-in: only one job per run")
        return self._inner.run(run_input, shots=shots)


class FailingStandIn(_Delegate):
    """A local backend whose job submission fails, to exercise the error path."""
    __module__ = "qiskit.providers.basic_provider.ui_stub"
    name = "basic_simulator (stand-in that fails)"

    def run(self, *a, **k):
        raise RuntimeError("simulated provider failure (stub)")


def _round(obj, sig=10):
    if isinstance(obj, float):
        return float("%.*g" % (sig, obj))
    if isinstance(obj, dict):
        return {k: _round(v, sig) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round(v, sig) for v in obj]
    return obj


def _call(fn, *args):
    return json.loads(fn(*args))


def _dial(params):
    d = _call(ui_api.noise_dial_json, json.dumps(params))
    if "error" in d:
        raise SystemExit("noise_dial_json failed for %r: %s" % (params, d["error"]))
    return _round({k: d[k] for k in DIAL_KEEP})


def build():
    basic = _seeded_basic()
    backends = {
        "basic": basic,
        "readout": ReadoutFlipStandIn(_seeded_basic()),
        "ionq": IonQShapedStandIn(_seeded_basic()),
        "error": FailingStandIn(_seeded_basic()),
    }
    profiles, runs, texts = {}, {}, {}
    for kind, be in backends.items():
        ui_api._UI["jobs"] = 0            # each stand-in starts as a fresh run
        profiles[kind] = _call(ui_api.profile_json, be)
        for mit in (True, False):
            if kind == "ionq" and not mit:
                continue                  # one job per run: only the default is canned
            ui_api._UI["jobs"] = 0
            if kind == "ionq":
                be.jobs = 0
            r = _call(ui_api.run_chsh_json, be, SHOTS, "auto", mit)
            runs["%s:%s" % (kind, "mit" if mit else "raw")] = r
            if "card" in r:
                t = _call(ui_api.card_text_json, json.dumps(r["card"]))
                texts[r["card"]["provenance"]["job"]["job_id"] or kind] = t
        if kind == "ionq":
            # A second press on a one-job backend: the real refusal from ui_api.
            runs["ionq:refused"] = _call(ui_api.run_chsh_json, be, SHOTS, "auto", True)
    ui_api._UI["jobs"] = 0

    dial_custom = [{"p2": p2, "ro": ro, "resp": _dial({"preset": "custom", "p2": p2, "r01": ro, "r10": ro})}
                   for ro in RO_GRID for p2 in P2_GRID]
    dial_presets = {
        preset: [{"scale": s, "resp": _dial({"preset": preset, "scale": s})} for s in SCALE_GRID]
        for preset in ("ionq_forte_like", "ionq_forte_like_spam")
    }
    shared = json.loads(ui_api.noise_dial_json("{}"))
    shared = {k: v for k, v in shared.items() if k not in DIAL_KEEP}
    shared["preset_note_ionq"] = json.loads(ui_api.noise_dial_json(
        json.dumps({"preset": "ionq_forte_like"})))["preset_note"]

    return {
        "generated_by": "tools/make_ui_stubs.py (real ui_api calls under CPython)",
        "shots": SHOTS,
        "profiles": profiles,
        "runs": runs,
        "card_texts": texts,
        "curve": json.loads(ui_api.curve_json()),
        "dial": {"p2_grid": P2_GRID, "ro_grid": RO_GRID, "scale_grid": SCALE_GRID,
                 "shared": shared, "custom": dial_custom, "presets": dial_presets},
    }


def main():
    data = build()
    text = json.dumps(data, allow_nan=False, separators=(",", ":"), sort_keys=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("// GENERATED by tools/make_ui_stubs.py -- do not edit by hand.\n")
        fh.write("// Canned answers from the real ui_api functions (local simulators only).\n")
        fh.write("export const STUB = " + text + ";\n")
    print("wrote %s (%d bytes, %d dial points, runs: %s)" % (
        os.path.relpath(OUT, ROOT), len(text), len(data["dial"]["custom"]) + sum(
            len(v) for v in data["dial"]["presets"].values()), ", ".join(sorted(data["runs"]))))


if __name__ == "__main__":
    main()
