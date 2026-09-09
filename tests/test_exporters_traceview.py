# -*- coding: utf-8 -*-
"""traceview 导出单测（伪造最小 dat/pbs）。"""

from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from logel2txt.exporters import (
    PBS_HEADER_SIZE,
    PBS_MAGIC,
    PBS_REC_SIZE,
    export_from_traceview,
)
from logel2txt.format import format_hms_ms


def _build_pbs_record(
    sn: int,
    sub: int,
    tick_ms: int,
    core: int,
    strlen: int,
    stroff: int,
) -> bytes:
    # <IiIIiI at 0, <HHIIII at 24
    head = struct.pack(
        "<IiIIiI",
        1,  # seq
        sn,
        sub,
        tick_ms,
        core,
        0,  # unk0
    )
    tail = struct.pack(
        "<HHIIII",
        0,  # pad
        strlen,
        stroff,
        0,
        0,
        0,
    )
    rec = head + tail
    assert len(rec) == PBS_REC_SIZE
    return rec


class TestExportFromTraceview(unittest.TestCase):
    def test_one_record(self):
        content = b"TRACE_HELLO\0"
        dat = content
        stroff = 0
        strlen = len(content)
        sn, sub, tick_ms, core = 42, 3, 2500, 1
        rec = _build_pbs_record(sn, sub, tick_ms, core, strlen, stroff)
        pbs = PBS_MAGIC + b"\0" * (PBS_HEADER_SIZE - 4) + rec

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dat_path = root / "traceview.dat"
            pbs_path = root / "traceview.pbs"
            dat_path.write_bytes(dat)
            pbs_path.write_bytes(pbs)

            ue_base = 17 * 3600 * 1000  # 17:00:00.000
            lines = export_from_traceview(dat_path, pbs_path, ue_base)

        self.assertEqual(len(lines), 2)  # HDR + 1
        data = lines[1]
        parts = data.split("\t")
        self.assertTrue(parts[0].startswith("42-3"))
        self.assertIn(format_hms_ms(ue_base + tick_ms), parts[1])
        self.assertEqual(parts[2].strip(), "1")
        self.assertTrue(parts[3].startswith("TRACE_HELLO"))
        self.assertIn(format_hms_ms(tick_ms), parts[5])

    def test_bad_magic(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dat_path = root / "traceview.dat"
            pbs_path = root / "traceview.pbs"
            dat_path.write_bytes(b"x")
            pbs_path.write_bytes(b"XXXX" + b"\0" * (PBS_HEADER_SIZE + PBS_REC_SIZE))
            with self.assertRaises(ValueError):
                export_from_traceview(dat_path, pbs_path, 0)


if __name__ == "__main__":
    unittest.main()
