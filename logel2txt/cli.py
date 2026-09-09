# -*- coding: utf-8 -*-
"""命令行入口。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from logel2txt import __version__
from logel2txt.discover import default_output_path, resolve_inputs
from logel2txt.exporters import (
    export_from_logel_raw,
    export_from_traceview,
    write_lines,
)
from logel2txt.format import parse_hms_ms


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Export ArmLogel/Logel ARM logs to txt (Export Trace-aligned format)"
        )
    )
    ap.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"logel2txt {__version__}",
    )
    ap.add_argument(
        "input",
        type=Path,
        help="armlog directory, .logel, or a directory containing traceview.dat/pbs",
    )
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="output path (default: .txt next to the input)",
    )
    ap.add_argument(
        "--ue-base",
        type=parse_hms_ms,
        default=None,
        help=(
            "UE start time HH:MM:SS.mmm "
            "(default 0: UE Time shares TickCount origin)"
        ),
    )
    ap.add_argument(
        "--ext",
        choices=("txt", "trace"),
        default="txt",
        help="default extension when -o is omitted (default: txt)",
    )
    args = ap.parse_args(argv)

    try:
        mode, payload = resolve_inputs(args.input)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    ue_base = args.ue_base if args.ue_base is not None else 0
    out = args.output
    if out is None:
        out = default_output_path(args.input, mode, payload)
        if args.ext == "trace" and out.suffix.lower() != ".trace":
            out = out.with_suffix(".trace")

    try:
        if mode == "trace_copy":
            src: Path = payload  # type: ignore
            data = src.read_bytes()
            out.write_bytes(data)
            print(f"[DONE] Copied {src} -> {out} ({len(data)} bytes)")
            return 0

        if mode == "traceview":
            dat, pbs = payload  # type: ignore
            print(f"[INFO] Using traceview: {dat.parent.name}")
            lines = export_from_traceview(dat, pbs, ue_base)
            note = "full decode (traceview)"
        else:
            logel: Path = payload  # type: ignore
            print(
                f"[WARN] No traceview found; plaintext extract from logel: "
                f"{logel.name}\n"
                "       Open the log in Logel first (to create *_pb / replay "
                "cache), then export again."
            )
            lines = export_from_logel_raw(logel, ue_base)
            note = "plaintext extract (incomplete)"

        write_lines(out, lines)
        data_lines = len(lines) - 1
        size = out.stat().st_size
        print(f"[DONE] {note}")
        print(f"       lines: {data_lines}")
        print(f"       output: {out}")
        print(f"       size: {size / (1024 * 1024):.2f} MB")
        if args.ue_base is None:
            print(
                "       note: --ue-base not set; UE Time starts at 0:00:00.000; "
                "use e.g. --ue-base 17:15:12.275 to align with device clock"
            )
        return 0
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 2
