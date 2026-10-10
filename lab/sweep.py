"""Parameter sweeps -> one small JSON dataset with provenance (off-platform).

    python lab/sweep.py --experiment chsh --grid p2=0:0.35:71 --shots 0 \
        --out qollab_project/data/chsh_noise.json

--grid name=start:stop:num  (inclusive linspace) or name=v1,v2,...; repeatable
        (cartesian product). --fixed name=value adds a constant parameter.
--shots 0 means exact (density matrix); >0 adds a seeded sampled estimate.
Output is validated (qk_data schema) and refused above --max-bytes (default 2 MB).
"""

import argparse
import itertools
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (HERE, os.path.join(ROOT, "qollab_project")):
    if p not in sys.path:
        sys.path.insert(0, p)

import experiments  # noqa: E402
import qk_data  # noqa: E402


def parse_grid(spec):
    name, _, values = spec.partition("=")
    if not name or not values:
        raise ValueError("bad --grid %r (want name=start:stop:num or name=v1,v2)" % spec)
    if ":" in values:
        start, stop, num = values.split(":")
        start, stop, num = float(start), float(stop), int(num)
        if num < 1:
            raise ValueError("num must be >= 1")
        if num == 1:
            return name, [start]
        step = (stop - start) / (num - 1)
        return name, [round(start + i * step, 12) for i in range(num)]
    return name, [float(v) for v in values.split(",")]


def parse_fixed(spec):
    name, _, value = spec.partition("=")
    return name, float(value)


def git_commit(explicit=None):
    if explicit:
        return explicit
    try:
        out = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short=12", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            dirty = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"],
                                   capture_output=True, text=True, timeout=10).stdout.strip()
            return out.stdout.strip() + ("-dirty" if dirty else "")
    except Exception:
        pass
    return "unknown"


def _run_point(task):
    name, point, shots, seed = task
    return experiments.EXPERIMENTS[name](point, shots=shots, seed=seed)


def sweep(experiment, grids, fixed, shots, seed, workers):
    names = [g[0] for g in grids]
    points = []
    for combo in itertools.product(*[g[1] for g in grids]) if grids else [()]:
        pt = dict(fixed)
        pt.update(zip(names, combo))
        points.append(pt)
    tasks = [(experiment, pt, shots, seed + i) for i, pt in enumerate(points)]
    if workers > 1 and len(tasks) > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_run_point, tasks, chunksize=max(1, len(tasks) // (4 * workers))))
    else:
        results = [_run_point(t) for t in tasks]
    return [dict(params=pt, **res) for pt, res in zip(points, results)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--experiment", required=True, choices=sorted(experiments.EXPERIMENTS))
    ap.add_argument("--grid", action="append", default=[])
    ap.add_argument("--fixed", action="append", default=[])
    ap.add_argument("--shots", type=int, default=0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--out", required=True)
    ap.add_argument("--git-commit", default=None)
    ap.add_argument("--max-bytes", type=int, default=qk_data.SIZE_LIMIT)
    a = ap.parse_args(argv)

    grids = [parse_grid(g) for g in a.grid]
    fixed = dict(parse_fixed(f) for f in a.fixed)
    t0 = time.perf_counter()
    rows = sweep(a.experiment, grids, fixed, a.shots, a.seed, a.workers)
    derived = experiments.DERIVED.get(a.experiment, lambda: {})()
    elapsed = time.perf_counter() - t0
    params = {"experiment": a.experiment, "grid": {n: v for n, v in grids}, "fixed": fixed,
              "shots": a.shots, "seed": a.seed, "workers": a.workers,
              "elapsed_s": round(elapsed, 3)}
    ds = qk_data.make_dataset("lab/sweep.py", params, {"rows": rows, "derived": derived},
                              git_commit=git_commit(a.git_commit))
    text = qk_data.dumps_dataset(ds)
    n = qk_data.check_size(text, a.max_bytes)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w") as fh:
        fh.write(text)
    print("wrote %s: %d rows, %d bytes, %.2fs" % (a.out, len(rows), n, elapsed))
    return 0


if __name__ == "__main__":       # required: process pools use forkserver on Python 3.14
    sys.exit(main())
