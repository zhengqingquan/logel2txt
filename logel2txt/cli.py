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
        description="导出 ArmLogel/Logel ARM 日志为 txt（对齐 Export Trace 格式）"
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
        help="armlog 目录、.logel，或已含 traceview.dat/pbs 的目录",
    )
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="输出文件路径（默认写到输入旁 .txt）",
    )
    ap.add_argument(
        "--ue-base",
        type=parse_hms_ms,
        default=None,
        help="UE 起始时刻 HH:MM:SS.mmm（默认 0，即 UE Time 与 TickCount 同起点）",
    )
    ap.add_argument(
        "--ext",
        choices=("txt", "trace"),
        default="txt",
        help="未指定 -o 时的默认扩展名（默认 txt）",
    )
    args = ap.parse_args(argv)

    try:
        mode, payload = resolve_inputs(args.input)
    except FileNotFoundError as e:
        print(f"[错误] {e}", file=sys.stderr)
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
            print(f"[完成] 已复制 {src} -> {out} ({len(data)} bytes)")
            return 0

        if mode == "traceview":
            dat, pbs = payload  # type: ignore
            print(f"[信息] 使用 traceview: {dat.parent.name}")
            lines = export_from_traceview(dat, pbs, ue_base)
            note = "完整解码（traceview）"
        else:
            logel: Path = payload  # type: ignore
            print(
                f"[警告] 未找到 traceview，仅从 logel 抽取明文: {logel.name}\n"
                "       建议先用 Logel 打开该日志（生成 *_pb 或回放目录）后再导出。"
            )
            lines = export_from_logel_raw(logel, ue_base)
            note = "明文抽取（不完整）"

        write_lines(out, lines)
        data_lines = len(lines) - 1
        size = out.stat().st_size
        print(f"[完成] {note}")
        print(f"       行数: {data_lines}")
        print(f"       输出: {out}")
        print(f"       大小: {size / (1024 * 1024):.2f} MB")
        if args.ue_base is None:
            print(
                "       提示: 未指定 --ue-base，UE Time 从 0:00:00.000 起算；"
                "若需对齐设备时钟可加如 --ue-base 17:15:12.275"
            )
        return 0
    except Exception as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 2
