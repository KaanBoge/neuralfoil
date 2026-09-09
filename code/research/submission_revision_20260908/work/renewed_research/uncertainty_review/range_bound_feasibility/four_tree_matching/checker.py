"""Independent four-tree certificate replay; no producer import or data access.

The caller authenticates serialized model bytes before passing arrays. Only the
previous independent checker supplies primitive tree intake and directed sums.
This module independently constructs all six pair inventories, matching bounds,
four-operation errors, and separate old/new interval chains from those arrays.
"""
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import time
import types

PRIMITIVE_SHA = '33e04358f4ac925b79f5022880c128bd6b0e55016c8e45262e2db8a5ea4bf30b'
MODEL_SHA = 'ff9c030097f307be0b30627e79f05daf8da7c7176b5621039ff2e3485a9cf327'
PAIRS = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
MATCHINGS = ((0, 5), (1, 4), (2, 3))
U = F(1, 2**53)
HALF_ETA = F(1, 2**1075)
MEMORY_CAP = 256 * 2**20
INPUT_CAP = 64 * 2**20


def primitives():
    path = Path(__file__).resolve().parent.parent / 'paired_checker.py'
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PRIMITIVE_SHA:
        raise ValueError('independent primitive source changed')
    module = types.ModuleType('independent_paired_primitives')
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def encoded(x):
    x = F(x)
    if max(abs(x.numerator).bit_length(), x.denominator.bit_length()) > 4096:
        raise ValueError('rational limb cap')
    return {'encoding': 'signed_hex_fraction_v1',
            'numerator': hex(x.numerator), 'denominator': hex(x.denominator)}


def interval(bounds):
    return [encoded(v) for v in bounds]


def safe_json(value, depth=0):
    """Reject oversized/noncanonical scalar encodings before equality dumps."""
    if depth > 16:
        raise ValueError('certificate nesting cap')
    if type(value) is dict:
        if len(value) > 32 or any(type(k) is not str or len(k) > 64 for k in value):
            raise ValueError('dictionary shape')
        if 'encoding' in value:
            if set(value) != {'encoding', 'numerator', 'denominator'}:
                raise ValueError('rational keys')
            if value['encoding'] != 'signed_hex_fraction_v1':
                raise ValueError('rational encoding')
            numbers = []
            for k in ('numerator', 'denominator'):
                s = value[k]
                if type(s) is not str or len(s) > 1027:
                    raise ValueError('rational text cap')
                try:
                    n = int(s, 16)
                except ValueError as exc:
                    raise ValueError('rational integer') from exc
                if hex(n) != s or abs(n).bit_length() > 4096:
                    raise ValueError('canonical bounded rational integer')
                numbers.append(n)
            n, d = numbers
            if d <= 0 or F(n, d).numerator != n or F(n, d).denominator != d:
                raise ValueError('reduced positive denominator')
        for item in value.values():
            safe_json(item, depth + 1)
    elif type(value) is list:
        if len(value) > 6000:
            raise ValueError('list cap')
        for item in value:
            safe_json(item, depth + 1)
    elif type(value) is str:
        if len(value) > 1027:
            raise ValueError('string cap')
    elif type(value) is int:
        if value.bit_length() > 64:
            raise ValueError('plain integer cap')
    elif type(value) is not bool:
        raise ValueError('unsupported certificate scalar')


def owned_estimate(array_bytes, source_bytes, input_bytes, parsed_bytes=0):
    """Conservative algorithm-owned estimate, explicitly not sampled RSS.

    Includes the larger of five serialized-input equivalents and a lexical
    pre-parse container/string allocation charge for parsed containers and dumps,
    full independent 6000x62 boxes, all 84000 path edges, bounded block scratch,
    rational limbs, source/model bytes, and 8 MiB fixed overhead. The wrapper
    must apply this same admission check before JSON parsing/model loading.
    """
    for value in (array_bytes, source_bytes, input_bytes, parsed_bytes):
        if type(value) is not int or value < 0:
            raise ValueError('nonnegative strict byte count')
    if input_bytes > INPUT_CAP:
        raise MemoryError('certificate input limit')
    return (8 * 2**20 + max(5 * input_bytes, parsed_bytes) + source_bytes + array_bytes
            + 6000 * 62 * 128 + 84000 * 256 + 100 * 65536 + 135000 * 8)


def parse_certificate(raw, *, array_bytes=0, source_bytes=0):
    """Bound lexical allocation before JSON containers exist.

    These CPython engineering charges deliberately overcount commas and string
    bytes. They are not a general ABI or RSS theorem. Arrays/objects, dictionary
    entries, scalar slots, strings and input/decode buffers are all charged.
    Only canonical certificate types are subsequently accepted by safe_json.
    """
    if type(raw) is not bytes or len(raw) > INPUT_CAP:
        raise ValueError('bounded certificate bytes')
    containers = colons = commas = strings = depth = 0
    quoted = escaped = False
    string_length = 0
    for byte in raw:
        if quoted:
            string_length += 1
            if string_length > 6 * 1027:
                raise ValueError('pre-parse string length cap')
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
            continue
        if byte == 34:
            quoted = True
            strings += 1
            string_length = 0
        elif byte in (91, 123):
            containers += 1
            depth += 1
            if depth > 16 or containers > 250000:
                raise ValueError('pre-parse container/depth cap')
        elif byte in (93, 125):
            depth -= 1
            if depth < 0:
                raise ValueError('pre-parse unmatched container')
        elif byte == 58:
            colons += 1
        elif byte == 44:
            commas += 1
    if quoted or depth:
        raise ValueError('pre-parse incomplete JSON')
    allocation = (7 * len(raw) + 128 * containers + 96 * colons
                  + 64 * commas + 128 * strings)
    estimate = owned_estimate(array_bytes, source_bytes, len(raw), allocation)
    if estimate > MEMORY_CAP:
        raise MemoryError('pre-parse conservative owned-memory admission')
    def unique(rows):
        result = {}
        for k, v in rows:
            if k in result:
                raise ValueError('duplicate certificate key')
            result[k] = v
        return result
    def integer(s):
        if len(s) > 21:
            raise ValueError('pre-parse integer length')
        n = int(s)
        if n.bit_length() > 64:
            raise ValueError('pre-parse integer bits')
        return n
    def no_float(s):
        raise ValueError('no JSON floating certificate scalars')
    result = json.loads(raw, object_pairs_hook=unique, parse_int=integer,
                        parse_float=no_float, parse_constant=no_float)
    safe_json(result)
    return result, allocation


def check(certificate, arrays, deadline=None, *, expected_model_sha=MODEL_SHA,
          source_bytes=0, input_bytes=0, parsed_bytes=0):
    p = primitives()
    p.runtime()
    p.tick(deadline)
    if (type(expected_model_sha) is not str or len(expected_model_sha) != 64
            or any(c not in '0123456789abcdef' for c in expected_model_sha)):
        raise ValueError('expected model hash')
    if type(arrays) is not dict:
        raise ValueError('array mapping')
    array_bytes = sum(int(getattr(a, 'nbytes', 0)) for a in arrays.values())
    estimate = owned_estimate(array_bytes, source_bytes, input_bytes, parsed_bytes)
    if estimate > MEMORY_CAP:
        raise MemoryError('checker conservative owned-memory admission')
    safe_json(certificate)
    p.keys(certificate, ('schema', 'model_sha256', 'domain', 'initial', 'paths',
                         'blocks', 'stage0', 'original_adjacent', 'final',
                         'counts', 'accounting'))
    if (certificate['schema'] != 'FOUR_TREE_MATCHING_CERTIFICATE_V1'
            or certificate['domain'] != 'FINITE_X62_V1'
            or certificate['model_sha256'] != expected_model_sha):
        raise ValueError('certificate identity')
    initial, trees = p.inventory(arrays, 400, deadline)
    trees = [sorted(t, key=lambda z: z[0]['leaf']) for t in trees]
    p.exact_object(certificate['initial'], initial.hex())
    expected_paths = []
    paths = edges = 0
    for j, tree in enumerate(trees):
        rows = []
        for row, box in tree:
            rows.append({'leaf': row['leaf'], 'value': row['value'],
                         'empty': box is None,
                         'edges': [[e['node'], e['feature'], e['threshold'],
                                    0 if e['branch'] == 'L' else 1]
                                   for e in row['edges']]})
            paths += 1
            edges += len(row['edges'])
        expected_paths.append({'stage': j, 'leaves': rows})
    p.exact_object(certificate['paths'], expected_paths)
    del expected_paths
    if type(certificate['blocks']) is not list or len(certificate['blocks']) != 100:
        raise ValueError('exact 100 blocks')
    stage0 = (F(initial), F(initial))
    for tree in trees:
        values = [F(p.hx(row['value'])) for row, _ in tree]
        stage0 = (p.directed(stage0[0] + min(values), False),
                  p.directed(stage0[1] + max(values), True))
    current = original = (F(initial), F(initial))
    classified = feasible_total = witness_checks = 0
    for j, saved in enumerate(certificate['blocks']):
        p.tick(deadline)
        pair_rows, sequences, pair_ranges = [], [], []
        for a, b in PAIRS:
            left, right = trees[4*j+a], trees[4*j+b]
            status = bytearray()
            native_sequences, sums = [], []
            for lrow, lbox in left:
                for rrow, rbox in right:
                    if classified % 64 == 0:
                        p.tick(deadline)
                    classified += 1
                    if lbox is None or rbox is None:
                        status.append(0)
                        continue
                    box = p.intersect(lbox, rbox)
                    if box is None:
                        status.append(1)
                        continue
                    status.append(2)
                    # Full lower-endpoint witness, checked against both paths.
                    point = [lo for lo, _ in box]
                    for row in (lrow, rrow):
                        for edge in row['edges']:
                            if ((point[edge['feature']] <= p.hx(edge['threshold']))
                                    != (edge['branch'] == 'L')):
                                raise ValueError('independent lower witness')
                            witness_checks += 1
                    values = (p.hx(lrow['value']), p.hx(rrow['value']))
                    native_sequences.append(values)
                    sums.append(F(values[0]) + F(values[1]))
                    feasible_total += 1
            if not sums:
                raise ValueError('nonempty D must reach a leaf pair')
            bounds = (min(sums), max(sums))
            pair_ranges.append(bounds)
            sequences.append(native_sequences)
            pair_rows.append({'stages': [4*j+a, 4*j+b],
                              'shape': [len(left), len(right)],
                              'status_hex': status.hex(),
                              'feasible': len(sums), 'real_sum': interval(bounds)})
        matching_rows, matching_bounds = [], []
        for a, b in MATCHINGS:
            summed = tuple(pair_ranges[a][k] + pair_ranges[b][k] for k in (0, 1))
            matching_bounds.append(summed)
            matching_rows.append({'pair_indices': [a, b], 'real_sum': interval(summed)})
        real = (max(z[0] for z in matching_bounds), min(z[1] for z in matching_bounds))
        if real[0] > real[1]:
            raise ValueError('empty real matching intersection')
        adjacent1 = p.propagate(*current, sequences[0])
        adjacent2 = p.propagate(*adjacent1, sequences[5])
        old_before = original
        original = p.propagate(*p.propagate(*original, sequences[0]), sequences[5])
        cartesian = current
        errors, allowance = [], F(0)
        for k in range(4):
            vals = [F(p.hx(row['value'])) for row, _ in trees[4*j+k]]
            pre = (cartesian[0] + min(vals), cartesian[1] + max(vals))
            magnitude = max(abs(x) for x in pre)
            delta = U * magnitude + HALF_ETA
            after = (p.directed(pre[0], False), p.directed(pre[1], True))
            errors.append({'stage': 4*j+k, 'incoming': interval(cartesian),
                           'pre_sum': interval(pre), 'magnitude': encoded(magnitude),
                           'delta': encoded(delta), 'outgoing': interval(after)})
            allowance += delta
            cartesian = after
        rounded = (p.directed(current[0] + real[0] - allowance, False),
                   p.directed(current[1] + real[1] + allowance, True))
        narrowed = (max(adjacent2[0], rounded[0]), min(adjacent2[1], rounded[1]))
        if not original[0] <= narrowed[0] <= narrowed[1] <= original[1]:
            raise ValueError('block nonloosening invariant')
        expected = {'block': j, 'stages': list(range(4*j, 4*j+4)),
                    'pairs': pair_rows, 'matchings': matching_rows,
                    'real_sum': interval(real), 'incoming': interval(current),
                    'adjacent_transfer': [interval(adjacent1), interval(adjacent2)],
                    'error_steps': errors, 'error_total': encoded(allowance),
                    'rounding_branch': interval(rounded), 'outgoing': interval(narrowed),
                    'original_incoming': interval(old_before),
                    'original_outgoing': interval(original)}
        p.exact_object(saved, expected)
        current = narrowed
    for key, bound in (('stage0', stage0), ('original_adjacent', original), ('final', current)):
        p.exact_object(certificate[key], {'lower': encoded(bound[0]),
                                       'upper': encoded(bound[1]),
                                       'B': encoded(p.structural(*bound))})
    if not (stage0[0] <= original[0] <= current[0] <= current[1] <= original[1] <= stage0[1]
            and p.structural(*current) <= p.structural(*original) <= p.structural(*stage0)):
        raise ValueError('final nested enclosures and B')
    counts = {'stages': 400, 'blocks': 100, 'paths': paths, 'path_edges': edges,
              'pair_classifications': classified, 'feasible_pairs': feasible_total}
    p.exact_object(certificate['counts'], counts)
    account = certificate['accounting']
    p.keys(account, ('measure', 'estimated_owned_bytes', 'source_bytes', 'input_bytes',
                     'array_bytes', 'path_limit', 'edge_limit', 'block_limit',
                     'classification_limit'))
    if account['measure'] != 'conservative_algorithm_owned_not_RSS':
        raise ValueError('producer accounting scope')
    for k in set(account) - {'measure'}:
        if type(account[k]) is not int or account[k] < 0:
            raise ValueError('producer accounting strict nonnegative integers')
    for k, v in (('array_bytes', array_bytes), ('path_limit', 6000),
                 ('edge_limit', 84000), ('block_limit', 100), ('classification_limit', 135000)):
        if account[k] != v:
            raise ValueError('producer accounting inventory')
    if (account['estimated_owned_bytes'] > 128 * 2**20
            or account['estimated_owned_bytes'] < array_bytes + account['source_bytes'] + account['input_bytes']):
        raise ValueError('producer accounting admission declaration')
    declared = (16 * 2**20 + 4 * account['source_bytes'] + 2 * account['input_bytes']
                + 6 * array_bytes + 1024 * 6000 + 512 * 84000
                + 262144 * 100 + 4 * 135000 + 4 * 2**20)
    if account['estimated_owned_bytes'] != declared:
        raise ValueError('independent producer accounting formula replay')
    p.tick(deadline)
    return {'status': 'PASS_INDEPENDENT_FOUR_TREE_MATCHING_REPLAY',
            'model_sha256': expected_model_sha, 'counts': counts,
            'stage0': certificate['stage0'], 'original_adjacent': certificate['original_adjacent'],
            'final': certificate['final'], 'branch_witness_checks': witness_checks,
            'checker_accounting': {'measure': 'conservative_algorithm_owned_not_RSS',
                                   'estimated_owned_bytes': estimate, 'limit_bytes': MEMORY_CAP},
            'producer_accounting_formula_checked_not_checker_memory_certificate': True,
            'input_byte_authentication_required_from_wrapper': True}
