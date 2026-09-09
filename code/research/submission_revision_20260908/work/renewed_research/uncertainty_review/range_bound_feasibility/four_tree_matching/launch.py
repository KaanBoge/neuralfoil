"""Root-owned bounded console capture for one explicitly approved phase.

No scientific imports, model reads, local log files or automatic retries.
The phase's own immutable writer controls its64MiB local output. This separate
capture limits combined stdout/stderr to64KiB and the complete child to900seconds.
"""
import argparse
import os
import selectors
import signal
import subprocess
import sys
import time

CAP = 65536


def captured(command, seconds=900, limit=CAP):
    start = time.monotonic()
    child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             start_new_session=True)
    selector = selectors.DefaultSelector()
    selector.register(child.stdout, selectors.EVENT_READ, 'stdout')
    selector.register(child.stderr, selectors.EVENT_READ, 'stderr')
    saved = {'stdout': bytearray(), 'stderr': bytearray()}
    size = 0
    try:
        while selector.get_map() or child.poll() is None:
            if time.monotonic()-start >= seconds:
                raise TimeoutError('root complete phase deadline')
            for key, _ in selector.select(.05):
                chunk = os.read(key.fd, 8192)
                if not chunk:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                    continue
                size += len(chunk)
                if size > limit:
                    raise RuntimeError('root bounded console capture exceeded')
                saved[key.data].extend(chunk)
        code = child.wait(timeout=max(.001, seconds-(time.monotonic()-start)))
        if time.monotonic()-start > seconds:
            raise TimeoutError('root post-exit deadline')
        return code, saved, time.monotonic()-start
    finally:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGKILL)
        child.wait(timeout=5)
        selector.close()
        for stream in (child.stdout, child.stderr):
            stream.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command:
        parser.error('explicit already-approved phase command required')
    code, output, elapsed = captured(args.command)
    sys.stdout.write(output['stdout'].decode('utf-8', errors='replace'))
    sys.stderr.write(output['stderr'].decode('utf-8', errors='replace'))
    sys.stderr.write('\nRoot bounded capture elapsed_seconds='+str(elapsed)+' exit_code='+str(code)+'\n')
    raise SystemExit(code)
