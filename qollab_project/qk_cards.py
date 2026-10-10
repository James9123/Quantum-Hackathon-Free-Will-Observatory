"""Claim cards: one JSON-safe record per claim, linking

    claim -> assumptions -> witness -> classical bound -> measured value -> verdict

plus a plain-text (console) and a Markdown rendering of the same record.

The verdict is a fixed rule on a z-score against the classical bound:

    direction="max" (classical theories give value <= bound): z = (value - bound) / se
    direction="min" (classical theories give value >= bound): z = (bound - value) / se

computed on the mitigated value when the card has one, else on the raw value:

    z >= 3       -> "exceeds classical bound"
    z <= 0       -> "consistent with classical bound"   (value on the classical side)
    otherwise    -> "inconclusive (0 < z < 3)"

se = 0 (every shot agreed) gives z = +-inf, stored as None. A z-score speaks only
to statistical error; the assumptions, "not shown" and counterargument lists say
what else a reader must accept. Simulator cards carry SIM_NOTE once; hardware cards never.
"""

import json
import math
import numbers
import textwrap
import unicodedata

import qk_data

__all__ = [
    "SCHEMA", "SIM_NOTE", "EXCEEDS", "CONSISTENT", "INCONCLUSIVE", "MD_HEADINGS",
    "claim_card", "verdict_for", "card_text", "card_markdown",
]

SCHEMA = "claim-card/1"
Z_THRESHOLD = 3.0
EXCEEDS = "exceeds classical bound"
CONSISTENT = "consistent with classical bound"
INCONCLUSIVE = "inconclusive (0 < z < 3)"
DIRECTIONS = ("max", "min")
SIM_NOTE = ("This is a simulation. It computes what quantum theory predicts, and how the "
            "chosen noise model degrades it; it is not a test of nature.")
REQUIRED = ("id", "claim", "assumptions", "witness", "bound", "quantum_ideal", "raw",
            "backend", "shots")
OPTIONAL = ("direction", "mitigated", "noise", "provenance", "not_shown", "counterarguments",
            "simulator", "notes")
# Keys claim_card computes. Passed back in (claim_card(**card)) they are ignored and
# recomputed, so a card can be rebuilt with a changed field; a verdict is never input.
COMPUTED = ("schema", "z_raw", "z_mitigated", "z_threshold", "verdict_basis", "verdict")
MD_HEADINGS = ("Claim", "Assumptions", "Witness", "Result \u00b1 se",
               "What this does NOT show", "Counterarguments")
WIDTH = 100
_LABEL = 18                     # label column width in card_text
_RULE_TEXT = "rule: z >= 3 exceeds, z <= 0 consistent, else inconclusive"
_ASCII = {
    "\u2264": "<=", "\u2265": ">=", "\u00b1": "+-", "\u2212": "-", "\u2013": "-",
    "\u2014": "--", "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u27e8": "<", "\u27e9": ">", "\u00d7": "x", "\u00b7": "*", "\u221a": "sqrt",
    "\u2026": "...", "\u2192": "->", "\u2248": "~", "\u2260": "!=", "\u221e": "inf",
    "\u2297": "(x)", "\u2020": "^dag", "\u00b2": "^2",
}


def _real(x):
    """float(x) for a real number (Python or numpy, not bool); None otherwise."""
    if isinstance(x, numbers.Real) and not isinstance(x, bool):
        return float(x)
    return None


def _z(value, se, bound, direction):
    d = (value - bound) if direction == "max" else (bound - value)
    if se > 0:
        return d / se
    return 0.0 if d == 0 else math.copysign(math.inf, d)


def verdict_for(z):
    """The verdict string for a z-score (see module docstring)."""
    if z >= Z_THRESHOLD:
        return EXCEEDS
    if z <= 0:
        return CONSISTENT
    return INCONCLUSIVE


def _str_list(name, val, problems, nonempty=False):
    if isinstance(val, str) or not isinstance(val, (list, tuple)):
        problems.append("%s must be a list of str" % name)
        return []
    if any(not isinstance(s, str) or not s.strip() for s in val):
        problems.append("%s items must be non-empty str" % name)
    if nonempty and not val:
        problems.append("%s must not be empty" % name)
    return [str(s) for s in val]


def _measured(name, m, problems, need_method):
    keys = ("value", "se", "method") if need_method else ("value", "se")
    if not isinstance(m, dict):
        problems.append("%s must be a dict with keys %s" % (name, ", ".join(keys)))
        return None
    missing = [k for k in keys if m.get(k) is None]
    if missing:
        problems.append("%s missing %s" % (name, ", ".join(missing)))
        return None
    value, se = _real(m["value"]), _real(m["se"])
    if value is None or not math.isfinite(value):
        problems.append("%s.value must be a finite number" % name)
    if se is None or not math.isfinite(se) or se < 0:
        problems.append("%s.se must be a finite number >= 0" % name)
    out = dict(m)
    out.update(value=value, se=se)
    if need_method:
        out["method"] = str(m["method"])
    return out


def claim_card(**fields):
    """Build a claim card: a JSON-safe dict (numpy cast, NaN/inf -> None).

    Required: id, claim, assumptions, witness, bound, quantum_ideal, raw={value, se},
    backend, shots. Optional: direction ("max"|"min"), mitigated={value, se, method},
    noise, provenance, not_shown, counterarguments, simulator (default True), notes.
    Computed keys (COMPUTED) in the input are ignored, so claim_card(**card) == card.
    Raises ValueError listing every missing, unknown or malformed field.
    """
    missing = [k for k in REQUIRED if fields.get(k) is None]
    unknown = sorted(set(fields) - set(REQUIRED) - set(OPTIONAL) - set(COMPUTED))
    problems = []
    if missing:
        problems.append("missing required field(s): " + ", ".join(missing))
    if unknown:
        problems.append("unknown field(s): " + ", ".join(unknown))
    if problems:
        raise ValueError("claim_card: " + "; ".join(problems))
    f = fields
    for key in ("claim", "witness", "backend"):
        if not isinstance(f[key], str) or not f[key].strip():
            problems.append("%s must be a non-empty str" % key)
    if not isinstance(f["id"], (str, numbers.Integral)) or isinstance(f["id"], bool) \
            or not str(f["id"]).strip():
        problems.append("id must be a non-empty str")
    assumptions = _str_list("assumptions", f["assumptions"], problems, nonempty=True)
    direction = f.get("direction") or "max"
    if direction not in DIRECTIONS:
        problems.append("direction must be one of %r, got %r" % (DIRECTIONS, direction))
    bound = _real(f["bound"])
    if bound is None or not math.isfinite(bound):
        problems.append("bound must be a finite number")
    ideal = _real(f["quantum_ideal"])
    if ideal is None:
        problems.append("quantum_ideal must be a number")
    shots = f["shots"]
    if not isinstance(shots, numbers.Integral) or isinstance(shots, bool) or shots <= 0:
        problems.append("shots must be a positive int")
    raw = _measured("raw", f["raw"], problems, need_method=False)
    mit = f.get("mitigated")
    if mit is not None:
        mit = _measured("mitigated", mit, problems, need_method=True)
    for key in ("noise", "provenance"):
        if f.get(key) is not None and not isinstance(f[key], dict):
            problems.append("%s must be a dict or None" % key)
    not_shown = _str_list("not_shown", f.get("not_shown") or [], problems)
    counter = _str_list("counterarguments", f.get("counterarguments") or [], problems)
    simulator = f.get("simulator", True)
    if simulator not in (True, False):
        problems.append("simulator must be a bool")
    notes = f.get("notes") or ""
    if not isinstance(notes, str):
        problems.append("notes must be a str")
    if problems:
        raise ValueError("claim_card: " + "; ".join(problems))

    z_raw = _z(raw["value"], raw["se"], bound, direction)
    z_mit = _z(mit["value"], mit["se"], bound, direction) if mit is not None else None
    # Exactly once on simulator cards; never on hardware cards (it would be false there).
    not_shown = [s for s in not_shown if s != SIM_NOTE] + ([SIM_NOTE] if simulator else [])
    card = {
        "schema": SCHEMA,
        "id": str(f["id"]),
        "claim": f["claim"],
        "assumptions": assumptions,
        "witness": f["witness"],
        "bound": bound,
        "direction": direction,
        "quantum_ideal": ideal,
        "raw": raw,
        "mitigated": mit,
        "z_raw": z_raw,
        "z_mitigated": z_mit,
        "z_threshold": Z_THRESHOLD,
        "verdict_basis": "raw" if mit is None else "mitigated",
        "verdict": verdict_for(z_raw if mit is None else z_mit),
        "backend": f["backend"],
        "shots": int(shots),
        "simulator": bool(simulator),
        "noise": f.get("noise"),
        "provenance": f.get("provenance") or {},
        "not_shown": not_shown,
        "counterarguments": counter,
        "notes": notes,
    }
    return qk_data.json_safe(card)


# ---------------------------------------------------------------- rendering

def _ascii(s):
    """ASCII-only text: common math symbols spelled out, Greek letters named,
    accents dropped, control characters blanked, anything else -> '?'."""
    out = []
    for ch in unicodedata.normalize("NFKD", "".join(_ASCII.get(c, c) for c in str(s))):
        if ord(ch) < 32 or ord(ch) == 127:
            out.append(" ")
        elif ord(ch) < 128:
            out.append(ch)
        elif unicodedata.combining(ch):
            continue
        else:
            name = unicodedata.name(ch, "")
            if name.startswith("GREEK SMALL LETTER "):
                out.append(name.split()[-1].lower())
            elif name.startswith("GREEK CAPITAL LETTER "):
                out.append(name.split()[-1].capitalize())
            else:
                out.append("?")
    return "".join(out)


def _num(x):
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return "%.6g" % x
    return str(x)


def _zstr(card, key):
    """z of card[key] ('raw'/'mitigated') vs the bound, recomputed so se = 0 shows +-inf."""
    m = card.get(key)
    if not m or m.get("value") is None or m.get("se") is None or card.get("bound") is None:
        return "n/a"
    z = _z(m["value"], m["se"], card["bound"], card.get("direction", "max"))
    return ("%+.2f" % z) + (" (se = 0)" if not m["se"] else "")


def _bound_text(card, le="<=", ge=">="):
    if card.get("direction", "max") == "max":
        return "classical value %s %s; the claim needs a larger value" % (le, _num(card["bound"]))
    return "classical value %s %s; the claim needs a smaller value" % (ge, _num(card["bound"]))


def _kv(d):
    if not d:
        return "none"
    return ", ".join("%s=%s" % (k, v if isinstance(v, str) else json.dumps(v, sort_keys=True))
                     for k, v in d.items())


def _noise_text(card):
    # noise=None only means the caller recorded none: a noisy simulator (fake device,
    # vendor noise model) still applies its own, so never call it "ideal" here.
    if card.get("noise") is None:
        return "none recorded"
    return _kv(card["noise"])


def _verdict_basis(card):
    basis = card.get("verdict_basis", "raw")
    return "%s z = %s" % (basis, _zstr(card, basis))


def card_text(card, width=WIDTH):
    """Plain-text console rendering: ASCII only, no colors, every line <= `width`."""
    lines = []

    def field(label, text):
        lines.extend(textwrap.wrap(_ascii(text), width, initial_indent=label.ljust(_LABEL),
                                   subsequent_indent=" " * _LABEL) or [label.rstrip()])

    def bullets(title, items):
        lines.append(title)
        for s in items or ["(none recorded)"]:
            lines.extend(textwrap.wrap(_ascii(s), width, initial_indent="  - ",
                                       subsequent_indent="    "))

    lines.append("=" * width)
    field("CLAIM CARD", "%s  (%s)" % (card.get("id"), card.get("schema", SCHEMA)))
    field("Claim:", card.get("claim", ""))
    lines.append("-" * width)
    bullets("Assumptions:", card.get("assumptions"))
    field("Witness:", card.get("witness", ""))
    field("Classical bound:", _bound_text(card))
    field("Quantum ideal:", _num(card.get("quantum_ideal")))
    raw = card.get("raw") or {}
    field("Raw:", "%s +- %s  (z = %s)" % (_num(raw.get("value")), _num(raw.get("se")),
                                          _zstr(card, "raw")))
    mit = card.get("mitigated")
    if mit:
        field("Mitigated:", "%s +- %s  (z = %s; method: %s)" % (
            _num(mit.get("value")), _num(mit.get("se")), _zstr(card, "mitigated"),
            mit.get("method", "unspecified")))
    field("VERDICT:", "%s" % card.get("verdict"))
    field("", "basis: %s; %s" % (_verdict_basis(card), _RULE_TEXT))
    field("Backend:", "%s (%s) | shots: %s" % (
        card.get("backend"), "simulator" if card.get("simulator") else "hardware",
        _num(card.get("shots"))))
    field("Noise:", _noise_text(card))
    if card.get("provenance"):
        field("Provenance:", _kv(card["provenance"]))
    bullets("What this does NOT show:", card.get("not_shown"))
    bullets("Counterarguments:", card.get("counterarguments"))
    if card.get("notes"):
        field("Notes:", card["notes"])
    lines.append("=" * width)
    return "\n".join(lines)


def _md_cell(x):
    return str(x).replace("|", "\\|").replace("\n", " ")


def _md_line(s):
    """One Markdown line: a newline in user text must not start a heading or list item."""
    return " ".join(str(s).splitlines())


def _bullets_md(items):
    return ["- %s" % _md_line(s) for s in items or ["(none recorded)"]]


def card_markdown(card, level=2):
    """Markdown section: Claim -> Assumptions -> Witness -> Result +- se ->
    What this does NOT show -> Counterarguments (headings: MD_HEADINGS)."""
    raw, mit = card.get("raw") or {}, card.get("mitigated")
    rule = _RULE_TEXT.replace(">=", "\u2265").replace("<=", "\u2264")
    result = ["| | value \u00b1 se | z vs bound | method |", "|---|---|---|---|",
              "| raw | %s \u00b1 %s | %s | none |" % (
                  _num(raw.get("value")), _num(raw.get("se")), _zstr(card, "raw"))]
    if mit:
        result.append("| mitigated | %s \u00b1 %s | %s | %s |" % (
            _num(mit.get("value")), _num(mit.get("se")), _zstr(card, "mitigated"),
            _md_cell(mit.get("method", "unspecified"))))
    result += ["", "**Verdict: %s** (basis: %s; %s)" % (card.get("verdict"),
                                                       _verdict_basis(card), rule),
               "", "Backend: `%s` (%s) \u00b7 shots: %s \u00b7 noise: %s" % (
                   card.get("backend"), "simulator" if card.get("simulator") else "hardware",
                   _num(card.get("shots")), _noise_text(card))]
    if card.get("provenance"):
        result += ["", "Provenance: %s" % _kv(card["provenance"])]
    bodies = (
        [_md_line(card.get("claim", ""))],
        _bullets_md(card.get("assumptions")),
        ["**%s**. Classical bound: %s. Quantum ideal: %s." % (
            _md_line(card.get("witness")), _bound_text(card, "\u2264", "\u2265"),
            _num(card.get("quantum_ideal")))],
        result,
        _bullets_md(card.get("not_shown")),
        _bullets_md(card.get("counterarguments")),
    )
    out = ["%s Claim card: %s" % ("#" * level, card.get("id"))]
    for heading, body in zip(MD_HEADINGS, bodies):
        out += ["", "%s %s" % ("#" * (level + 1), heading), ""] + body
    if card.get("notes"):
        out += ["", "*Notes:* %s" % _md_line(card["notes"])]
    return "\n".join(out) + "\n"
