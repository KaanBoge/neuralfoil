"""Manufactured-input eight-tree prototype only; no archive/model/CLI loader.

No production certificate is emitted by this module. Exact arithmetic follows
PROOF.md; an independently authenticated original-four chain is still required
before a production adapter can exist. Prior producer code is not imported.
"""
from fractions import Fraction as F
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys
import time

U = F(1, 2**53)
HALF_ETA = F(1, 2**1075)
MAX = sys.float_info.max
PAIRS = tuple(itertools.combinations(range(8), 2))
OWNED_CAP = 128 * 2**20
OUTPUT_CAP = 64 * 2**20
FAILURE_RESERVE = 2**20
LINE_CAP = 2**20


def matchings(vertices=tuple(range(8))):
    if not vertices:
        yield ()
        return
    a = vertices[0]
    for b in vertices[1:]:
        rest = tuple(v for v in vertices if v not in (a, b))
        for tail in matchings(rest):
            yield (PAIRS.index((a, b)),) + tail


MATCHINGS = tuple(matchings())


def rational(v):
    v = F(v)
    if max(v.numerator.bit_length(), v.denominator.bit_length()) > 4096:
        raise ValueError('4096-bit rational admission')
    return v


def encode(v):
    v = rational(v)
    return dict(encoding='signed_hex_fraction_v1',
                numerator=hex(v.numerator), denominator=hex(v.denominator))


def ep(v):
    return [encode(v[0]), encode(v[1])]


def directed(v, up):
    v = rational(v)
    try:
        f = float(v)
    except OverflowError as e:
        raise ValueError('outward overflow') from e
    if not math.isfinite(f):
        raise ValueError('nonfinite outward endpoint')
    if (F(f) < v) if up else (F(f) > v):
        f = math.nextafter(f, math.inf if up else -math.inf)
    if not math.isfinite(f):
        raise ValueError('outward overflow')
    return F(f)


def structural(interval):
    clip = lambda v: max(F(-1, 2), min(F(1), v))
    e = 4*U + 2*U*U
    return max(abs(clip(clip(interval[0])-e)),
               abs(clip(clip(interval[1])+e)))/2 + 3*U/2


def finite_hex(v):
    if not isinstance(v, str):
        raise ValueError('hex string required')
    f = float.fromhex(v)
    if not math.isfinite(f) or f.hex() != v:
        raise ValueError('canonical finite float')
    return f


def path_box(edges):
    if len(edges) > 14:
        raise ValueError('path depth')
    box = [(-MAX, MAX)] * 62
    empty = False
    for edge in edges:
        if type(edge) != list or len(edge) != 4:
            raise ValueError('edge schema')
        node, feat, raw, branch = edge
        if (type(node) != int or not 0 <= node < 29 or type(feat) != int
                or not 0 <= feat < 62 or type(branch) != int or branch not in (0, 1)):
            raise ValueError('edge index')
        threshold = finite_hex(raw)
        lo, hi = box[feat]
        if branch == 0:
            hi = min(hi, threshold)
        else:
            lo = max(lo, math.nextafter(threshold, math.inf))
        empty |= lo > hi or not math.isfinite(lo)
        box[feat] = lo, hi
    return None if empty else tuple(box)


def compatible(a, b):
    return all(max(x[0], y[0]) <= min(x[1], y[1]) for x, y in zip(a, b))


def validate_paths(row, stage):
    if set(row) != {'stage', 'leaves'} or row['stage'] != stage:
        raise ValueError('stage identity')
    leaves = row['leaves']
    if not 1 <= len(leaves) <= 15:
        raise ValueError('leaf cardinality')
    ids = []
    boxes = []
    values = []
    for leaf in leaves:
        if set(leaf) != {'leaf', 'value', 'edges', 'empty'}:
            raise ValueError('leaf fields')
        i = leaf['leaf']
        if type(i) != int or not 0 <= i < 29 or type(leaf['empty']) != bool:
            raise ValueError('leaf identity')
        box = path_box(leaf['edges'])
        if leaf['empty'] != (box is None):
            raise ValueError('empty path flag')
        ids.append(i)
        boxes.append(box)
        values.append(F(finite_hex(leaf['value'])))
    if ids != sorted(set(ids)):
        raise ValueError('leaf ordering/duplication')
    return boxes, values


class Budget:
    def __init__(self, seconds=900):
        if not 0 < seconds <= 900:
            raise ValueError('time cap')
        self.deadline = time.monotonic() + seconds
        self.pairs = 0

    def check(self):
        if time.monotonic() >= self.deadline:
            raise TimeoutError('fixed deadline')
        if self.pairs > 315000:
            raise ValueError('classification cap')


def block(trees, incoming, old4_stage, old4_global, budget):
    """Pure arithmetic. Caller must independently establish old4 validity.

    This function cannot authenticate a supplied enclosure and is NOT a
    production barrier. Synthetic tests supply manufactured valid old bounds.
    """
    if len(trees) != 8:
        raise ValueError('exact eight stages')
    first = trees[0]['stage']
    if first % 8 or old4_stage != first + 8:
        raise ValueError('same GLOBAL stage required')
    if incoming[0] > incoming[1] or old4_global[0] > old4_global[1]:
        raise ValueError('empty input interval')
    boxes, values = zip(*(validate_paths(row, first+k) for k, row in enumerate(trees)))
    records, ranges = [], []
    for a, b in PAIRS:
        codes = bytearray()
        lo = hi = None
        feasible = 0
        for i, va in enumerate(values[a]):
            for j, vb in enumerate(values[b]):
                budget.pairs += 1
                budget.check()
                aa, bb = boxes[a][i], boxes[b][j]
                code = 0 if aa is None or bb is None else (2 if compatible(aa, bb) else 1)
                codes.append(code)
                if code == 2:
                    value = rational(va + vb)
                    lo = value if lo is None else min(lo, value)
                    hi = value if hi is None else max(hi, value)
                    feasible += 1
        if lo is None:
            raise ValueError('empty feasible pair on D')
        ranges.append((lo, hi))
        records.append(dict(stages=[first+a, first+b], shape=[len(values[a]), len(values[b])],
                            status_hex=codes.hex(), feasible=feasible, real_sum=ep((lo, hi))))
    matching_records = []
    lows, highs = [], []
    for ids in MATCHINGS:
        lo = rational(sum((ranges[i][0] for i in ids), F(0)))
        hi = rational(sum((ranges[i][1] for i in ids), F(0)))
        lows.append(lo)
        highs.append(hi)
        matching_records.append(dict(pair_indices=list(ids), real_sum=ep((lo, hi))))
    real = max(lows), min(highs)
    if real[0] > real[1]:
        raise ValueError('empty matching intersection')
    cart = incoming
    error = F(0)
    steps = []
    for k, vals in enumerate(values):
        pre = rational(cart[0]+min(vals)), rational(cart[1]+max(vals))
        magnitude = max(abs(pre[0]), abs(pre[1]))
        delta = rational(U*magnitude + HALF_ETA)
        after = directed(pre[0], False), directed(pre[1], True)
        error = rational(error+delta)
        steps.append(dict(stage=first+k, incoming=ep(cart), pre_sum=ep(pre),
                          magnitude=encode(magnitude), delta=encode(delta), outgoing=ep(after)))
        cart = after
    branch = (directed(incoming[0]+real[0]-error, False),
              directed(incoming[1]+real[1]+error, True))
    out = max(branch[0], old4_global[0]), min(branch[1], old4_global[1])
    if out[0] > out[1]:
        raise ValueError('empty old4 global intersection')
    result = dict(kind='block', block=first//8, stages=list(range(first, first+8)),
                  pairs=records, matchings=matching_records, real_sum=ep(real),
                  incoming=ep(incoming), error_steps=steps, error_total=encode(error),
                  rounding_branch=ep(branch), old4_stage=old4_stage,
                  old4_global_outgoing=ep(old4_global), outgoing=ep(out))
    budget.check()
    return result, out


def memory_plan(source_bytes, input_bytes, array_bytes):
    for n in (source_bytes, input_bytes, array_bytes):
        if type(n) != int or n < 0:
            raise ValueError('nonnegative integer byte charge')
    estimate = 96*2**20 + 4*source_bytes + 2*input_bytes + 6*array_bytes
    if estimate > OWNED_CAP:
        raise MemoryError('fixed 128 MiB owned admission')
    return dict(estimate=estimate, cap=OWNED_CAP,
                status='CONDITIONAL_NO_PRODUCTION_ADAPTER_REVIEW', measure='owned_estimate_not_RSS')


class SyntheticStream:
    """Exclusive bounded JSONL sink, NEVER a production completion receipt.

    Failed/truncated file remains. Caller must retain exception/failure metadata.
    Sources/proof/predecessor approval belong in a separately reviewed wrapper.
    """
    def __init__(self, path):
        path = Path(path)
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('symlink path')
        self.f = path.open('xb')
        self.size = 0
        self.sha = hashlib.sha256()

    def write(self, record):
        # Iterate encoder with a bound, rather than build unbounded full text.
        buf = bytearray()
        for token in json.JSONEncoder(sort_keys=True, separators=(',', ':'),
                                      ensure_ascii=True, allow_nan=False).iterencode(record):
            part = token.encode('ascii')
            if len(buf)+len(part)+1 > LINE_CAP:
                raise MemoryError('JSONL line cap')
            buf.extend(part)
        buf.extend(b'\n')
        if self.size + len(buf) > OUTPUT_CAP - FAILURE_RESERVE:
            raise OSError('output cap/failure reserve')
        self.f.write(buf)
        self.f.flush()
        self.sha.update(buf)
        self.size += len(buf)

    def close(self):
        self.f.close()
