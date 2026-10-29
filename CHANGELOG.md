# logel2txt 更新记录

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 新增

- `logel2txt playback`：Logel 命令行回放生成 `*_pb` 后导出（默认 `Logel_R9.21.1403`）；支持 `--logel` / `--no-hide` / `--skip-playback`。
- `logel2txt/playback.py`：回放逻辑模块（`logel2txt playback` 子命令）。

### 修复

- Content 中 `0xFF` 等字节改为 latin-1 编解码，避免写成 U+FFFD，更接近 Logel Export Trace。

### 文档

- 说明 R9.26.x CLI PBS 与 logel2txt 不兼容；推荐 R9.21 做命令行回放；主推 `playback` 子命令。

## [0.1.0] - 2026-09-09

### 新增

- 从 ArmLogel / Logel 的 `traceview.dat` / `traceview.pbs`（优先 `*_pb`）导出 Tab 分隔文本（`.txt` / `.trace`），列与 Export Trace 对齐。
- 支持 `-o`、`--ue-base`、`--ext`，以及 `-V` / `--version`。
- 包结构 `logel2txt/`（`format` / `discover` / `exporters` / `cli`），入口 `logel2txt.py` / `python -m logel2txt`。
- `logel2txt.spec`：PyInstaller 单文件 `dist/logel2txt.exe`。
- `tests/`：格式化、traceview、路径发现、CLI 错误路径（标准库 unittest）。
- `docs/`：armlog 目录结构与能力边界 / 常见问题。

### 变更

- CLI 日志、错误与 argparse 帮助为英文；`[WARN]` / `[ERROR]` 输出到 stderr。
- 非 `*_pb`、0 行导出、读写失败等路径补充告警（含路径与异常类型）。

### 移除

- 不再提供 `logel2txt.bat`；请使用 `logel2txt.exe` 或 `python logel2txt.py`。
