# -*- coding: utf-8 -*-
"""format 模块单测。"""

from __future__ import annotations

import argparse
import unittest

from logel2txt.format import (
    format_core,
    format_hms_ms,
    format_line,
    format_sn,
    parse_hms_ms,
)


class TestParseHmsMs(unittest.TestCase):
    def test_full(self):
        self.assertEqual(parse_hms_ms("17:15:12.275"), 62112275)

    def test_short_ms_padded(self):
        self.assertEqual(parse_hms_ms("0:00:00.27"), 270)
        self.assertEqual(parse_hms_ms("0:00:00.2"), 200)

    def test_invalid(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            parse_hms_ms("bad")
        with self.assertRaises(argparse.ArgumentTypeError):
            parse_hms_ms("17:15:12")


class TestFormatHmsMs(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(format_hms_ms(0), "0:00:00.000")

    def test_negative_clamped(self):
        self.assertEqual(format_hms_ms(-1), "0:00:00.000")

    def test_roundtrip_sample(self):
        ms = parse_hms_ms("1:02:03.004")
        self.assertEqual(format_hms_ms(ms), "1:02:03.004")


class TestFormatLine(unittest.TestCase):
    def test_columns_and_tabs(self):
        line = format_line(10, 1, 1500, 2, "hello", "mod", 0)
        parts = line.split("\t")
        self.assertGreaterEqual(len(parts), 6)
        self.assertEqual(format_sn(10, 1), "10-1")
        self.assertTrue(parts[0].startswith("10-1"))
        self.assertIn("0:00:01.500", parts[1])
        self.assertEqual(parts[2].strip(), "2")
        self.assertTrue(parts[3].startswith("hello"))
        self.assertIn("0:00:01.500", parts[5])

    def test_core_negative(self):
        self.assertEqual(format_core(-1), "--")
        line = format_line(1, 0, 0, -1, "x", "", 0)
        self.assertEqual(line.split("\t")[2].strip(), "--")


if __name__ == "__main__":
    unittest.main()
