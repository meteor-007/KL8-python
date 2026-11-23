# 体检卡 · 研究引擎迁移

## 结论：PASS

独立审查：**0 High / 0 Medium / 6 Low**；Low 已在发布前逐项收紧。

## 已验证

- `research/kl8_engine/` 12 个 .py 与 C `kl8_engine/` SHA-256 全部一致；`research/tests/` 7 个文件与 C `tests/` 一致；`research/cli.py` 与 C `main.py` 一致；LICENSE 已复制。
- A 全量 **359 passed**；`research/tests` **40 passed**；`research/cli.py --help`、`research_compare --help` exit 0。
- 真实 `research_compare.py --period 2026302 --epochs 1` exit 0，报告头部声明“不进入 A 的生产 Top5、不写入预注册台账”。
- 默认引擎路径 `ROOT/research`；运行实测导入 `research/kl8_engine/__init__.py`。
- 冻结核心零改动；C 删除后 A 359、research 40、data_sync exit 0、预注册 active 均正常。
- 迁移未夹带 `legacy_archive`、daily 自动推送、重复历史/输出；无密钥/PII；研究依赖独立。
- C 本地备份：`backup/kl8-prediction-engine-407ba73.zip`（218 条目，testzip 通过，1,177,341 B）。

## Low 闭环

| 项 | 处理 |
|---|---|
| 每日指令仍写“调 C 引擎” | 已改为本地 `research/kl8_engine` 与 `research/requirements.txt` |
| 报告仍写“C 30 码/C 口径” | 已改为“研究 30 码/研究口径” |
| `output/research/c_engine` 命名 | 默认改为 `output/research/engine_state` |
| vendored CLI 可能写 A 根 | `research/README.md` 明确警告，正式入口用 `research_compare.py`（强制 `no_sync=True`） |
| 发布三件套缺失 | 已补 review-card / handover / publish-copy |
| README 未引用迁移文档 | 已补 `research/VENDORED.md` 与迁移矩阵路径 |

## 结论

研究引擎已自包含进 A；C 本地目录已备份并删除，GitHub 仓库保留作历史备份。