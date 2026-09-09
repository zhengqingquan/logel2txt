# logel2txt 更新记录

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

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
