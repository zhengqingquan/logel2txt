# 常见问题

本工具**不替代** Logel 做完整解码：优先读已生成的 `traceview.dat` / `.pbs`，否则从 `.logel` 抽明文（不完整）。目录含义见 [armlog-layout.md](armlog-layout.md)；命令见 [README.md](../README.md)。

## 为什么必须先用 Logel（或 `playback`）？

`.logel` 里很多条目是「格式串 ID + 参数」，可读 `Content` 依赖 Logel 闭源解析库与数据库（如 `TraceId2Trace.dll`、`Trace_Data.bin`），没有公开稳定 API。

| 做法 | 结果 |
|------|------|
| `logel2txt playback`（R9.21–R9.26）→ `*_pb` → 导出 | 可与 Export Trace 对齐；不必手点 GUI |
| GUI 打开一次 → 生成 `*_pb\traceview.*` → 再导出 | 同样可对齐 |
| 只解压压缩包 / 只拿 `.logel` 就导出 | 仅明文抽取，常见只覆盖约三成条目 |
| 自行硬调 Logel DLL | 脆、难维护；不建议 |

## Logel 版本（CLI 写出的 PBS）

| 版本 | CLI PBS 记录 | `playback` |
|------|--------------|------------|
| R9.21 / R9.23 | 约 **44B**/条 | 可用（`--logel-root` 优先 R9.21） |
| R9.25 | 约 **52B**/条（44 + 8 尾填充） | 可用 |
| R9.26 | 约 **76B**/条（偏移 24 插入 4B） | 可用 |
| 其它 / 未知 | 自动探测；无法识别则报错 | 可试；或 GUI 生成 `_pb` 后再普通导出 |

须指定 `--logel` / `LOGEL_EXE` 或 `--logel-root` / `LOGEL_ROOT`（无内置默认路径）。R9.23/R9.25/R9.26 CLI 常在写完后 `0xC0000005`；已有 `*_pb\traceview` 仍继续导出。回放后 PBS 异常大（约 >30MB）或无法识别布局会报错退出。

## 现象与处理

| 现象 | 原因 | 怎么处理 |
|------|------|----------|
| 有 `*_pb\traceview.*`，导出完整 | 解码缓存齐全 | 推荐路径；加 `--ue-base` 可对齐设备时钟 |
| 只有非 `_pb` 的 `traceview.*`，行数偏少 | 缓存未充分回放或较旧 | 用 Logel / `playback` 生成或更新 `_pb` 后再导 |
| 只有 `.logel`，内容残缺 | 未走 Logel 解码 | 先回放；不要指望「只解压就完整」 |
| `*_trace.txt` 为 0 字节 | 占位/未导出 | 忽略；用 logel2txt 或 Logel Export Trace |
| 与参考 Export 差「大约等于行数」的字节 | 旧结果可能是 LF，本工具为 **CRLF** | 比内容而非仅比文件大小 |
| TickCount 对、UE Time 对不上 | 未设 `--ue-base` 时 UE 从 `0:00:00.000` 起算 | 从 Export 首行抄 `UE Time`，如 `--ue-base 17:15:12.275` |
| 与 Export 仅少数 Content 大数不同（后段全 0） | CLI `*_pb` 偶发 double 零填充 | 同包若有非 `_pb` traceview，导出会自动补全；仅 CLI 缓存时无法凭空恢复 |
| 目录下多个 `.logel` / 多个 `*_armlog` | 只处理其中一个 | stderr `[WARN] multiple .logel`；改为传入具体 `.logel` 或单个 `*_armlog` |
| 多个 `traceview`（`*_pb` / `_pb1` / 非 `_pb`） | 默认优先精确 `*_pb`，可能与 Export 不一致 | stderr `[WARN] multiple traceview` 并列出；用 `--traceview xxx_pb1`（或缓存目录路径）指定 |
| `.rar`/`.7z` 报 7z not found | 未配置解压工具 | `--7z`，或 `SEVEN_ZIP`/`7Z_EXE`，或 PATH 中的 `7z`；`.zip` 一般不需要 |
| 第一次导出少几百行，开过 Logel 后又齐了 | 当时读的是旧/非 `_pb` 的 `traceview` | 确认选用的是 `*_pb`；非 `_pb` 时 stderr 会有 `[WARN]` |
| 控制台只有 `[DONE]`、管道里看不到告警 | `[WARN]`/`[ERROR]` 在 **stderr** | 重定向时保留 stderr，或 `2>&1` |
| `lines: 0` 且退出码 2 | 未导出到任何数据行（仅表头） | 检查输入；生成 `traceview` 后再导 |
| `playback` 提示未配置 Logel | 未传路径且无环境变量 | `--logel` / `--logel-root`，或 `LOGEL_EXE` / `LOGEL_ROOT` |
| CLI 回放 exit 非 0 | 部分版本写完后偶发崩溃 | 若已写出可识别 `traceview.*`，工具会继续导出 |
| `unsupported PBS layout` | 未知记录长度 | 换 R9.21–R9.26，或 GUI 打开后再导 |
| 想知道日志是哪版 Logel 抓的 | 看主 `*.lst` 的 `Tool Version` | `logel2txt info <armlog|.logel|zip>`；`*_pb*.lst` 是后来打开的版本 |

## 行为预期

- 仅有非 `_pb` 的 `traceview`、尚无 `_pb`：行数可能比 Export Trace 少一批，但已导出部分的 Content / Tick 通常能对上；补上 `--ue-base` 后 UE 也可对齐。
- 已有 `*_pb` 且工具选用该目录：在相同 `--ue-base` 下，行数与体积可与 Export Trace 完全一致。
