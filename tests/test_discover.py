# -*- coding: utf-8 -*-
"""discover 模块单测。"""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from logel2txt.discover import (
    default_output_path,
    find_logel,
    find_traceview_pair,
    resolve_inputs,
)
from logel2txt.exporters import PBS_HEADER_SIZE, PBS_MAGIC, PBS_REC_SIZE


def _touch_traceview(dir_path: Path, dat_size: int = 100) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "traceview.dat").write_bytes(b"x" * dat_size)
    (dir_path / "traceview.pbs").write_bytes(
        PBS_MAGIC + b"\0" * (PBS_HEADER_SIZE + PBS_REC_SIZE - 4)
    )


class TestDiscover(unittest.TestCase):
    def test_prefer_pb(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _touch_traceview(root / "plain", dat_size=200)
            _touch_traceview(root / "sample_pb", dat_size=50)
            pair = find_traceview_pair(root)
            self.assertIsNotNone(pair)
            dat, _ = pair
            self.assertEqual(dat.parent.name, "sample_pb")

    def test_prefer_exact_pb_over_pb1(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _touch_traceview(root / "sample_pb1", dat_size=500)
            _touch_traceview(root / "sample_pb", dat_size=50)
            err = io.StringIO()
            with redirect_stderr(err):
                pair = find_traceview_pair(root)
            self.assertIsNotNone(pair)
            dat, _ = pair
            self.assertEqual(dat.parent.name, "sample_pb")
            self.assertIn("multiple traceview", err.getvalue())
            self.assertIn("--traceview", err.getvalue())

    def test_traceview_prefer_name(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _touch_traceview(root / "sample_pb", dat_size=50)
            _touch_traceview(root / "sample_pb1", dat_size=500)
            pair = find_traceview_pair(root, prefer="sample_pb1")
            self.assertIsNotNone(pair)
            self.assertEqual(pair[0].parent.name, "sample_pb1")
            mode, payload = resolve_inputs(root, prefer_traceview="sample_pb1")
            self.assertEqual(mode, "traceview")
            self.assertEqual(payload[0].parent.name, "sample_pb1")

    def test_traceview_prefer_missing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _touch_traceview(root / "sample_pb")
            with self.assertRaises(FileNotFoundError) as cm:
                find_traceview_pair(root, prefer="no_such_pb")
            self.assertIn("--traceview", str(cm.exception))
            self.assertIn("sample_pb", str(cm.exception))

    def test_resolve_logel_only(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            logel = root / "a.logel"
            logel.write_bytes(b"dummy")
            mode, payload = resolve_inputs(root)
            self.assertEqual(mode, "logel")
            self.assertEqual(payload, logel.resolve())

    def test_resolve_traceview_over_logel(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.logel").write_bytes(b"dummy")
            _touch_traceview(root / "x_pb")
            mode, payload = resolve_inputs(root)
            self.assertEqual(mode, "traceview")
            dat, pbs = payload
            self.assertEqual(dat.parent.name, "x_pb")
            self.assertTrue(pbs.is_file())

    def test_find_logel_largest(self):
        import io
        from contextlib import redirect_stderr

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            small = root / "small.logel"
            big = root / "big.logel"
            small.write_bytes(b"a")
            big.write_bytes(b"bbbb")
            err = io.StringIO()
            with redirect_stderr(err):
                self.assertEqual(find_logel(root), big)
            self.assertIn("multiple .logel", err.getvalue())
            self.assertIn(str(small), err.getvalue())

    def test_default_output_traceview(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pb = root / "foo_pb"
            _touch_traceview(pb)
            dat = pb / "traceview.dat"
            out = default_output_path(root, "traceview", (dat, pb / "traceview.pbs"))
            self.assertEqual(out, root / "foo_pb.txt")


if __name__ == "__main__":
    unittest.main()
