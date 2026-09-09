"""Array-tree refinement with coherent immutable snapshots; no artifact I/O."""
from fractions import Fraction
import math
import sys
import time

MAX = sys.float_info.max


class Budget(Exception):
    pass


def owned_size(obj, seen=None):
    """Conservative Python/container/array estimate, NOT a process RSS limit."""
    seen = set() if seen is None else seen
    if id(obj) in seen:
        return 0
    seen.add(id(obj))
    n = sys.getsizeof(obj)
    if hasattr(obj, 'nbytes'):
        n += int(obj.nbytes)  # Deliberate conservative double count of owned arrays.
    if isinstance(obj, dict):
        n += sum(owned_size(k, seen) + owned_size(v, seen) for k, v in obj.items())
    elif isinstance(obj, (list, tuple, set, frozenset)):
        n += sum(owned_size(v, seen) for v in obj)
    elif isinstance(obj, Fraction):
        n += owned_size(obj.numerator, seen) + owned_size(obj.denominator, seen)
    return n


class Limits:
    def __init__(self, stages, seconds=120, visits=4000000, memory=128*1024*1024):
        self.deadline = time.monotonic() + seconds
        self.visits = 0
        self.max_visits = visits
        self.memory = memory
        self.stages = stages
        self.persistent = ()
        self.peak_estimate = 0

    def check(self, transient=(), visit=False):
        if visit:
            if self.visits >= self.max_visits:
                raise Budget('node visit budget')
            self.visits += 1
        if time.monotonic() >= self.deadline:
            raise Budget('search time budget')
        # Account full model, old snapshot, candidate state, traversal stacks,
        # value lists, and reserve 3x for copies/JSON serialization plus 8 MiB.
        estimate = 3 * owned_size((self.stages, self.persistent, transient)) + 8*1024*1024
        self.peak_estimate = max(self.peak_estimate, estimate)
        if estimate > self.memory:
            raise Budget('algorithm-owned allocation estimate budget')


def partition(box, feature, threshold):
    lo, hi = box[feature]
    a, b = min(hi, threshold), max(lo, math.nextafter(threshold, math.inf))
    def make(x, y):
        if x > y or not math.isfinite(x) or not math.isfinite(y):
            return None
        out = list(box)
        out[feature] = (x, y)
        return tuple(out)
    return make(lo, a), make(b, hi)


def bound(stages, initial, box, enclosure, limits):
    values = []
    cuts = set()
    for tree in stages:
        leaves = []
        stack = [(0, box)]
        while stack:
            limits.check((values, cuts, leaves, stack), visit=True)
            index, path = stack.pop()
            node = tree[index]
            if node['is_leaf']:
                leaves.append(float(node['value']))
                continue
            feature, threshold = int(node['feature_idx']), float(node['num_threshold'])
            left, right = partition(path, feature, threshold)
            if left is not None and right is not None:
                cuts.add((feature, threshold))
            if right is not None:
                stack.append((int(node['right']), right))
            if left is not None:
                stack.append((int(node['left']), left))
        if not leaves:
            raise ValueError('nonempty box without reachable leaf')
        values.append(leaves)
    limits.check((values, cuts))
    result = enclosure(initial, values)
    return {'box': box, 'lower': result['lower'], 'upper': result['upper'],
            'cuts': tuple(sorted(cuts))}


def snapshot(frontier, trace):
    return {'frontier': tuple(frontier), 'trace': tuple(trace),
            'lower': str(min(Fraction(x['lower']) for x in frontier)),
            'upper': str(max(Fraction(x['upper']) for x in frontier)),
            'splits': len(trace)}


def refine(stages, initial, enclosure, limits, publish, splits=128, dimensions=62):
    """Failure at any point leaves every previously published snapshot untouched."""
    first = bound(stages, initial, ((-MAX, MAX),)*dimensions, enclosure, limits)
    first['id'] = 0
    current = snapshot((first,), ())
    limits.persistent = current
    publish(current)
    for _ in range(splits):
        choices = [x for x in current['frontier'] if x['cuts']]
        if not choices:
            return current
        parent = min(choices, key=lambda x: (-(Fraction(x['upper'])-Fraction(x['lower'])), x['id']))
        feature, threshold = parent['cuts'][0]
        boxes = partition(parent['box'], feature, threshold)
        if any(b is None for b in boxes):
            raise ValueError('nonpartitioning frontier split')
        children = []
        for b in boxes:
            limits.persistent = (current, children)
            child = bound(stages, initial, b, enclosure, limits)
            if not Fraction(parent['lower']) <= Fraction(child['lower']) <= Fraction(child['upper']) <= Fraction(parent['upper']):
                raise ValueError('nonmonotone enclosure')
            child['id'] = 2*len(current['trace']) + 1 + len(children)
            children.append(child)
        trace = current['trace'] + ({'parent': parent['id'], 'feature': feature,
                                    'threshold': threshold, 'children': [c['id'] for c in children]},)
        frontier = tuple(x for x in current['frontier'] if x['id'] != parent['id']) + tuple(children)
        candidate = snapshot(frontier, trace)
        limits.check((candidate, children))
        # One reference assignment; no deletion from a live frontier ever occurs.
        current = candidate
        limits.persistent = current
        if current['splits'] in (1, 4, 16, 64, 128):
            publish(current)
    return current
