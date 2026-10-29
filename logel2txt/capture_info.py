# -*- coding: utf-8 -*-
"""从 armlog 旁 .lst 读取抓取 / 回放所用的 Logel（Tool Version）。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# 只用横向空白，避免 "Modem Version:\nParserLib..." 被 \s 吃掉换行后误拼一行
_FIELD_RE = re.compile(
    r"^(Modem Version|ParserLib Version|Tool Version)[ \t]*:[ \t]*(.*)$",
    re.IGNORECASE | re.MULTILINE,
)
# …/name.lst 抓取；…/name_pb.lst、name_pb1.lst 等为回放留下的
_REPLAY_LST_RE = re.compile(r"^(?P<stem>.+)_pb(?P<n>\d*)\.lst$", re.IGNORECASE)


@dataclass
class LstMeta:
    path: Path
    tool_version: Optional[str] = None
    parser_lib_version: Optional[str] = None
    modem_version: Optional[str] = None
    raw_fields: Dict[str, str] = field(default_factory=dict)

    @property
    def is_replay(self) -> bool:
        return _REPLAY_LST_RE.match(self.path.name) is not None

    @property
    def capture_stem(self) -> str:
        m = _REPLAY_LST_RE.match(self.path.name)
        if m:
            return m.group("stem")
        if self.path.suffix.lower() == ".lst":
            return self.path.stem
        return self.path.stem


@dataclass
class CaptureInfo:
    """一份日志的工具版本信息（抓取为主，回放缓存另列）。"""

    root: Path
    capture: Optional[LstMeta] = None
    replays: List[LstMeta] = field(default_factory=list)
    all_lst: List[LstMeta] = field(default_factory=list)

    @property
    def tool_version(self) -> Optional[str]:
        """抓取时的 Tool Version（主 .lst）。"""
        return self.capture.tool_version if self.capture else None


def parse_lst_text(text: str, path: Optional[Path] = None) -> LstMeta:
    # .lst 常见 CRLF / 偶发裸 CR；统一成 \n 再按行匹配
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    meta = LstMeta(path=path or Path("."))
    for m in _FIELD_RE.finditer(text):
        key = m.group(1).strip()
        val = m.group(2).strip()
        meta.raw_fields[key] = val
        kl = key.lower()
        if kl == "tool version":
            meta.tool_version = val or None
        elif kl == "parserlib version":
            meta.parser_lib_version = val or None
        elif kl == "modem version":
            meta.modem_version = val or None
    return meta


def parse_lst_file(path: Path) -> LstMeta:
    raw = path.read_bytes()
    # .lst 多为 ASCII/latin-1 短文本
    text = raw.decode("utf-8", errors="replace")
    if "\x00" in text[:200]:
        text = raw.decode("utf-16-le", errors="replace")
    return parse_lst_text(text, path=path)


def list_lst_files(root: Path) -> List[Path]:
    root = root.expanduser()
    if root.is_file():
        if root.suffix.lower() == ".lst":
            return [root]
        # .logel → 同 stem .lst；目录则搜树
        if root.suffix.lower() == ".logel":
            sibling = root.with_suffix(".lst")
            return [sibling] if sibling.is_file() else []
        return []
    if not root.is_dir():
        return []
    return sorted(root.rglob("*.lst"))


def _pick_capture(
    metas: List[LstMeta], logel_stem: Optional[str] = None
) -> Optional[LstMeta]:
    """Prefer non-replay .lst; if logel stem known, match that name."""
    primary = [m for m in metas if not m.is_replay]
    if logel_stem:
        for m in primary:
            if m.path.stem.lower() == logel_stem.lower():
                return m
    if len(primary) == 1:
        return primary[0]
    if primary:
        # largest sibling group: prefer longest tool_version present, else first by name
        with_ver = [m for m in primary if m.tool_version]
        pool = with_ver or primary
        return sorted(pool, key=lambda m: m.path.as_posix().lower())[0]
    return None


def inspect_capture_info(
    path: Path,
    *,
    logel_stem: Optional[str] = None,
) -> CaptureInfo:
    """Scan path (armlog dir / .logel / .lst) for Tool Version metadata."""
    path = path.expanduser().resolve()
    info = CaptureInfo(root=path)

    if path.is_file() and path.suffix.lower() == ".logel" and logel_stem is None:
        logel_stem = path.stem

    lst_paths = list_lst_files(path)
    # If given a directory that only contains nested armlog, rglob still finds them.
    metas: List[LstMeta] = []
    for lp in lst_paths:
        try:
            metas.append(parse_lst_file(lp))
        except OSError:
            continue
    info.all_lst = metas
    info.capture = _pick_capture(metas, logel_stem=logel_stem)
    info.replays = [m for m in metas if m.is_replay]
    # Stable order for replays
    info.replays.sort(key=lambda m: m.path.as_posix().lower())
    return info


def format_capture_info(info: CaptureInfo) -> str:
    lines: List[str] = []
    if info.capture and info.capture.tool_version:
        lines.append(f"capture Tool Version: {info.capture.tool_version}")
        lines.append(f"  lst: {info.capture.path}")
        if info.capture.parser_lib_version:
            lines.append(f"  ParserLib Version: {info.capture.parser_lib_version}")
        if info.capture.modem_version:
            lines.append(f"  Modem Version: {info.capture.modem_version}")
    elif info.capture:
        lines.append("capture .lst found but no Tool Version field")
        lines.append(f"  lst: {info.capture.path}")
    else:
        lines.append("no capture .lst / Tool Version found")
        lines.append(f"  searched under: {info.root}")

    if info.replays:
        lines.append("replay .lst (opened later; not necessarily capture tool):")
        for m in info.replays:
            ver = m.tool_version or "(no Tool Version)"
            lines.append(f"  {m.path.name}: {ver}")
            lines.append(f"    lst: {m.path}")
    return "\n".join(lines)
