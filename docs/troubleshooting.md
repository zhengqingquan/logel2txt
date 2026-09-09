# 常见问题与能力说明

对应 [README](../README.md)「能力边界」：本工具**不替代** Logel 做完整解码，只读取已生成的 `traceview` 或从 `.logel` 抽明文。

## 为什么必须先用 Logel 打开？

`.logel` 里很多条目是「格式串 ID + 参数」，要变成可读 `Content`，依赖 Logel 内置解析库与数据库（例如 `TraceId2Trace.dll`、`Trace_Data.bin`）。这些是闭源商业组件，没有公开稳定 API，完整链路绑在 Logel 主程序上。

因此：

| 做法 | 结果 |
|------|------|
| Logel 打开一次 → 生成 `*_pb\traceview.*` → logel2txt 导出 | 可与 Export Trace **对齐**（含逐字节一致） |
| 只解压 rar / 只拿 `.logel` 就导出 | 仅明文抽取，常见只覆盖约三成条目 |
| 自行硬调 Logel DLL 做同等导出 | 脆、难维护、需版本匹配；**不建议** |

## README 能力表展开

| 现象 | 原因 | 怎么处理 |
|------|------|----------|
| 有 `*_pb\traceview.*`，导出完整 | 回放缓存已含解码后的字符串与索引 | 推荐路径；加 `--ue-base` 可对齐设备时钟 |
| 只有非 `_pb` 的 `traceview.*`，行数偏少 | 缓存未充分回放或较旧 | 用 Logel 再打开，等生成/更新 `_pb` 后再导出 |
| 只有 `.logel`，内容残缺 | 未走 Logel 解码 | 先开 Logel；不要指望「不解压直接完整」 |
| `*_trace.txt` 为 0 字节 | 占位/未导出 | 忽略；用 logel2txt 或 Logel Export Trace |
| 与参考 Export 差「大约等于行数」的字节 | 旧结果可能是 LF，本工具为 **CRLF** | 比内容而非仅比文件大小 |
| TickCount 对、UE Time 对不上 | 未设 `--ue-base` 时 UE 从 `0:00:00.000` 起算 | 从 Export 首行抄 `UE Time`，例如 `--ue-base 17:15:12.275` |
| 同一包第一次导出少几百行，开过 Logel 后又齐了 | 当时还没有（或没用到）`*_pb`，工具读了旧 `traceview` | 确认日志里打印的是 `*_pb` 目录名 |

## 实测对照（行为预期）

在「已有非 `_pb` 的 `traceview`、尚未生成 `_pb`」时：导出可能比 Logel Export **少一批行**，但已导出部分的 Content / Tick 通常能对上；补上 `--ue-base` 后 UE 也可对齐。

生成 `*_pb` 且工具选用该目录后：行数、体积可与 Export Trace **完全一致**（在相同 `--ue-base` 下）。

## 相关文档

- 目录里有哪些文件：[armlog-layout.md](armlog-layout.md)
- 命令与参数：[README.md](../README.md)
