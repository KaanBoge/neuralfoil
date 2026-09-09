"""Independent streamed eight-tree replay, authored from the schema and proof.

No eight-tree producer imports and no automatic model/file intake. The caller
must authenticate model archive bytes and the named predecessor replay chain.
This checker independently replays the complete original four-tree certificate
against those arrays before using any global-stage endpoint. Its mathematical
primitives are the already authenticated, independently authored prior checker.
"""
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import time
import types

FOUR_SHA = 'ad4bbdf7b70fd862c959e3d916990890133f5ac4f9af714fb1e5ec6cc7706f1a'
U = F(1, 2**53)
HALF_ETA = F(1, 2**1075)
PAIRS = tuple((i, j) for i in range(8) for j in range(i+1, 8))
MEMORY_CAP = 256 * 2**20
LINE_CAP = 2**20
STREAM_CAP = 63 * 2**20


def prior_checker():
    p = Path(__file__).resolve().parent.parent/'four_tree_matching/checker.py'
    raw = p.read_bytes()
    if hashlib.sha256(raw).hexdigest() != FOUR_SHA:
        raise ValueError('prior independent four-tree source changed')
    m = types.ModuleType('eight_independent_prior_four')
    m.__file__ = str(p)
    exec(compile(raw, str(p), 'exec'), m.__dict__)
    return m


def matchings():
    def visit(rest):
        if not rest:
            yield ()
            return
        first = rest[0]
        for other in rest[1:]:
            remaining = tuple(x for x in rest if x not in (first, other))
            for tail in visit(remaining):
                yield (PAIRS.index((first, other)),) + tail
    result = tuple(visit(tuple(range(8))))
    if len(result) != 105 or len(set(result)) != 105:
        raise ValueError('complete 105 matchings')
    for row in result:
        if len(row) != 4 or sorted(v for k in row for v in PAIRS[k]) != list(range(8)):
            raise ValueError('disjoint complete matching')
    return result


def encoded(value):
    x = F(value)
    if max(abs(x.numerator).bit_length(), x.denominator.bit_length()) > 4096:
        raise ValueError('bounded rational limbs')
    return {'encoding': 'signed_hex_fraction_v1',
            'numerator': hex(x.numerator), 'denominator': hex(x.denominator)}


def interval(values):
    return [encoded(x) for x in values]


def summary(p, values):
    return dict(zip(('lower', 'upper', 'B'),
                    (encoded(values[0]), encoded(values[1]), encoded(p.structural(*values)))))


def owned_estimate(array_bytes, source_bytes, old_raw_bytes, line_bytes=0, parsed_bytes=0):
    """Conservative CPython-owned accounting, not an RSS/ABI theorem.

    Fixed96MiB covers full6000x62 path boxes (128bytes/coordinate),84000
    path-edge objects (256bytes/edge),16MiB active block/exact rational scratch
    and remaining fixed/control overhead. Sources, model/decompression copies,
    retained old raw certificate, line buffers and lexical parser allocation
    are additional rather than absorbed into that fixed charge.
    """
    for x in (array_bytes, source_bytes, old_raw_bytes, line_bytes, parsed_bytes):
        if type(x) is not int or x < 0:
            raise ValueError('strict nonnegative byte count')
    if line_bytes > LINE_CAP or old_raw_bytes > 64*2**20:
        raise MemoryError('finite serialized input cap')
    return 96*2**20 + 6*array_bytes + 4*source_bytes + 2*old_raw_bytes + 8*line_bytes + parsed_bytes


def expected_block(p, trees, j, incoming, old_global, deadline=None):
    """Reconstruct one block from independently reconstructed path/box tuples."""
    pair_rows = []
    pair_bounds = []
    classifications = feasible = witness_checks = 0
    for left_id, right_id in PAIRS:
        left, right = trees[8*j+left_id], trees[8*j+right_id]
        status = bytearray()
        low = high = None
        accepted = 0
        for lr, lb in left:
            for rr, rb in right:
                if classifications % 64 == 0:
                    p.tick(deadline)
                classifications += 1
                if lb is None or rb is None:
                    status.append(0)
                    continue
                box = p.intersect(lb, rb)
                if box is None:
                    status.append(1)
                    continue
                status.append(2)
                point = tuple(a for a, b in box)
                for row in (lr, rr):
                    for edge in row['edges']:
                        test = point[edge['feature']] <= p.hx(edge['threshold'])
                        if test != (edge['branch'] == 'L'):
                            raise ValueError('model branch intersection witness')
                        witness_checks += 1
                value = F(p.hx(lr['value'])) + F(p.hx(rr['value']))
                low = value if low is None else min(low, value)
                high = value if high is None else max(high, value)
                accepted += 1
        if not accepted:
            raise ValueError('no feasible leaf pair on nonempty D')
        feasible += accepted
        pair_bounds.append((low, high))
        pair_rows.append({'stages': [8*j+left_id, 8*j+right_id],
                          'shape': [len(left), len(right)], 'status_hex': status.hex(),
                          'feasible': accepted, 'real_sum': interval((low, high))})
    matching_rows = []
    lows, highs = [], []
    for indices in matchings():
        low = sum((pair_bounds[k][0] for k in indices), F(0))
        high = sum((pair_bounds[k][1] for k in indices), F(0))
        lows.append(low)
        highs.append(high)
        matching_rows.append({'pair_indices': list(indices), 'real_sum': interval((low, high))})
    real = max(lows), min(highs)
    if real[0] > real[1]:
        raise ValueError('empty exact matching intersection')
    cartesian = incoming
    steps = []
    allowance = F(0)
    for k in range(8):
        values = [F(p.hx(row['value'])) for row, box in trees[8*j+k]]
        pre = cartesian[0] + min(values), cartesian[1] + max(values)
        magnitude = max(abs(x) for x in pre)
        delta = U*magnitude + HALF_ETA
        after = p.directed(pre[0], False), p.directed(pre[1], True)
        steps.append({'stage': 8*j+k, 'incoming': interval(cartesian),
                      'pre_sum': interval(pre), 'magnitude': encoded(magnitude),
                      'delta': encoded(delta), 'outgoing': interval(after)})
        allowance += delta
        cartesian = after
    rounded = (p.directed(incoming[0]+real[0]-allowance, False),
               p.directed(incoming[1]+real[1]+allowance, True))
    outgoing = max(rounded[0], old_global[0]), min(rounded[1], old_global[1])
    if not old_global[0] <= outgoing[0] <= outgoing[1] <= old_global[1]:
        raise ValueError('global-stage intersection/nonloosening')
    record = {'kind': 'block', 'block': j, 'stages': list(range(8*j, 8*j+8)),
              'pairs': pair_rows, 'matchings': matching_rows, 'real_sum': interval(real),
              'incoming': interval(incoming), 'error_steps': steps,
              'error_total': encoded(allowance), 'rounding_branch': interval(rounded),
              'old4_stage': 8*(j+1), 'old4_global_outgoing': interval(old_global),
              'outgoing': interval(outgoing)}
    return record, outgoing, (classifications, feasible, witness_checks)


def check_stream(stream, arrays, old4_raw, *, expected, source_bytes=0, deadline=None):
    """Caller supplies bounded stream and authenticated model arrays.

    expected must independently bind model, original certificate and original
    model-array replay identities. The old certificate bytes are hashed here;
    all old block mathematics are independently replayed before new intake.
    No claimed certificate field can choose its own expected model identity.
    """
    if type(expected) is not dict or set(expected) != {
            'model_sha256', 'old4_certificate_sha256', 'old4_replay_complete_sha256'}:
        raise ValueError('explicit three-identity expectation')
    if any(type(h) is not str or len(h) != 64 or any(c not in '0123456789abcdef' for c in h)
           for h in expected.values()):
        raise ValueError('expected SHA256 identities')
    if type(old4_raw) is not bytes or hashlib.sha256(old4_raw).hexdigest() != expected['old4_certificate_sha256']:
        raise ValueError('original four-tree byte binding')
    four = prior_checker()
    p = four.primitives()
    p.tick(deadline)
    if type(arrays) is not dict:
        raise ValueError('model array mapping')
    array_bytes = sum(int(getattr(a, 'nbytes', 0)) for a in arrays.values())
    estimate = owned_estimate(array_bytes, source_bytes, len(old4_raw), LINE_CAP)
    if estimate > MEMORY_CAP:
        raise MemoryError('eight-tree owned-memory admission')
    old4, allocation = four.parse_certificate(old4_raw, array_bytes=array_bytes, source_bytes=source_bytes)
    old_qa = four.check(old4, arrays, deadline, expected_model_sha=expected['model_sha256'],
                        source_bytes=source_bytes, input_bytes=len(old4_raw), parsed_bytes=allocation)
    old_chain = [tuple(p.rational(v) for v in row['outgoing']) for row in old4['blocks']]
    old_final = dict(old4['final'])
    old_estimate = old_qa['checker_accounting']['estimated_owned_bytes']
    del old4, old_qa
    initial, trees = p.inventory(arrays, 400, deadline)
    trees = [sorted(tree, key=lambda v: v[0]['leaf']) for tree in trees]
    digest = hashlib.sha256()
    total = records = 0
    largest_owned = max(estimate, old_estimate)

    def next_record():
        nonlocal total, records, largest_owned
        p.tick(deadline)
        raw = stream.readline(LINE_CAP+1)
        if not raw or len(raw) > LINE_CAP or not raw.endswith(b'\n'):
            raise ValueError('bounded complete JSONL record')
        total += len(raw)
        if total > STREAM_CAP:
            raise MemoryError('complete stream byte cap with reserve')
        digest.update(raw)
        # Admit BEFORE JSON allocation. The prior lexical charge is
        # 7L+128containers+96colons+64commas+128strings. Each of the first
        # three counts is at most L and strings at most L/2, giving359L;
        # 384L is a deliberately conservative integer upper bound.
        reserve = owned_estimate(array_bytes, source_bytes, len(old4_raw), len(raw), 384*len(raw))
        if reserve > MEMORY_CAP:
            raise MemoryError('pre-parse stream live-owned admission')
        largest_owned = max(largest_owned, reserve)
        # Reuse only the independently authored lexical admission/parser;
        # its measured lexical charge must fit the admitted reserve.
        value, allocated = four.parse_certificate(raw[:-1], array_bytes=array_bytes, source_bytes=source_bytes)
        if allocated > 384*len(raw):
            raise MemoryError('lexical reserve invariant')
        charge = owned_estimate(array_bytes, source_bytes, len(old4_raw), len(raw), allocated)
        if charge > MEMORY_CAP:
            raise MemoryError('stream record live-owned admission')
        largest_owned = max(largest_owned, charge)
        if json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()+b'\n' != raw:
            raise ValueError('canonical JSONL record')
        records += 1
        return value

    header = {'kind': 'header', 'schema': 'EIGHT_TREE_MATCHING_JSONL_V1',
              'domain': 'FINITE_X62_V1', **expected, 'initial': initial.hex(), 'stages': 400, 'blocks': 50}
    p.exact_object(next_record(), header)
    paths = edges = 0
    for stage, tree in enumerate(trees):
        leaves = []
        for row, box in tree:
            leaves.append({'leaf': row['leaf'], 'value': row['value'], 'empty': box is None,
                           'edges': [[e['node'], e['feature'], e['threshold'],
                                      0 if e['branch'] == 'L' else 1] for e in row['edges']]})
            paths += 1
            edges += len(row['edges'])
        p.exact_object(next_record(), {'kind': 'paths', 'stage': stage, 'leaves': leaves})
    current = F(initial), F(initial)
    classifications = feasible = witnesses = 0
    for j in range(50):
        record, current, counts = expected_block(p, trees, j, current, old_chain[2*j+1], deadline)
        p.exact_object(next_record(), record)
        classifications += counts[0]
        feasible += counts[1]
        witnesses += counts[2]
        del record
    counts = {'stages': 400, 'blocks': 50, 'paths': paths, 'path_edges': edges,
              'pair_classifications': classifications, 'feasible_pairs': feasible}
    final = summary(p, current)
    p.exact_object(next_record(), {'kind': 'footer', 'counts': counts, 'original_four': old_final, 'final': final})
    if stream.read(1) or records != 452 or classifications > 315000:
        raise ValueError('complete exact stream inventory/no trailing bytes')
    if p.rational(final['B']) > p.rational(old_final['B']):
        raise ValueError('final bound widened')
    p.tick(deadline)
    return {'status': 'PASS_INDEPENDENT_EIGHT_TREE_STREAM_REPLAY', 'identities': expected,
            'counts': counts, 'records': records, 'stream_bytes': total,
            'stream_sha256': digest.hexdigest(), 'branch_witness_checks': witnesses,
            'original_four': old_final, 'final': final,
            'estimated_owned_bytes': largest_owned, 'limit_bytes': MEMORY_CAP,
            'scope': 'Independent model-array enclosure replay, not physical accuracy or all-platform memory proof',
            'model_byte_and_replay_chain_authentication_required_from_wrapper': True}
