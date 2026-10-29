# -*- coding: utf-8 -*-
"""Logel 命令行回放生成 *_pb，再交给导出逻辑。

须指定 Logel（无内置默认路径）：
  - --logel / LOGEL_EXE / LOGEL_HOME：Logel.exe 或安装目录
  - --logel-root / LOGEL_ROOT：在目录下扫描 Logel_R*\\Bin\\Logel.exe，优先 R9.21

CLI 回放写出的 PBS：
  - Logel_R9.21.x：与 GUI 一致（约 44B/条），logel2txt 可完整导出
  - Logel_R9.25 / R9.26：同参数 PBS 布局不同 → 拒绝并提示改用 R9.21
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

PBS_SIZE_WARN = 30_000_000

# (major, minor) — CLI PBS layout known-good for logel2txt
_CLI_COMPAT_MINORS = {(9, 21)}
_CLI_INCOMPAT_MINORS = {(9, 25), (9, 26)}

_VERSION_RE = re.compile(r"[Rr]?9[._](\d+)[._](\d+)", re.IGNORECASE)


class IncompatibleLogelError(RuntimeError):
    """Logel build is known to write CLI PBS that logel2txt cannot parse."""


class LogelNotConfiguredError(FileNotFoundError):
    """No --logel / env / --logel-root was provided."""


def parse_logel_version(path: Path) -> Optional[Tuple[int, int, int]]:
    """From path like .../Logel_R9.21.1403/... → (9, 21, 1403)."""
    m = _VERSION_RE.search(str(path))
    if not m:
        return None
    minor, build = int(m.group(1)), int(m.group(2))
    return (9, minor, build)


def version_label(ver: Optional[Tuple[int, int, int]]) -> str:
    if ver is None:
        return "unknown"
    return f"R9.{ver[1]}.{ver[2]}"


def cli_pbs_status(path: Path) -> str:
    """Return 'compatible' | 'incompatible' | 'unknown' for CLI playback PBS."""
    ver = parse_logel_version(path)
    if ver is None:
        return "unknown"
    key = (ver[0], ver[1])
    if key in _CLI_COMPAT_MINORS:
        return "compatible"
    if key in _CLI_INCOMPAT_MINORS:
        return "incompatible"
    return "unknown"


def _exe_under_home(home: Path) -> Path:
    return home / "Bin" / "Logel.exe"


def _normalize_exe(path: Path) -> Path:
    path = path.expanduser()
    if path.is_dir():
        bin_exe = path / "Bin" / "Logel.exe"
        if bin_exe.is_file() or (path / "Bin").is_dir():
            return bin_exe
        return path / "Logel.exe"
    return path


def list_logel_under_root(root: Path) -> List[Path]:
    """Scan <root>/Logel_R*/Bin/Logel.exe (and <root>/Bin/Logel.exe)."""
    root = root.expanduser()
    seen = set()
    out: List[Path] = []

    def _add(exe: Path) -> None:
        key = str(exe).lower()
        if key in seen:
            return
        seen.add(key)
        if exe.is_file():
            out.append(exe.resolve())

    if not root.is_dir():
        return out

    direct = root / "Logel.exe"
    if direct.is_file():
        _add(direct.resolve())
    bin_exe = root / "Bin" / "Logel.exe"
    if bin_exe.is_file():
        _add(bin_exe.resolve())

    for home in sorted(root.glob("Logel_R*")):
        _add(_exe_under_home(home))
    return out


def config_hint(root: Optional[Path] = None) -> str:
    lines = [
        "Specify Logel for playback (no built-in default path):",
        "  --logel PATH          Logel.exe or install dir (prefer R9.21.x)",
        "  LOGEL_EXE / LOGEL_HOME",
        "  --logel-root DIR      scan DIR\\Logel_R*\\Bin\\Logel.exe (prefer R9.21)",
        "  LOGEL_ROOT",
    ]
    if root is not None:
        exes = list_logel_under_root(root)
        if exes:
            lines.append(f"Under {root}:")
            for exe in exes:
                st = cli_pbs_status(exe)
                ver = version_label(parse_logel_version(exe))
                mark = {
                    "compatible": "OK",
                    "incompatible": "NO",
                    "unknown": "?",
                }.get(st, "?")
                lines.append(f"  [{mark}] {ver}: {exe}")
            lines.append(
                "Use R9.21.x for CLI playback. R9.25 / R9.26 CLI PBS differs — "
                "GUI-open then export, or --logel to R9.21."
            )
        else:
            lines.append(f"No Logel.exe found under {root}.")
    return "\n".join(lines)


def format_install_hint(exes: Optional[List[Path]] = None) -> str:
    if not exes:
        return config_hint()
    lines = ["Logel candidates (CLI PBS status for logel2txt):"]
    for exe in exes:
        st = cli_pbs_status(exe)
        ver = version_label(parse_logel_version(exe))
        mark = {"compatible": "OK", "incompatible": "NO", "unknown": "?"}.get(
            st, "?"
        )
        lines.append(f"  [{mark}] {ver}: {exe}")
    lines.append(
        "For `logel2txt playback`, use R9.21.x (compatible). "
        "R9.25 / R9.26 CLI PBS layout differs — open in GUI then export, "
        "or point --logel to R9.21."
    )
    return "\n".join(lines)


def check_cli_compatible(
    logel: Path,
    *,
    allow_unknown: bool = True,
    hint_exes: Optional[List[Path]] = None,
) -> None:
    """Raise IncompatibleLogelError if this Logel must not be used for CLI playback."""
    status = cli_pbs_status(logel)
    ver = version_label(parse_logel_version(logel))
    if status == "compatible":
        return
    if status == "unknown" and allow_unknown:
        print(
            f"[WARN] Logel version unknown from path ({logel}); "
            "CLI PBS may not match logel2txt. Prefer Logel_R9.21.x.",
            file=sys.stderr,
        )
        return
    raise IncompatibleLogelError(
        f"Logel {ver} CLI playback writes PBS that logel2txt cannot parse "
        f"(empty Content / inflated line count).\n"
        f"  refused: {logel}\n"
        f"{format_install_hint(hint_exes)}"
    )


def _pick_compatible(exes: List[Path]) -> Path:
    compatible = [e for e in exes if cli_pbs_status(e) == "compatible"]
    if compatible:
        for e in compatible:
            if "R9.21" in str(e):
                return e
        return compatible[0]
    raise IncompatibleLogelError(
        "No CLI-compatible Logel (R9.21.x) found among candidates.\n"
        f"{format_install_hint(exes)}"
    )


def find_logel(
    explicit: Optional[Path] = None,
    root: Optional[Path] = None,
) -> Path:
    """Resolve Logel.exe from --logel / env / --logel-root. No hardcoded default."""
    if explicit is not None:
        p = _normalize_exe(explicit)
        check_cli_compatible(p)
        return p

    env = os.environ.get("LOGEL_EXE") or os.environ.get("LOGEL_HOME")
    if env:
        p = _normalize_exe(Path(env))
        check_cli_compatible(p)
        return p

    root_env = root
    if root_env is None:
        env_root = os.environ.get("LOGEL_ROOT")
        if env_root:
            root_env = Path(env_root)

    if root_env is not None:
        root_env = root_env.expanduser()
        if not root_env.is_dir():
            raise FileNotFoundError(
                f"LOGEL_ROOT / --logel-root not a directory: {root_env}\n"
                f"{config_hint()}"
            )
        found = list_logel_under_root(root_env)
        if not found:
            raise FileNotFoundError(
                f"No Logel.exe under {root_env}\n{config_hint(root_env)}"
            )
        return _pick_compatible(found)

    raise LogelNotConfiguredError(
        "Logel path not configured.\n" + config_hint()
    )


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
        raise FileNotFoundError(
            f"Logel.exe not found: {logel}\n{config_hint()}"
        )
    ver = version_label(parse_logel_version(logel))
    args: List[str] = [str(logel), "-f", str(logel_file), "-q"]
    args += ["-w", "hide" if hide else "max"]
    print(f"[INFO] Logel {ver} playback: {' '.join(args)}")
    t0 = time.time()
    r = subprocess.run(args, cwd=str(logel.parent))
    print(f"[INFO] Logel exit={r.returncode} elapsed={time.time() - t0:.1f}s")
    return int(r.returncode)


def ensure_playback_cache(
    logel_file: Path,
    logel: Optional[Path] = None,
    logel_root: Optional[Path] = None,
    hide: bool = True,
) -> Path:
    """Run Logel CLI playback and return the *_pb directory.

    Continues if Logel exits non-zero but traceview.* already exist
    (some versions crash after writing the cache).
    """
    exe = find_logel(logel, root=logel_root)
    code = run_logel_playback(exe, logel_file, hide=hide)
    pb = expect_pb_dir(logel_file)
    if not (pb / "traceview.dat").is_file() or not (pb / "traceview.pbs").is_file():
        raise FileNotFoundError(
            f"playback finished (exit={code}) but missing {pb}\\traceview.*"
        )
    pbs_size = (pb / "traceview.pbs").stat().st_size
    print(f"[INFO] playback cache: {pb} (pbs {pbs_size} bytes)")
    if pbs_size > PBS_SIZE_WARN:
        raise IncompatibleLogelError(
            f"PBS unusually large ({pbs_size} bytes); likely R9.25/R9.26 CLI layout, "
            "not the 44-byte/record format logel2txt expects.\n"
            f"  cache: {pb}\n"
            f"{config_hint()}"
        )
    return pb
