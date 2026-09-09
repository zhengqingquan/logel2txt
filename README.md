# logel2txt

将展锐 **ArmLogel / Logel** 的 ARM 日志导出为文本（`.txt` / `.trace`），格式对齐 **Export Trace**。

版本 **0.1.0** · 列：`SN` / `UE Time` / `CORE` / `Content` / `Module` / `TickCount`（Tab · CRLF）· 详见 [CHANGELOG.md](CHANGELOG.md)

更多说明：[目录结构](docs/armlog-layout.md) · [常见问题](docs/troubleshooting.md)

## 快速开始

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

## 能力边界

本工具**不调用** Logel 解析库，只读已解码缓存或抽明文。完整解码依赖 Logel 闭源库，无法仅靠 `.logel` / rar 对齐完整 Export。细节见 [docs/troubleshooting.md](docs/troubleshooting.md)。

| 输入 | 效果 |
|------|------|
| `*_pb\traceview.*`（推荐） | 完整导出，可对齐 Export Trace |
| 非 `_pb` 的旧 `traceview.*` | 可能偏少 |
| 仅 `.logel` / 刚解压 rar | 明文抽取，不完整 |
| 空的 `*_trace.txt` | 无效 |

优先 `*_pb`。无 `--ue-base` 时 TickCount 仍对，UE Time 为相对时间。目录含义见 [docs/armlog-layout.md](docs/armlog-layout.md)。

## 开发

- 依赖：Windows；运行可用 exe，或 Python 3.7+
- 测试：`python -m unittest discover -s tests -v`
- 打包：`python -m PyInstaller --noconfirm --clean logel2txt.spec` → `dist\logel2txt.exe`
