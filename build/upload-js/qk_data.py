"""Shipped precomputed datasets: build, serialize, parse and validate.

Datasets are generated offline under CPython and shipped as JSON next to the
project. In the browser the loader takes TEXT, never a path: the runtime only
bundles files whose path appears literally at the call site, so write

    d = qk_data.parse_dataset(open("data/chsh_noise.json").read())

Every dataset records its schema tag, generator, git commit, UTC creation time,
library versions and the class of machine that computed it, so a shipped number
can be traced back to the code and settings that produced it.

Serialized datasets are strict JSON: NaN/inf become null, numpy scalars and
arrays become plain Python values, and text containing NaN/Infinity literals (or
a number that overflows to inf, like 1e999) is rejected on parse.
"""

import json
import math
import re
import sys
from datetime import datetime, timezone

import numpy as np

__all__ = [
    "SCHEMA", "MACHINE", "SIZE_LIMIT", "make_dataset", "dumps_dataset", "parse_dataset",
    "validate_dataset", "dataset_problems", "check_size", "json_safe", "detect_versions",
    "utc_stamp",
]

SCHEMA = "qollab-hack-dataset/1"
MACHINE = "48-thread x86 workstation"
SIZE_LIMIT = 2_000_000
KEYS = ("schema", "generator", "git_commit", "created_utc", "versions", "machine",
        "params", "results")
VERSION_KEYS = ("python", "qiskit", "qiskit_aer", "numpy")
_VERSION_SOURCES = (           # key, distribution name, module name
    ("qiskit", "qiskit", "qiskit"),
    ("qiskit_aer", "qiskit-aer", "qiskit_aer"),
    ("numpy", "numpy", "numpy"),
)
_UTC_FMT = "%Y-%m-%dT%H:%M:%SZ"
# [0-9], not \d: \d (and strptime) would accept non-ASCII digits such as fullwidth ones.
_UTC_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")


def json_safe(obj, _path="$"):
    """Deep copy of `obj` built from JSON types only.

    numpy scalars/arrays -> Python values, tuples -> lists, NaN/inf -> None,
    non-str dict keys -> their JSON text (3 -> "3", True -> "true"). Anything
    else (complex, sets, arbitrary objects) raises TypeError naming the path.
    """
    if obj is None or isinstance(obj, bool):
        return obj
    if isinstance(obj, str):
        return str(obj)
    if isinstance(obj, int):
        return int(obj)
    if isinstance(obj, float):
        return float(obj) if math.isfinite(obj) else None
    if isinstance(obj, np.generic):
        return json_safe(obj.item(), _path)
    if isinstance(obj, np.ndarray):
        return json_safe(obj.tolist(), _path)
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            key = str(k) if isinstance(k, str) else json.dumps(json_safe(k, _path + "<key>"))
            if key in out:
                raise ValueError("duplicate key %r at %s after conversion" % (key, _path))
            out[key] = json_safe(v, "%s.%s" % (_path, key))
        return out
    if isinstance(obj, (list, tuple)):
        return [json_safe(v, "%s[%d]" % (_path, i)) for i, v in enumerate(obj)]
    raise TypeError("not JSON-safe at %s: %s" % (_path, type(obj).__name__))


def _version(dist, module):
    """Version of an installed package, or None. Reads an already-imported module's
    __version__ first, else package metadata; never imports the package itself."""
    mod = sys.modules.get(module)
    ver = getattr(mod, "__version__", None) if mod is not None else None
    if ver is None:
        try:
            from importlib import metadata
            ver = metadata.version(dist)
        except Exception:
            ver = None
    return str(ver) if ver is not None else None


def detect_versions():
    """{python, qiskit, qiskit_aer, numpy} -> version string, None when not installed."""
    out = {"python": "%d.%d.%d" % tuple(sys.version_info[:3])}
    for key, dist, module in _VERSION_SOURCES:
        out[key] = _version(dist, module)
    return out


def utc_stamp(when=None):
    """ISO 8601 UTC stamp "YYYY-MM-DDTHH:MM:SSZ". None -> now; naive datetimes are
    taken as UTC; strings pass through unchanged (validation checks them)."""
    if when is None:
        when = datetime.now(timezone.utc)
    if isinstance(when, datetime):
        if when.tzinfo is not None:
            when = when.astimezone(timezone.utc)
        return when.strftime(_UTC_FMT)
    return when


def make_dataset(generator, params, results, *, git_commit, versions=None, machine=MACHINE,
                 created_utc=None):
    """Assemble and validate a dataset dict. `params`/`results` are made JSON-safe."""
    d = {
        "schema": SCHEMA,
        "generator": generator,
        "git_commit": git_commit,
        "created_utc": utc_stamp(created_utc),
        "versions": detect_versions() if versions is None else versions,
        "machine": machine,
        "params": params,
        "results": results,
    }
    d = json_safe(d)
    validate_dataset(d)
    return d


def _nonempty_str(x):
    return isinstance(x, str) and bool(x.strip())


def _utc_ok(s):
    if not isinstance(s, str) or not _UTC_RE.fullmatch(s):
        return False
    try:
        datetime.strptime(s, _UTC_FMT)
    except ValueError:
        return False
    return True


def dataset_problems(d):
    """Every problem with `d` as a list of messages; [] means valid."""
    if not isinstance(d, dict):
        return ["dataset must be a JSON object (dict), got %s" % type(d).__name__]
    problems = ["missing key %r" % k for k in KEYS if k not in d]
    if "schema" in d and d["schema"] != SCHEMA:
        problems.append("schema is %r, expected %r" % (d["schema"], SCHEMA))
    for key in ("generator", "git_commit", "machine"):
        if key in d and not _nonempty_str(d[key]):
            problems.append("%s must be a non-empty str, got %r" % (key, d[key]))
    if "created_utc" in d and not _utc_ok(d["created_utc"]):
        problems.append("created_utc must be 'YYYY-MM-DDTHH:MM:SSZ' (UTC), got %r"
                        % (d["created_utc"],))
    if "versions" in d:
        ver = d["versions"]
        if not isinstance(ver, dict):
            problems.append("versions must be a dict, got %s" % type(ver).__name__)
        else:
            problems += ["versions missing key %r" % k for k in VERSION_KEYS if k not in ver]
            problems += ["versions[%r] must be a str or None, got %r" % (k, v)
                         for k, v in ver.items() if v is not None and not isinstance(v, str)]
    if "params" in d and not isinstance(d["params"], dict):
        problems.append("params must be a dict, got %s" % type(d["params"]).__name__)
    if "results" in d and not isinstance(d["results"], (dict, list)):
        problems.append("results must be a dict or list, got %s" % type(d["results"]).__name__)
    return problems


def validate_dataset(d):
    """Raise ValueError listing ALL problems with `d`; return None when valid."""
    problems = dataset_problems(d)
    if problems:
        raise ValueError("invalid dataset (%d problem%s): %s" % (
            len(problems), "" if len(problems) == 1 else "s", "; ".join(problems)))


def dumps_dataset(d):
    """Validated, compact, key-sorted strict JSON text for a dataset."""
    d = json_safe(d)
    validate_dataset(d)
    return json.dumps(d, separators=(",", ":"), sort_keys=True, allow_nan=False)


def _reject_constant(name):
    raise ValueError("dataset JSON contains %s; NaN/inf must be serialized as null" % name)


def _finite_float(s):
    x = float(s)
    if not math.isfinite(x):        # e.g. 1e999 overflows to inf without any literal
        _reject_constant(s)
    return x


def parse_dataset(text):
    """JSON TEXT -> validated dataset dict. Takes the file's contents, never a path."""
    if isinstance(text, (bytes, bytearray)):
        text = bytes(text).decode("utf-8")
    if not isinstance(text, str):
        raise TypeError("parse_dataset takes JSON text (str), got %s" % type(text).__name__)
    stripped = text.strip()
    if stripped.endswith(".json") and not stripped.startswith(("{", "[")):
        raise ValueError("parse_dataset takes JSON text, not a path; use "
                         "parse_dataset(open(%r).read())" % stripped)
    d = json.loads(text, parse_constant=_reject_constant, parse_float=_finite_float)
    validate_dataset(d)
    return d


def check_size(text, limit=SIZE_LIMIT):
    """UTF-8 size of `text` in bytes; ValueError when it exceeds `limit`."""
    n = len(text) if isinstance(text, (bytes, bytearray)) else len(text.encode("utf-8"))
    if n > limit:
        raise ValueError("dataset is %d bytes, over the %d-byte limit" % (n, limit))
    return n
