import json
import math
import re

import numpy as np
import pytest

import qk_cards as qc
import qk_data as qd


def fields(**over):
    f = dict(id="chsh-ideal", claim="The Bell-state CHSH value exceeds the local bound.",
             assumptions=["Locality", "Free choice of settings"], witness="CHSH S",
             bound=2.0, quantum_ideal=2 * math.sqrt(2), raw={"value": 2.80, "se": 0.02},
             backend="basic_simulator", shots=4000)
    f.update(over)
    return f


def card(**over):
    return qc.claim_card(**fields(**over))


# ---------------------------------------------------------------- verdicts

@pytest.mark.parametrize("value,expect", [   # se = 0.25: exact binary fractions
    (2.75, qc.EXCEEDS),          # z = 3 exactly
    (2.80, qc.EXCEEDS),
    (2.70, qc.INCONCLUSIVE),     # z = 2.8
    (2.001, qc.INCONCLUSIVE),
    (2.00, qc.CONSISTENT),       # z = 0 exactly
    (1.50, qc.CONSISTENT),
])
def test_verdict_direction_max(value, expect):
    c = card(raw={"value": value, "se": 0.25})
    assert c["verdict"] == expect and c["verdict_basis"] == "raw"
    assert c["z_raw"] == pytest.approx((value - 2.0) / 0.25)
    assert c["z_mitigated"] is None and c["mitigated"] is None


@pytest.mark.parametrize("value,expect", [
    (-0.4, qc.EXCEEDS), (0.25, qc.EXCEEDS),     # z = 3 exactly at 0.25
    (0.30, qc.INCONCLUSIVE), (0.999, qc.INCONCLUSIVE), (1.0, qc.CONSISTENT), (1.3, qc.CONSISTENT),
])
def test_verdict_direction_min(value, expect):
    c = card(direction="min", bound=1.0, quantum_ideal=-0.5, raw={"value": value, "se": 0.25})
    assert c["direction"] == "min"
    assert c["z_raw"] == pytest.approx((1.0 - value) / 0.25)
    assert c["verdict"] == expect


def test_mitigated_is_the_basis_when_present():
    c = card(raw={"value": 2.03, "se": 0.02},
             mitigated={"value": 2.5, "se": 0.05, "method": "readout"})
    assert c["verdict"] == qc.EXCEEDS and c["verdict_basis"] == "mitigated"
    assert c["z_raw"] == pytest.approx(1.5) and c["z_mitigated"] == pytest.approx(10.0)
    c = card(raw={"value": 2.8, "se": 0.02},
             mitigated={"value": 1.9, "se": 0.05, "method": "zne"})
    assert c["verdict"] == qc.CONSISTENT and c["verdict_basis"] == "mitigated"
    c = card(direction="min", bound=0.0, raw={"value": 0.5, "se": 0.1},
             mitigated={"value": -0.1, "se": 0.1, "method": "zne"})
    assert c["verdict"] == qc.INCONCLUSIVE and c["z_mitigated"] == pytest.approx(1.0)


def test_zero_se_gives_infinite_z_stored_as_none():
    c = card(raw={"value": 3.0, "se": 0.0})
    assert c["z_raw"] is None and c["verdict"] == qc.EXCEEDS
    assert "+inf (se = 0)" in qc.card_text(c)
    c = card(raw={"value": 1.0, "se": 0.0})
    assert c["z_raw"] is None and c["verdict"] == qc.CONSISTENT
    c = card(raw={"value": 2.0, "se": 0.0})
    assert c["z_raw"] == 0.0 and c["verdict"] == qc.CONSISTENT
    c = card(direction="min", bound=1.0, raw={"value": 0.5, "se": 0.0},
             mitigated={"value": 1.5, "se": 0.0, "method": "m"})
    assert c["z_raw"] is None and c["z_mitigated"] is None and c["verdict"] == qc.CONSISTENT
    json.dumps(c, allow_nan=False)
    assert "z = +inf (se = 0)" in qc.card_text(c) and "z = -inf (se = 0)" in qc.card_text(c)


def test_verdict_for():
    assert qc.verdict_for(3.0) == qc.EXCEEDS
    assert qc.verdict_for(math.inf) == qc.EXCEEDS
    assert qc.verdict_for(0.0) == qc.CONSISTENT
    assert qc.verdict_for(-math.inf) == qc.CONSISTENT
    assert qc.verdict_for(1e-9) == qc.INCONCLUSIVE


# ---------------------------------------------------------------- fields

def test_schema_and_defaults():
    c = card()
    assert c["schema"] == "claim-card/1" and c["direction"] == "max"
    assert c["simulator"] is True and c["noise"] is None and c["provenance"] == {}
    assert c["counterarguments"] == [] and c["notes"] == ""


def test_missing_required_fields_listed():
    f = fields()
    for k in ("claim", "bound", "raw"):
        del f[k]
    with pytest.raises(ValueError) as ei:
        qc.claim_card(**f)
    assert "missing required field(s): claim, bound, raw" in str(ei.value)
    with pytest.raises(ValueError, match="id, claim, assumptions, witness, bound"):
        qc.claim_card()


@pytest.mark.parametrize("over,msg", [
    ({"direction": "up"}, "direction must be one of"),
    ({"assumptions": "Locality"}, "assumptions must be a list of str"),
    ({"assumptions": []}, "assumptions must not be empty"),
    ({"assumptions": ["ok", ""]}, "assumptions items"),
    ({"bound": float("nan")}, "bound must be a finite number"),
    ({"bound": "2"}, "bound must be a finite number"),
    ({"shots": 0}, "shots must be a positive int"),
    ({"shots": 10.5}, "shots must be a positive int"),
    ({"raw": {"value": 2.5}}, "raw missing se"),
    ({"raw": {"value": float("nan"), "se": 0.1}}, "raw.value must be a finite number"),
    ({"raw": {"value": 2.5, "se": -0.1}}, "raw.se must be"),
    ({"raw": [2.5, 0.1]}, "raw must be a dict"),
    ({"mitigated": {"value": 2.5, "se": 0.1}}, "mitigated missing method"),
    ({"noise": "depolarizing"}, "noise must be a dict or None"),
    ({"simulator": "False"}, "simulator must be a bool"),
    ({"claim": ""}, "claim must be a non-empty str"),
    ({"witness": 5}, "witness must be a non-empty str"),
    ({"mitgated": {}}, "unknown field(s): mitgated"),
])
def test_malformed_fields(over, msg):
    with pytest.raises(ValueError) as ei:
        card(**over)
    assert msg in str(ei.value)


def test_simulator_note_added_exactly_once():
    c = card(not_shown=["Device-independent security."])
    assert c["not_shown"] == ["Device-independent security.", qc.SIM_NOTE]
    assert qc.SIM_NOTE == ("This is a simulation. It computes what quantum theory predicts, "
                           "and how the chosen noise model degrades it; it is not a test of "
                           "nature.")
    again = card(not_shown=c["not_shown"] + [qc.SIM_NOTE])
    assert again["not_shown"].count(qc.SIM_NOTE) == 1
    rebuilt = qc.claim_card(**{k: v for k, v in c.items() if k in qc.REQUIRED + qc.OPTIONAL})
    assert rebuilt == c
    hw = card(simulator=False, not_shown=["x"])
    assert hw["not_shown"] == ["x"] and hw["simulator"] is False
    assert qc.claim_card(**dict(c, simulator=False))["not_shown"] == [
        "Device-independent security."]                 # never claims "simulation" on hardware


def test_card_rebuilds_from_itself_with_recomputed_verdict():
    c = card(mitigated={"value": 2.5, "se": 0.1, "method": "readout"})
    assert qc.claim_card(**c) == c and c["not_shown"].count(qc.SIM_NOTE) == 1
    worse = qc.claim_card(**dict(c, mitigated={"value": 2.1, "se": 0.1, "method": "readout"}))
    assert worse["verdict"] == qc.INCONCLUSIVE and worse["z_mitigated"] == pytest.approx(1.0)
    forged = qc.claim_card(**dict(c, verdict=qc.EXCEEDS, z_raw=99.0, schema="x/9",
                                  raw={"value": 1.0, "se": 0.5}, mitigated=None))
    assert forged["verdict"] == qc.CONSISTENT and forged["z_raw"] == pytest.approx(-2.0)
    assert forged["schema"] == qc.SCHEMA and forged["verdict_basis"] == "raw"


def test_json_safe_with_numpy_and_nan():
    c = card(id=np.int64(7), bound=np.float64(2.0), quantum_ideal=np.float32(2.75),
             raw={"value": np.float64(2.5), "se": np.float32(0.05), "n": np.int64(4)},
             mitigated={"value": np.float64(2.6), "se": 0.06, "method": np.str_("zne")},
             shots=np.int64(1000), simulator=np.bool_(True),
             noise={"p": np.array([0.01, 0.02]), "t1": float("inf")},
             provenance={"seed": np.int64(3), "bad": float("nan")},
             assumptions=("Locality",))
    text = json.dumps(c, allow_nan=False)
    assert json.loads(text) == c
    assert c["id"] == "7" and type(c["shots"]) is int and type(c["bound"]) is float
    assert type(c["raw"]["n"]) is int and c["noise"] == {"p": [0.01, 0.02], "t1": None}
    assert c["provenance"]["bad"] is None and c["mitigated"]["method"] == "zne"
    assert c["simulator"] is True and c["assumptions"] == ["Locality"]
    c = card(quantum_ideal=float("nan"))
    assert c["quantum_ideal"] is None
    json.dumps(c, allow_nan=False)


def test_card_survives_dataset_round_trip():
    c = card(mitigated={"value": 2.7, "se": 0.03, "method": "readout"})
    d = qd.make_dataset("gen.py", {}, {"cards": [c]}, git_commit="c",
                        created_utc="2026-10-09T00:00:00Z")
    assert qd.parse_dataset(qd.dumps_dataset(d))["results"]["cards"][0] == c


# ---------------------------------------------------------------- rendering

def long_card():
    return card(
        id="ghz-" + "x" * 130,
        claim="The GHZ state |ψ⟩ = (|000⟩ + |111⟩)/√2 gives "
              "⟨M⟩ ≥ 2 ± noise. " * 4 + "café 漢 \x1b[31mred\x1b[0m",
        assumptions=["A very long assumption " * 12, "unbreakable-" + "y" * 150],
        mitigated={"value": 3.5, "se": 0.1, "method": "readout | zne " * 10},
        noise={"model": "depolarizing", "p": [0.001] * 40},
        provenance={"generator": "lab/gen.py", "seed": 11, "layout": {"mode": "tile"}},
        counterarguments=["Counterargument " * 20], notes="note " * 40,
        not_shown=["Loophole-free violation."])


def test_card_text_ascii_and_width():
    for c in (card(), long_card()):
        text = qc.card_text(c)
        assert text.isascii() and "\x1b" not in text
        assert all(len(line) <= 100 for line in text.splitlines())
        assert all(ord(ch) >= 32 for line in text.splitlines() for ch in line)
    text = qc.card_text(long_card())
    assert "|psi> = (|000> + |111>)/sqrt2" in text and ">= 2 +- noise" in text
    assert "cafe ?" in text


def test_card_text_content():
    c = card(mitigated={"value": 2.5, "se": 0.1, "method": "readout"},
             counterarguments=["Readout errors are modeled, not measured."],
             noise={"readout": 0.02})
    text = qc.card_text(c)
    lines = text.splitlines()
    assert lines[1].startswith("CLAIM CARD") and "chsh-ideal" in lines[1]
    order = ["Claim:", "Assumptions:", "Witness:", "Classical bound:", "Quantum ideal:", "Raw:",
             "Mitigated:", "VERDICT:", "Backend:", "Noise:", "What this does NOT show:",
             "Counterarguments:"]
    pos = [next(i for i, l in enumerate(lines) if l.startswith(lab)) for lab in order]
    assert pos == sorted(pos)
    assert "VERDICT:          exceeds classical bound" in text
    assert "2.8 +- 0.02  (z = +40.00)" in text
    assert "method: readout" in text and "readout=0.02" in text
    assert "basis: mitigated z = +5.00" in text and "shots: 4000" in text
    assert "it is not a test" in text
    plain = qc.card_text(card(simulator=False))
    assert "Mitigated:" not in plain and "(hardware)" in plain and "(none recorded)" in plain
    noise_line = next(l for l in qc.card_text(card()).splitlines() if l.startswith("Noise:"))
    assert "ideal" not in noise_line and "none recorded" in noise_line


def test_card_markdown_sections_in_order():
    c = card(mitigated={"value": 2.5, "se": 0.1, "method": "a|b"},
             counterarguments=["Finite statistics."], notes="See appendix.")
    md = qc.card_markdown(c)
    heads = re.findall(r"^### (.+)$", md, flags=re.M)
    assert tuple(heads) == qc.MD_HEADINGS
    assert qc.MD_HEADINGS == ("Claim", "Assumptions", "Witness", "Result ± se",
                              "What this does NOT show", "Counterarguments")
    assert md.startswith("## Claim card: chsh-ideal")
    assert "**Verdict: exceeds classical bound**" in md
    assert "| raw | 2.8 ± 0.02 | +40.00 | none |" in md
    assert "| mitigated | 2.5 ± 0.1 | +5.00 | a\\|b |" in md
    assert "- Locality" in md and "- Finite statistics." in md and qc.SIM_NOTE in md
    assert md.index("Finite statistics.") > md.index(qc.SIM_NOTE) > md.index("**Verdict")
    assert "*Notes:* See appendix." in md
    md4 = qc.card_markdown(long_card(), level=3)
    assert tuple(re.findall(r"^#### (.+)$", md4, flags=re.M)) == qc.MD_HEADINGS
    sneaky = card(claim="line one\n### Injected", assumptions=["a\n# Also injected"],
                  counterarguments=["c\r\n### x"], notes="n\n### y")
    md = qc.card_markdown(sneaky)
    assert tuple(re.findall(r"^#+ (.+)$", md, flags=re.M)) == ("Claim card: chsh-ideal",) + \
        qc.MD_HEADINGS
    assert "line one ### Injected" in md and "- a # Also injected" in md


def test_markdown_min_direction_bound_text():
    md = qc.card_markdown(card(direction="min", bound=1.0, raw={"value": 0.5, "se": 0.1}))
    assert "classical value ≥ 1; the claim needs a smaller value" in md
    assert "classical value >= 1" in qc.card_text(card(direction="min", bound=1.0,
                                                       raw={"value": 0.5, "se": 0.1}))
