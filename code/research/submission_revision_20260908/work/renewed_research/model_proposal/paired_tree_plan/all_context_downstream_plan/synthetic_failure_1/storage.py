"""Explicit logical-byte guards. No imports or monkeypatches of scientific code."""
import hashlib
import json
import os
import stat
from pathlib import Path

CAP = 9 * 2**28
RESERVE = 2**20


def safe(path):
    p = Path(os.path.abspath(path))
    if any(ord(c) < 32 or ord(c) == 127 for c in str(p)):
        raise ValueError('control-character path')
    if any(x.is_symlink() for x in (p, *p.parents)):
        raise ValueError('symlink path')
    return p


def digest(path):
    h = hashlib.sha256()
    with safe(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


class Budget:
    def __init__(self, roots, destination, names, cap=CAP, reserve=RESERVE):
        self.roots = tuple(safe(p) for p in roots)
        if len(set(self.roots)) != len(self.roots) or any(
            x != y and x.is_relative_to(y) for x in self.roots for y in self.roots
        ):
            raise ValueError('overlapping roots')
        self.destination = safe(destination)
        if self.destination not in self.roots:
            raise ValueError('unregistered destination')
        self.names = frozenset(names)
        if any(Path(n).name != n or n in ('', '.', '..') for n in self.names):
            raise ValueError('noncanonical filename')
        if not 0 < reserve < cap:
            raise ValueError('budget parameters')
        self.cap, self.reserve = cap, reserve
        self.accepted = {}
        self.usage()

    def usage(self):
        total = 0
        def walk(p):
            nonlocal total
            mode = p.lstat().st_mode
            if stat.S_ISLNK(mode):
                raise ValueError('symlink output')
            if stat.S_ISREG(mode):
                total += p.stat().st_size  # Each hardlink pathname counts.
            elif stat.S_ISDIR(mode):
                for child in p.iterdir():
                    walk(child)
            else:
                raise ValueError('special output file')
        for root in self.roots:
            safe(root)
            if root.exists():
                if not root.is_dir():
                    raise ValueError('output root must be directory')
                walk(root)
        if total > self.cap:
            raise OSError('cumulative extension cap already exceeded')
        return total

    def check(self, growth=0, emergency=False):
        if type(growth) is not int or growth < 0:
            raise ValueError('growth')
        if self.usage() + growth > self.cap - (0 if emergency else self.reserve):
            raise OSError('pre-write cumulative extension cap')

    def target(self, path):
        p = safe(path)
        if p.parent != self.destination or p.name not in self.names:
            raise ValueError('unapproved output path')
        if p.exists():
            raise FileExistsError(p)
        return p

    def binary(self, path, emergency=False, expected=0):
        p = self.target(path)
        self.check(expected, emergency)
        return Binary(self, p, emergency)

    def accepted_file(self, path):
        p = safe(path)
        h = digest(p)
        if str(p) in self.accepted and self.accepted[str(p)] != h:
            raise ValueError('accepted file mutated')
        self.accepted[str(p)] = h
        self.check()
        return h

    def verify(self):
        self.check()
        for p, h in self.accepted.items():
            if digest(p) != h:
                raise ValueError('accepted file mutated')

    def bytes(self, path, raw, emergency=False):
        if type(raw) is not bytes:
            raise TypeError('bytes required')
        with self.binary(path, emergency, len(raw)) as stream:
            stream.write(raw)
        if emergency:
            self.usage()
            return digest(path)
        return self.accepted_file(path)

    def json(self, path, obj, emergency=False):
        raw = json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        return self.bytes(path, raw, emergency)

    def scalar(self, path, obj, codec):
        raw = (json.dumps(obj, default=codec.encode, indent=2, allow_nan=False) + '\n').encode()
        return self.bytes(path, raw)

    def npz(self, path, arrays):
        import numpy as np
        with self.binary(path) as stream:
            np.savez_compressed(stream, **arrays)
        return self.accepted_file(path)

    def csv(self, path, frame):
        with self.binary(path) as stream:
            frame.to_csv(Text(stream), index=False)
        return self.accepted_file(path)


class Binary:
    def __init__(self, budget, path, emergency):
        self.budget, self.path, self.emergency = budget, path, emergency
        self.file = path.open('xb', buffering=0)

    def write(self, raw):
        raw = memoryview(raw)
        size = os.fstat(self.file.fileno()).st_size
        growth = max(size, self.tell() + raw.nbytes) - size
        self.budget.check(growth, self.emergency)
        n = self.file.write(raw)
        if n != raw.nbytes:
            raise OSError('short write; partial output retained')
        return n

    def tell(self):
        return self.file.tell()

    def seek(self, offset, whence=0):
        size = os.fstat(self.file.fileno()).st_size
        if type(offset) is not int or whence not in (0, 1, 2):
            raise ValueError('seek arguments')
        position = offset + (0 if whence == 0 else self.tell() if whence == 1 else size)
        if not 0 <= position <= size:
            raise ValueError('seek outside existing extent')
        return self.file.seek(offset, whence)

    def flush(self):
        self.file.flush()

    def __enter__(self):
        return self

    def __exit__(self, typ, value, tb):
        try:
            if typ is None:
                self.flush()
                os.fsync(self.file.fileno())
        finally:
            self.file.close()


class Text:
    encoding = 'utf-8'
    def __init__(self, binary):
        self.binary = binary

    def write(self, text):
        self.binary.write(text.encode('utf-8'))
        return len(text)


def failure_payload(meta, exc, outputs, ledger):
    # Deliberately no unbounded repr(exc), full ledger or output inventory here.
    name = type(exc).__name__[:128]
    return dict(status='FAILED_STOP_NO_RETRY', phase=str(meta.get('phase', ''))[:32],
                error_type=name, detailed_error_not_serialized=True,
                successful_output_count=len(outputs), access_record_count=len(ledger),
                access_ledger_complete=False, partial_files_retained=True)

