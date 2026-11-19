# -*- coding: utf-8 -*-
"""增长中的 traceview 增量导出 / follow 单测。"""

from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from logel2txt.cli import follow_main, follow_once
from logel2txt.exporters import (
    PBS_HEADER_SIZE,
    PBS_MAGIC,
    PBS_REC_SIZE,
    append_data_lines,
    count_data_lines,
    detect_pbs_rec_size,
    export_traceview_incremental,
)
from logel2txt.format import HDR


def _build_pbs_record(
    sn: int,
    sub: int,
    tick_ms: int,
    core: int,
    strlen: int,
    stroff: int,
    *,
    rec_size: int = PBS_REC_SIZE,
) -> bytes:
    head = struct.pack("<IiIIiI", 1, sn, sub, tick_ms, core, 0)
    str_block = struct.pack("<HHIIII", 0, strlen, stroff, 0, 0, 0)
    if rec_size == 44:
        rec = head + str_block
    elif rec_size == 52:
        rec = head + str_block + (b"\0" * 8)
    elif rec_size == 76:
        rec = head + (b"\0" * 4) + str_block + (b"\0" * 28)
    else:
        raise ValueError(rec_size)
    assert len(rec) == rec_size
    return rec


def _pack_cache(root: Path, records: list, dat: bytes) -> tuple[Path, Path]:
    body = b"".join(records)
    pbs = PBS_MAGIC + b"\0" * (PBS_HEADER_SIZE - 4) + body
    dat_path = root / "traceview.dat"
    pbs_path = root / "traceview.pbs"
    dat_path.write_bytes(dat)
    pbs_path.write_bytes(pbs)
    return dat_path, pbs_path


class TestIncrementalExport(unittest.TestCase):
    def test_partial_pbs_tail_ignored(self):
        content = b"HELLO\0"
        rec = _build_pbs_record(1, 1, 100, 0, len(content), 0)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dat_path, pbs_path = _pack_cache(root, [rec], content)
            # 追加半截记录
            pbs_path.write_bytes(pbs_path.read_bytes() + b"\x00\x01\x02")
            self.assertEqual(
                detect_pbs_rec_size(pbs_path.read_bytes(), content, allow_partial=True),
                PBS_REC_SIZE,
            )
            slice_ = export_traceview_incremental(dat_path, pbs_path, 0)
            self.assertEqual(len(slice_.lines), 1)
            self.assertEqual(slice_.next_index, 1)
            self.assertTrue(slice_.lines[0].split("\t")[3].startswith("HELLO"))

    def test_incomplete_dat_string_waits(self):
        # PBS 指向 10 字节串，但 dat 只有 4 字节 → 不产出，next_index 不动
        rec = _build_pbs_record(1, 1, 100, 0, 10, 0)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dat_path, pbs_path = _pack_cache(root, [rec], b"ABCD")
            slice_ = export_traceview_incremental(dat_path, pbs_path, 0)
            self.assertEqual(slice_.lines, [])
            self.assertEqual(slice_.next_index, 0)
            # dat 补齐后再导
            dat_path.write_bytes(b"ABCDEFGHIJ")
            slice2 = export_traceview_incremental(
                dat_path, pbs_path, 0, start_index=0, rec_size=slice_.rec_size
            )
            self.assertEqual(len(slice2.lines), 1)
            self.assertEqual(slice2.next_index, 1)

    def test_start_index_skips_old(self):
        c1 = b"ONE\0"
        c2 = b"TWO\0"
        dat = c1 + c2
        r1 = _build_pbs_record(1, 1, 10, 0, len(c1), 0)
        r2 = _build_pbs_record(2, 1, 20, 0, len(c2), len(c1))
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dat_path, pbs_path = _pack_cache(root, [r1, r2], dat)
            slice_ = export_traceview_incremental(
                dat_path, pbs_path, 0, start_index=1
            )
            self.assertEqual(len(slice_.lines), 1)
            self.assertTrue(slice_.lines[0].split("\t")[3].startswith("TWO"))
            self.assertEqual(slice_.next_index, 2)

    def test_append_and_count_lines(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "live.txt"
            self.assertEqual(count_data_lines(out), 0)
            append_data_lines(out, ["row1\t..."], write_header=True)
            self.assertTrue(out.read_bytes().startswith(HDR.encode("latin-1")[:2]))
            self.assertEqual(count_data_lines(out), 1)
            append_data_lines(out, ["row2\t..."], write_header=False)
            self.assertEqual(count_data_lines(out), 2)


class TestFollowOnce(unittest.TestCase):
    def test_follow_once_appends_then_idempotent(self):
        content = b"LIVE\0"
        rec = _build_pbs_record(9, 1, 50, 1, len(content), 0)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cache = root / "sess"
            cache.mkdir()
            _pack_cache(cache, [rec], content)
            out = root / "live.txt"
            added, nxt, _rs, err = follow_once(cache, out, ue_base_ms=0)
            self.assertIsNone(err)
            self.assertEqual(added, 1)
            self.assertEqual(nxt, 1)
            self.assertEqual(count_data_lines(out), 1)
            added2, nxt2, _rs2, err2 = follow_once(
                cache, out, ue_base_ms=0, start_index=nxt
            )
            self.assertIsNone(err2)
            self.assertEqual(added2, 0)
            self.assertEqual(nxt2, 1)
            self.assertEqual(count_data_lines(out), 1)

    def test_follow_cli_once(self):
        content = b"CLI\0"
        rec = _build_pbs_record(3, 1, 1, 0, len(content), 0)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cache = root / "tv"
            cache.mkdir()
            _pack_cache(cache, [rec], content)
            out = root / "out.txt"
            rc = follow_main([str(cache), "-o", str(out), "--once"])
            self.assertEqual(rc, 0)
            self.assertEqual(count_data_lines(out), 1)


if __name__ == "__main__":
    unittest.main()
