# -*- coding: utf-8 -*-
"""输入路径解析：查找 traceview / logel，决定导出模式。"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple


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
        raise FileNotFoundError(f"unsupported file type: {path}")

    if not path.is_dir():
        raise FileNotFoundError(path)

    pair = find_traceview_pair(path)
    if pair:
        return "traceview", pair
    logel = find_logel(path)
    if logel:
        return "logel", logel
    raise FileNotFoundError(
        f"no traceview.dat/pbs or .logel found: {path}\n"
        "hint: open the log in ArmLogel/Logel to build a replay cache, "
        "then export for a full decode."
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
