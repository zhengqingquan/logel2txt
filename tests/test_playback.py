# -*- coding: utf-8 -*-
"""playback 子命令单元测试（不真跑 Logel）。"""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from logel2txt.cli import main
from logel2txt.exporters import PBS_HEADER_SIZE, PBS_MAGIC, PBS_REC_SIZE
from logel2txt.playback import (
    DEFAULT_LOGEL,
    expect_pb_dir,
    find_logel,
    resolve_logel_file,
    run_logel_playback,
)


def _write_traceview(pb_dir: Path, dat_size: int = 64) -> None:
    pb_dir.mkdir(parents=True, exist_ok=True)
    (pb_dir / "traceview.dat").write_bytes(b"x" * dat_size)
    (pb_dir / "traceview.pbs").write_bytes(
        PBS_MAGIC + b"\0" * (PBS_HEADER_SIZE + PBS_REC_SIZE - 4)
    )


class TestPlaybackHelpers(unittest.TestCase):
    def test_resolve_logel_file_from_dir(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            logel = root / "a.logel"
            logel.write_bytes(b"xx")
            self.assertEqual(resolve_logel_file(root), logel.resolve())

    def test_resolve_logel_file_missing(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):
                resolve_logel_file(Path(td))

    def test_expect_pb_dir(self):
        p = Path(r"D:\work\logs\sample.logel")
        self.assertEqual(
            expect_pb_dir(p),
            Path(r"D:\work\logs\sample_pb").resolve(),
        )

    def test_find_logel_default(self):
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("LOGEL_EXE", None)
            os.environ.pop("LOGEL_HOME", None)
            self.assertEqual(find_logel(None), DEFAULT_LOGEL)

    def test_find_logel_env_dir(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            with patch.dict("os.environ", {"LOGEL_HOME": str(home)}):
                self.assertEqual(find_logel(None), home / "Logel.exe")

    def test_run_logel_playback_builds_args(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            logel_exe = root / "Logel.exe"
            logel_exe.write_bytes(b"mz")
            logel_file = root / "x.logel"
            logel_file.write_bytes(b"xx")
            mock_run = MagicMock(return_value=MagicMock(returncode=0))
            with patch("logel2txt.playback.subprocess.run", mock_run):
                code = run_logel_playback(logel_exe, logel_file, hide=True)
            self.assertEqual(code, 0)
            args = mock_run.call_args[0][0]
            self.assertEqual(args[0], str(logel_exe))
            self.assertIn("-f", args)
            self.assertIn(str(logel_file), args)
            self.assertIn("-q", args)
            self.assertEqual(args[args.index("-w") + 1], "hide")


class TestPlaybackCli(unittest.TestCase):
    def test_playback_help(self):
        err = io.StringIO()
        out = io.StringIO()
        with redirect_stderr(err), redirect_stdout(out):
            with self.assertRaises(SystemExit) as cm:
                main(["playback", "-h"])
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("playback", out.getvalue().lower())

    def test_missing_logel_exe(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.logel").write_bytes(b"xx")
            out = root / "out.txt"
            missing = root / "no_such_Logel.exe"
            err = io.StringIO()
            with redirect_stderr(err), redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "playback",
                        str(root),
                        "-o",
                        str(out),
                        "--logel",
                        str(missing),
                    ]
                )
            self.assertEqual(code, 1)
            self.assertIn("[ERROR]", err.getvalue())
            self.assertIn("Logel.exe not found", err.getvalue())

    def test_playback_missing_pb_after_run(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            logel_exe = root / "Logel.exe"
            logel_exe.write_bytes(b"mz")
            (root / "a.logel").write_bytes(b"xx")
            out = root / "out.txt"
            mock_run = MagicMock(return_value=MagicMock(returncode=0))
            err = io.StringIO()
            with patch("logel2txt.playback.subprocess.run", mock_run):
                with redirect_stderr(err), redirect_stdout(io.StringIO()):
                    code = main(
                        [
                            "playback",
                            str(root),
                            "-o",
                            str(out),
                            "--logel",
                            str(logel_exe),
                        ]
                    )
            self.assertEqual(code, 2)
            self.assertIn("missing", err.getvalue().lower())

    def test_skip_playback_exports(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.logel").write_bytes(b"xx")
            _write_traceview(root / "a_pb")
            out = root / "out.txt"
            err = io.StringIO()
            buf = io.StringIO()
            with redirect_stderr(err), redirect_stdout(buf):
                code = main(
                    [
                        "playback",
                        str(root),
                        "-o",
                        str(out),
                        "--skip-playback",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertTrue(out.is_file())
            self.assertIn("[DONE]", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
