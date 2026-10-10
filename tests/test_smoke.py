import filecmp
import os
import time

import pytest

import run_smoke_local

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def summary(out):
    block = out.split("=== SMOKE SUMMARY")[1].split("=== END SMOKE SUMMARY")[0]
    lines = [l for l in block.splitlines()[1:] if "=" in l]
    return dict(l.split("=", 1) for l in lines)


@pytest.mark.parametrize("module", ["qk_runtime.py", "qk_packer.py"])
def test_smoke_copies_in_sync(module):
    assert filecmp.cmp(os.path.join(ROOT, "qollab_project", module),
                       os.path.join(ROOT, "smoke", module), shallow=False), \
        "smoke/%s is stale: cp qollab_project/%s smoke/" % (module, module)


@pytest.mark.parametrize("mode", ["tile", "list"])
def test_smoke_runs_locally_one_job_under_10s(mode, capsys):
    t0 = time.perf_counter()
    be = run_smoke_local.run(mode=mode, shots=1000)
    elapsed = time.perf_counter() - t0
    out = capsys.readouterr().out
    s = summary(out)
    assert elapsed < 10, elapsed
    assert be.jobs == 1
    assert s["jobs_submitted"] == "1"
    assert s["orientation_ok"] == "True"
    assert s["package_import"] == "ok" and s["flat_import"] == "ok" and s["data_literal_path"] == "ok"
    assert s["family"] == "basic"
    assert "FAILED" not in s["dm_bench"]
    S, rest = s["S"].split("+/-")
    se = float(rest.split()[0])
    assert abs(float(S) - 2 * 2 ** 0.5) < 3 * se
    assert "Traceback" not in out and ": FAILED" not in out.replace("ErrorMitigation: FAILED", "")


def test_smoke_fake_ionq_path_one_job_no_transpile(capsys):
    be = run_smoke_local.run(mode="tile", shots=600, debias=False, fake_ionq=True)
    s = summary(capsys.readouterr().out)
    assert be.jobs == 1
    assert s["family"] == "ionq_sim" and s["one_job"] == "True"
    assert "'transpiled': False" in s["prepare"]
    assert s["orientation_ok"] == "True"


def test_smoke_main_has_no_main_guard_and_no_backend_construction():
    src = open(os.path.join(ROOT, "smoke", "main.py")).read()
    assert "__main__\":" not in src and "__name__ ==" not in src
    for forbidden in ("BasicSimulator(", "AerSimulator(", "IonQProvider(", "get_backend("):
        assert forbidden not in src


@pytest.mark.parametrize("call_line,mode", [('main(1000,"tile",True)', "tile"),
                                            ('main(400,"list",False)', "list")])
def test_smoke_qollab_style_exec_runs_exactly_once(call_line, mode, capsys):
    be = run_smoke_local.run_qollab_style(call_line)
    out = capsys.readouterr().out
    assert out.count("=== SMOKE SUMMARY") == 1     # main() ran once, despite __name__ == "__main__"
    assert be.jobs == 1
    s = summary(out)
    assert s["orientation_ok"] == "True" and s["flat_import"] == "ok" and s["package_import"] == "ok"
    assert ("mode=%s" % mode) in s["packed"]
    assert s["scipy"] != "None" and not s["scipy"].startswith("MISSING")


def test_smoke_signature_is_qollab_form_compatible():
    import re
    src = open(os.path.join(ROOT, "smoke", "main.py")).read()
    sigs = re.findall(r"^def\s+main\s*\(.*$", src, flags=re.M)
    assert len(sigs) == 1
    params = re.search(r"\((.*)\)", sigs[0]).group(1).split(",")
    for p in params:
        name, rest = p.split(":")
        ann, default = [x.strip() for x in rest.split("=")]
        assert ann in ("int", "float", "str", "bool"), p
        assert not default.startswith("-") and default not in ("None",), p
