"""Independent full-cover and reachable-path certificate replay (no engine import)."""
from fractions import Fraction
import math
import sys
import time


def full_cover(checkpoint, dimensions=62):
    """Reconstruct exact binary partition; do not trust serialized box claims."""
    if set(checkpoint) != {'frontier', 'trace', 'lower', 'upper', 'splits'}:
        raise ValueError('checkpoint schema')
    if type(checkpoint['splits']) is not int or checkpoint['splits'] != len(checkpoint['trace']) or not 0 <= checkpoint['splits'] <= 128:
        raise ValueError('split count')
    boxes = {0: ((-sys.float_info.max, sys.float_info.max),)*dimensions}
    for k, event in enumerate(checkpoint['trace']):
        if set(event) != {'parent', 'feature', 'threshold', 'children'}:
            raise ValueError('partition event schema')
        p, f, t = event['parent'], event['feature'], event['threshold']
        if type(p) is not int or p not in boxes or type(f) is not int or not 0 <= f < dimensions or type(t) is not float or not math.isfinite(t):
            raise ValueError('partition event')
        children = event['children']
        if children != [2*k+1, 2*k+2] or any(type(c) is not int for c in children):
            raise ValueError('fresh child identities')
        box = boxes[p]
        lo, hi = box[f]
        right = math.nextafter(t, math.inf)
        if not lo <= t < hi or not math.isfinite(right) or not lo < right <= hi:
            raise ValueError('split fails exact finite-domain partition')
        left_box, right_box = list(box), list(box)
        left_box[f] = (lo, t)
        right_box[f] = (right, hi)
        del boxes[p]
        boxes[children[0]], boxes[children[1]] = tuple(left_box), tuple(right_box)
    rows = checkpoint['frontier']
    if len(rows) != len(boxes):
        raise ValueError('frontier count')
    seen = set()
    for row in rows:
        if set(row) != {'id', 'box', 'lower', 'upper', 'cuts'} or type(row['id']) is not int or row['id'] in seen or row['id'] not in boxes:
            raise ValueError('frontier schema or duplicate')
        seen.add(row['id'])
        b = row['box']
        if len(b) != dimensions or any(len(pair) != 2 or any(type(v) is not float or not math.isfinite(v) for v in pair) for pair in b):
            raise ValueError('box numeric schema')
        if tuple(tuple(pair) for pair in b) != boxes[row['id']]:
            raise ValueError('box is not reconstructed full-cover leaf')
    return boxes


def replay(checkpoint, stages, initial, enclosure, dimensions=62, deadline=None):
    boxes = full_cover(checkpoint, dimensions)
    visits = 0
    bounds = []
    for row in checkpoint['frontier']:
        box = boxes[row['id']]
        values = []
        for tree in stages:
            leaves = []
            # Separate implementation: accumulated lower/upper constraints,
            # traversing a node only after checking all path intersections.
            todo = [(0, {}, {})]
            while todo:
                if deadline is not None and time.monotonic() >= deadline:
                    raise TimeoutError('independent replay deadline')
                j, lower, upper = todo.pop()
                visits += 1
                if any(max(box[f][0], lower.get(f, -math.inf)) > min(box[f][1], upper.get(f, math.inf)) for f in lower.keys() | upper.keys()):
                    continue
                node = tree[j]
                if node['is_leaf']:
                    leaves.append(float(node['value']))
                else:
                    f, t = int(node['feature_idx']), float(node['num_threshold'])
                    u = dict(upper)
                    u[f] = min(u.get(f, math.inf), t)
                    l = dict(lower)
                    l[f] = max(l.get(f, -math.inf), math.nextafter(t, math.inf))
                    todo.append((int(node['left']), dict(lower), u))
                    todo.append((int(node['right']), l, dict(upper)))
            if not leaves:
                raise ValueError('no reachable leaves')
            values.append(leaves)
        result = enclosure(initial, values)
        lo, hi = Fraction(result['lower']), Fraction(result['upper'])
        if lo != Fraction(row['lower']) or hi != Fraction(row['upper']):
            raise ValueError('fresh outward enclosure mismatch')
        bounds.append((lo, hi))
    lo, hi = min(v[0] for v in bounds), max(v[1] for v in bounds)
    if lo != Fraction(checkpoint['lower']) or hi != Fraction(checkpoint['upper']):
        raise ValueError('global enclosure mismatch')
    return {'status': 'PASS_FULL_DOMAIN_REPLAY', 'lower': str(lo), 'upper': str(hi),
            'boxes': len(boxes), 'splits': checkpoint['splits'], 'replay_node_visits': visits}
