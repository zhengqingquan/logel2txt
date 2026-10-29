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
from logel2txt.playback import (
    DEFAULT_LOGEL,
    ensure_playback_cache,
    resolve_logel_file,
)


def _err(msg: str) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr)


def _warn(msg: str) -> None:
    print(f"[WARN] {msg}", file=sys.stderr)


def _info(msg: str) -> None:
    print(f"[INFO] {msg}")


def _done(msg: str) -> None:
    print(f"[DONE] {msg}")


def run_export(
    input_path: Path,
    output: Optional[Path] = None,
    ue_base_ms: Optional[int] = None,
    ext: str = "txt",
) -> int:
    """Export from an already-resolved input path. Shared by export and playback."""
    try:
        mode, payload = resolve_inputs(input_path)
    except FileNotFoundError as e:
        _err(str(e) if str(e) else f"input path not found: {input_path}")
        return 1
    except OSError as e:
        _err(f"cannot access input {input_path}: {type(e).__name__}: {e}")
        return 1

    ue_base = ue_base_ms if ue_base_ms is not None else 0
    out = output
    if out is None:
        out = default_output_path(input_path, mode, payload)
        if ext == "trace" and out.suffix.lower() != ".trace":
            out = out.with_suffix(".trace")
    try:
        out = out.expanduser().resolve()
    except OSError as e:
        _err(f"invalid output path {out}: {type(e).__name__}: {e}")
        return 1

    try:
        if mode == "trace_copy":
            src: Path = payload  # type: ignore
            try:
                data = src.read_bytes()
            except OSError as e:
                _err(f"failed to read {src}: {type(e).__name__}: {e}")
                return 2
            try:
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(data)
            except OSError as e:
                _err(f"failed to write {out}: {type(e).__name__}: {e}")
                return 2
            _done(f"Copied {src} -> {out} ({len(data)} bytes)")
            return 0

        if mode == "traceview":
            dat, pbs = payload  # type: ignore
            parent_name = dat.parent.name
            _info(f"Using traceview: {parent_name}")
            _info(f"  dat: {dat}")
            _info(f"  pbs: {pbs}")
            if "_pb" not in parent_name.lower():
                _warn(
                    f"traceview is not under a *_pb directory ({parent_name}); "
                    "export may be incomplete vs Logel Export Trace. "
                    "Open the log in Logel to build *_pb, then export again."
                )
            lines = export_from_traceview(dat, pbs, ue_base)
            note = "full decode (traceview)"
            incomplete = "_pb" not in parent_name.lower()
        else:
            logel: Path = payload  # type: ignore
            _warn(
                f"No traceview found; plaintext extract from logel: {logel}\n"
                "       Open the log in Logel first (to create *_pb / replay "
                "cache), then export again."
            )
            lines = export_from_logel_raw(logel, ue_base)
            note = "plaintext extract (incomplete)"
            incomplete = True

        write_lines(out, lines)
        data_lines = len(lines) - 1
        size = out.stat().st_size
        _done(note)
        print(f"       lines: {data_lines}")
        print(f"       output: {out}")
        print(f"       size: {size / (1024 * 1024):.2f} MB")
        if ue_base_ms is None:
            print(
                "       note: --ue-base not set; UE Time starts at 0:00:00.000; "
                "use e.g. --ue-base 17:15:12.275 to align with device clock"
            )
        if data_lines <= 0:
            _warn(
                "no data rows exported (header only); "
                "check input or open the log in Logel to build traceview."
            )
            return 2
        if incomplete:
            _warn(
                "export finished but may be incomplete; "
                "prefer *_pb\\traceview for Export Trace alignment."
            )
        return 0
    except Exception as e:
        _err(f"{type(e).__name__}: {e} (output={out})")
        return 2


def export_main(argv: Optional[List[str]] = None) -> int:
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
    return run_export(
        args.input,
        output=args.output,
        ue_base_ms=args.ue_base,
        ext=args.ext,
    )


def playback_main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="logel2txt playback",
        description=(
            "Logel CLI playback -> *_pb/traceview -> export "
            "(Export Trace text). Prefer Logel_R9.21.1403."
        ),
    )
    ap.add_argument(
        "input",
        type=Path,
        help="armlog directory or .logel file",
    )
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="output .txt",
    )
    ap.add_argument(
        "--ue-base",
        type=parse_hms_ms,
        default=None,
        help="UE start HH:MM:SS.mmm (optional)",
    )
    ap.add_argument(
        "--logel",
        type=Path,
        default=None,
        help=f"Logel.exe path (default: {DEFAULT_LOGEL} or LOGEL_EXE)",
    )
    ap.add_argument(
        "--no-hide",
        action="store_true",
        help="show Logel window during playback",
    )
    ap.add_argument(
        "--skip-playback",
        action="store_true",
        help="only export (assume *_pb already exists)",
    )
    args = ap.parse_args(argv)

    try:
        logel_file = resolve_logel_file(args.input)
    except FileNotFoundError as e:
        _err(str(e))
        return 1

    if not args.skip_playback:
        try:
            ensure_playback_cache(
                logel_file,
                logel=args.logel,
                hide=not args.no_hide,
            )
        except FileNotFoundError as e:
            _err(str(e))
            # missing Logel.exe -> 1; missing pb after playback -> 2
            msg = str(e).lower()
            if "logel.exe not found" in msg:
                return 1
            return 2

    return run_export(
        logel_file.parent,
        output=args.output,
        ue_base_ms=args.ue_base,
    )


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "playback":
        return playback_main(argv[1:])
    return export_main(argv)
