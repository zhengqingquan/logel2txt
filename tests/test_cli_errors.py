# -*- coding: utf-8 -*-
"""CLI error-path logging tests."""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from logel2txt.cli import main
from logel2txt.exporters import PBS_HEADER_SIZE, PBS_MAGIC, PBS_REC_SIZE


def _touch_traceview(dir_path: Path, dat_size: int = 64) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "traceview.dat").write_bytes(b"x" * dat_size)
    (dir_path / "traceview.pbs").write_bytes(
        PBS_MAGIC + b"\0" * (PBS_HEADER_SIZE + PBS_REC_SIZE - 4)
    )


class TestCliErrorPaths(unittest.TestCase):
    def test_missing_input(self):
        err = io.StringIO()
        with redirect_stderr(err):
            code = main([str(Path("E:/no_such_logel2txt_input_zzz"))])
        self.assertEqual(code, 1)
        self.assertIn("[ERROR]", err.getvalue())
        self.assertIn("input path not found", err.getvalue())

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as td:
            err = io.StringIO()
            with redirect_stderr(err):
                code = main([td])
            self.assertEqual(code, 1)
            self.assertIn("[ERROR]", err.getvalue())
            self.assertIn("no traceview.dat/pbs or .logel", err.getvalue())

    def test_logel_only_warns_on_stderr_and_zero_rows(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            logel = root / "a.logel"
            logel.write_bytes(b"xxxx")
            out = root / "out.txt"
            err = io.StringIO()
            out_buf = io.StringIO()
            with redirect_stderr(err), redirect_stdout(out_buf):
                code = main([str(root), "-o", str(out)])
            self.assertEqual(code, 2)
            err_s = err.getvalue()
            self.assertIn("[WARN]", err_s)
            self.assertIn("No traceview found", err_s)
            self.assertIn("no data rows exported", err_s)
            self.assertTrue(out.is_file())

    def test_non_pb_traceview_warns(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _touch_traceview(root / "plain")
            out = root / "out.txt"
            err = io.StringIO()
            out_buf = io.StringIO()
            with redirect_stderr(err), redirect_stdout(out_buf):
                code = main([str(root), "-o", str(out)])
            # one empty-ish record still counts as a data row
            err_s = err.getvalue()
            self.assertIn("[WARN]", err_s)
            self.assertIn("*_pb", err_s)
            self.assertIn("may be incomplete", err_s)
            self.assertIn(code, (0, 2))


if __name__ == "__main__":
    unittest.main()
