# Taskboard · 20261113-kl8-integration

> 写作用域不重叠；依赖阶段串行。状态：todo / doing / done / blocked。

| ID | 任务 | 输入 | 交付物 | 写作用域 | 验收命令 | 依赖 | 状态 |
|---|---|---|---|---|---|---|---|
| T1 | 统一数据契约与只读校验 | A/B/C 历史与点位 | `tools/data_sync.py`、`scripts/data_sync.py`、`tests/test_data_sync.py`、数据清单 evidence | `tools/`、`scripts/data_sync.py`、`tests/` | `python -m pytest -q tests/test_data_sync.py`；`python scripts/data_sync.py --json` | 无 | done |
| T2 | C 研究引擎桥接 | C `kl8_engine.pipeline.run_pipeline` 接口 | `tools/research_bridge.py`、`scripts/research_compare.py`、`tests/test_research_bridge.py` | `tools/`、`scripts/research_compare.py`、`tests/` | `python -m pytest -q tests/test_research_bridge.py`；`python scripts/research_compare.py --help` | T1 | done |
| T3 | 统一文档与入口 | 契约、T1/T2 | README 整合章节、每日指令补充、`docs/.../contract.md` | `README.md`、`每日指令.txt`、`docs/` | 文档字段审查 | T1,T2 | done |
| T4 | QA 全量回归 | T1–T3 | 测试日志 evidence | 只读 + `evidence/` | A `pytest -q`；B `pytest -q`；C `pytest -q` | T1–T3 | done |
| T5 | 独立质检 | 全量 diff | `release/review-card.md` | `docs/.../release/` | 体检卡零 High/Medium | T4 | done |
| T6 | 发布就绪 | G1–G4 | `release/handover.md`、`release/publish-copy.md` | `docs/.../release/` | G1–G5 逐项证据 | T4,T5 | done |
| T7 | B/C 历史回灌 | A canonical history | B/C 历史对齐（2123 期 / 2026302）+ 备份 | B/C 数据文件（不提交） | `python scripts/data_sync.py --json` exit 0；B 27 / C 40 | T1 | done |
| T8 | B 前瞻记录归档 | B `pre_registered_20261110.jsonl` | `docs/archive/yuce-kaiyuan/forward_test/`（源文件 + README） | `docs/archive/` | SHA-256 与源文件一致；5 行 JSONL 可解析 | T7 | done |
| T9 | 删除 B 本地副本 | B 已推送/已归档资产 | B 内容与空目录均已删除 | `C:\D-pan\Dpanqianyi\yuce-kaiyuan` | 路径不存在；无进程 cwd 指向 B | T8 | done |

## 能力映射（防止重复实现）

| 能力 | 归属 | 整合策略 |
|---|---|---|
| 20 点位 → 环形三元组 → 10/13 模块 → H1–H7 | A（B 为其前身） | 保留 A；B 仅作历史参考，不合并重复模块 |
| 严格 walk-forward / BH-FDR / 预注册 / 试验登记 | A | A 为唯一生产/审计线 |
| 330 期点位档案 / 200 期前瞻 | B | 数据资产：A 已持有同源 337 期档案；B 不再跑每日流水线 |
| Transformer + 贝叶斯图谱 + Borda 双融合 | C | 以“研究引擎”方式桥接，输出独立对比报告，不进入 A 的生产 Top5 |
| 30 码级联缩水 / 每日复盘 / 排序 AUC | C | 研究对比报告的组成部分；是否进入生产需另行预注册评估 |

## 证据规范

- 每条证据：命令 + cwd + exit code + 关键输出 + 结论，落盘 `evidence/`。
- 测试日志命名：`phase0-test-*`、`phase4-qa-*`。
- 不把大段日志贴进聊天，回答中引用路径。