# logel2txt

将展锐 **ArmLogel / Logel** 抓取的 ARM 日志导出为文本（`.txt` / `.trace`），格式对齐 Logel 的 **Export Trace**。

当前版本：**0.1.0**（详见 [CHANGELOG.md](CHANGELOG.md)）。

输出列：`SN` / `UE Time` / `CORE` / `Content` / `Module` / `TickCount`（Tab 分隔，CRLF 换行）。

## 依赖

- Windows
- Python 3.7+（命令行可用 `python`）

## 文件

| 文件 / 目录 | 说明 |
|-------------|------|
| `logel2txt/` | 包：`format` / `discover` / `exporters` / `cli` |
| `logel2txt.py` | 薄入口（调用包内 CLI） |
| `logel2txt.bat` | Windows 快捷入口 |
| `tests/` | 标准库 unittest |
| `README.md` | 本说明 |
| `CHANGELOG.md` | 更新记录 |

## 用法

```bat
REM 查看版本
logel2txt.bat --version
python logel2txt.py -V
python -m logel2txt -V

REM 方式一：bat
logel2txt.bat "D:\work\logs\xxx_armlog"

REM 方式二：python / 模块
python logel2txt.py "D:\work\logs\xxx_armlog"
python -m logel2txt "D:\work\logs\xxx_armlog"
python logel2txt.py "D:\work\logs\xxx_armlog" -o "D:\work\logs\out.txt"
python logel2txt.py "D:\work\logs\xxx_armlog" -o out.txt --ue-base 17:15:12.275
python logel2txt.py "D:\work\logs\xxx.logel" -o out.txt
```

### 测试

```bat
python -m unittest discover -s tests -v
```

### 参数

| 参数 | 说明 |
|------|------|
| `input` | armlog 目录、`.logel`，或已含 `traceview.dat/.pbs` 的目录 |
| `-V` / `--version` | 显示版本号后退出 |
| `-o` / `--output` | 输出路径；省略则写到输入旁的 `.txt` |
| `--ue-base` | 设备起始时刻 `HH:MM:SS.mmm`；省略则 UE Time 从 `0:00:00.000` 起算 |
| `--ext` | 未指定 `-o` 时的扩展名：`txt`（默认）或 `trace` |

## 推荐流程（要与 Logel 回放导出一致）

1. 用 **ArmLogel / Logel** 打开 `.logel`（或整包 armlog）
2. 等待解析完成，确认生成 `*_pb` 目录（内含 `traceview.dat` / `traceview.pbs`）
3. 再运行本工具导出 txt

```bat
cd /d D:\work\logel2txt
logel2txt.bat "..\xxx_armlog" -o "..\out.txt" --ue-base 17:15:12.275
```

`--ue-base` 可从 Logel Export Trace 首行的 `UE Time` 抄取，用于对齐设备时钟。

## 导出能力说明（重要）

本工具**不调用** Logel 解析库，只读取已解码缓存或抽取明文。

| 输入情况 | 效果 | 能否对齐「完整回放后再 Export」 |
|----------|------|--------------------------------|
| 有 `*_pb\traceview.dat` + `traceview.pbs` | **完整导出**（推荐） | 能 |
| 仅有普通目录下旧的 `traceview.*`（未充分回放） | 可能行数偏少 | 通常不能 |
| 只有 `.logel` / 刚解压的 rar | 仅抽明文 TRACE | **不能**（常见仅约三成条目） |
| 空的 `*_trace.txt`（0 字节） | 无效 | — |

### 为什么不能「不解压后直接开 Logel」就得到完整结果？

`.logel` 里大量条目是「格式串 ID + 参数」，要变成可读文本依赖 Logel 内置解析库与数据库（如 `TraceId2Trace.dll`、`Trace_Data.bin`）。这些是**闭源商业二进制**，没有公开 API 文档，完整解码链路还绑在 Logel 主程序上。

因此：

- **可以**：Logel 打开一次 → 生成 `traceview` → 用本工具快速导出 txt（与 Export Trace 对齐）
- **不可以指望**：跳过 Logel，仅靠 `.logel` / rar，就得到与完整回放导出逐字节一致的结果
- **不建议**：自行硬调 DLL 做同等导出（需逆向，脆、难维护、版本要匹配）

## 注意

- 优先使用 `*_pb` 下的 `traceview`（通常比未回放目录更新、更全）
- 未指定 `--ue-base` 时，`TickCount` 仍正确；`UE Time` 为相对时间，会与 Logel 绝对 UE Time 看起来不同
- 换行符与 Logel 一致为 **CRLF**；若与参考文件差「正好等于行数」的字节，多半是旧版 LF 换行导致，内容本身可能相同
- 重新解压 rar 后若没有 `*_pb`，请先用 Logel 打开再导出
