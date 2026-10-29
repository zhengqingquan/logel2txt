# -*- coding: utf-8 -*-
"""archive extract unit tests."""

from __future__ import annotations

import io
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from logel2txt.archive import (
    ArchiveError,
    extract_archive,
    find_7z,
    is_archive,
    prepare_input,
)
from logel2txt.cli import main


class TestArchiveHelpers(unittest.TestCase):
    def test_is_archive(self):
        self.assertTrue(is_archive(Path("a.zip")))
        self.assertTrue(is_archive(Path("a.RAR")))
        self.assertFalse(is_archive(Path("a.logel")))

    def test_find_7z_missing(self):
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("SEVEN_ZIP", None)
            os.environ.pop("7Z_EXE", None)
            with patch("logel2txt.archive.shutil.which", return_value=None):
                with self.assertRaises(ArchiveError) as cm:
                    find_7z(None)
                self.assertIn("--7z", str(cm.exception))

    def test_find_7z_env(self):
        with tempfile.TemporaryDirectory() as td:
            exe = Path(td) / "7z.exe"
            exe.write_bytes(b"mz")
            with patch.dict("os.environ", {"SEVEN_ZIP": str(exe)}):
                self.assertEqual(find_7z(None), exe)

    def test_extract_zip_and_reuse(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            zpath = root / "sample_armlog.zip"
            # archive contains sample_armlog/x.logel
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("sample_armlog/x.logel", b"logel-bytes")
            err = io.StringIO()
            with redirect_stderr(err), redirect_stdout(io.StringIO()):
                out1 = extract_archive(zpath)
            self.assertTrue((out1 / "x.logel").is_file() or list(out1.rglob("*.logel")))
            with redirect_stderr(err), redirect_stdout(io.StringIO()):
                out2 = extract_archive(zpath)
            self.assertEqual(out1.resolve(), out2.resolve())
            self.assertIn("reuse", err.getvalue().lower())

    def test_prepare_input_passthrough_dir(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            self.assertEqual(prepare_input(p), p.resolve())

    def test_extract_to_custom_dir(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            zpath = root / "sample_armlog.zip"
            dest = root / "custom_out"
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("nested/x.logel", b"logel-bytes")
            with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                out = extract_archive(zpath, extract_to=dest)
            self.assertTrue(str(out).startswith(str(dest.resolve())))
            self.assertTrue(any(out.rglob("*.logel")))

    def test_extract_rar_calls_7z(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            rar = root / "pkg_armlog.rar"
            rar.write_bytes(b"Rar!")
            seven = root / "7z.exe"
            seven.write_bytes(b"mz")

            def fake_run(args, **kwargs):
                # simulate 7z writing nested folder with logel
                dest = Path(args[3][2:])  # -oDEST
                nested = dest / "pkg_armlog"
                nested.mkdir(parents=True, exist_ok=True)
                (nested / "a.logel").write_bytes(b"xx")
                return MagicMock(returncode=0, stdout="", stderr="")

            with patch("logel2txt.archive.subprocess.run", side_effect=fake_run):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    out = extract_archive(rar, seven_zip=seven)
            self.assertTrue((out / "a.logel").is_file())


class TestArchiveCli(unittest.TestCase):
    def test_export_from_zip(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            zpath = root / "pack_armlog.zip"
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("pack_armlog/only.logel", b"xxxx")
            out = root / "out.txt"
            err = io.StringIO()
            buf = io.StringIO()
            with redirect_stderr(err), redirect_stdout(buf):
                code = main([str(zpath), "-o", str(out)])
            # plaintext extract from tiny logel -> likely 0 rows / code 2
            self.assertIn(code, (0, 2))
            self.assertTrue(out.is_file() or "No traceview" in err.getvalue() or "[DONE]" in buf.getvalue() or "[WARN]" in err.getvalue())


if __name__ == "__main__":
    unittest.main()
