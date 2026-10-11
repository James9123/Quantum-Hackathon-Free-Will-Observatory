"""Generate dev/stub_data.js: canned answers for the Observatory UI's stub mode.

Every answer comes from the REAL qollab_project/observatory_api.py functions under
CPython, on local stand-in backends: a seeded BasicSimulator, an IonQ-shaped wrapper
(profiles as one job per run, runs locally) and a failing backend. The canned runs
cover the three demo settings of the build guide (w = 0 / phi = pi/2, w = 0 / phi = pi,
w = 1 / phi = pi/2), the half-coupling case w = 0.5, and two Observer settings
(perspective 90 degrees at w = 0, perspective 45 degrees at w = 0.5). dev/stub_api.js
serves these for matching settings and synthesizes anything else in JavaScript from
the closed-form distributions, clearly marked "[stub]".

    .venv/bin/python tools/make_ui_stubs.py

Not part of the Qollab upload. Every stub number is an ideal-simulator or
exact-model number: nothing here is a measurement of anything.

This effort is supported by Qollab & IonQ
"""

import json
import math
import os
import sys

from qiskit.providers.basic_provider import BasicSimulator

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.join(ROOT, "qollab_project")
if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)

import observatory_api  # noqa: E402
import qk_runtime  # noqa: E402

OUT = os.path.join(ROOT, "dev", "stub_data.js")
SEED = 7
SHOTS = 1024

# (intention degrees, world coupling, perspective degrees, shots): the demo acts first.
SETTINGS = [
    (90, 0.0, 0, SHOTS),      # act 1: open future, full capacity
    (180, 0.0, 0, SHOTS),     # act 2: intention directs the outcome
    (90, 1.0, 0, SHOTS),      # act 3: open but constrained (capacity ~ 0)
    (90, 0.5, 0, SHOTS),      # half coupling
    (90, 0.0, 90, SHOTS),     # observer: perspective = intention -> P(Self=1) = 0
    (90, 0.5, 45, SHOTS),     # observer at half coupling
]


def settings_key(phi_deg, w, beta_deg, shots):
    """The lookup key dev/stub_api.js builds from a settings object."""
    return "%d|%s|%d|%d" % (round(phi_deg), ("%g" % round(w, 2)), round(beta_deg), int(shots))


def settings_obj(phi_deg, w, beta_deg, shots):
    return {
        "intention_rad": math.radians(phi_deg),
        "world_coupling": float(w),
        "perspective_rad": math.radians(beta_deg),
        "shots_per_probe": int(shots),
        "persona": "self",
        "mode": "auto",
        "canary": True,
    }


def _seeded_basic(seed=SEED):
    be = BasicSimulator()
    be.set_options(seed_simulator=seed)
    return be


class _Delegate:
    """Delegates everything except run() to an inner BasicSimulator."""

    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, item):
        return getattr(self._inner, item)


class IonQShapedStandIn(_Delegate):
    """Looks like an IonQ simulator to qk_runtime.backend_profile (one job per run,
    remote), but runs on a local ideal BasicSimulator and refuses a second job."""
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


def _call(fn, *args):
    out = json.loads(fn(*args))
    if not isinstance(out, dict):
        raise SystemExit("%s did not return a JSON object" % fn.__name__)
    return out


def build():
    basic = _seeded_basic()
    profiles = {
        "basic": _call(observatory_api.profile_json, basic, True),
        "ionq": _call(observatory_api.profile_json, IonQShapedStandIn(_seeded_basic()), True),
        "error": _call(observatory_api.profile_json, FailingStandIn(_seeded_basic()), True),
    }
    for kind, p in profiles.items():
        if "error" in p:
            raise SystemExit("profile_json failed for %s: %s" % (kind, p["error"]))

    predicts, runs = {}, {"basic": {}, "ionq": {}, "error": {}}
    for i, (phi, w, beta, shots) in enumerate(SETTINGS):
        key = settings_key(phi, w, beta, shots)
        s = settings_obj(phi, w, beta, shots)
        predicts[key] = _call(observatory_api.predict_json, json.dumps(s))
        if "error" in predicts[key]:
            raise SystemExit("predict_json failed for %s: %s" % (key, predicts[key]["error"]))
        qk_runtime.begin_run()
        be = _seeded_basic(SEED + i)
        r = _call(observatory_api.run_json, be, json.dumps(s))
        if r.get("status") != "completed":
            raise SystemExit("run_json failed for %s: %s" % (key, r.get("error")))
        runs["basic"][key] = r

    # IonQ-shaped stand-in: the one job of the default settings, then the refusal.
    qk_runtime.begin_run()
    ionq = IonQShapedStandIn(_seeded_basic(SEED + 50))
    default_key = settings_key(*SETTINGS[0])
    first = _call(observatory_api.run_json, ionq, json.dumps(settings_obj(*SETTINGS[0])))
    if first.get("status") != "completed":
        raise SystemExit("ionq stand-in run failed: %s" % first.get("error"))
    runs["ionq"][default_key] = first
    runs["ionq:refused"] = _call(observatory_api.run_json, ionq, json.dumps(settings_obj(*SETTINGS[0])))
    if runs["ionq:refused"].get("status") != "failed":
        raise SystemExit("the IonQ stand-in should refuse a second job")

    qk_runtime.begin_run()
    failed = _call(observatory_api.run_json, FailingStandIn(_seeded_basic()),
                   json.dumps(settings_obj(*SETTINGS[0])))
    if failed.get("status") != "failed":
        raise SystemExit("the failing stand-in should fail")
    runs["error"][default_key] = failed
    qk_runtime.begin_run()

    curves = _call(observatory_api.curves_json)
    if "error" in curves:
        raise SystemExit("curves_json failed: %s" % curves["error"])

    return {
        "generated_by": "tools/make_ui_stubs.py (real observatory_api calls under CPython)",
        "model_version": observatory_api.MODEL_VERSION,
        "shots": SHOTS,
        "settings": [{"key": settings_key(*s), "intention_deg": s[0], "world_coupling": s[1],
                      "perspective_deg": s[2], "shots_per_probe": s[3]} for s in SETTINGS],
        "profiles": profiles,
        "predicts": predicts,
        "runs": runs,
        "curves": curves,
    }


def main():
    data = build()
    text = json.dumps(data, allow_nan=False, separators=(",", ":"), sort_keys=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("// GENERATED by tools/make_ui_stubs.py -- do not edit by hand.\n")
        fh.write("// Canned answers from the real observatory_api functions (local simulators only).\n")
        fh.write("export const STUB = " + text + ";\n")
    print("wrote %s (%d bytes; %d canned settings; runs: %s)" % (
        os.path.relpath(OUT, ROOT), len(text), len(data["settings"]),
        ", ".join("%s=%d" % (k, len(v)) for k, v in data["runs"].items() if isinstance(v, dict) and k != "ionq:refused")))


if __name__ == "__main__":
    main()
