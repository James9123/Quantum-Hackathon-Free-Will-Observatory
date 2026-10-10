import pytest
from qiskit import QuantumCircuit
from qiskit.providers.basic_provider import BasicSimulator

import qk_runtime as rt


# ---------------------------------------------------------------- normalize_counts

def test_normalize_plain_and_padding():
    assert rt.normalize_counts({"1": 3, "10": 5}, 4) == {"0001": 3, "0010": 5}


def test_normalize_strips_register_spaces():
    assert rt.normalize_counts({"01 10": 7, "00 00": 1}, 4) == {"0000": 1, "0110": 7}


def test_normalize_hex_int_and_0b_keys():
    raw = {"0x5": 2, 3: 4, "0b110": 1}
    assert rt.normalize_counts(raw, 3) == {"011": 4, "101": 2, "110": 1}


def test_normalize_decimal_keys():
    # IonQ-API-style histograms key outcomes by decimal state index
    assert rt.normalize_counts({"5": 1, "2": 2}, 3) == {"010": 2, "101": 1}
    assert rt.normalize_counts({"10": 1}, 4, key_format="dec") == {"1010": 1}
    assert rt.normalize_counts({"10": 1}, 4) == {"0010": 1}   # auto: 0/1 only -> binary


def test_normalize_merges_collisions():
    assert rt.normalize_counts({"01": 1, "0x1": 2, 1: 3}, 2) == {"01": 6}


def test_normalize_trims_only_zero_padding():
    assert rt.normalize_counts({"00101": 4}, 3) == {"101": 4}
    with pytest.raises(ValueError):
        rt.normalize_counts({"10101": 4}, 3)


def test_normalize_probabilities_scaled_by_shots():
    out = rt.normalize_counts({"00": 0.25, "11": 0.75}, 2, shots=1000)
    assert out == {"00": 250, "11": 750}


def test_normalize_drops_zero_counts_and_rejects_garbage():
    assert rt.normalize_counts({"00": 0, "11": 2}, 2) == {"11": 2}
    with pytest.raises(ValueError):
        rt.normalize_counts({"abc": 1}, 2)


# ---------------------------------------------------------------- backend_profile

def _fake_backend(module, name, num_qubits=None):
    cls = type("FakeBackend", (), {"__module__": module})
    obj = cls()
    obj.name = name
    if num_qubits is not None:
        obj.num_qubits = num_qubits
    return obj


@pytest.mark.parametrize("module,name,qubits,family,one_job,maxq", [
    ("qiskit_ionq.ionq_backend", "simulator", 29, "ionq_sim", True, 29),
    ("qollab.bridge", "IonQ Forte 1", None, "ionq_sim", True, 29),
    ("qiskit_ionq.ionq_backend", "qpu.forte-1", 36, "ionq_qpu", True, 36),
    ("qiskit_braket_provider.providers.braket_backend", "default", 25, "braket_local", False, 25),
    ("qiskit_ibm_runtime.fake_provider.backends.fez.fake_fez", "fake_fez", 156, "ibm_noise", False, 24),
    ("qiskit_aer.backends.aer_simulator", "aer_simulator_from(fake_fez)", 156, "ibm_noise", False, 24),
    ("somewhere.else", "mystery", None, "unknown", True, 20),
    ("somewhere.else", "mystery", 12, "unknown", True, 12),
])
def test_profile_families(module, name, qubits, family, one_job, maxq):
    p = rt.backend_profile(_fake_backend(module, name, qubits))
    assert p["family"] == family
    assert p["one_job"] is one_job
    assert p["max_qubits"] == maxq
    assert p["transpile"] is (not family.startswith("ionq"))


class _Opts(dict):
    pass


def test_profile_ionq_noise_model_cap_and_implausible_qubit_count():
    be = _fake_backend("qiskit_ionq.ionq_backend", "ionq_simulator", 4)   # lookup-failure fallback
    be.options = _Opts(noise_model="forte-1")
    p = rt.backend_profile(be)
    assert p["max_qubits"] == 29 and p["reported_qubits"] == 4 and p["noise_model"] == "forte-1"
    be.options = _Opts(noise_model="aria-1")
    assert rt.backend_profile(be)["max_qubits"] == 25
    be2 = _fake_backend("qiskit_ionq.ionq_backend", "ionq_simulator", 20)
    assert rt.backend_profile(be2)["max_qubits"] == 20


def test_profile_basic_simulator():
    p = rt.backend_profile(BasicSimulator())
    assert p["family"] == "basic" and p["max_qubits"] == 24 and p["one_job"] is False
    assert p["remote"] is False and p["noisy"] is False


# ---------------------------------------------------------------- run_once / guard

def _bell():
    qc = QuantumCircuit(2, 2)
    qc.h(0)
    qc.cx(0, 1)
    qc.measure([0, 1], [0, 1])
    return qc


def _ghz3():
    qc = QuantumCircuit(3, 3)
    qc.h(0)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.measure([0, 1, 2], [0, 1, 2])
    return qc


def test_run_once_single_and_list():
    be = BasicSimulator()
    be.set_options(seed_simulator=3)
    prof = rt.backend_profile(be)
    rt.begin_run()
    one = rt.run_once(be, _bell(), 200, prof)
    assert len(one) == 1 and set(one[0]) <= {"00", "11"} and sum(one[0].values()) == 200
    two = rt.run_once(be, [_bell(), _ghz3()], 100, prof)   # local backends: more jobs allowed
    assert set(two[1]) <= {"000", "111"} and rt.LAST_RUN["submitted_as"] == "list"
    assert rt.jobs_submitted() == 2


def test_one_job_guard_blocks_second_submission_and_resets():
    be = BasicSimulator()
    prof = dict(rt.backend_profile(be), one_job=True)
    rt.begin_run()
    rt.run_once(be, _bell(), 10, prof)
    with pytest.raises(RuntimeError, match="one-job guard"):
        rt.run_once(be, _bell(), 10, prof)
    assert rt.jobs_submitted() == 1
    rt.begin_run()
    rt.run_once(be, _bell(), 10, prof)


def test_prepare_transpiles_local_and_leaves_ionq_alone():
    be = BasicSimulator()
    qc = _bell()
    out = rt.prepare([qc], be, rt.backend_profile(be))
    assert rt.LAST_RUN["prepare"]["transpiled"] is True and len(out) == 1
    ionq = dict(rt.backend_profile(be), family="ionq_sim", transpile=False)
    out2 = rt.prepare([qc], be, ionq)
    assert out2[0] is qc and rt.LAST_RUN["prepare"]["transpiled"] is False


def test_prepare_falls_back_when_transpile_fails():
    qc = _bell()
    out = rt.prepare([qc], object(), {"transpile": True})
    assert out[0] is qc and rt.LAST_RUN["prepare"]["error"]


def test_ionq_run_kwargs_default_and_missing_provider():
    assert rt.ionq_run_kwargs(True) == {}
    try:
        import qiskit_ionq  # noqa: F401
    except ImportError:
        assert rt.ionq_run_kwargs(False) == {}
        assert "unavailable" in rt.LAST_RUN["debias_note"]
