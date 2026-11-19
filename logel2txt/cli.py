# -*- coding: utf-8 -*-
"""命令行入口。"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

from logel2txt import __version__
from logel2txt.archive import ArchiveError, prepare_input
from logel2txt.capture_info import (
    LstMeta,
    format_capture_info,
    inspect_capture_info,
)
from logel2txt.discover import default_output_path, resolve_inputs
from logel2txt.exporters import (
    append_data_lines,
    count_data_lines,
    export_from_logel_raw,
    export_from_traceview,
    export_traceview_incremental,
    write_lines,
)
from logel2txt.format import parse_hms_ms
from logel2txt.playback import (
    IncompatibleLogelError,
    LogelNotConfiguredError,
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
    prefer_traceview: Optional[str] = None,
) -> int:
    """Export from an already-resolved input path. Shared by export and playback."""
    try:
        mode, payload = resolve_inputs(
            input_path, prefer_traceview=prefer_traceview
        )
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
        help=(
            "armlog directory, .logel, .zip/.rar/.7z, "
            "or a directory containing traceview.dat/pbs"
        ),
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
    ap.add_argument(
        "--7z",
        dest="seven_zip",
        type=Path,
        default=None,
        help="7z.exe for .rar/.7z (or SEVEN_ZIP / 7Z_EXE / PATH)",
    )
    ap.add_argument(
        "--extract-to",
        type=Path,
        default=None,
        help="directory to extract archive into (default: <archive_stem> beside it)",
    )
    ap.add_argument(
        "--force-extract",
        action="store_true",
        help="re-extract archive even if extract dir already has .logel",
    )
    ap.add_argument(
        "--traceview",
        default=None,
        metavar="NAME",
        help=(
            "which traceview cache to use when several exist: "
            "cache dir name (e.g. xxx_pb1) or path to that folder"
        ),
    )
    args = ap.parse_args(argv)
    try:
        input_path = prepare_input(
            args.input,
            seven_zip=args.seven_zip,
            extract_to=args.extract_to,
            force_extract=args.force_extract,
        )
    except ArchiveError as e:
        _err(str(e))
        return 1
    except FileNotFoundError as e:
        _err(str(e))
        return 1
    return run_export(
        input_path,
        output=args.output,
        ue_base_ms=args.ue_base,
        ext=args.ext,
        prefer_traceview=args.traceview,
    )


def playback_main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="logel2txt playback",
        description=(
            "Logel CLI playback -> *_pb/traceview -> export "
            "(Export Trace text). Requires --logel / LOGEL_EXE / "
            "--logel-root / LOGEL_ROOT (no built-in default). "
            "Supports Logel R9.21–R9.26 CLI PBS (44/52/76B records)."
        ),
    )
    ap.add_argument(
        "input",
        type=Path,
        help="armlog directory, .logel, or .zip/.rar/.7z archive",
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
        help="Logel.exe or install dir (R9.21–R9.26); or set LOGEL_EXE",
    )
    ap.add_argument(
        "--logel-root",
        type=Path,
        default=None,
        help=(
            "scan ROOT\\Logel_R* and ROOT\\Logel\\Bin, prefer R9.21 then newer; "
            "or set LOGEL_ROOT"
        ),
    )
    ap.add_argument(
        "--7z",
        dest="seven_zip",
        type=Path,
        default=None,
        help="7z.exe for .rar/.7z (or SEVEN_ZIP / 7Z_EXE / PATH)",
    )
    ap.add_argument(
        "--extract-to",
        type=Path,
        default=None,
        help="directory to extract archive into (default: <archive_stem> beside it)",
    )
    ap.add_argument(
        "--force-extract",
        action="store_true",
        help="re-extract archive even if extract dir already has .logel",
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
    ap.add_argument(
        "--traceview",
        default=None,
        metavar="NAME",
        help=(
            "which traceview cache to export when several exist: "
            "cache dir name (e.g. xxx_pb1) or path; "
            "with playback default remains the new *_pb"
        ),
    )
    args = ap.parse_args(argv)

    try:
        input_path = prepare_input(
            args.input,
            seven_zip=args.seven_zip,
            extract_to=args.extract_to,
            force_extract=args.force_extract,
        )
        logel_file = resolve_logel_file(input_path)
    except ArchiveError as e:
        _err(str(e))
        return 1
    except FileNotFoundError as e:
        _err(str(e))
        return 1

    if not args.skip_playback:
        try:
            ensure_playback_cache(
                logel_file,
                logel=args.logel,
                logel_root=args.logel_root,
                hide=not args.no_hide,
            )
        except IncompatibleLogelError as e:
            _err(str(e))
            return 1
        except (LogelNotConfiguredError, FileNotFoundError) as e:
            _err(str(e))
            msg = str(e).lower()
            if "missing" in msg and "traceview" in msg:
                return 2
            return 1

    # After playback, default to the fresh *_pb unless user overrides.
    prefer = args.traceview
    if prefer is None and not args.skip_playback:
        prefer = f"{logel_file.stem}_pb"
        _info(f"export will prefer playback cache: {prefer}")

    return run_export(
        logel_file.parent,
        output=args.output,
        ue_base_ms=args.ue_base,
        prefer_traceview=prefer,
    )


def _resolve_follow_traceview(
    input_path: Path,
    prefer_traceview: Optional[str],
) -> Tuple[Optional[Path], Optional[Path], Optional[str]]:
    """返回 (dat, pbs, err)。暂无缓存时 err 为提示且 dat/pbs 为 None。"""
    try:
        mode, payload = resolve_inputs(
            input_path, prefer_traceview=prefer_traceview
        )
    except FileNotFoundError as e:
        return None, None, str(e) if str(e) else f"input path not found: {input_path}"
    except OSError as e:
        return None, None, f"cannot access input {input_path}: {type(e).__name__}: {e}"
    if mode != "traceview":
        return None, None, "no traceview cache yet (still waiting for Logel decode cache)"
    dat, pbs = payload  # type: ignore
    return dat, pbs, None


def follow_once(
    input_path: Path,
    output: Path,
    *,
    ue_base_ms: int = 0,
    prefer_traceview: Optional[str] = None,
    start_index: Optional[int] = None,
    rec_size: Optional[int] = None,
    to_stdout: bool = False,
) -> Tuple[int, int, Optional[int], Optional[str]]:
    """跑一轮增量追加。

    返回 ``(added, next_index, rec_size, error)``；``error`` 非空表示本轮跳过/失败
    （调用方决定是否继续轮询）。
    """
    dat, pbs, err = _resolve_follow_traceview(input_path, prefer_traceview)
    if err or dat is None or pbs is None:
        return 0, start_index or 0, rec_size, err

    if start_index is None:
        if to_stdout:
            start_index = 0
        else:
            start_index = count_data_lines(output)

    try:
        slice_ = export_traceview_incremental(
            dat,
            pbs,
            ue_base_ms,
            start_index=start_index,
            rec_size=rec_size,
            enrich_from_siblings=False,
        )
    except (OSError, ValueError) as e:
        return 0, start_index, rec_size, f"{type(e).__name__}: {e}"

    if not slice_.lines:
        return 0, slice_.next_index, slice_.rec_size or rec_size, None

    if to_stdout:
        for line in slice_.lines:
            sys.stdout.write(line + "\n")
        sys.stdout.flush()
    else:
        write_header = not output.is_file() or output.stat().st_size == 0
        try:
            append_data_lines(output, slice_.lines, write_header=write_header)
        except OSError as e:
            return 0, start_index, slice_.rec_size or rec_size, f"{type(e).__name__}: {e}"

    return len(slice_.lines), slice_.next_index, slice_.rec_size, None


def follow_main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="logel2txt follow",
        description=(
            "Follow a growing plain traceview cache and append decoded lines "
            "(for live capture). Tolerates trailing incomplete .pbs/.dat records. "
            "Not Export Trace-complete; use normal export/playback after capture stops."
        ),
    )
    ap.add_argument(
        "input",
        type=Path,
        help="armlog directory, .logel, or directory containing traceview.dat/pbs",
    )
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="append-only live txt (default: <input>/live.txt when input is a dir)",
    )
    ap.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="poll seconds between incremental reads (default: 2)",
    )
    ap.add_argument(
        "--once",
        action="store_true",
        help="run one incremental pass then exit (for external pollers like lcapt)",
    )
    ap.add_argument(
        "--stdout",
        action="store_true",
        help="print new data lines to stdout instead of appending a file",
    )
    ap.add_argument(
        "--ue-base",
        type=parse_hms_ms,
        default=None,
        help="UE start time HH:MM:SS.mmm (default 0)",
    )
    ap.add_argument(
        "--from-index",
        type=int,
        default=None,
        help="start PBS record index (default: resume from existing -o data lines)",
    )
    ap.add_argument(
        "--traceview",
        default=None,
        metavar="NAME",
        help="which traceview cache to follow when several exist",
    )
    ap.add_argument(
        "--7z",
        dest="seven_zip",
        type=Path,
        default=None,
        help="7z.exe for .rar/.7z archives",
    )
    ap.add_argument(
        "--extract-to",
        type=Path,
        default=None,
        help="directory to extract archive into",
    )
    ap.add_argument(
        "--force-extract",
        action="store_true",
        help="re-extract archive even if extract dir already has .logel",
    )
    args = ap.parse_args(argv)

    try:
        input_path = prepare_input(
            args.input,
            seven_zip=args.seven_zip,
            extract_to=args.extract_to,
            force_extract=args.force_extract,
        )
    except ArchiveError as e:
        _err(str(e))
        return 1
    except FileNotFoundError as e:
        _err(str(e))
        return 1

    out = args.output
    if out is None and not args.stdout:
        if input_path.is_dir():
            out = input_path / "live.txt"
        else:
            out = input_path.parent / "live.txt"
    if out is not None:
        try:
            out = out.expanduser().resolve()
        except OSError as e:
            _err(f"invalid output path {out}: {type(e).__name__}: {e}")
            return 1

    ue_base = args.ue_base if args.ue_base is not None else 0
    interval = max(0.2, float(args.interval))
    start_index = args.from_index
    rec_size: Optional[int] = None
    total_added = 0

    if not args.stdout and out is not None:
        _info(f"follow live txt: {out}")

    def _one_pass() -> Tuple[int, Optional[str]]:
        nonlocal start_index, rec_size, total_added
        added, next_index, new_rec, err = follow_once(
            input_path,
            out if out is not None else Path("."),
            ue_base_ms=ue_base,
            prefer_traceview=args.traceview,
            start_index=start_index,
            rec_size=rec_size,
            to_stdout=bool(args.stdout),
        )
        if err:
            # 缓存尚未出现 / 读锁冲突：跳过本轮，保留 start_index 以便续传
            return 0, err
        if added:
            total_added += added
            if not args.stdout:
                _info(f"+{added} lines (total {total_added}, next_index={next_index})")
        start_index = next_index
        if new_rec:
            rec_size = new_rec
        return added, None

    if args.once:
        _added, err = _one_pass()
        if err:
            _warn(err)
        print(f"       lines: {total_added}")
        print(f"       next_index: {start_index if start_index is not None else 0}")
        if out is not None and not args.stdout:
            print(f"       output: {out}")
        return 0

    try:
        while True:
            _one_pass()
            time.sleep(interval)
    except KeyboardInterrupt:
        _done(f"follow stopped; appended {total_added} lines")
        print(f"       lines: {total_added}")
        print(f"       next_index: {start_index if start_index is not None else 0}")
        if out is not None and not args.stdout:
            print(f"       output: {out}")
        return 0


def info_main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="logel2txt info",
        description=(
            "Show which Logel Tool Version captured the log "
            "(from *.lst next to .logel). Also lists replay *_pb*.lst if present."
        ),
    )
    ap.add_argument(
        "input",
        type=Path,
        help="armlog directory, .logel, .lst, or .zip/.rar/.7z archive",
    )
    ap.add_argument(
        "--7z",
        dest="seven_zip",
        type=Path,
        default=None,
        help="7z.exe for .rar/.7z (or SEVEN_ZIP / 7Z_EXE / PATH)",
    )
    ap.add_argument(
        "--extract-to",
        type=Path,
        default=None,
        help="directory to extract archive into (default: <archive_stem> beside it)",
    )
    ap.add_argument(
        "--force-extract",
        action="store_true",
        help="re-extract archive even if extract dir already has .logel",
    )
    args = ap.parse_args(argv)

    try:
        input_path = prepare_input(
            args.input,
            seven_zip=args.seven_zip,
            extract_to=args.extract_to,
            force_extract=args.force_extract,
        )
    except ArchiveError as e:
        _err(str(e))
        return 1
    except FileNotFoundError as e:
        _err(str(e))
        return 1

    logel_stem = None
    try:
        if input_path.is_file() and input_path.suffix.lower() == ".logel":
            logel_stem = input_path.stem
        elif input_path.is_file() and input_path.suffix.lower() == ".lst":
            logel_stem = LstMeta(path=input_path).capture_stem
        elif input_path.is_dir():
            logel_stem = resolve_logel_file(input_path).stem
    except FileNotFoundError:
        logel_stem = None

    try:
        info = inspect_capture_info(input_path, logel_stem=logel_stem)
    except OSError as e:
        _err(f"cannot read lst under {input_path}: {type(e).__name__}: {e}")
        return 1

    print(format_capture_info(info))
    if info.tool_version:
        return 0
    if info.capture is not None:
        _warn(
            "capture .lst has no Tool Version field; "
            "cannot determine which Logel captured this log."
        )
    elif info.replays:
        _warn(
            "no capture .lst (only *_pb*.lst replay summaries); "
            "those Tool Versions are from later open/playback, not capture."
        )
    else:
        _warn(
            "no *.lst with Tool Version found; "
            "capture tool version unknown for this input."
        )
    return 2


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "playback":
        return playback_main(argv[1:])
    if argv and argv[0] == "info":
        return info_main(argv[1:])
    if argv and argv[0] == "follow":
        return follow_main(argv[1:])
    return export_main(argv)
