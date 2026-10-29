# 抓取目录结构（ArmLogel / armlog）

展锐工具抓取或解压后的 ARM 日志，常见是「时间戳 + `_armlog`」目录；同级可能还有压缩包与已导出的 `.txt` / `.trace`。名称中的时间戳因抓取而异；关键后缀是 `_armlog`、`.logel`、`*_pb`、`traceview.dat` / `.pbs`。

## 典型布局

```
2026_08_25_17_24_05_960_armlog/          # 抓取包根目录
├── 2026_08_25_17_24_05_960.logel        # 原始日志（二进制）
├── 2026_08_25_17_24_05_960_log_stat.txt # 统计信息（可选）
├── 2026_08_25_17_24_05_960_trace.txt    # 常为 0 字节占位，不是完整导出
├── 2026_08_25_17_24_05_960/             # 非 _pb 回放缓存（可能偏旧/偏少）
│   ├── traceview.dat
│   ├── traceview.pbs
│   └── phytraceview.*                   # 物理层相关缓存
└── 2026_08_25_17_24_05_960_pb/          # Logel 打开/回放后生成的解码缓存
    ├── traceview.dat                    # 字符串表
    ├── traceview.pbs                    # 索引记录（与 .dat 成对）
    ├── msgview.* / msgflowview.*        # 其它视图缓存
    └── phytraceview.* / phyparamchart.*
```

同级目录还可能有：

| 文件 | 说明 |
|------|------|
| `*_armlog.rar` / `.zip` / `.7z` | 抓取压缩包；解压后得到上表目录树 |
| `*_armlog.txt` / `*.trace` | Export Trace 或其它工具写出的文本结果 |

## 文件角色

| 路径 / 后缀 | 含义 |
|-------------|------|
| `*.logel` | 原始抓取二进制；大量条目为「格式串 ID + 参数」，本身不含完整可读 Content |
| `*_pb\` | 完整回放后的解码缓存目录（名称通常为「与 .logel 同名 + `_pb`」） |
| 非 `_pb` 同名目录 | 较早或未充分回放的缓存，条目可能少于 `_pb` |
| `traceview.dat` | 字符串表（Content 等文本） |
| `traceview.pbs` | 与同目录 `.dat` 配套的索引：魔数 `TIND`、约 512 字节头、其后定长记录（常见 **44 / 52 / 76** 字节/条，含 TickCount、CORE、指向 dat 的偏移等） |
| `*_trace.txt`（0 字节） | 占位，无有效内容 |
| `*_log_stat.txt` | 统计摘要，不是逐条 Trace |
| `msgview.*` / `msgflowview.*` / `phytraceview.*` / `phyparamchart.*` | 其它视图或物理层缓存，与 `traceview` 并行存在 |

一对完整的 Trace 视图缓存 = 同目录下的 `traceview.dat` + `traceview.pbs`。通常以 `*_pb` 下这一对为准；非 `_pb` 目录下也可能有同名文件，但内容可能不完整。

使用与排错见 [troubleshooting.md](troubleshooting.md)；命令见 [README.md](../README.md)。
