# -*- coding: utf-8 -*-
"""输入路径解析：查找 traceview / logel，决定导出模式。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional, Tuple


def list_traceview_pairs(root: Path) -> List[Tuple[Path, Path]]:
    """目录树内全部 traceview.dat/.pbs 对（不排序去重）。"""
    pairs: List[Tuple[Path, Path]] = []
    for dat in root.rglob("traceview.dat"):
        pbs = dat.with_suffix(".pbs")
        if pbs.is_file():
            pairs.append((dat, pbs))
    return pairs


def _pb_dir_priority(name: str) -> int:
    """Lower is better: exact *_pb, then other *_pb*, then non-pb."""
    n = name.lower()
    if n.endswith("_pb"):
        return 0
    if "_pb" in n:
        return 1
    return 2


def ranked_traceview_pairs(root: Path) -> List[Tuple[Path, Path]]:
    """All traceview pairs under root, preferred first."""
    candidates: List[Tuple[int, int, Path, Path]] = []
    for dat, pbs in list_traceview_pairs(root):
        pri = _pb_dir_priority(dat.parent.name)
        try:
            size = dat.stat().st_size
        except OSError:
            size = 0
        candidates.append((pri, -size, dat, pbs))
    candidates.sort(key=lambda x: (x[0], x[1]))
    return [(dat, pbs) for _pri, _sz, dat, pbs in candidates]


def _format_traceview_candidates(pairs: List[Tuple[Path, Path]]) -> str:
    lines = []
    for dat, pbs in pairs:
        try:
            pbs_sz = pbs.stat().st_size
        except OSError:
            pbs_sz = -1
        lines.append(f"  - {dat.parent.name}  (pbs {pbs_sz} bytes)  dir={dat.parent}")
    return "\n".join(lines)


def _match_traceview_prefer(
    pairs: List[Tuple[Path, Path]],
    prefer: str,
    root: Path,
) -> Optional[Tuple[Path, Path]]:
    """Match --traceview value to a cache dir name or path."""
    prefer = prefer.strip().strip("\"'")
    if not prefer:
        return None

    # Absolute / relative path to cache directory (or to dat/pbs)
    cand = Path(prefer)
    try:
        if not cand.is_absolute():
            cand = (root / cand).resolve()
        else:
            cand = cand.expanduser().resolve()
    except OSError:
        cand = None  # type: ignore

    if cand is not None:
        if cand.is_file():
            # allow pointing at traceview.dat / .pbs
            if cand.name.lower() in ("traceview.dat", "traceview.pbs"):
                cand = cand.parent
            else:
                cand = None  # type: ignore
        if cand is not None and cand.is_dir():
            dat = cand / "traceview.dat"
            pbs = cand / "traceview.pbs"
            if dat.is_file() and pbs.is_file():
                return dat, pbs

    prefer_l = prefer.lower()
    # Exact directory name
    for dat, pbs in pairs:
        if dat.parent.name == prefer or dat.parent.name.lower() == prefer_l:
            return dat, pbs
    # Unique suffix / substring on directory name
    suffix_hits = [
        (dat, pbs)
        for dat, pbs in pairs
        if dat.parent.name.lower().endswith(prefer_l)
    ]
    if len(suffix_hits) == 1:
        return suffix_hits[0]
    contains_hits = [
        (dat, pbs)
        for dat, pbs in pairs
        if prefer_l in dat.parent.name.lower()
    ]
    if len(contains_hits) == 1:
        return contains_hits[0]
    return None


def find_traceview_pair(
    root: Path,
    prefer: Optional[str] = None,
    *,
    warn: bool = True,
) -> Optional[Tuple[Path, Path]]:
    """在目录树中查找 traceview.dat/.pbs，优先名以 _pb 结尾的目录。

    prefer: 缓存目录名（如 xxx_pb1）或含 traceview 的目录路径（--traceview）。
    多份缓存且未指定 prefer 时向 stderr 警告并列出候选项。
    """
    pairs = ranked_traceview_pairs(root)
    if not pairs:
        return None

    if prefer is not None:
        matched = _match_traceview_prefer(pairs, prefer, root)
        if matched is None:
            raise FileNotFoundError(
                f"no traceview matching --traceview {prefer!r} under {root}\n"
                f"candidates:\n{_format_traceview_candidates(pairs)}\n"
                "hint: pass cache dir name (e.g. xxx_pb1) or path to that folder"
            )
        return matched

    chosen = pairs[0]
    if warn and len(pairs) > 1:
        print(
            f"[WARN] multiple traceview caches under {root} ({len(pairs)}); "
            f"using {chosen[0].parent.name}",
            file=sys.stderr,
        )
        print(_format_traceview_candidates(pairs), file=sys.stderr)
        print(
            "       if Export differs, pass --traceview <cache_dir_name> "
            "(e.g. xxx_pb1) to select another",
            file=sys.stderr,
        )
    return chosen


def sibling_traceview_pairs(primary_dat: Path) -> List[Tuple[Path, Path]]:
    """与主 cache 同 armlog 包下的其它 traceview 对（用于 Content 补全）。"""
    primary_dat = primary_dat.resolve()
    # *_pb 或普通 cache 的父级一般为 armlog 根
    roots = {primary_dat.parent, primary_dat.parent.parent}
    seen = {primary_dat}
    out: List[Tuple[Path, Path]] = []
    for root in roots:
        if not root.is_dir():
            continue
        for dat, pbs in list_traceview_pairs(root):
            dat = dat.resolve()
            if dat in seen:
                continue
            seen.add(dat)
            out.append((dat, pbs))
    return out


def find_logel(root: Path) -> Optional[Path]:
    logs = sorted(root.rglob("*.logel"), key=lambda p: -p.stat().st_size)
    if not logs:
        return None
    chosen = logs[0]
    if len(logs) > 1:
        print(
            f"[WARN] multiple .logel under {root} ({len(logs)}); "
            f"using largest {chosen}",
            file=sys.stderr,
        )
        for p in logs[1:]:
            print(f"       also: {p}", file=sys.stderr)
        print(
            "       pass a specific .logel or *_armlog directory to select another",
            file=sys.stderr,
        )
    return chosen


def resolve_inputs(
    path: Path,
    prefer_traceview: Optional[str] = None,
) -> Tuple[str, object]:
    """
    返回 (mode, payload)
    mode: 'traceview' | 'logel' | 'trace_copy'
    """
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"input path not found: {path}")

    if path.is_file():
        suf = path.suffix.lower()
        if suf == ".logel":
            # 只在 .logel 同级目录树查找，避免扫到上级其它 armlog 包的缓存
            pair = find_traceview_pair(
                path.parent, prefer=prefer_traceview
            )
            if pair:
                return "traceview", pair
            if prefer_traceview:
                raise FileNotFoundError(
                    f"no traceview matching --traceview {prefer_traceview!r} "
                    f"near {path}"
                )
            return "logel", path
        if suf in (".trace", ".txt"):
            return "trace_copy", path
        raise FileNotFoundError(f"unsupported file type: {path}")

    if not path.is_dir():
        raise FileNotFoundError(f"input is not a file or directory: {path}")

    try:
        pair = find_traceview_pair(path, prefer=prefer_traceview)
    except FileNotFoundError:
        raise
    if pair:
        return "traceview", pair
    if prefer_traceview:
        raise FileNotFoundError(
            f"no traceview matching --traceview {prefer_traceview!r} under {path}"
        )
    logel = find_logel(path)
    if logel:
        return "logel", logel
    raise FileNotFoundError(
        f"no traceview.dat/pbs or .logel found under: {path}\n"
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
