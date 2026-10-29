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
    IncompatibleLogelError,
    LogelNotConfiguredError,
    check_cli_compatible,
    cli_pbs_status,
    expect_pb_dir,
    find_logel,
    list_logel_under_root,
    parse_logel_version,
    resolve_logel_file,
    run_logel_playback,
)


def _write_traceview(pb_dir: Path, dat_size: int = 64) -> None:
    pb_dir.mkdir(parents=True, exist_ok=True)
    (pb_dir / "traceview.dat").write_bytes(b"x" * dat_size)
    (pb_dir / "traceview.pbs").write_bytes(
        PBS_MAGIC + b"\0" * (PBS_HEADER_SIZE + PBS_REC_SIZE - 4)
    )


def _fake_install(root: Path, name: str) -> Path:
    home = root / name
    exe = home / "Bin" / "Logel.exe"
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_bytes(b"mz")
    return exe


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

    def test_resolve_logel_file_multiple_warns(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            a = root / "pkg_a"
            b = root / "pkg_b"
            a.mkdir()
            b.mkdir()
            la = a / "a.logel"
            lb = b / "b.logel"
            la.write_bytes(b"xx")
            lb.write_bytes(b"yy")
            err = io.StringIO()
            with redirect_stderr(err):
                chosen = resolve_logel_file(root)
            # sorted by path name: pkg_a/a.logel first
            self.assertEqual(chosen, la.resolve())
            err_s = err.getvalue()
            self.assertIn("[WARN]", err_s)
            self.assertIn("multiple .logel", err_s)
            self.assertIn(str(lb), err_s)

    def test_expect_pb_dir(self):
        p = Path(r"D:\work\logs\sample.logel")
        self.assertEqual(
            expect_pb_dir(p),
            Path(r"D:\work\logs\sample_pb").resolve(),
        )

    def test_parse_and_cli_status(self):
        p21 = Path(r"X:\tools\Logel_R9.21.1403\Bin\Logel.exe")
        p25 = Path(r"X:\tools\Logel_R9.25.1801\Bin\Logel.exe")
        p26 = Path(r"X:\tools\Logel_R9.26.3802\Bin\Logel.exe")
        self.assertEqual(parse_logel_version(p21), (9, 21, 1403))
        self.assertEqual(cli_pbs_status(p21), "compatible")
        self.assertEqual(cli_pbs_status(p25), "incompatible")
        self.assertEqual(cli_pbs_status(p26), "incompatible")
        check_cli_compatible(p21)
        with self.assertRaises(IncompatibleLogelError) as cm:
            check_cli_compatible(p26)
        self.assertIn("R9.26", str(cm.exception))
        self.assertIn("R9.21", str(cm.exception))

    def test_find_logel_requires_config(self):
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("LOGEL_EXE", None)
            os.environ.pop("LOGEL_HOME", None)
            os.environ.pop("LOGEL_ROOT", None)
            with self.assertRaises(LogelNotConfiguredError) as cm:
                find_logel(None)
            self.assertIn("--logel", str(cm.exception))

    def test_find_logel_root_prefers_r921(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _fake_install(root, "Logel_R9.26.3802")
            exe21 = _fake_install(root, "Logel_R9.21.1403")
            _fake_install(root, "Logel_R9.25.1801")
            with patch.dict("os.environ", {}, clear=False):
                import os

                os.environ.pop("LOGEL_EXE", None)
                os.environ.pop("LOGEL_HOME", None)
                os.environ.pop("LOGEL_ROOT", None)
                self.assertEqual(find_logel(None, root=root), exe21.resolve())

    def test_list_logel_under_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            e1 = _fake_install(root, "Logel_R9.21.1403")
            e2 = _fake_install(root, "Logel_R9.26.3802")
            found = list_logel_under_root(root)
            self.assertEqual(set(found), {e1.resolve(), e2.resolve()})

    def test_find_logel_root_only_incompatible(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _fake_install(root, "Logel_R9.25.1801")
            with self.assertRaises(IncompatibleLogelError) as cm:
                find_logel(None, root=root)
            self.assertIn("R9.21", str(cm.exception))

    def test_find_logel_env_dir_unknown_warns(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            (home / "Logel.exe").write_bytes(b"mz")
            err = io.StringIO()
            with patch.dict("os.environ", {"LOGEL_HOME": str(home)}, clear=False):
                import os

                os.environ.pop("LOGEL_EXE", None)
                with redirect_stderr(err):
                    self.assertEqual(find_logel(None), home / "Logel.exe")
            self.assertIn("[WARN]", err.getvalue())

    def test_find_logel_explicit_r926_refused(self):
        p = Path(r"X:\tools\Logel_R9.26.3802\Bin\Logel.exe")
        with self.assertRaises(IncompatibleLogelError):
            find_logel(p)

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
        text = out.getvalue().lower()
        self.assertIn("playback", text)
        self.assertIn("logel-root", text)

    def test_missing_config(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.logel").write_bytes(b"xx")
            out = root / "out.txt"
            err = io.StringIO()
            with patch.dict("os.environ", {}, clear=False):
                import os

                os.environ.pop("LOGEL_EXE", None)
                os.environ.pop("LOGEL_HOME", None)
                os.environ.pop("LOGEL_ROOT", None)
                with redirect_stderr(err), redirect_stdout(io.StringIO()):
                    code = main(
                        ["playback", str(root), "-o", str(out)]
                    )
            self.assertEqual(code, 1)
            self.assertIn("[ERROR]", err.getvalue())
            self.assertIn("--logel", err.getvalue())

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

    def test_playback_refuses_r926(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.logel").write_bytes(b"xx")
            out = root / "out.txt"
            bad = Path(r"X:\tools\Logel_R9.26.3802\Bin\Logel.exe")
            err = io.StringIO()
            with redirect_stderr(err), redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "playback",
                        str(root),
                        "-o",
                        str(out),
                        "--logel",
                        str(bad),
                    ]
                )
            self.assertEqual(code, 1)
            err_s = err.getvalue()
            self.assertIn("[ERROR]", err_s)
            self.assertIn("cannot parse", err_s.lower())
            self.assertIn("R9.21", err_s)

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

    def test_logel_root_cli(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tools = root / "tools"
            exe = _fake_install(tools, "Logel_R9.21.1403")
            (root / "a.logel").write_bytes(b"xx")
            out = root / "out.txt"
            pb = root / "a_pb"
            mock_run = MagicMock(
                side_effect=lambda *a, **k: (
                    _write_traceview(pb),
                    MagicMock(returncode=0),
                )[1]
            )
            buf = io.StringIO()
            err = io.StringIO()
            with patch("logel2txt.playback.subprocess.run", mock_run):
                with redirect_stderr(err), redirect_stdout(buf):
                    code = main(
                        [
                            "playback",
                            str(root),
                            "-o",
                            str(out),
                            "--logel-root",
                            str(tools),
                        ]
                    )
            self.assertEqual(code, 0)
            args = mock_run.call_args[0][0]
            self.assertEqual(args[0], str(exe.resolve()))


if __name__ == "__main__":
    unittest.main()
