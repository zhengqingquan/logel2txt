# 抓取目录结构（ArmLogel / armlog）

展锐工具抓取或解压后的 ARM 日志，常见是「时间戳 + `_armlog`」目录，旁边可能还有 `.rar` 与已导出的 `.txt` / `.trace`。

## 典型布局

```
2026_08_25_17_24_05_960_armlog/          # 抓取包根目录（也可直接把此路径交给 logel2txt）
├── 2026_08_25_17_24_05_960.logel        # 原始日志（二进制；大量条目需 Logel 解码）
├── 2026_08_25_17_24_05_960_log_stat.txt # 统计信息（可选）
├── 2026_08_25_17_24_05_960_trace.txt    # 常为 0 字节占位，不能当完整导出用
├── 2026_08_25_17_24_05_960/             # 非 _pb 回放缓存（可能偏旧/偏少）
│   ├── traceview.dat
│   ├── traceview.pbs
│   └── phytraceview.*                   # 物理层相关缓存（本工具不读）
└── 2026_08_25_17_24_05_960_pb/          # Logel 打开/回放后生成（推荐）
    ├── traceview.dat                    # 字符串表
    ├── traceview.pbs                    # 索引记录（本工具主要输入）
    ├── msgview.* / msgflowview.*        # 其它视图缓存（本工具不读）
    └── phytraceview.* / phyparamchart.*
```

同级目录还可能有：

| 文件 | 说明 |
|------|------|
| `*_armlog.rar` | 压缩包；仅解压不够，需 Logel 打开才会有完整 `_pb` |
| `*_armlog.txt` / `*.trace` | Logel **Export Trace** 或本工具的导出结果 |

名称中的时间戳因抓取而异；关键后缀是 `_armlog`、`.logel`、`*_pb`、`traceview.dat` / `.pbs`。

## 各文件对 logel2txt 的意义

| 路径 | 本工具如何用 |
|------|----------------|
| `*_pb\traceview.dat` + `traceview.pbs` | **优先**；完整解码，可对齐 Export Trace |
| 非 `_pb` 目录下的 `traceview.*` | 次选；行数可能少于 `_pb` |
| 仅有 `.logel` | 明文 TLV 抽取，**不完整** |
| `*_trace.txt`（0 字节） | 忽略 |
| `msgview.*` / `phytraceview.*` 等 | 不使用 |

查找规则：在输入路径下递归搜索 `traceview.dat`，要求同目录有 `traceview.pbs`；父目录名含 `_pb` 的优先，同优先级再取更大的 `dat`。

## 推荐操作顺序

1. 解压 rar（若有）得到 `*_armlog`
2. 用 **ArmLogel / Logel** 打开该目录或 `.logel`，等待解析结束
3. 确认出现 `*_pb\traceview.dat` 与 `traceview.pbs`
4. 再运行 `logel2txt.exe` 或 `python logel2txt.py`（需要绝对 UE Time 时加 `--ue-base`）

更细的「为何必须先开 Logel、行数对不齐」见 [troubleshooting.md](troubleshooting.md)。
