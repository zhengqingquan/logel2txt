# logel2txt 更新记录

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 新增

- `logel2txt playback`：Logel 命令行回放生成 `*_pb` 后导出；支持 `--logel` / `--no-hide` / `--skip-playback`。
- `logel2txt/playback.py`：回放逻辑；须 `--logel` / `LOGEL_EXE` 或 `--logel-root` / `LOGEL_ROOT`（无内置默认路径）；在 root 下优先 R9.21；R9.25/R9.26 CLI 不兼容时拒绝并提示。
- 支持直接输入 `.zip` / `.rar` / `.7z`（`logel2txt/archive.py`）；`.zip` 用标准库，`.rar`/`.7z` 需 `--7z` 或 `SEVEN_ZIP`/`7Z_EXE`/PATH；可用 `--extract-to` 指定解压目录。

### 修复

- Content 中 `0xFF` 等字节改为 latin-1 编解码，避免写成 U+FFFD，更接近 Logel Export Trace。
- CLI `*_pb` 中偶发 double 零填充大数 Content：若同包其它 traceview 缓存有同 SN/sub/Tick 的更完整串则替换。
- 输入目录含多个 `.logel` 时 stderr 提示并列出其它文件（仍选用其中一个）。

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
