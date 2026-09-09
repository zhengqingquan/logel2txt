# logel2txt 更新记录

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 变更

- 将单文件拆为包 `logel2txt/`（`format` / `discover` / `exporters` / `cli`）；根目录 `logel2txt.py` 改为薄入口，并支持 `python -m logel2txt`。
- 新增 `tests/`：格式化、traceview 最小伪造字节、路径发现（标准库 unittest）。

## [0.1.0] - 2026-09-09

### 新增

- 提供 `logel2txt.py` / `logel2txt.bat`：从 ArmLogel / Logel 的 `traceview.dat` / `traceview.pbs`（优先 `*_pb`）导出 Tab 分隔文本（`.txt` / `.trace`），列与 Export Trace 对齐。
- 支持指定输出路径（`-o`）、设备起始时刻（`--ue-base`）及默认扩展名（`--ext`）。
- 支持 `-V` / `--version` 显示版本号（当前 `0.1.0`）。
- 补充 README：推荐「先用 Logel 打开生成缓存再导出」流程，并说明仅 `.logel` / 明文抽取时的能力边界。
