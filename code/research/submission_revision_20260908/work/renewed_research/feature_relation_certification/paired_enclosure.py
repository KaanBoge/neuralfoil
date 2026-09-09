"""Pure outward propagation through fixed compatible adjacent-stage blocks.

The caller must supply a complete superset of possible within-block sequences.
This arithmetic module does NOT establish tree-path compatibility or coverage.
"""
from fractions import Fraction
import math
import sys


def _binary64():
    info = sys.float_info
    if (info.radix, info.mant_dig, info.min_exp, info.max_exp) != (2, 53, -1021, 1024):
        raise RuntimeError("binary64 Python float required")


def _finite(value):
    if type(value) is not float or not math.isfinite(value):
        raise ValueError("finite builtin binary64 value required")
    return Fraction.from_float(value)


def _directed(value, upward):
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError("nonfinite directed enclosure") from exc
    if not math.isfinite(result):
        raise ValueError("nonfinite directed enclosure")
    represented = Fraction.from_float(result)
    if (upward and represented < value) or (not upward and represented > value):
        result = math.nextafter(result, math.inf if upward else -math.inf)
    if not math.isfinite(result):
        raise ValueError("nonfinite directed enclosure")
    represented = Fraction.from_float(result)
    if (upward and represented < value) or (not upward and represented > value):
        raise ValueError("failed directed enclosure")
    return represented


def enclose(initial, blocks):
    """Enclose unchanged ordered addition, preserving within-block compatibility.

    Up to 200 blocks, at most 225 supplied sequences per block, and one or two
    finite leaf values per sequence. Empty blocks are invalid here: an empty
    geometric domain belongs to the future path-checker's separate contract.
    Returned endpoints are exact Fractions representing binary64 values.
    """
    _binary64()
    lo = hi = _finite(initial)
    if not isinstance(blocks, (list, tuple)) or not 1 <= len(blocks) <= 200:
        raise ValueError("one to two hundred explicit blocks required")
    stage_count = 0
    for block in blocks:
        if not isinstance(block, (list, tuple)) or not 1 <= len(block) <= 225:
            raise ValueError("bounded nonempty sequence collection required")
        lengths = []
        lower, upper = [], []
        for sequence in block:
            if not isinstance(sequence, (list, tuple)) or len(sequence) not in (1, 2):
                raise ValueError("one or two ordered values required")
            lengths.append(len(sequence))
            a, b = lo, hi
            for value in sequence:
                rational = _finite(value)
                a = _directed(a + rational, False)
                b = _directed(b + rational, True)
            lower.append(a)
            upper.append(b)
        if len(set(lengths)) != 1:
            raise ValueError("all sequences in a block require the same length")
        lo, hi = min(lower), max(upper)
        stage_count += lengths[0]
    return {"lower": lo, "upper": hi, "stages": stage_count, "blocks": len(blocks)}
