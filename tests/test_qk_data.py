import json
import re
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

import qk_data as qd


def good(**over):
    d = qd.make_dataset("gen_chsh.py", {"shots": 4000, "angles": [0.0, 0.785]},
                        {"S": [2.81, 2.79]}, git_commit="abc1234",
                        versions={"python": "3.14.4", "qiskit": "2.5.2", "qiskit_aer": None,
                                  "numpy": "2.5.3"},
                        created_utc="2026-10-09T12:00:00Z")
    d.update(over)
    return d


def problems_of(d):
    with pytest.raises(ValueError) as ei:
        qd.validate_dataset(d)
    return str(ei.value)


# ---------------------------------------------------------------- building

def test_make_dataset_keys_and_round_trip():
    d = good()
    assert set(d) == set(qd.KEYS)
    assert d["schema"] == qd.SCHEMA and d["machine"] == qd.MACHINE
    text = qd.dumps_dataset(d)
    assert qd.parse_dataset(text) == d
    assert qd.dumps_dataset(qd.parse_dataset(text)) == text


def test_results_may_be_list():
    d = qd.make_dataset("g", {}, [1, 2, 3], git_commit="c", created_utc="2026-01-01T00:00:00Z")
    assert qd.parse_dataset(qd.dumps_dataset(d))["results"] == [1, 2, 3]


def test_default_created_utc_is_now_in_utc():
    d = qd.make_dataset("g", {}, {}, git_commit="c")
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", d["created_utc"])
    stamp = datetime.strptime(d["created_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert abs((datetime.now(timezone.utc) - stamp).total_seconds()) < 60


def test_created_utc_from_datetime():
    aware = datetime(2026, 10, 9, 18, 30, 5, tzinfo=timezone(timedelta(hours=-6)))
    assert qd.utc_stamp(aware) == "2026-10-10T00:30:05Z"
    assert qd.utc_stamp(datetime(2026, 1, 2, 3, 4, 5)) == "2026-01-02T03:04:05Z"


def test_default_versions_detected_without_importing_aer(monkeypatch):
    import qiskit
    for name in [m for m in sys.modules if m == "qiskit_aer" or m.startswith("qiskit_aer.")]:
        monkeypatch.delitem(sys.modules, name)
    d = qd.make_dataset("g", {}, {}, git_commit="c")
    assert "qiskit_aer" not in sys.modules
    v = d["versions"]
    assert set(v) == set(qd.VERSION_KEYS)
    assert v["python"] == "%d.%d.%d" % sys.version_info[:3]
    assert v["numpy"] == np.__version__ and v["qiskit"] == qiskit.__version__
    assert v["qiskit_aer"] is None or isinstance(v["qiskit_aer"], str)


def test_missing_package_version_is_none():
    assert qd._version("no-such-dist-xyz", "no_such_module_xyz") is None


def test_make_dataset_validates():
    with pytest.raises(ValueError, match="versions missing key 'numpy'"):
        qd.make_dataset("g", {}, {}, git_commit="c", versions={"python": "3", "qiskit": "2",
                                                                "qiskit_aer": None})
    with pytest.raises(ValueError, match="git_commit"):
        qd.make_dataset("g", {}, {}, git_commit="")


# ---------------------------------------------------------------- JSON safety

def test_dumps_is_compact_and_sorted():
    d = good(params={"b": 1, "a": [1, 2]})
    text = qd.dumps_dataset(d)
    assert text == json.dumps(d, separators=(",", ":"), sort_keys=True)
    assert ", " not in text and ": " not in text
    assert text.startswith('{"created_utc":')


def test_nan_and_inf_become_null():
    d = good(results={"x": float("nan"), "y": [np.inf, -np.inf, 1.5],
                      "z": np.array([np.nan, 2.0])})
    text = qd.dumps_dataset(d)
    assert "NaN" not in text and "Infinity" not in text
    back = qd.parse_dataset(text)["results"]
    assert back == {"x": None, "y": [None, None, 1.5], "z": [None, 2.0]}


def test_numpy_types_become_python():
    d = qd.make_dataset("g", {"n": np.int64(7), "flag": np.bool_(True), "name": np.str_("q")},
                        {"m": np.arange(6).reshape(2, 3), "f": np.float32(0.5),
                         "t": (np.float64(1.0), 2), np.int64(3): "int key"},
                        git_commit="c", created_utc="2026-01-01T00:00:00Z")
    p, r = d["params"], d["results"]
    assert type(p["n"]) is int and type(p["flag"]) is bool and type(p["name"]) is str
    assert r["m"] == [[0, 1, 2], [3, 4, 5]] and type(r["m"][0][0]) is int
    assert type(r["f"]) is float and r["t"] == [1.0, 2] and type(r["t"][0]) is float
    assert r["3"] == "int key"
    assert qd.parse_dataset(qd.dumps_dataset(d)) == d


def test_json_safe_rejects_non_json():
    with pytest.raises(TypeError, match=r"\$\.results\.c"):
        qd.json_safe({"results": {"c": 1 + 2j}})
    with pytest.raises(TypeError):
        qd.json_safe({1, 2})
    with pytest.raises(ValueError, match="duplicate key"):
        qd.json_safe({1: "a", "1": "b"})


def test_parse_rejects_nan_literals_and_paths():
    text = qd.dumps_dataset(good()).replace('"S":[2.81,2.79]', '"S":[NaN,2.79]')
    with pytest.raises(ValueError, match="NaN"):
        qd.parse_dataset(text)
    with pytest.raises(ValueError, match="not a path"):
        qd.parse_dataset("data/chsh.json")
    with pytest.raises(TypeError):
        qd.parse_dataset(None)
    assert qd.parse_dataset(qd.dumps_dataset(good()).encode("utf-8")) == good()


@pytest.mark.parametrize("literal", ["Infinity", "-Infinity", "1e999", "-1e999"])
def test_parse_rejects_infinite_numbers(literal):
    text = qd.dumps_dataset(good()).replace('"S":[2.81,2.79]', '"S":[%s,2.79]' % literal)
    with pytest.raises(ValueError, match="must be serialized as null"):
        qd.parse_dataset(text)


# ---------------------------------------------------------------- validation

def test_valid_dataset_passes():
    assert qd.validate_dataset(good()) is None
    assert qd.dataset_problems(good()) == []


def test_not_a_dict():
    assert "must be a JSON object" in problems_of([1, 2])
    with pytest.raises(ValueError):
        qd.parse_dataset("[1, 2]")


def test_wrong_and_missing_schema():
    assert "schema is 'other/1'" in problems_of(good(schema="other/1"))
    d = good()
    del d["schema"]
    assert "missing key 'schema'" in problems_of(d)


@pytest.mark.parametrize("key", qd.KEYS)
def test_each_missing_key(key):
    d = good()
    del d[key]
    assert "missing key %r" % key in problems_of(d)


@pytest.mark.parametrize("key,bad", [("generator", 3), ("generator", " "), ("git_commit", None),
                                     ("git_commit", ""), ("machine", ""), ("machine", ["x"])])
def test_string_fields(key, bad):
    assert "%s must be a non-empty str" % key in problems_of(good(**{key: bad}))


@pytest.mark.parametrize("bad", ["2026-10-09 12:00:00", "2026-10-09T12:00:00",
                                 "2026-13-01T00:00:00Z", "2026-10-09T12:00:00+00:00",
                                 "2026-02-30T00:00:00Z", "2026-10-09T12:00:00Z\n",
                                 "2026-10-09T12:00:00.5Z", "\uff12\uff10\uff12\uff16-10-09T12:00:00Z",
                                 1760000000, None])
def test_bad_created_utc(bad):
    assert "created_utc must be" in problems_of(good(created_utc=bad))


def test_versions_problems():
    assert "versions must be a dict" in problems_of(good(versions=["3.14"]))
    v = dict(good()["versions"])
    del v["qiskit_aer"]
    assert "versions missing key 'qiskit_aer'" in problems_of(good(versions=v))
    v = dict(good()["versions"], numpy=2)
    assert "versions['numpy'] must be a str or None" in problems_of(good(versions=v))


def test_params_and_results_types():
    assert "params must be a dict, got list" in problems_of(good(params=[1]))
    assert "results must be a dict or list, got str" in problems_of(good(results="x"))
    assert "results must be a dict or list" in problems_of(good(results=None))


def test_all_problems_listed_at_once():
    d = good(schema="x", generator="", created_utc="yesterday", machine=None, params=3,
             results=4, versions={})
    del d["git_commit"]
    msg = problems_of(d)
    for part in ("schema is 'x'", "missing key 'git_commit'", "generator must", "created_utc must",
                 "machine must", "params must", "results must", "versions missing key 'python'",
                 "versions missing key 'numpy'"):
        assert part in msg
    assert "(11 problems)" in msg


# ---------------------------------------------------------------- size

def test_check_size_counts_utf8_bytes():
    assert qd.check_size("abc") == 3
    assert qd.check_size("\u00b1") == 2
    assert qd.check_size(b"abcd") == 4
    text = qd.dumps_dataset(good())
    assert qd.check_size(text) == len(text.encode("utf-8"))


def test_check_size_limit():
    assert qd.check_size("x" * 10, limit=10) == 10
    with pytest.raises(ValueError, match="11 bytes, over the 10-byte limit"):
        qd.check_size("x" * 11, limit=10)
    assert qd.check_size("x" * qd.SIZE_LIMIT) == 2_000_000
    with pytest.raises(ValueError, match="2000001 bytes"):
        qd.check_size("x" * (qd.SIZE_LIMIT - 1) + "\u00b1")   # 2 UTF-8 bytes tip it over
    big = qd.dumps_dataset(good(results={"blob": "y" * qd.SIZE_LIMIT}))
    with pytest.raises(ValueError, match="over the 2000000-byte limit"):
        qd.check_size(big)
