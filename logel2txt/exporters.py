# -*- coding: utf-8 -*-
"""从 traceview / logel 导出文本行，并写出文件。"""

from __future__ import annotations

import re
import struct
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from logel2txt.discover import sibling_traceview_pairs
from logel2txt.format import HDR, format_line

PBS_MAGIC = b"TIND"
PBS_HEADER_SIZE = 512
# Legacy alias: R9.21 / early GUI 44B/record
PBS_REC_SIZE = 44
# Known CLI/GUI index strides (body must divide evenly)
PBS_REC_SIZES = (44, 52, 76)

# (sn, sub, tick_ms) -> candidate Content strings from a cache
ContentIndex = Dict[Tuple[int, int, int], List[str]]

# CLI 回放偶发：大数经 double 打印后零填充（与 GUI Export 不一致）
_DEGRADED_EQ = re.compile(r"^=\d{10,20}0{16,}")
_DEGRADED_ZEROS = re.compile(r"^0{16,}.*\.0+$")


def _decode_content(raw: bytes) -> str:
    # latin-1 保留 0xFF 等字节，与 Logel Export Trace 一致
    return raw.split(b"\0", 1)[0].decode("latin-1", errors="replace")


def detect_pbs_rec_size(
    pbs: bytes, dat: Optional[bytes] = None
) -> int:
    """Detect PBS record stride: 44 (R9.21/R9.23), 52 (R9.25), 76 (R9.26)."""
    if len(pbs) < 4 or pbs[:4] != PBS_MAGIC:
        raise ValueError(f"invalid traceview.pbs magic={pbs[:4]!r}")
    if len(pbs) < PBS_HEADER_SIZE + min(PBS_REC_SIZES):
        raise ValueError("traceview.pbs too small")
    body = len(pbs) - PBS_HEADER_SIZE
    candidates = [s for s in PBS_REC_SIZES if body >= s and body % s == 0]
    if not candidates:
        raise ValueError(
            f"unsupported PBS layout (body={body} bytes; "
            f"expected multiple of {PBS_REC_SIZES})"
        )
    if len(candidates) == 1:
        return candidates[0]
    if dat is not None:
        return max(candidates, key=lambda s: _score_pbs_stride(pbs, dat, s))
    # Ambiguous without dat: prefer larger stride (avoids mis-splitting 76 as 44)
    return max(candidates)


def _score_pbs_stride(pbs: bytes, dat: bytes, stride: int) -> int:
    n = (len(pbs) - PBS_HEADER_SIZE) // stride
    checked = min(200, n)
    good = 0
    for i in range(checked):
        rec = pbs[PBS_HEADER_SIZE + i * stride : PBS_HEADER_SIZE + (i + 1) * stride]
        try:
            _sn, _sub, _tick, _core, strlen, stroff = _unpack_pbs_record(rec, stride)
        except struct.error:
            return 0
        if strlen == 0:
            continue
        if stroff < len(dat) and stroff + min(strlen, 1) <= len(dat):
            good += 1
    return good


def _unpack_pbs_record(
    rec: bytes, rec_size: int
) -> Tuple[int, int, int, int, int, int]:
    """Return sn, sub, tick_ms, core, strlen, stroff."""
    _seq, sn, sub, tick_ms, core, _unk0 = struct.unpack_from("<IiIIiI", rec, 0)
    # R9.26 (76B): 4-byte field inserted at offset 24; string block starts at 28.
    # R9.21/23 (44) and R9.25 (52=44+pad): string block at 24.
    field_off = 28 if rec_size >= 76 else 24
    _pad, strlen, stroff, _u1, _u2, _u3 = struct.unpack_from(
        "<HHIIII", rec, field_off
    )
    return sn, sub, tick_ms, core, strlen, stroff


def _content_richness(s: str) -> int:
    """Rough score: prefer non-zero digits; penalize long zero runs (float pad)."""
    t = s.rstrip()
    if not t:
        return 0
    nonzero = sum(1 for c in t if c.isdigit() and c != "0")
    penalty = sum(len(m.group(0)) for m in re.finditer(r"0{8,}", t))
    return nonzero * 10 - penalty


def looks_degraded_numeric(s: str) -> bool:
    t = s.rstrip()
    return bool(_DEGRADED_EQ.match(t) or _DEGRADED_ZEROS.match(t))


def _same_content_family(primary: str, other: str) -> bool:
    a, b = primary.rstrip(), other.rstrip()
    if not a or not b:
        return False
    if len(a) == len(b):
        return True
    if a.startswith("=") and b.startswith("="):
        return a[1:15] == b[1:15]
    n = min(12, len(a), len(b))
    return n >= 8 and a[:n] == b[:n]


def build_content_index(dat_path: Path, pbs_path: Path) -> ContentIndex:
    dat = dat_path.read_bytes()
    pbs = pbs_path.read_bytes()
    try:
        rec_size = detect_pbs_rec_size(pbs, dat)
    except ValueError:
        return {}
    n = (len(pbs) - PBS_HEADER_SIZE) // rec_size
    idx: ContentIndex = defaultdict(list)
    for i in range(n):
        off = PBS_HEADER_SIZE + i * rec_size
        rec = pbs[off : off + rec_size]
        sn, sub, tick_ms, _core, strlen, stroff = _unpack_pbs_record(rec, rec_size)
        if stroff >= len(dat) or strlen == 0:
            content = ""
        else:
            content = _decode_content(dat[stroff : stroff + strlen])
        idx[(sn, sub, tick_ms)].append(content)
    return idx


def enrich_content(
    sn: int,
    sub: int,
    tick_ms: int,
    content: str,
    alt_indexes: Sequence[ContentIndex],
) -> str:
    """If primary Content looks float-degraded, prefer richer sibling cache string."""
    if not alt_indexes or not looks_degraded_numeric(content):
        return content
    key = (sn, sub, tick_ms)
    best = content
    best_score = _content_richness(content)
    for index in alt_indexes:
        for cand in index.get(key, []):
            if not _same_content_family(content, cand):
                continue
            score = _content_richness(cand)
            if score > best_score:
                best, best_score = cand, score
    return best


def export_from_traceview(
    dat_path: Path,
    pbs_path: Path,
    ue_base_ms: int,
    *,
    enrich_from_siblings: bool = True,
) -> List[str]:
    try:
        dat = dat_path.read_bytes()
    except OSError as e:
        raise OSError(f"failed to read {dat_path}: {e}") from e
    try:
        pbs = pbs_path.read_bytes()
    except OSError as e:
        raise OSError(f"failed to read {pbs_path}: {e}") from e
    if len(pbs) < 4:
        raise ValueError(f"traceview.pbs too small: {pbs_path}")
    if pbs[:4] != PBS_MAGIC:
        raise ValueError(
            f"invalid traceview.pbs (magic={pbs[:4]!r}): {pbs_path}"
        )
    try:
        rec_size = detect_pbs_rec_size(pbs, dat)
    except ValueError as e:
        raise ValueError(f"{e}: {pbs_path}") from e

    alt_indexes: List[ContentIndex] = []
    if enrich_from_siblings:
        for alt_dat, alt_pbs in sibling_traceview_pairs(dat_path):
            try:
                alt_indexes.append(build_content_index(alt_dat, alt_pbs))
            except OSError:
                continue

    n = (len(pbs) - PBS_HEADER_SIZE) // rec_size
    lines = [HDR]
    for i in range(n):
        off = PBS_HEADER_SIZE + i * rec_size
        rec = pbs[off : off + rec_size]
        sn, sub, tick_ms, core, strlen, stroff = _unpack_pbs_record(rec, rec_size)
        if stroff >= len(dat) or strlen == 0:
            content = ""
        else:
            content = _decode_content(dat[stroff : stroff + strlen])
        if alt_indexes:
            content = enrich_content(sn, sub, tick_ms, content, alt_indexes)
        lines.append(
            format_line(sn, sub, tick_ms, core, content, "", ue_base_ms)
        )
    return lines


def export_from_logel_raw(logel_path: Path, ue_base_ms: int) -> List[str]:
    """无 traceview 时：从 .logel 抽取 0x9104 明文 TLV（不含需 DB 解码的格式化 TRACE）。"""
    try:
        data = logel_path.read_bytes()
    except OSError as e:
        raise OSError(f"failed to read {logel_path}: {e}") from e
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
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # 与 Logel Export Trace 一致：CRLF；latin-1 写出以保留 Content 中的 0xFF 等字节
        text = "\r\n".join(lines)
        if not text.endswith("\r\n"):
            text += "\r\n"
        path.write_bytes(text.encode("latin-1", errors="replace"))
    except OSError as e:
        raise OSError(f"failed to write {path}: {e}") from e
