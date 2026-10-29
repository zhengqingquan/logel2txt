# -*- coding: utf-8 -*-
"""压缩包输入：解压 .zip / .rar / .7z 后再交给导出 / playback。

无内置解压工具默认路径：
  - .zip：优先标准库 zipfile（无需外部工具）
  - .rar / .7z：须 --7z / 环境变量 SEVEN_ZIP 或 7Z_EXE，或 PATH 中的 7z
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import List, Optional, Set

ARCHIVE_SUFFIXES: Set[str] = {".zip", ".rar", ".7z"}


class ArchiveError(RuntimeError):
    """Archive extract / tool resolution failed."""


def is_archive(path: Path) -> bool:
    """True if path looks like a supported archive (by suffix)."""
    return path.suffix.lower() in ARCHIVE_SUFFIXES


def find_7z(explicit: Optional[Path] = None) -> Path:
    """Resolve 7z.exe: --7z / SEVEN_ZIP / 7Z_EXE / PATH. No hardcoded install path."""
    if explicit is not None:
        p = explicit.expanduser()
        if p.is_dir():
            p = p / "7z.exe"
        if not p.is_file():
            raise ArchiveError(f"7z not found: {p}")
        return p

    for key in ("SEVEN_ZIP", "7Z_EXE"):
        env = os.environ.get(key)
        if env:
            p = Path(env).expanduser()
            if p.is_dir():
                p = p / "7z.exe"
            if p.is_file():
                return p
            raise ArchiveError(f"{key} set but 7z not found: {p}")

    for name in ("7z.exe", "7z"):
        which = shutil.which(name)
        if which:
            return Path(which)

    raise ArchiveError(
        "7z required for .rar/.7z (and as zip fallback).\n"
        "  pass --7z PATH, or set SEVEN_ZIP / 7Z_EXE, or add 7z to PATH"
    )


def _has_logel_here(root: Path) -> bool:
    return root.is_dir() and any(root.glob("*.logel"))


def _has_logel(root: Path) -> bool:
    if not root.is_dir():
        return False
    return _has_logel_here(root) or any(root.glob("*/*.logel"))


def _unwrap_extract_root(dest: Path) -> Path:
    """If extract created a single nested folder with .logel, return that folder."""
    if not dest.is_dir():
        return dest
    if _has_logel_here(dest):
        return dest
    subs = sorted(p for p in dest.iterdir() if p.is_dir())
    if len(subs) == 1 and _has_logel_here(subs[0]):
        return subs[0]
    return dest


def _extract_zip_stdlib(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "r") as zf:
        zf.extractall(dest)


def _extract_with_7z(archive: Path, dest: Path, seven_zip: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    # 7z treats -oDIR as output root (no space after -o)
    args: List[str] = [str(seven_zip), "x", str(archive), f"-o{dest}", "-y"]
    print(f"[INFO] extract: {' '.join(args)}")
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        detail = (r.stderr or r.stdout or "").strip()
        raise ArchiveError(
            f"7z extract failed (exit={r.returncode}): {archive}\n{detail}"
        )


def extract_archive(
    archive: Path,
    *,
    seven_zip: Optional[Path] = None,
    extract_to: Optional[Path] = None,
    force: bool = False,
) -> Path:
    """Extract archive into extract_to, or beside it into <stem>/.

    Reuses dest if .logel already present (unless force).
    Returns a directory suitable for resolve_logel_file / export.
    """
    archive = archive.expanduser().resolve()
    if not is_archive(archive):
        raise ArchiveError(f"not a supported archive: {archive}")

    if extract_to is not None:
        dest = extract_to.expanduser().resolve()
    else:
        dest = archive.parent / archive.stem
    if dest.is_dir() and _has_logel(dest) and not force:
        print(f"[INFO] reuse extracted dir: {dest}", file=sys.stderr)
        return _unwrap_extract_root(dest)

    suf = archive.suffix.lower()
    print(f"[INFO] extracting {archive.name} -> {dest}")

    if suf == ".zip":
        try:
            _extract_zip_stdlib(archive, dest)
        except zipfile.BadZipFile:
            # uncommon zip variants: fall back to 7z if available
            exe = find_7z(seven_zip)
            _extract_with_7z(archive, dest, exe)
        except OSError as e:
            raise ArchiveError(f"failed to extract zip {archive}: {e}") from e
    else:
        exe = find_7z(seven_zip)
        _extract_with_7z(archive, dest, exe)

    root = _unwrap_extract_root(dest)
    if not _has_logel(root):
        raise ArchiveError(
            f"extract finished but no .logel under {dest}\n"
            "  expected an armlog package inside the archive"
        )
    print(f"[INFO] extract ready: {root}")
    return root


def prepare_input(
    path: Path,
    *,
    seven_zip: Optional[Path] = None,
    extract_to: Optional[Path] = None,
    force_extract: bool = False,
) -> Path:
    """If path is an archive, extract and return content dir; else return path."""
    path = path.expanduser().resolve()
    if path.is_file() and is_archive(path):
        return extract_archive(
            path,
            seven_zip=seven_zip,
            extract_to=extract_to,
            force=force_extract,
        )
    if extract_to is not None:
        print(
            "[WARN] --extract-to ignored (input is not an archive)",
            file=sys.stderr,
        )
    return path
