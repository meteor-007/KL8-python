# Handover · 研究引擎迁移（2026-11-13）

## 1. 结果

C 的研究引擎已 vendored 进 A，A 不再依赖 `C:\D-pan\Dpanqianyi\微积分分区`：

| 项 | 路径 |
|---|---|
| 引擎 | `research/kl8_engine/`（12 个 .py，来自 C `407ba73`） |
| 测试 | `research/tests/`（40 项） |
| CLI | `research/cli.py`（原 C `main.py`） |
| 依赖 | `research/requirements.txt`（`-r ../requirements-dev.txt` + openpyxl/torch） |
| 来源/更新说明 | `research/VENDORED.md`、`research/README.md` |
| LICENSE | `research/LICENSE`（MIT） |

## 2. 入口

```bash
cd "C:/D-pan/Dpanqianyi/点位+遗漏号分析"
python scripts/research_compare.py --period 2026302 --epochs 1
python -m pytest -q research/tests
```

- `research_compare.py` 默认 `--engine-root research/`，内部固定 `no_sync=True`，只写 `output/research/`。
- A 生产测试由 `pytest.ini` 固定为 `tests/`，不加载 torch：`python -m pytest -q` → 359。
- `research/cli.py` 保留 C 原始默认（`kl8_history.txt`、`output/`、同步开启），**不要**把 `--history` 指向 A canonical；详见 `research/README.md`。

## 3. 验证

- A **359 passed**；research **40 passed**。
- 真实对比 2026302 exit 0，Borda 主选 `02 25 36 43 45 47 51 58 63 72 73 75`。
- C 删除后复跑：A 359、research 40、`data_sync` exit 0（B/C 目标自动 skipped）、预注册 active、冻结校验通过。
- 报告头部明确“不进入 A 的生产 Top5、不写入预注册台账”。

## 4. C 本地备份

- `C:\D-pan\Dpanqianyi\backup\kl8-prediction-engine-407ba73.zip`
- 218 个条目，1,177,341 B，`testzip=None`
- SHA-256：`71fffc76ccc9ec803f4f07a3a1d61378eab7a438f81dd1b0d1d6519596621895`
- C 本地目录已删除；GitHub 仓库 `meteor-007/kl8-prediction-engine` 保留（HEAD `407ba73`）。

## 5. G1–G5

| Goal | 结论 | 证据 |
|---|---|---|
| G1 契约保真 | 达成 | `contract.md`、逐字节比对 |
| G2 数据脚本 | 达成（ACL/DDL N/A） | A canonical 数据未动 |
| G3 编译与验证 | 达成 | `evidence/phase3-qa-20261113.log` |
| G4 工业质检 | 达成 | `release/review-card.md`（PASS） |
| G5 发布就绪 | 达成 | 本文件、`publish-copy.md` |

## 6. 回滚

- A：删除 `research/`、`pytest.ini`，把 `scripts/research_compare.py` 默认路径改回外部 C，即可恢复迁移前状态。
- C：从备份 zip 解压，或从 GitHub `meteor-007/kl8-prediction-engine` 重新 clone（`407ba73`）。

## 7. 注意

- 研究依赖 torch 较重，只在研究路径安装；A 生产不需要。
- 不增加第二套每日自动推送；A 的 `daily_all.py` 仍是唯一生产调度。
- 预注册 `KL8-2026-11-11-001` 未变，剩余 298 期。