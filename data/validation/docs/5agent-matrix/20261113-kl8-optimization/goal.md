# Goal · A 项目整理与优化（2026-11-13）

## 一句话需求

以 A 为唯一系统，归档历史一次性脚本、清理可再生成的图片/scratch、整理根目录文档与输出目录，保持冻结核心、预注册模型和 359 项生产测试不变。

## R0 体检

| 项 | 结果 |
|---|---|
| 工作区 | `main...origin/main`，HEAD `5ed8250`，干净 |
| 生产测试（策略 A） | `python -m pytest -q` → **359 passed**（约 52s） |
| 研究测试 | `python -m pytest -q research/tests` → **40 passed** |
| 冻结核心 | `kl8/*.py`、`main.py`、`config.yaml`、`scripts/fusion_engine_template.py`、`scripts/run_daily.py`、`scripts/prereg.py` |
| 可直接清理 | `output/extracted_images` 28M（无代码引用）、`scratch` 1.7M（gitignored）、`__pycache__`/`.pytest_cache` |
| 可归档 | 历史 `fusion_engine_2026297/296/299–302`、`make_fusion_294/295/296`、`patch_*`、`update_fusion_294`、`test_backtest_294` |
| 必须保留 | `fusion_engine_293/294/295/2026298`（测试）、`fusion_engine_template`（冻结）、`make_fusion_daily`（日报入口） |
| G2 | 无 ACL/DDL，N/A |

## G1–G5

| Goal | 验收 | 证据 |
|---|---|---|
| G1 契约保真 | 历史脚本进 `legacy/`；根文档进 `docs/archive/source/`；不删测试依赖 | `contract.md`、diff |
| G2 数据脚本 | 不新增数据脚本；`file/`、canonical 数据不动 | N/A |
| G3 编译与验证 | A 359、research 40、日报入口 `make_fusion_daily --help` | `evidence/phase3-*` |
| G4 独立质检 | 0 High / 0 Medium | `release/review-card.md` |
| G5 发布就绪 | 变更清单、回滚、清理量 | `release/handover.md` |

## 约束

- 不改冻结核心；不改变预注册/生产 Top5。
- 不删除测试依赖脚本和当前日报链路。
- `scratch` 先备份再删除；`output/extracted_images` 确认无引用后删除（可由 `file/` 原始 xls 重导出）；`file/` 输入不动。
- 历史脚本保留在 `legacy/`，不直接丢弃。