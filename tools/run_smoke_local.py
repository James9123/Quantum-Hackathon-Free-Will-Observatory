"""Run smoke/main.py locally under CPython, the way Qollab would: inject `backend`
as a module global, chdir into the project folder, call main(**params).

    .venv/bin/python tools/run_smoke_local.py [--mode tile|list] [--shots N] [--fake-ionq]

--fake-ionq wraps BasicSimulator in a stand-in whose class/module look like an
IonQ backend and which raises on a second job, to exercise the one-job path.
This file is NOT part of the upload.
"""
import argparse
import importlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class FakeIonQSimulator:
    """Stand-in for the IonQ simulator: one job per run, no transpile needed."""
    __module__ = "qiskit_ionq.ionq_backend"
    name = "ionq_simulator(fake)"
    num_qubits = 29

    def __init__(self, inner):
        self._inner = inner
        self.jobs = 0

    def run(self, run_input, shots=1024, **kwargs):
        self.jobs += 1
        if self.jobs > 1:
            raise RuntimeError("fake IonQ: only one job per run")
        unknown = set(kwargs) - {"error_mitigation", "noise_model", "seed_simulator"}
        if unknown:
            raise TypeError("fake IonQ: unexpected run kwargs %s" % sorted(unknown))
        return self._inner.run(run_input, shots=shots)


class CountingBackend:
    """Wrap a backend and count backend.run calls; everything else delegates."""

    def __init__(self, inner):
        self._inner = inner
        self.jobs = 0

    def __getattr__(self, item):
        return getattr(self._inner, item)

    def run(self, *a, **k):
        self.jobs += 1
        return self._inner.run(*a, **k)


def load_smoke(project_dir="smoke"):
    path = os.path.join(ROOT, project_dir)
    os.chdir(path)
    if path not in sys.path:
        sys.path.insert(0, path)
    for mod in ("main", "qk_runtime", "qk_packer", "pkgtest", "pkgtest.sub"):
        sys.modules.pop(mod, None)
    return importlib.import_module("main")


def run(mode="tile", shots=1000, debias=True, fake_ionq=False, seed=11):
    from qiskit.providers.basic_provider import BasicSimulator
    inner = BasicSimulator()
    inner.set_options(seed_simulator=seed)
    be = FakeIonQSimulator(inner) if fake_ionq else CountingBackend(inner)
    cwd = os.getcwd()
    try:
        smoke = load_smoke()
        smoke.backend = be
        smoke.main(shots=shots, mode=mode, debias=debias)
    finally:
        os.chdir(cwd)
    return be


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="tile")
    ap.add_argument("--shots", type=int, default=1000)
    ap.add_argument("--no-debias", action="store_true")
    ap.add_argument("--fake-ionq", action="store_true")
    a = ap.parse_args()
    be = run(a.mode, a.shots, not a.no_debias, a.fake_ionq)
    print("\n[local runner] backend.run calls: %d" % be.jobs)
