"""The Free Will Observatory: the quantum model behind the fiction.

A two-qubit instrument. Qubit 0 is the "Self", qubit 1 the "World". Three controls:

- Intention: a phase phi on the Self, RZ(phi). Range 0..2*pi, default pi/2.
- World coupling: the slider w in 0..1 sets gamma = w*pi/2, applied as a
  controlled RY(2*gamma) from the Self onto the World (RY/CX/RY/CX block).
- Perspective: an equatorial readout angle beta in 0..pi: RZ(-beta), then H,
  then a Z measurement of the Self.

Circuit (guide p.4): prepare |00>; H(Self); RZ(phi, Self); controlled-RY(2*gamma);
RZ(-beta, Self); H(Self); measure both. Before readout the state is, up to a phase,
[|00> + e^{i phi} cos(gamma)|10> + e^{i phi} sin(gamma)|11>] / sqrt(2) (ket order
Self, World). Ideal P(Self=1) = [1 - cos(gamma) cos(phi - beta)] / 2.

Four probes make one run (guide p.5): display (the user's phi, gamma, beta),
intent_low (phi = beta), intent_high (phi = beta + pi) and connection (phi, gamma,
no final RZ/H, both qubits read in Z). Three readings (guide p.6):

- Capacity C = |p_high - p_low|, the total variation distance between the two
  binary Self distributions under opposite intentions; ideal C = cos(gamma).
- Openness O = binary entropy of the display P(Self=1), in bits.
- Connection I = classical mutual information of the connection probe, in bits.

A conservative 95% interval for d = p_high - p_low is d +/- e with
e = sqrt(ln(80)/(2 N_low)) + sqrt(ln(80)/(2 N_high)) (Hoeffding + union bound),
clipped to [-1, 1] and mapped through |.| to an interval for C. When that interval
includes zero the honest reading is "No resolved influence at this shot count."

Bit order: the app uses SelfWorld ("10" = Self 1, World 0). The block-local keys
that qk_packer returns for a block measured as [Self, World] are Qiskit's, clbit 0
rightmost, i.e. World then Self; `canonical_counts` reverses them exactly once.

Honesty: a simulator computes what quantum theory predicts for these circuits (and
how a noise model degrades it); it does not test nature. The correspondence
between the controls and the words "intention", "World" and "perspective" is
designed, not discovered, and the readings are a fictional model of agency, not a
measurement of free will.

Works under CPython and Pyodide; depends on qiskit, numpy and the qk_* toolkit.

This effort is supported by Qollab & IonQ
"""

import math
import time

import qk_data
import qk_noise
import qk_packer
import qk_runtime

__all__ = [
    "MODEL_VERSION", "BIT_ORDER", "PROBES", "OUTCOMES", "PERSONAS", "MODES", "DEFAULTS",
    "SHOTS_MIN", "SHOTS_MAX", "FORMULA", "NO_RESOLVED", "SIM_NOTE", "ATTRIBUTION",
    "validate_settings", "make_circuit", "probes", "canonical_counts", "ideal_p_self_1",
    "binary_entropy", "mutual_information", "hoeffding_e", "capacity_interval",
    "metrics", "exact_probe_distributions", "exact_metrics", "prediction",
    "noisy_prediction", "baselines", "explanation", "run", "versions",
]

MODEL_VERSION = "fwo-1"
BIT_ORDER = "SelfWorld"
PROBES = ("display", "intent_low", "intent_high", "connection")
OUTCOMES = ("00", "01", "10", "11")
PERSONAS = ("self", "demon", "observer")
MODES = ("auto", "tile", "list")
SHOTS_MIN, SHOTS_MAX = 1, 4096
TWO_PI = 2.0 * math.pi
LN80 = math.log(80.0)
_TOL = 1e-9                      # slack on the upper range limits (JS rounding of 2*pi)

DEFAULTS = {
    "intention_rad": math.pi / 2,
    "world_coupling": 0.0,
    "perspective_rad": 0.0,
    "shots_per_probe": 1024,
    "persona": "self",
    "mode": "auto",
    "canary": True,
}
FORMULA = "P(Self=1) = [1 - cos(gamma) cos(phi - beta)] / 2, with gamma = w * pi / 2"
NO_RESOLVED = "No resolved influence at this shot count."
SIM_NOTE = ("This is a simulation: it computes what quantum theory predicts for these "
            "circuits, and how a noise model would degrade that prediction. It does not "
            "test nature. The readings are a designed, fictional model of agency, not a "
            "measurement of free will.")
ATTRIBUTION = "This effort is supported by Qollab & IonQ"
PERSONA_NOTE = ("Persona lines are artistic interpretation of a designed model; the "
                "factual sentence and the counts are the record.")
_BASELINE_NOTE = ("Theoretical classical references: their contrast explains the metric; "
                  "it is not a proof that classical systems cannot have capacity.")


# ---------------------------------------------------------------- settings

def _missing(value):
    """True for None and for Pyodide's stand-ins for JS null/undefined."""
    return value is None or type(value).__name__ in ("JsNull", "JsUndefined")


def _as_float(value, what, lo, hi):
    if isinstance(value, bool):
        raise ValueError("%s must be a number, got a bool" % what)
    try:
        x = float(value)
    except (TypeError, ValueError):
        raise ValueError("%s must be a number, got %r" % (what, value))
    if not math.isfinite(x):
        raise ValueError("%s must be finite" % what)
    if x < lo or x > hi + _TOL * max(1.0, abs(hi)):
        raise ValueError("%s must be in [%g, %g], got %g" % (what, lo, hi, x))
    return min(max(x, lo), hi)


def _as_int(value, what, lo, hi):
    if isinstance(value, bool):
        raise ValueError("%s must be an integer, got a bool" % what)
    if isinstance(value, str):
        value = value.strip()
        if not value.lstrip("-").isdigit():
            raise ValueError("%s must be an integer, got %r" % (what, value))
    try:
        x = float(value)
    except (TypeError, ValueError):
        raise ValueError("%s must be an integer, got %r" % (what, value))
    if not math.isfinite(x) or not x.is_integer():
        raise ValueError("%s must be a whole number, got %r" % (what, value))
    n = int(x)
    if n < lo or n > hi:
        raise ValueError("%s must be in [%d, %d], got %d" % (what, lo, hi, n))
    return n


def _as_bool(value, what):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ("1", "true", "yes", "on"):
            return True
        if s in ("0", "false", "no", "off", ""):
            return False
    raise ValueError("%s must be true or false, got %r" % (what, value))


def _as_choice(value, what, choices):
    if not isinstance(value, str):
        raise ValueError("%s must be one of %s, got %r" % (what, ", ".join(choices), value))
    s = value.strip().lower()
    if s not in choices:
        raise ValueError("%s must be one of %s, got %r" % (what, ", ".join(choices), value))
    return s


def validate_settings(settings=None):
    """Validated, normalized settings dict (contract fields plus gamma_rad).

    Missing fields take DEFAULTS; a JS null/undefined counts as missing. Unknown
    keys are ignored. Out-of-range or ill-typed values raise ValueError.
    """
    if _missing(settings):
        settings = {}
    if not isinstance(settings, dict):
        raise ValueError("settings must be a JSON object, got %s" % type(settings).__name__)
    given = {k: v for k, v in settings.items() if not _missing(v)}

    def get(key):
        return given.get(key, DEFAULTS[key])

    out = {
        "intention_rad": _as_float(get("intention_rad"), "intention_rad", 0.0, TWO_PI),
        "world_coupling": _as_float(get("world_coupling"), "world_coupling", 0.0, 1.0),
        "perspective_rad": _as_float(get("perspective_rad"), "perspective_rad", 0.0, math.pi),
        "shots_per_probe": _as_int(get("shots_per_probe"), "shots_per_probe", SHOTS_MIN, SHOTS_MAX),
        "persona": _as_choice(get("persona"), "persona", PERSONAS),
        "mode": _as_choice(get("mode"), "mode", MODES),
        "canary": _as_bool(get("canary"), "canary"),
    }
    out["gamma_rad"] = out["world_coupling"] * math.pi / 2.0
    return out


# ---------------------------------------------------------------- circuits

def make_circuit(phi, gamma, beta=0.0, reference=False):
    """Unmeasured 2-qubit circuit, q0 = Self, q1 = World, angles in radians (guide p.7).

    reference=True omits the final RZ(-beta)/H so both qubits are read in Z."""
    from qiskit import QuantumCircuit
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.rz(float(phi), 0)
    # Controlled RY(2*gamma), control = Self, target = World, in standard gates.
    qc.ry(float(gamma), 1)
    qc.cx(0, 1)
    qc.ry(-float(gamma), 1)
    qc.cx(0, 1)
    if not reference:
        qc.rz(-float(beta), 0)
        qc.h(0)
    return qc


def _probe_angles(s):
    """{probe: (phi, gamma, beta, reference)} for validated settings."""
    phi, gamma, beta = s["intention_rad"], s["gamma_rad"], s["perspective_rad"]
    return {
        "display": (phi, gamma, beta, False),
        "intent_low": (beta, gamma, beta, False),
        "intent_high": (beta + math.pi, gamma, beta, False),
        "connection": (phi, gamma, 0.0, True),
    }


def _probe_circuits(settings):
    s = validate_settings(settings)
    out = {}
    for name, (phi, gamma, beta, ref) in _probe_angles(s).items():
        qc = make_circuit(phi, gamma, beta, reference=ref)
        qc.name = name
        out[name] = (qc, {"probe": name, "phi": phi, "gamma": gamma,
                          "beta": None if ref else beta, "reference": ref})
    return s, out


def probes(settings):
    """The four probe blocks for qk_packer, measured as [Self, World]."""
    _, circs = _probe_circuits(settings)
    return [qk_packer.Block(name, qc, [0, 1], meta) for name, (qc, meta) in circs.items()]


# ---------------------------------------------------------------- counts

def canonical_counts(raw):
    """Block-local counts (Qiskit order: World then Self) -> SelfWorld counts.

    Reverses each two-bit key exactly once, fills absent outcomes with zero and
    rejects anything that is not a two-bit key (guide p.7)."""
    out = {key: 0 for key in OUTCOMES}
    for key, value in dict(raw).items():
        bits = str(key).replace(" ", "").zfill(2)
        if len(bits) != 2 or any(x not in "01" for x in bits):
            raise ValueError("expected two-bit Qiskit counts, got key %r" % (key,))
        n = int(value)
        if n < 0:
            raise ValueError("negative count %r for key %r" % (value, key))
        out[bits[::-1]] += n
    return out


def _total(dist):
    return float(sum(float(v) for v in dist.values()))


def _p_self_1(dist):
    total = _total(dist)
    if total <= 0:
        raise ValueError("a probe has no counts")
    return (float(dist.get("10", 0)) + float(dist.get("11", 0))) / total


# ---------------------------------------------------------------- closed forms

def ideal_p_self_1(phi, gamma, beta=0.0):
    """P(Self=1) = [1 - cos(gamma) cos(phi - beta)] / 2 (guide p.4)."""
    return (1.0 - math.cos(gamma) * math.cos(phi - beta)) / 2.0


def binary_entropy(p):
    """-p log2 p - (1-p) log2 (1-p) in bits, with 0 log 0 = 0."""
    p = min(max(float(p), 0.0), 1.0)
    h = 0.0
    for q in (p, 1.0 - p):
        if q > 0:
            h -= q * math.log2(q)
    return h


def mutual_information(dist):
    """Classical mutual information (bits) between Self and World from SelfWorld
    weights {"00","01","10","11"} (counts or probabilities). Zero terms are skipped."""
    total = _total(dist)
    if total <= 0:
        raise ValueError("the connection probe has no counts")
    p = {k: float(dist.get(k, 0)) / total for k in OUTCOMES}
    ps = {s: p[s + "0"] + p[s + "1"] for s in "01"}
    pw = {w: p["0" + w] + p["1" + w] for w in "01"}
    info = 0.0
    for s in "01":
        for w in "01":
            joint = p[s + w]
            if joint > 0:
                info += joint * math.log2(joint / (ps[s] * pw[w]))
    return max(0.0, info)


def hoeffding_e(n_low, n_high):
    """e = sqrt(ln 80 / (2 N_low)) + sqrt(ln 80 / (2 N_high)); inf when a probe is empty."""
    e = 0.0
    for n in (n_low, n_high):
        n = float(n)
        if n <= 0:
            return math.inf
        e += math.sqrt(LN80 / (2.0 * n))
    return e


def capacity_interval(delta, e):
    """([lo, hi] for C = |d|, resolved): d +/- e clipped to [-1, 1], then mapped
    through |.|: an interval spanning zero gets lower limit 0 and the largest
    endpoint magnitude as upper limit; "resolved" means it excludes zero."""
    if not math.isfinite(e):
        return [0.0, 1.0], False
    d_lo = max(-1.0, float(delta) - float(e))
    d_hi = min(1.0, float(delta) + float(e))
    if d_lo <= 0.0 <= d_hi:
        return [0.0, max(abs(d_lo), abs(d_hi))], False
    return [min(abs(d_lo), abs(d_hi)), max(abs(d_lo), abs(d_hi))], True


def _core(dists):
    """Readings shared by sampled and exact inputs: {probe: SelfWorld weights}."""
    for name in PROBES:
        if name not in dists:
            raise ValueError("missing probe %r" % name)
    p = _p_self_1(dists["display"])
    p_low = _p_self_1(dists["intent_low"])
    p_high = _p_self_1(dists["intent_high"])
    delta = p_high - p_low
    return {
        "p_self_1": p,
        "p_low": p_low,
        "p_high": p_high,
        "delta_signed": delta,
        "capacity": abs(delta),
        "openness_bits": binary_entropy(p),
        "connection_bits": mutual_information(dists["connection"]),
    }


def metrics(counts):
    """All readings from SelfWorld counts {probe: {"00","01","10","11": int}}.

    Capacity's interval uses the ACTUAL totals of the two intent probes (a provider
    that rounds prob*shots can return totals that differ from the request)."""
    out = _core(counts)
    n = {name: int(round(_total(counts[name]))) for name in PROBES}
    e = hoeffding_e(n["intent_low"], n["intent_high"])
    ci, resolved = capacity_interval(out["delta_signed"], e)
    out.update({
        "hoeffding_e": e,
        "capacity_ci95": ci,
        "resolved": bool(resolved),
        "shots_seen": n,
    })
    return out


# ---------------------------------------------------------------- exact model

def _to_self_world(dist):
    """{Qiskit key (World,Self): p} -> {SelfWorld key: p}, zeros filled."""
    out = {k: 0.0 for k in OUTCOMES}
    for key, p in dist.items():
        bits = str(key).zfill(2)
        if len(bits) != 2:
            raise ValueError("expected two-bit keys, got %r" % (key,))
        out[bits[::-1]] += float(p)
    return out


def exact_probe_distributions(settings, noise=None):
    """{probe: {SelfWorld key: probability}}: Statevector when noise is None, else
    the density-matrix noise model of qk_noise (a NoiseSpec, a dict or None)."""
    _, circs = _probe_circuits(settings)
    out = {}
    for name, (qc, _) in circs.items():
        if noise is None:
            dist = qk_noise.ideal_distribution(qc, [0, 1])
        else:
            dist = qk_noise.exact_distribution(qc, [0, 1], noise)
        out[name] = _to_self_world(dist)
    return out


def exact_metrics(settings, noise=None):
    """Readings computed from exact distributions (no sampling, no interval)."""
    return _core(exact_probe_distributions(settings, noise))


def prediction(settings):
    """The Demon's forecast: ideal readings, the formula and the probe distributions."""
    s = validate_settings(settings)
    dists = exact_probe_distributions(s)
    out = _core(dists)
    out.update({
        "formula_p_self_1": FORMULA,
        "p_self_1_closed_form": ideal_p_self_1(s["intention_rad"], s["gamma_rad"],
                                               s["perspective_rad"]),
        "capacity_closed_form": math.cos(s["gamma_rad"]),
        "probe_distributions": dists,
        "bit_order": BIT_ORDER,
    })
    return out


def noisy_prediction(settings, noise=None):
    """Readings under an IonQ-like noise model (qk_noise.ionq_forte_like() unless a
    NoiseSpec/dict is given): a modeled approximation, not a measurement."""
    spec = qk_noise.ionq_forte_like() if noise is None else noise
    out = exact_metrics(settings, spec)
    spec_obj = spec if isinstance(spec, qk_noise.NoiseSpec) else qk_noise.NoiseSpec.from_dict(spec)
    out["noise"] = spec_obj.to_dict()
    out["note"] = ("Modeled approximation under an IonQ-like depolarizing noise model, "
                   "not a fresh measurement. " + qk_noise.IONQ_PRESET_NOTE)
    return out


def baselines():
    """The two theoretical classical references of guide p.14."""
    return {
        "fixed_output": {
            "capacity": 0.0, "openness_bits": 0.0,
            "label": "fixed output",
            "description": "always the same outcome whatever the intention: nothing to "
                           "reshape, nothing uncertain",
        },
        "fair_coin": {
            "capacity": 0.0, "openness_bits": 1.0,
            "label": "intention-independent fair coin",
            "description": "50/50 whatever the intention: fully uncertain, nothing reshaped",
        },
        "kind": "theoretical classical references",
        "note": _BASELINE_NOTE,
    }


def versions():
    """Library versions for provenance (qk_data's set plus qiskit-ionq)."""
    out = qk_data.detect_versions()
    try:
        from importlib import metadata
        out["qiskit_ionq"] = str(metadata.version("qiskit-ionq"))
    except Exception:
        out["qiskit_ionq"] = None
    out["model_version"] = MODEL_VERSION
    return out


# ---------------------------------------------------------------- explanation

def _future(p):
    return "Future 1" if p >= 0.5 else "Future 0"


# Persona lines after a run (design/persona-dialogue.md): each guide speaks only about what
# it can see. The Self sees its own intention dial; it feels World coupling only as a shorter
# reach and perspective only as an aim that lands elsewhere. Laplace's Demon knows the law and
# the World's record, not the dials. The Observer sees all three inputs. Each function returns
# (line, animation); the animation names are the persona sprite actions.
_LAW_ZERO = 0.05        # below this ideal capacity the model itself says the dial moves nothing
_W_LOW = 0.05           # World coupling below this: no record (band W0)
_W_STRONG = 0.65        # from here the World records most of the Self (band W2)
_BETA_TILT = math.radians(6.0)   # perspective from here on: the Observer reads at a tilt
_THIN_RANGE = 0.15      # an unresolved range below this: the odds stay where they are
_FULL_REACH = 0.85      # a resolved range below this: the Self notices a shorter reach


def _aim(phi):
    """The Self's aim, read straight on: "F0", "F1" or "both"."""
    d = math.degrees(phi) % 360.0
    if d <= 60.0 or d >= 300.0:
        return "F0"
    if 120.0 <= d <= 240.0:
        return "F1"
    return "both"


def _aim_matched(s, m):
    aim = _aim(s["intention_rad"])
    p, o = m["p_self_1"], m["openness_bits"]
    return (aim == "F0" and p < 0.5) or (aim == "F1" and p > 0.5) or (aim == "both" and o >= 0.9)


def _world_band(w, law_capacity):
    if law_capacity < _LAW_ZERO:
        return "W3"
    if w < _W_LOW:
        return "W0"
    return "W1" if w < _W_STRONG else "W2"


def _self_line(s, m, resolved):
    p, o, c = m["p_self_1"], m["openness_bits"], m["capacity"]
    aim = _aim(s["intention_rad"])
    target = {"F0": "Future 0", "F1": "Future 1"}.get(aim)
    if not resolved:
        if c < _THIN_RANGE and o >= 0.9:
            line = ("My futures are wide open, P(Future 1) = %.3f, yet whichever way I lean the "
                    "odds stay where they are. In this model, uncertainty alone is not freedom." % p)
        elif c < _THIN_RANGE:
            line = ("The odds sit at P(Future 1) = %.3f, and whichever way I lean they stay there. "
                    "Nothing I intend is shown to move them." % p)
        else:
            line = ("%s; the odds came out P(Future 1) = %.3f, and this run is too small to show "
                    "whether my intention moved them."
                    % ("I aimed for " + target if target else "I tried to keep both open", p))
        return line + " " + NO_RESOLVED, "angry"
    if _aim_matched(s, m):
        if aim == "both":
            line = ("I tried to keep both futures open, and they stayed open: P(Future 1) = %.3f. "
                    "Opposite intentions swing the odds by %.2f: in this model, that range is my "
                    "freedom." % (p, c))
        elif o <= 0.35:
            line = ("I aimed for %s, and it came: P(Future 1) = %.3f. This future is nearly "
                    "settled, and settled because I set it; opposite intentions could still swing "
                    "the odds by %.2f. Predictability and capacity can coexist." % (target, p, c))
        else:
            line = ("I aimed for %s, and the odds lean that way: P(Future 1) = %.3f. I can still "
                    "swing them by %.2f: a future that is tilted, not fixed." % (target, p, c))
        action = "happy"
    else:
        line = ("%s, but the odds came out P(Future 1) = %.3f. Something I can't see turned my "
                "aim. My range is still %.2f."
                % ("I aimed for " + target if target else "I tried to keep both futures open", p, c))
        action = "idle"
    if c < _FULL_REACH:
        line += " My reach is shorter than it should be, and I can't see what's holding it."
    return line, action


def _demon_line(s, m, pred, resolved, n_display):
    p, p_hat = float(pred["p_self_1"]), m["p_self_1"]
    law, c, bits = float(pred["capacity"]), m["capacity"], m["connection_bits"]
    sigma = math.sqrt(max(p * (1.0 - p), 1e-12) / max(float(n_display), 1.0))
    outside = abs(p_hat - p) > 2.0 * sigma
    nr = "" if resolved else " " + NO_RESOLVED
    line = ("I wrote P(Self=1) = %.3f; the sample read %.3f, %s the shot noise of %d shots. "
            % (p, p_hat, "outside" if outside else "within", int(n_display)))
    band = _world_band(s["world_coupling"], law)
    if outside:
        return line + "The law stands; this sample strayed." + nr, "anger"
    if band == "W0":
        if resolved:
            return line + ("The World kept no record, so the dial moved the odds by %.2f. A blank "
                           "ledger is the only place a dial reaches that far." % c), "anger"
        return line + ("The World kept no record; the law allows the dial %.2f, but this sample "
                       "did not resolve it." % law) + nr, "idle"
    if band == "W1":
        return line + ("The World recorded %.3f bits of the Self; the dial moved the odds by %.2f, "
                       "of the %.2f the law allows." % (bits, c, law)) + nr, "idle"
    if band == "W2":
        return line + ("The World recorded %.3f bits of the Self, and the dial's reach shrank to "
                       "%.2f. The record holds." % (bits, c)) + nr, "gesture"
    return line + ("The World recorded %.3f bits: the whole Self. The law said the dial moves "
                   "nothing." % bits) + nr, "gesture"


def _observer_line(s, m, resolved):
    beta, w = s["perspective_rad"], s["world_coupling"]
    c, bits = m["capacity"], m["connection_bits"]
    line = ("The whole picture: the Self's intention %.0f\u00b0, World coupling %.2f, my perspective "
            "beta = %.2f rad. I read P(Self=1) = %.3f; the Self's range is %.2f; the World holds "
            "%.3f bits." % (math.degrees(s["intention_rad"]), w, beta, m["p_self_1"], c, bits))
    tilted = beta >= _BETA_TILT
    if tilted and not _aim_matched(s, m):
        line += (" The Self's aim reached me turned by %.0f\u00b0: I changed the question, not the "
                 "state." % math.degrees(beta))
    if tilted:
        line += " The range probes use my readout too, so %.2f stays comparable at any angle." % c
    if w >= _W_LOW and c < _FULL_REACH:
        line += " Its range is %.2f, not 1, because the World is holding %.3f bits of it." % (c, bits)
    if not resolved:
        line += " " + NO_RESOLVED
    return line, ("dance" if bits >= 0.5 else ("stare" if tilted else "idle"))


def explanation(settings, m, pred):
    """One factual sentence (numbers only) and three persona interpretations."""
    s = validate_settings(settings)
    resolved = bool(m.get("resolved", False))
    ci = m.get("capacity_ci95") or [None, None]
    n_display = (m.get("shots_seen") or {}).get("display", s["shots_per_probe"])
    factual = ("With intention %.3f rad, World coupling %.2f and perspective %.3f rad: "
               "measured P(Self=1) = %.3f (Demon forecast %.3f); capacity %.3f, "
               "conservative 95%% interval %.3f to %.3f (ideal %.3f); openness %.3f bits; "
               "connection %.3f bits from the reference probe."
               % (s["intention_rad"], s["world_coupling"], s["perspective_rad"],
                  m["p_self_1"], float(pred["p_self_1"]), m["capacity"],
                  float(ci[0]), float(ci[1]), float(pred["capacity"]),
                  m["openness_bits"], m["connection_bits"]))
    if not resolved:
        factual += " " + NO_RESOLVED
    self_line, self_act = _self_line(s, m, resolved)
    demon_line, demon_act = _demon_line(s, m, pred, resolved, n_display)
    observer_line, observer_act = _observer_line(s, m, resolved)
    return {
        "factual": factual,
        "poetic": {"self": self_line, "demon": demon_line, "observer": observer_line},
        "animation": {"self": self_act, "demon": demon_act, "observer": observer_act},
        "resolved": resolved,
        "note": PERSONA_NOTE,
    }


# ---------------------------------------------------------------- one job

def _last(key, default=None):
    return qk_runtime.LAST_RUN.get(key, default)


def source_info(profile, mode, shots, shots_seen=None, canary=None, layout=None):
    """Provenance for a run (or for a failed one: whatever LAST_RUN knows)."""
    family = profile.get("family")
    bit_check = {
        "orientation_ok": None if canary is None else bool(canary["orientation_ok"]),
        "p_flip_0to1_mean": None if canary is None else canary["p_flip_0to1_mean"],
        "p_flip_1to0_mean": None if canary is None else canary["p_flip_1to0_mean"],
        "note": ("canary blocks checked the bit order and readout flips in the same job"
                 if canary is not None else "canary disabled: bit order not checked"),
    }
    return {
        "provider_family": family,
        "backend_name": profile.get("name"),
        "mode": mode,
        "simulator": family != "ionq_qpu",
        "noisy": bool(profile.get("noisy")),
        "remote": bool(profile.get("remote")),
        "job_id": _last("job_id"),
        "job_returned": bool(_last("job_returned", False)),
        "submitted_as": _last("submitted_as"),
        "n_circuits": _last("n_circuits"),
        "wall_s": _last("wall_s"),
        "shots_requested": int(shots),
        "shots_seen": dict(shots_seen or {}),
        "versions": versions(),
        "bit_order_check": bit_check,
        "transpile": _last("prepare"),
        "layout": layout,
        "sim_note": SIM_NOTE if family != "ionq_qpu" else None,
    }


def run(backend, settings, profile=None):
    """ONE job: canary blocks + the four probes, then counts, readings, forecast and
    explanation. Returns the result dict of the contract (not JSON); raises on failure."""
    s = validate_settings(settings)
    profile = profile or qk_runtime.backend_profile(backend)
    mode = qk_runtime.preferred_mode(profile, s["mode"])
    blocks = probes(s)
    max_qubits = int(profile["max_qubits"])
    if mode == "tile" and qk_packer.capacity(blocks, max_qubits, canary=s["canary"]) < len(blocks):
        mode = "tiles"              # still one submission: first-fit tiles in a list job
    packed = qk_packer.pack(blocks, max_qubits=max_qubits, mode=mode, canary=s["canary"])
    circs = qk_runtime.prepare(packed.circuits, backend, profile)
    t0 = time.perf_counter()
    counts_list = qk_runtime.run_once(backend, circs, s["shots_per_probe"], profile,
                                      allow_partial=False)
    wall = time.perf_counter() - t0
    unpacked = qk_packer.unpack(packed, counts_list)
    canary = qk_packer.canary_report(unpacked) if s["canary"] else None
    counts = {name: canonical_counts(unpacked[name]) for name in PROBES}
    m = metrics(counts)
    pred = prediction(s)
    layout = packed.summary()
    source = source_info(profile, mode, s["shots_per_probe"], m["shots_seen"], canary, layout)
    if source["wall_s"] is None:
        source["wall_s"] = round(wall, 3)
    return {
        "status": "completed",
        "settings": dict(s),
        "source": source,
        "bit_order": BIT_ORDER,
        "counts": counts,
        "metrics": m,
        "prediction": pred,
        "explanation": explanation(s, m, pred),
        "baselines": baselines(),
        "model_version": MODEL_VERSION,
    }
