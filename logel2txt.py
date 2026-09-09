#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
logel2txt — 将展锐 ArmLogel / Logel 抓取的 ARM 日志导出为文本（.txt / .trace）

优先使用 Logel 打开/回放后生成的 traceview.dat + traceview.pbs（完整解码，
含格式化 TRACE）；若只有 .logel，则尽力抽取明文字符串（不完整）。

用法:
  python logel2txt.py <armlog目录|.logel|含traceview的目录> [-o 输出.txt]
  python -m logel2txt <armlog目录|.logel> [-o 输出.txt]
  python logel2txt.py --version

说明:
  - 若目录下存在 *_pb\\traceview.*（回放缓存），优先使用，结果最接近 Logel「Export Trace」
  - UE Time = ue_base + TickCount；可用 --ue-base 指定设备起始时刻，缺省为 00:00:00.000
"""

from __future__ import annotations

import sys

from logel2txt.cli import main

if __name__ == "__main__":
    sys.exit(main())
