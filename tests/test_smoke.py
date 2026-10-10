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
    assert s["backend_run_calls"] == "1" and s["job_returned"] == "True"
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
    assert ("mode=%s" % mode) in s["packed"] and s["mode"].startswith(mode)
    assert s["scipy"] != "None" and not s["scipy"].startswith("MISSING")


def test_smoke_signature_is_qollab_form_compatible():
    import re
    src = open(os.path.join(ROOT, "smoke", "main.py")).read()
    assert 'mode: str = "auto"' in src
    sigs = re.findall(r"^def\s+main\s*\(.*$", src, flags=re.M)
    assert len(sigs) == 1
    params = re.search(r"\((.*)\)", sigs[0]).group(1).split(",")
    for p in params:
        name, rest = p.split(":")
        ann, default = [x.strip() for x in rest.split("=")]
        assert ann in ("int", "float", "str", "bool"), p
        assert not default.startswith("-") and default not in ("None",), p


class _FailingResultBackend:
    """Submits fine, then result() raises a multi-line error twice (poll + retry)."""
    __module__ = "qiskit_ionq.ionq_backend"
    name = "ionq_simulator(fake-failing)"
    num_qubits = 29

    def __init__(self):
        self.jobs = 0

    def run(self, run_input, shots=1024, **kw):
        self.jobs += 1

        class _Job:
            def job_id(self_):
                return "job-123"

            def result(self_):
                raise RuntimeError("IonQ: simulation failed\n(second line of detail)")
        return _Job()


def test_smoke_keeps_job_evidence_when_result_fails(capsys, monkeypatch):
    be = _FailingResultBackend()
    path = os.path.join(ROOT, "smoke")
    monkeypatch.chdir(path)
    monkeypatch.syspath_prepend(path)
    import sys
    for m in ("main", "qk_runtime", "qk_packer", "pkgtest", "pkgtest.sub"):
        sys.modules.pop(m, None)
    src = open(os.path.join(path, "main.py")).read()
    ns = {"__name__": "__main__", "backend": be}
    exec(compile(src + '\nmain(1000,"tile",False)\n', "<exec>", "exec"), ns)
    out = capsys.readouterr().out
    s = summary(out)
    assert be.jobs == 1                                   # the retry polls; it never resubmits
    assert s["job_id"] == "job-123" and s["job_returned"] == "True"
    assert s["backend_run_calls"] == "1"
    assert "RuntimeError" in s["result_retry"] and "RuntimeError" in s["job"]
    block = out.split("=== SMOKE SUMMARY")[1].split("=== END SMOKE SUMMARY")[0]
    assert all("=" in line for line in block.splitlines()[1:] if line.strip())   # one line per key


def test_smoke_survives_namespace_pkgtest(tmp_path, capsys):
    import shutil
    import sys
    proj = tmp_path / "smoke"
    shutil.copytree(os.path.join(ROOT, "smoke"), proj,
                    ignore=shutil.ignore_patterns("__pycache__"))
    (proj / "pkgtest" / "__init__.py").unlink()
    for m in ("main", "qk_runtime", "qk_packer", "pkgtest", "pkgtest.sub"):
        sys.modules.pop(m, None)
    cwd = os.getcwd()
    saved_path = list(sys.path)
    smoke_dir = os.path.join(ROOT, "smoke")
    sys.path[:] = [str(proj)] + [p for p in sys.path if os.path.abspath(p or ".") != smoke_dir]
    os.chdir(proj)
    try:
        from qiskit.providers.basic_provider import BasicSimulator
        ns = {"__name__": "__main__", "backend": BasicSimulator()}
        src = (proj / "main.py").read_text()
        exec(compile(src + '\nmain(200,"tile",True)\n', "<exec>", "exec"), ns)
    finally:
        os.chdir(cwd)
        sys.path[:] = saved_path
        for m in ("main", "qk_runtime", "qk_packer", "pkgtest", "pkgtest.sub"):
            sys.modules.pop(m, None)
    s = summary(capsys.readouterr().out)
    assert s["package_import"].startswith("namespace")
    assert s["orientation_ok"] == "True" and s["backend_run_calls"] == "1"
