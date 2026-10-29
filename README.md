# logel2txt

将展锐 **ArmLogel / Logel** 的 ARM 日志导出为文本（`.txt` / `.trace`），格式对齐 **Export Trace**。

**0.1.0**（[CHANGELOG](CHANGELOG.md)）· 列：`SN` / `UE Time` / `CORE` / `Content` / `Module` / `TickCount`（Tab · CRLF）

说明：[目录结构](docs/armlog-layout.md) · [常见问题](docs/troubleshooting.md)

## 快速开始

### 一条命令（推荐，无需手动开 GUI）

用 **Logel_R9.21.1403** 命令行回放生成 `*_pb`，再导出文本（R9.26.x 的 CLI PBS 布局不同，会对不齐）：

```bat
python logel2txt.py playback "D:\work\logs\xxx.logel" -o out.txt --ue-base 14:35:27.569
python logel2txt.py playback "D:\work\logs\xxx_armlog" -o out.txt --ue-base 14:35:27.569
logel2txt.exe playback "D:\work\logs\xxx_armlog" -o out.txt --ue-base 14:35:27.569
```

默认 Logel：`D:\Unisoc_Tool\Logel_R9.21.1403\Bin\Logel.exe`（可用 `--logel` 或环境变量 `LOGEL_EXE` / `LOGEL_HOME` 覆盖）。

| `playback` 额外参数 | 说明 |
|------|------|
| `--logel` | Logel.exe 路径 |
| `--no-hide` | 回放时显示 Logel 窗口 |
| `--skip-playback` | 跳过回放，假定已有 `*_pb` |

### 已有 *_pb 时只导出

1. 用 Logel 打开 armlog / `.logel`，等解析完成并生成 `*_pb`（内含 `traceview.dat` / `.pbs`）
2. 导出（`--ue-base` 可从 Export Trace 首行 `UE Time` 抄取）：

```bat
logel2txt.exe "D:\work\logs\xxx_armlog" -o out.txt --ue-base 17:15:12.275
python logel2txt.py "D:\work\logs\xxx_armlog" -o out.txt --ue-base 17:15:12.275
```

| 参数 | 说明 |
|------|------|
| `input` | armlog 目录、`.logel`，或含 `traceview` 的目录 |
| `-o` | 输出路径（默认写到输入旁 `.txt`） |
| `--ue-base` | `HH:MM:SS.mmm`；省略则 UE Time 从 `0:00:00.000` 起 |
| `--ext` | 未指定 `-o` 时扩展名：`txt`（默认）/ `trace` |
| `-V` | 版本号 |

成功摘要在 stdout；`[WARN]` / `[ERROR]` 在 **stderr**（非 `*_pb`、0 行、读写失败等会告警）。

## 能力边界

本工具**不调用** Logel 解析库，只读已解码缓存或抽明文。完整解码依赖 Logel 闭源库，无法仅靠 `.logel` / rar 对齐完整 Export。`playback` 子命令会**外调** Logel.exe 做回放，再读 `*_pb`。细节见 [docs/troubleshooting.md](docs/troubleshooting.md)。

| 输入 | 效果 |
|------|------|
| `*_pb\traceview.*`（推荐） | 完整导出，可对齐 Export Trace |
| 非 `_pb` 的旧 `traceview.*` | 可能偏少（stderr 有警告） |
| 仅 `.logel` / 刚解压 rar | 明文抽取，不完整（请用 `playback`） |
| 空的 `*_trace.txt` | 无效 |

优先 `*_pb`。无 `--ue-base` 时 TickCount 仍对，UE Time 为相对时间。目录含义见 [docs/armlog-layout.md](docs/armlog-layout.md)。

## 开发

- 依赖：Windows；运行可用 exe，或 Python 3.7+
- 测试：`python -m unittest discover -s tests -v`
- 打包：`python -m PyInstaller --noconfirm --clean logel2txt.spec` → `dist\logel2txt.exe`（含 `playback` 子命令）
