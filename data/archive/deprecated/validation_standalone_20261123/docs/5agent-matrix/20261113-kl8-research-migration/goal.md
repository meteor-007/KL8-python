# Goal · KL8 研究引擎迁移（2026-11-13）

## 一句话需求

把 C `微积分分区` 的研究引擎（`kl8_engine/` + 40 测试）vendored 进 A `research/`，让 A 的研究对比默认使用本地引擎，验证后可归档/删除 C 本地目录。

## R0 体检

| 项 | 结果 |
|---|---|
| C 引擎范围 | `kl8_engine/` 360K，自包含；仅依赖 numpy / openpyxl / torch（+ 标准库） |
| C 测试 | `tests/` 40 项，使用临时目录，可迁移 |
| A 生产测试 | `pytest -q` → 359 passed（`pytest.ini` 固定 `testpaths = tests`） |
| A 研究桥接 | `tools/research_bridge.py` 通过 `engine_root/kl8_engine/pipeline.py` 加载；默认路径可切到 `research/` |
| 运行依赖 | A 生产不引入 torch；研究依赖放 `research/requirements.txt` |
| G2 | 无 ACL/DDL，N/A |

## G1–G5

| Goal | 验收 | 证据 |
|---|---|---|
| G1 契约保真 | 只迁引擎/测试/CLI/license；不迁 legacy、daily、重复数据 | `contract.md` |
| G2 数据脚本 | 不新增迁移脚本；历史数据继续用 A canonical | N/A |
| G3 编译与验证 | A 359；research 40；真实 `research_compare` exit 0 | `evidence/phase3-*` |
| G4 独立质检 | 0 High / 0 Medium | `release/review-card.md` |
| G5 发布就绪 | 变更清单、回滚、C 归档说明 | `release/handover.md` |

## 约束

- 不改 A 冻结核心；不改变预注册模型。
- 研究依赖可选，不进入 A 生产 requirements。
- C 本地目录先备份再删除；C GitHub 仓库保留。
- 不迁移 C 的 daily/auto-push、legacy_archive、重复历史文件。