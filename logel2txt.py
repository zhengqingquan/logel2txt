#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
logel2txt — 将展锐 ArmLogel / Logel 抓取的 ARM 日志导出为文本（.txt / .trace）

优先使用 Logel 打开/回放后生成的 traceview.dat + traceview.pbs（完整解码，
含格式化 TRACE）；若只有 .logel，则尽力抽取明文字符串（不完整）。

用法:
  python logel2txt.py <armlog目录|.logel|含traceview的目录> [-o 输出.txt]
  python logel2txt.py D:\\logs\\xxx_armlog
  python logel2txt.py D:\\logs\\xxx_armlog\\xxx.logel -o out.txt
  python logel2txt.py D:\\logs\\xxx_armlog --ue-base 17:15:12.275
  python logel2txt.py --version

说明:
  - 若目录下存在 *_pb\\traceview.*（回放缓存），优先使用，结果最接近 Logel「Export Trace」
  - UE Time = ue_base + TickCount；可用 --ue-base 指定设备起始时刻，缺省为 00:00:00.000
"""

from __future__ import annotations

import argparse
import os
import re
import struct
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

__version__ = "0.1.0"

PBS_MAGIC = b"TIND"
PBS_HEADER_SIZE = 512
PBS_REC_SIZE = 44

# 与 Logel 导出列宽大致对齐（以 tab 分隔）
HDR = (
    f"{'SN':<12}\t{'UE Time':<12}\t{'CORE':<4}\t"
    f"{'Content':<160}\t{'Module':<64}\t{'TickCount':<13}\t"
)


def format_hms_ms(total_ms: int) -> str:
    if total_ms < 0:
        total_ms = 0
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h}:{m:02d}:{s:02d}.{ms:03d}"


def parse_hms_ms(text: str) -> int:
    """解析 HH:MM:SS.mmm 或 H:MM:SS.mmm → 毫秒。"""
    m = re.match(r"^(\d+):(\d+):(\d+)\.(\d+)$", text.strip())
    if not m:
        raise argparse.ArgumentTypeError(
            f"无效时间格式: {text!r}，期望如 17:15:12.275"
        )
    h, mi, s, ms = map(int, m.groups())
    if len(m.group(4)) != 3:
        # 允许 27 / 275 / 2 → 归一到毫秒
        ms = int(m.group(4).ljust(3, "0")[:3])
    return ((h * 60 + mi) * 60 + s) * 1000 + ms


def format_sn(sn: int, sub: int) -> str:
    return f"{sn}-{sub}"


def format_core(core: int) -> str:
    return "--" if core < 0 else str(core)


def format_line(
    sn: int,
    sub: int,
    tick_ms: int,
    core: int,
    content: str,
    module: str,
    ue_base_ms: int,
) -> str:
    ue = format_hms_ms(ue_base_ms + tick_ms)
    tick = format_hms_ms(tick_ms)
    sn_s = format_sn(sn, sub)
    core_s = format_core(core)
    # 与参考导出类似：字段定宽 + tab
    return (
        f"{sn_s:<12}\t{ue:<12}\t{core_s:<4}\t"
        f"{content:<160}\t{module:<64}\t{tick:<13}\t"
    )


def find_traceview_pair(root: Path) -> Optional[Tuple[Path, Path]]:
    """在目录树中查找 traceview.dat/.pbs，优先 *_pb。"""
    candidates: List[Tuple[int, Path, Path]] = []
    for dat in root.rglob("traceview.dat"):
        pbs = dat.with_suffix(".pbs")
        if not pbs.is_file():
            continue
        pri = 0 if "_pb" in dat.parent.name.lower() else 1
        candidates.append((pri, dat, pbs))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], -x[1].stat().st_size))
    _, dat, pbs = candidates[0]
    return dat, pbs


def find_logel(root: Path) -> Optional[Path]:
    logs = sorted(root.rglob("*.logel"), key=lambda p: -p.stat().st_size)
    return logs[0] if logs else None


def export_from_traceview(
    dat_path: Path,
    pbs_path: Path,
    ue_base_ms: int,
) -> List[str]:
    dat = dat_path.read_bytes()
    pbs = pbs_path.read_bytes()
    if pbs[:4] != PBS_MAGIC:
        raise ValueError(f"不是有效的 traceview.pbs (magic={pbs[:4]!r}): {pbs_path}")
    if len(pbs) < PBS_HEADER_SIZE + PBS_REC_SIZE:
        raise ValueError(f"traceview.pbs 过小: {pbs_path}")

    n = (len(pbs) - PBS_HEADER_SIZE) // PBS_REC_SIZE
    lines = [HDR]
    for i in range(n):
        off = PBS_HEADER_SIZE + i * PBS_REC_SIZE
        rec = pbs[off : off + PBS_REC_SIZE]
        # seq, sn, sub, tick_ms, core, unk0, pad, strlen, stroff, unk1, unk2, unk3
        # seq(u32), sn(i32), sub(u32), tick_ms(u32), core(i32), unk0(u32)
        seq, sn, sub, tick_ms, core, _unk0 = struct.unpack_from("<IiIIiI", rec, 0)
        _pad, strlen, stroff, _u1, _u2, _u3 = struct.unpack_from("<HHIIII", rec, 24)
        if stroff >= len(dat) or strlen == 0:
            content = ""
        else:
            raw = dat[stroff : stroff + strlen]
            content = raw.split(b"\0", 1)[0].decode("ascii", errors="replace")
        lines.append(
            format_line(sn, sub, tick_ms, core, content, "", ue_base_ms)
        )
    return lines


def export_from_logel_raw(logel_path: Path, ue_base_ms: int) -> List[str]:
    """无 traceview 时：从 .logel 抽取 0x9104 明文 TLV（不含需 DB 解码的格式化 TRACE）。"""
    data = logel_path.read_bytes()
    lines = [HDR]
    # 回溯找最近 SN：包头近似 u32,a / i32,sn / u16,a_lo / u16,plen / u16,pad
    last_sn = 0
    sub = 0
    i = 0
    idx = 0
    while i + 4 < len(data):
        if data[i] == 0x04 and data[i + 1] == 0x91:
            ln = struct.unpack_from("<H", data, i + 2)[0]
            start = i + 4
            if 2 <= ln <= 4096 and start + ln <= len(data):
                payload = data[start : start + ln]
                # 尝试在 payload 内取 C 字符串
                if 0 in payload:
                    payload = payload[: payload.index(0)]
                if len(payload) >= 4 and all(32 <= c <= 126 for c in payload):
                    # 向前窥探 SN
                    for back in range(4, 64):
                        p = i - back
                        if p < 0:
                            break
                        if p + 14 <= i:
                            a = struct.unpack_from("<I", data, p)[0]
                            sn = struct.unpack_from("<i", data, p + 4)[0]
                            a2 = struct.unpack_from("<H", data, p + 8)[0]
                            plen = struct.unpack_from("<H", data, p + 10)[0]
                            if a2 == (a & 0xFFFF) and 4 <= plen <= 2_000_000:
                                if sn != last_sn:
                                    last_sn = sn
                                    sub = 0
                                break
                    sub += 1
                    idx += 1
                    text = payload.decode("ascii", errors="replace")
                    lines.append(
                        format_line(last_sn, sub, 0, -1, text, "", ue_base_ms)
                    )
                    i = start + ln
                    continue
        i += 1
    return lines


def resolve_inputs(path: Path) -> Tuple[str, object]:
    """
    返回 (mode, payload)
    mode: 'traceview' | 'logel' | 'trace_copy'
    """
    path = path.resolve()
    if path.is_file():
        suf = path.suffix.lower()
        if suf == ".logel":
            # 同级或父目录找 traceview
            for root in {path.parent, path.parent.parent}:
                pair = find_traceview_pair(root)
                if pair:
                    return "traceview", pair
            return "logel", path
        if suf in (".trace", ".txt"):
            return "trace_copy", path
        raise FileNotFoundError(f"不支持的文件类型: {path}")

    if not path.is_dir():
        raise FileNotFoundError(path)

    pair = find_traceview_pair(path)
    if pair:
        return "traceview", pair
    logel = find_logel(path)
    if logel:
        return "logel", logel
    raise FileNotFoundError(
        f"未找到 traceview.dat/pbs 或 .logel: {path}\n"
        "提示: 先用 ArmLogel/Logel 打开该日志生成回放缓存后再导出，可得到完整解码。"
    )


def default_output_path(input_path: Path, mode: str, payload: object) -> Path:
    if mode == "traceview":
        dat, _ = payload  # type: ignore
        return dat.parent.parent / f"{dat.parent.name}.txt"
    if mode == "logel":
        p = payload  # type: ignore
        return p.with_suffix(".txt")
    p = payload  # type: ignore
    return p.with_suffix(".txt")


def write_lines(path: Path, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # 与 Logel Export Trace 一致：CRLF 换行
    text = "\r\n".join(lines)
    if not text.endswith("\r\n"):
        text += "\r\n"
    path.write_bytes(text.encode("utf-8"))


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


if __name__ == "__main__":
    sys.exit(main())
