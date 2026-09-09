# -*- coding: utf-8 -*-
"""导出行格式化与时间解析。"""

from __future__ import annotations

import argparse
import re

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
