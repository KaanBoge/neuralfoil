"""Tiny printing subprocesses only; no scientific execution."""
import sys
import unittest
import launch


class Tests(unittest.TestCase):
    def test_exact_capture(self):
        code, output, elapsed = launch.captured([sys.executable, '-B', '-c',
            "import sys;print('one');print('two',file=sys.stderr)"], seconds=5)
        self.assertEqual(code, 0)
        self.assertEqual(output, {'stdout': b'one\n', 'stderr': b'two\n'})
        self.assertLess(elapsed, 5)

    def test_nonzero_status_preserved(self):
        code, output, _ = launch.captured([sys.executable, '-B', '-c', 'raise SystemExit(3)'], seconds=5)
        self.assertEqual(code, 3)

    def test_capture_cap_rejects(self):
        with self.assertRaisesRegex(RuntimeError, 'capture exceeded'):
            launch.captured([sys.executable, '-B', '-c', "print('x'*1000)"], seconds=5, limit=100)

    def test_deadline_rejects_owned_child(self):
        with self.assertRaises(TimeoutError):
            launch.captured([sys.executable, '-B', '-c', 'import time;time.sleep(1)'], seconds=.02)


if __name__ == '__main__':
    unittest.main()
