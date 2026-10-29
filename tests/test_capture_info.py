# -*- coding: utf-8 -*-
"""capture_info / info 子命令单测。"""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from logel2txt.capture_info import (
    format_capture_info,
    inspect_capture_info,
    parse_lst_text,
)
from logel2txt.cli import main


_SAMPLE_CAPTURE = """Start Logging[LittleEndian]
Modem Version:
ParserLib Version: FM_BASE_20A_THIN_MODEM_MP_RL_W23.41.1
Tool Version: R9.23.1102.0
Stop Logging
"""

_SAMPLE_REPLAY = """Start Logging[LittleEndian]
Modem Version:
ParserLib Version: FM_BASE_W20.21.2
Tool Version: R9.26.3802.0
"""


class TestCaptureInfo(unittest.TestCase):
    def test_parse_lst_text(self):
        m = parse_lst_text(_SAMPLE_CAPTURE, path=Path("x.lst"))
        self.assertEqual(m.tool_version, "R9.23.1102.0")
        self.assertIn("FM_BASE_20A", m.parser_lib_version or "")
        self.assertFalse(m.is_replay)

    def test_inspect_prefers_capture_lst(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stem = "2026_10_26_14_35_51_673"
            (root / f"{stem}.lst").write_text(_SAMPLE_CAPTURE, encoding="ascii")
            (root / f"{stem}_pb.lst").write_text(_SAMPLE_REPLAY, encoding="ascii")
            (root / f"{stem}_pb1.lst").write_text(_SAMPLE_REPLAY, encoding="ascii")
            (root / f"{stem}.logel").write_bytes(b"xx")

            info = inspect_capture_info(root, logel_stem=stem)
            self.assertEqual(info.tool_version, "R9.23.1102.0")
            self.assertIsNotNone(info.capture)
            self.assertEqual(info.capture.path.name, f"{stem}.lst")
            self.assertEqual(len(info.replays), 2)
            self.assertTrue(all(r.tool_version == "R9.26.3802.0" for r in info.replays))

            text = format_capture_info(info)
            self.assertIn("capture Tool Version: R9.23.1102.0", text)
            self.assertIn("replay .lst", text)
            self.assertIn(f"{stem}_pb.lst", text)

    def test_info_cli(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stem = "sample"
            (root / f"{stem}.lst").write_text(_SAMPLE_CAPTURE, encoding="ascii")
            (root / f"{stem}.logel").write_bytes(b"xx")
            out = io.StringIO()
            err = io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = main(["info", str(root)])
            self.assertEqual(code, 0)
            self.assertIn("R9.23.1102.0", out.getvalue())

    def test_info_cli_missing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.logel").write_bytes(b"xx")
            out = io.StringIO()
            with redirect_stdout(out), redirect_stderr(io.StringIO()):
                code = main(["info", str(root)])
            self.assertEqual(code, 2)
            self.assertIn("no capture", out.getvalue().lower())


if __name__ == "__main__":
    unittest.main()
