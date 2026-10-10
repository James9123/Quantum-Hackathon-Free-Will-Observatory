"""One-job packer/unpacker with canary (orientation + readout calibration) blocks.

A *block* is a small unmeasured circuit plus the list of its qubits to measure.
`pack` lays blocks out so that one `backend.run` covers them all:

- mode="tile":  every block side by side on disjoint qubits of ONE circuit.
- mode="list":  one circuit per block, submitted together as one list job.
- mode="tiles": blocks packed first-fit into as few tile circuits as fit
                `max_qubits`, submitted as one list job.

Bit conventions (Qiskit's): each packed circuit has ONE classical register.
Block-local results use the same convention: the bit for `measure[j]` is
character `-1 - j` of the block's key (bit 0 rightmost).

Canary blocks (canary=True) go first:
- "_canary_orient": qubits 0 and 1 flipped to |1>, measured in the order
  [2, 0, 1]. The expected key "110" is not a palindrome, and it differs
  from what a provider would report if it reversed keys or ignored the
  qubit->clbit map, so `diagnose_orientation` can tell those apart.
- "_canary_cal0" / "_canary_cal1": 3 qubits left in |0> / flipped to |1>.
  They give per-bit readout flip rates P(1|0) and P(0|1).
"""

from dataclasses import dataclass, field

import qk_runtime

CANARY_ORIENT = "_canary_orient"
CANARY_CAL0 = "_canary_cal0"
CANARY_CAL1 = "_canary_cal1"
CANARY_NAMES = (CANARY_ORIENT, CANARY_CAL0, CANARY_CAL1)
ORIENT_PREP = (1, 1, 0)        # prepared value of local qubits 0, 1, 2
ORIENT_MEASURE = [2, 0, 1]     # measured into local bits 0, 1, 2
MODES = ("tile", "list", "tiles")


@dataclass
class Block:
    name: str
    circuit: object                 # QuantumCircuit, unmeasured, local qubit indices
    measure: list                   # local qubits to measure, in result order (bit 0 first)
    meta: dict = field(default_factory=dict)

    @property
    def num_qubits(self):
        return int(self.circuit.num_qubits)


@dataclass
class Slot:
    name: str
    circuit_index: int
    qubits: list                    # global qubit index of each local qubit
    clbits: list                    # global clbit index of each measured bit
    measure: list                   # the block's local measure list
    meta: dict = field(default_factory=dict)


@dataclass
class PackedJob:
    circuits: list
    slots: list
    mode: str
    canary: bool
    max_qubits: int

    def slot(self, name):
        for s in self.slots:
            if s.name == name:
                return s
        raise KeyError(name)

    def summary(self):
        """JSON-safe description of the layout (for claim cards / provenance)."""
        return {
            "mode": self.mode,
            "canary": self.canary,
            "max_qubits": self.max_qubits,
            "n_circuits": len(self.circuits),
            "qubits_per_circuit": [int(c.num_qubits) for c in self.circuits],
            "clbits_per_circuit": [int(c.num_clbits) for c in self.circuits],
            "blocks": [
                {"name": s.name, "circuit": s.circuit_index,
                 "qubits": list(s.qubits), "clbits": list(s.clbits)}
                for s in self.slots
            ],
        }


def canary_blocks():
    from qiskit import QuantumCircuit
    orient = QuantumCircuit(3, name=CANARY_ORIENT)
    for q, v in enumerate(ORIENT_PREP):
        if v:
            orient.x(q)
    cal0 = QuantumCircuit(3, name=CANARY_CAL0)
    cal1 = QuantumCircuit(3, name=CANARY_CAL1)
    cal1.x([0, 1, 2])
    return [
        Block(CANARY_ORIENT, orient, list(ORIENT_MEASURE), {"canary": "orientation"}),
        Block(CANARY_CAL0, cal0, [0, 1, 2], {"canary": "cal0"}),
        Block(CANARY_CAL1, cal1, [0, 1, 2], {"canary": "cal1"}),
    ]


def expected_orientation_key():
    return "".join(str(ORIENT_PREP[q]) for q in reversed(ORIENT_MEASURE))


def _validate(blocks):
    seen = set()
    for b in blocks:
        if b.name in seen:
            raise ValueError("duplicate block name %r" % b.name)
        seen.add(b.name)
        c = b.circuit
        if c.num_clbits or any(inst.operation.name == "measure" for inst in c.data):
            raise ValueError("block %r: circuit must be unmeasured with no clbits" % b.name)
        n = c.num_qubits
        if not b.measure:
            raise ValueError("block %r: nothing to measure" % b.name)
        if len(set(b.measure)) != len(b.measure) or any(not 0 <= q < n for q in b.measure):
            raise ValueError("block %r: bad measure list %r for %d qubits" % (b.name, b.measure, n))


def _with_canary(blocks, canary):
    blocks = list(blocks)
    if any(b.name in CANARY_NAMES for b in blocks):
        raise ValueError("block names %r are reserved" % (CANARY_NAMES,))
    return (canary_blocks() + blocks) if canary else blocks


def _groups(blocks, mode, max_qubits):
    for b in blocks:
        if b.num_qubits > max_qubits:
            raise ValueError("block %r needs %d qubits > max_qubits %d"
                             % (b.name, b.num_qubits, max_qubits))
    if mode == "list":
        return [[b] for b in blocks]
    if mode == "tile":
        total = sum(b.num_qubits for b in blocks)
        if total > max_qubits:
            raise ValueError("tile needs %d qubits > max_qubits %d; use mode='tiles' or 'list'"
                             % (total, max_qubits))
        return [blocks]
    groups, cur, used = [], [], 0
    for b in blocks:
        if used + b.num_qubits > max_qubits:
            groups.append(cur)
            cur, used = [], 0
        cur.append(b)
        used += b.num_qubits
    if cur:
        groups.append(cur)
    return groups


def pack(blocks, *, max_qubits, mode="tile", canary=True):
    """Lay blocks out for ONE submission. Returns a PackedJob."""
    from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
    if mode not in MODES:
        raise ValueError("mode must be one of %r" % (MODES,))
    blocks = _with_canary(blocks, canary)
    _validate(blocks)
    circuits, slots = [], []
    for ci, group in enumerate(_groups(blocks, mode, int(max_qubits))):
        nq = sum(b.num_qubits for b in group)
        nc = sum(len(b.measure) for b in group)
        qc = QuantumCircuit(QuantumRegister(nq, "q"), ClassicalRegister(nc, "c"),
                            name=group[0].name if len(group) == 1 else "tile%d" % ci)
        q_off = c_off = 0
        group_slots = []
        for b in group:
            qubits = list(range(q_off, q_off + b.num_qubits))
            clbits = list(range(c_off, c_off + len(b.measure)))
            qc.compose(b.circuit, qubits=qubits, inplace=True)
            group_slots.append(Slot(b.name, ci, qubits, clbits, list(b.measure), dict(b.meta)))
            q_off += b.num_qubits
            c_off += len(b.measure)
        for s in group_slots:
            for j, lq in enumerate(s.measure):
                qc.measure(s.qubits[lq], s.clbits[j])
        circuits.append(qc)
        slots.extend(group_slots)
    return PackedJob(circuits, slots, mode, bool(canary), int(max_qubits))


def capacity(blocks, max_qubits, *, canary=True):
    """How many of `blocks` (in order) fit in one tile circuit, after the canary."""
    used = sum(b.num_qubits for b in canary_blocks()) if canary else 0
    n = 0
    for b in blocks:
        if used + b.num_qubits > max_qubits:
            break
        used += b.num_qubits
        n += 1
    return n


def _as_list(counts_list, n):
    if isinstance(counts_list, dict):
        counts_list = [counts_list]
    counts_list = list(counts_list)
    if len(counts_list) != n:
        raise ValueError("expected %d count dicts, got %d" % (n, len(counts_list)))
    return counts_list


def unpack(packed, counts_list, *, assume="clbit"):
    """Per-block marginal counts {block name: {local key: count}}.

    assume="clbit" is the correct reading. "reversed" and "qubit" re-read the same
    data as if the provider had reversed the key, or keyed bits by qubit index
    instead of clbit; they exist for `diagnose_orientation`.
    """
    counts_list = _as_list(counts_list, len(packed.circuits))
    out = {}
    for ci, circ in enumerate(packed.circuits):
        width = int(circ.num_qubits) if assume == "qubit" else int(circ.num_clbits)
        norm = qk_runtime.normalize_counts(counts_list[ci], width)
        if assume == "reversed":
            norm = {k[::-1]: v for k, v in norm.items()}
        for s in packed.slots:
            if s.circuit_index != ci:
                continue
            if assume == "qubit":
                positions = [s.qubits[lq] for lq in s.measure]
            else:
                positions = list(s.clbits)
            idx = [width - 1 - p for p in reversed(positions)]   # string index per local bit, MSB first
            marg = {}
            for key, n in norm.items():
                local = "".join(key[i] for i in idx)
                marg[local] = marg.get(local, 0) + n
            out[s.name] = dict(sorted(marg.items()))
    return out


def _frac(counts, key):
    total = sum(counts.values())
    return counts.get(key, 0) / total if total else 0.0


def _bit_rate(counts, bit, value):
    """Fraction of shots whose local bit `bit` reads `value`."""
    total = sum(counts.values())
    if not total:
        return float("nan")
    hit = sum(n for k, n in counts.items() if k[-1 - bit] == value)
    return hit / total


def canary_report(unpacked):
    """Orientation verdict and per-bit readout flip rates from the canary blocks."""
    exp = expected_orientation_key()
    orient = unpacked.get(CANARY_ORIENT, {})
    majority = max(orient, key=orient.get) if orient else None
    frac = _frac(orient, exp)
    cal0 = unpacked.get(CANARY_CAL0, {})
    cal1 = unpacked.get(CANARY_CAL1, {})
    p01 = [_bit_rate(cal0, i, "1") for i in range(3)] if cal0 else []
    p10 = [_bit_rate(cal1, i, "0") for i in range(3)] if cal1 else []
    return {
        "orientation_ok": bool(orient) and majority == exp and frac > 0.5,
        "orientation_expected": exp,
        "orientation_majority": majority,
        "orientation_fraction": frac,
        "p_flip_0to1": p01,
        "p_flip_1to0": p10,
        "p_flip_0to1_mean": sum(p01) / len(p01) if p01 else float("nan"),
        "p_flip_1to0_mean": sum(p10) / len(p10) if p10 else float("nan"),
    }


def diagnose_orientation(packed, counts_list):
    """Fraction of orientation-canary shots matching the expected key under
    each hypothesis about how the provider keyed the bits. The correct reading
    should be ~1 (minus readout error); the others should be well below it."""
    exp = expected_orientation_key()
    out = {}
    for assume in ("clbit", "reversed", "qubit"):
        try:
            u = unpack(packed, counts_list, assume=assume)
            out[assume] = round(_frac(u.get(CANARY_ORIENT, {}), exp), 4)
        except Exception as exc:
            out[assume] = "error: %s" % type(exc).__name__
    return out
