# -*- coding: utf-8 -*-
"""从 traceview / logel 导出文本行，并写出文件。"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Iterable, List

from logel2txt.format import HDR, format_line

PBS_MAGIC = b"TIND"
PBS_HEADER_SIZE = 512
PBS_REC_SIZE = 44


def export_from_traceview(
    dat_path: Path,
    pbs_path: Path,
    ue_base_ms: int,
) -> List[str]:
    dat = dat_path.read_bytes()
    pbs = pbs_path.read_bytes()
    if pbs[:4] != PBS_MAGIC:
        raise ValueError(
            f"invalid traceview.pbs (magic={pbs[:4]!r}): {pbs_path}"
        )
    if len(pbs) < PBS_HEADER_SIZE + PBS_REC_SIZE:
        raise ValueError(f"traceview.pbs too small: {pbs_path}")

    n = (len(pbs) - PBS_HEADER_SIZE) // PBS_REC_SIZE
    lines = [HDR]
    for i in range(n):
        off = PBS_HEADER_SIZE + i * PBS_REC_SIZE
        rec = pbs[off : off + PBS_REC_SIZE]
        # seq, sn, sub, tick_ms, core, unk0, pad, strlen, stroff, unk1, unk2, unk3
        # seq(u32), sn(i32), sub(u32), tick_ms(u32), core(i32), unk0(u32)
        _seq, sn, sub, tick_ms, core, _unk0 = struct.unpack_from("<IiIIiI", rec, 0)
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
                    text = payload.decode("ascii", errors="replace")
                    lines.append(
                        format_line(last_sn, sub, 0, -1, text, "", ue_base_ms)
                    )
                    i = start + ln
                    continue
        i += 1
    return lines


def write_lines(path: Path, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # 与 Logel Export Trace 一致：CRLF 换行
    text = "\r\n".join(lines)
    if not text.endswith("\r\n"):
        text += "\r\n"
    path.write_bytes(text.encode("utf-8"))
