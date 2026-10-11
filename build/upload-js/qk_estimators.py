"""Estimators on block-local counts: marginals, parities, witness values, error bars.

Works under CPython and Pyodide. Dependencies: numpy + stdlib.

Conventions (Qiskit's, as in qk_packer):
- Counts are {bitstring: int}. Local bit j of a key is character `-1 - j`
  (bit 0 rightmost), i.e. the outcome of the block's `measure[j]`.
- Outcome bit 0 -> eigenvalue +1, bit 1 -> -1. A correlator over several
  bits is the product of their eigenvalues (a parity).
- Witness specs are the dicts of qk_bounds.WITNESSES. For a correlator term,
  block_counts[term["label"]] holds the counts and local bit j is the outcome
  of term["vars"][j].

Error bars are binomial shot noise only: they say how far a finite-shot
estimate may sit from what the sampled circuit predicts, nothing more.
Return values are plain Python numbers/dicts/tuples (JSON-safe; nan/inf
where documented).
"""

import math

import numpy as np

__all__ = [
    "marginal", "probs", "parity", "witness_value", "win_rate", "z_vs_bound",
    "witness_sd_per_shot", "shots_for_sigma", "bootstrap", "Z95",
]

Z95 = 1.959963984540054     # two-sided 95% normal quantile
_NAN = float("nan")


def _positions(key_len, bits):
    """String index of each local bit in `bits` for a key of length key_len."""
    out = []
    for b in bits:
        b = int(b)
        if not 0 <= b < key_len:
            raise ValueError("bit %d out of range for %d-bit keys" % (b, key_len))
        out.append(key_len - 1 - b)
    if len(set(out)) != len(out):
        raise ValueError("repeated bit index in %r" % (list(bits),))
    return out


def marginal(counts, bits):
    """Keep local bits `bits`; bits[0] becomes the new rightmost bit."""
    bits = list(bits)
    out = {}
    for key, n in counts.items():
        n = int(n)
        if not n:
            continue
        pos = _positions(len(key), bits)
        k = "".join(key[i] for i in reversed(pos))
        out[k] = out.get(k, 0) + n
    return dict(sorted(out.items()))


def probs(counts, bits=None):
    """Normalized distribution {key: float}, marginalized over `bits` if given."""
    c = marginal(counts, bits) if bits is not None else {str(k): int(v) for k, v in counts.items()}
    total = sum(c.values())
    if not total:
        return {}
    return {k: v / total for k, v in sorted(c.items()) if v}


def parity(counts, bits=None):
    """(E, se): mean product of +-1 eigenvalues over `bits` (all bits if None).

    se = sqrt((1 - E^2) / N), the binomial standard error. N == 0 -> (nan, nan).
    """
    bits = None if bits is None else list(bits)     # reused per key: no one-shot iterators
    total = signed = 0
    for key, n in counts.items():
        n = int(n)
        if bits is None:
            ones = key.count("1")
        else:
            ones = sum(key[i] == "1" for i in _positions(len(key), bits))
        signed += -n if ones & 1 else n
        total += n
    if not total:
        return _NAN, _NAN
    e = signed / total
    return e, math.sqrt(max(0.0, 1.0 - e * e) / total)


def witness_value(spec, block_counts):
    """Value of a correlator witness: sum coef * E over its terms, with se.

    Returns {"value", "se", "terms": {label: {"E", "se", "n", "coef"}}}.
    Terms are independent blocks, so se = sqrt(sum coef^2 se^2).
    """
    kind = spec.get("kind")
    if kind == "game":
        raise NotImplementedError(
            "witness %r is a game: scoring is experiment-specific (decode answers, "
            "apply spec['win']), then use win_rate(wins, n)" % spec.get("name"))
    if kind != "correlator":
        raise ValueError("unknown witness kind %r" % (kind,))
    terms, value, var = {}, 0.0, 0.0
    for t in spec["terms"]:
        label = t["label"]
        if label not in block_counts:
            raise KeyError("no counts for witness term %r" % label)
        counts = block_counts[label]
        e, se = parity(counts, range(len(t["vars"])))
        coef = float(t["coef"])
        terms[label] = {"E": e, "se": se, "n": sum(int(v) for v in counts.values()), "coef": coef}
        value += coef * e
        var += coef * coef * se * se
    return {"value": value, "se": math.sqrt(var), "terms": terms}


def win_rate(wins, n):
    """Win fraction with its binomial se and the 95% Wilson score interval."""
    if wins != int(wins) or n != int(n) or not 0 <= int(wins) <= int(n):
        raise ValueError("need integers 0 <= wins <= n (got %r, %r)" % (wins, n))
    wins, n = int(wins), int(n)
    if not n:
        return {"p": _NAN, "se": _NAN, "wilson_lo": 0.0, "wilson_hi": 1.0, "wins": 0, "n": 0}
    p = wins / n
    z2 = Z95 * Z95
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = Z95 * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return {
        "p": p,
        "se": math.sqrt(p * (1 - p) / n),
        "wilson_lo": max(0.0, center - half),
        "wilson_hi": min(1.0, center + half),
        "wins": wins,
        "n": n,
    }


def z_vs_bound(value, se, bound, direction="max"):
    """Standard errors by which `value` beats `bound` (negative: it does not).

    direction "max": the bound is an upper bound, z = (value - bound) / se.
    direction "min": the bound is a lower bound, z = (bound - value) / se.
    se <= 0 gives +inf, -inf or 0.0 by the sign of the difference.
    """
    if direction not in ("max", "min"):
        raise ValueError("direction must be 'max' or 'min' (got %r)" % (direction,))
    diff = float(value) - float(bound)
    if direction == "min":
        diff = -diff
    se = float(se)
    if se <= 0:
        if math.isnan(diff):
            return _NAN
        return math.inf if diff > 0 else -math.inf if diff < 0 else 0.0
    return diff / se


def witness_sd_per_shot(spec, expectations):
    """Per-shot sd of a correlator witness when every term gets the same N shots:
    sqrt(sum coef^2 (1 - E^2)); the witness se is this / sqrt(N)."""
    if spec.get("kind") != "correlator":
        raise ValueError("witness_sd_per_shot needs a correlator witness")
    tot = 0.0
    for t in spec["terms"]:
        label = t["label"]
        if label not in expectations:
            raise KeyError("no expectation for witness term %r" % label)
        e = float(expectations[label])
        tot += float(t["coef"]) ** 2 * max(0.0, 1.0 - e * e)
    return math.sqrt(tot)


def shots_for_sigma(gap, sd_per_shot, k=5):
    """Smallest shots per term N with k * sd_per_shot / sqrt(N) <= gap."""
    gap, sd, k = float(gap), float(sd_per_shot), float(k)
    if not gap > 0:
        raise ValueError("gap must be > 0 (got %r)" % gap)
    if not (sd >= 0 and k >= 0):
        raise ValueError("sd_per_shot and k must be >= 0")
    if sd == 0 or k == 0:
        return 1
    n = max(1, math.ceil((k * sd / gap) ** 2))
    # Absorb float rounding in either direction. Bounded: past 2**53 sqrt(n) and
    # sqrt(n - 1) round alike, and an open-ended loop would spin for ages.
    for _ in range(4):
        if n > 1 and k * sd / math.sqrt(n - 1) <= gap:
            n -= 1
        elif k * sd / math.sqrt(n) > gap:
            n += 1
        else:
            break
    return int(n)


def bootstrap(block_counts, stat_fn, B=300, seed=0):
    """(mean, sd) of stat_fn over B parametric resamples of the data.

    Each block is redrawn multinomially from its own observed frequencies with
    the same total, independently of the other blocks. stat_fn takes a
    {block: {key: int}} dict and returns a float. sd uses ddof=1.
    """
    B = int(B)
    if B < 2:
        raise ValueError("bootstrap needs B >= 2")
    rng = np.random.default_rng(seed)
    draws = {}
    for name, counts in block_counts.items():
        items = [(str(k), int(v)) for k, v in counts.items() if int(v)]
        keys = [k for k, _ in items]
        n = np.array([v for _, v in items], dtype=np.int64)
        total = int(n.sum())
        draws[name] = (keys, rng.multinomial(total, n / total, size=B) if total else None)
    stats = np.empty(B)
    for b in range(B):
        sample = {}
        for name, (keys, d) in draws.items():
            sample[name] = {} if d is None else {k: int(c) for k, c in zip(keys, d[b]) if c}
        stats[b] = float(stat_fn(sample))
    return float(stats.mean()), float(stats.std(ddof=1))
