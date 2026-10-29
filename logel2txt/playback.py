# -*- coding: utf-8 -*-
"""Logel 命令行回放生成 *_pb，再交给导出逻辑。

请使用会写出「兼容 PBS」的 Logel。实测：
  - Logel_R9.21.1403：-f -q -w hide → PBS 与 GUI 一致（推荐）
  - Logel_R9.26.x：同参数 PBS 布局不同，logel2txt 会对不齐
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

DEFAULT_LOGEL = Path(r"D:\Unisoc_Tool\Logel_R9.21.1403\Bin\Logel.exe")
PBS_SIZE_WARN = 30_000_000


def find_logel(explicit: Optional[Path] = None) -> Path:
    if explicit is not None:
        return explicit
    env = os.environ.get("LOGEL_EXE") or os.environ.get("LOGEL_HOME")
    if env:
        p = Path(env)
        if p.is_dir():
            p = p / "Logel.exe"
        return p
    return DEFAULT_LOGEL


def resolve_logel_file(input_path: Path) -> Path:
    input_path = input_path.expanduser().resolve()
    if input_path.is_file() and input_path.suffix.lower() == ".logel":
        return input_path
    if input_path.is_dir():
        top = sorted(input_path.glob("*.logel"))
        if top:
            return top[0].resolve()
        cands = sorted(input_path.glob("*/*.logel"))
        if cands:
            return cands[0].resolve()
    raise FileNotFoundError(f"no .logel found under {input_path}")


def expect_pb_dir(logel_file: Path) -> Path:
    # Logel writes <stem>_pb next to the .logel
    return (logel_file.parent / f"{logel_file.stem}_pb").resolve()


def run_logel_playback(logel: Path, logel_file: Path, hide: bool = True) -> int:
    if not logel.is_file():
        raise FileNotFoundError(f"Logel.exe not found: {logel}")
    args: List[str] = [str(logel), "-f", str(logel_file), "-q"]
    args += ["-w", "hide" if hide else "max"]
    print(f"[INFO] Logel playback: {' '.join(args)}")
    t0 = time.time()
    r = subprocess.run(args, cwd=str(logel.parent))
    print(f"[INFO] Logel exit={r.returncode} elapsed={time.time() - t0:.1f}s")
    return int(r.returncode)


def ensure_playback_cache(
    logel_file: Path,
    logel: Optional[Path] = None,
    hide: bool = True,
) -> Path:
    """Run Logel CLI playback and return the *_pb directory.

    Continues if Logel exits non-zero but traceview.* already exist
    (some versions crash after writing the cache).
    """
    code = run_logel_playback(find_logel(logel), logel_file, hide=hide)
    pb = expect_pb_dir(logel_file)
    if not (pb / "traceview.dat").is_file() or not (pb / "traceview.pbs").is_file():
        raise FileNotFoundError(
            f"playback finished (exit={code}) but missing {pb}\\traceview.*"
        )
    pbs_size = (pb / "traceview.pbs").stat().st_size
    print(f"[INFO] playback cache: {pb} (pbs {pbs_size} bytes)")
    if pbs_size > PBS_SIZE_WARN:
        print(
            "[WARN] PBS unusually large; R9.26.x CLI layout may not match "
            "logel2txt. Prefer Logel_R9.21.1403.",
            file=sys.stderr,
        )
    return pb
