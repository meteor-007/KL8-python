# Goal · KL8 三项目整合

## 一句话需求

以 `kl8-point-analysis`（A）为生产/审计核心，统一数据源，吸收 `yuce-kaiyuan`（B）的历史验证资产与 `kl8-prediction-engine`（C）的缩水/复盘/双引擎能力，形成一个可运行、可审计、可自动化的专业 KL8 分析系统；不重复实现已覆盖的能力。

## R0 工程就绪体检（2026-11-13）

| 项目 | R1 构建 | R2 测试 | 结论 |
|---|---|---|---|
| A `点位+遗漏号分析` / `kl8-point-analysis` | `python main.py --help`；`scripts/daily_all.py` | `python -m pytest -q` → **341 passed**（58.6s） | 通过 |
| B `yuce-kaiyuan` | `python kl8_daily.py --no-sync ...`（README） | `python -m pytest -q` → **27 passed**（4.9s） | 通过；数据文件有未提交改动，历史落后 A 一期 |
| C `微积分分区` / `kl8-prediction-engine` | `python main.py --help` exit 0 | `python -m pytest -q` → **40 passed**（11.8s）；根目录误收 `legacy_archive/tests` 的问题已由 `pytest.ini` 修复 | 通过（2026-11-13 收尾后：pytest.ini + requirements.txt 已补） |

**R0 发现的问题**
1. C 的根目录 `pytest` 不可复现；已由 `pytest.ini`（`testpaths = tests`）修复，根目录 `pytest` 现为 40 passed。
2. C 无依赖清单/锁文件；已补 `requirements.txt`（按本机已装版本锁定，未升级依赖）。
3. 数据漂移：A 历史 2123 期（最新 2026302，倒序）；B 2122 期（最新 2026301，倒序）；C 2122 期（最新 2026301，正序，loader 内部会排序）。**2026-11-13 已把 A canonical 回灌到 B/C（均 2123 期，写前备份），并修正 3 期单号差异；B 本地副本随后删除，代码/历史在 GitHub，前瞻记录归档在 A。**
4. 点位：A 的 `data/cache/points_archive.txt` 与 B 的 `daily_points.txt` sha256 相同（337 期，最新 2026302）；A 共享目录的 `daily_points.txt` 哈希不同（需以缓存档案为准）。
5. A 存在活跃预注册 `KL8-2026-11-11-001`；任何触及冻结核心（`kl8/*.py`、`main.py`、`config.yaml`、融合模板、`run_daily.py`、`prereg.py`）的改动都必须显式作废并重新登记。

**证据**
- `evidence/phase0-test-A-*.log`
- `evidence/phase0-test-B-*.log`
- `evidence/phase0-test-C-tests-*.log`
- `evidence/phase0-help-C-*.log`

## G1–G5 验收契约

| Goal | 验收标准 | 证据类型 |
|---|---|---|
| **G1 需求契约保真** | 统一数据契约、CLI 契约、研究对比报告字段 1:1 落地；三个项目能力映射无遗漏 | `contract.md` + 代码 + 测试 |
| **G2 权限与数据脚本** | ACL：N/A（非 B 端 ACL 体系）；数据：只读校验脚本 + 可重复执行的同步说明；不修改共享源文件 | `tools/data_sync.py` + evidence |
| **G3 编译与验证** | 策略 A（自动化）：A 341 + 新增测试全绿；B 27；C 40（根目录 `pytest`） | pytest 日志 |
| **G4 工业质检** | 独立审查零 High/Medium、零红线违规 | `release/review-card.md` |
| **G5 发布就绪** | 变更清单、运行命令、数据源说明、研究引擎开关 | `release/handover.md` + `publish-copy.md` |

## 约束

- **不修改 A 的冻结核心**；新增能力放在 `tools/`、`scripts/`、`tests/`、`docs/`。若必须改核心，先显式作废并重新登记预注册。
- B 作为**历史参考/数据资产**，不合并其重复的 10 模块代码。
- C 作为**可选研究引擎**，通过 `run_pipeline(history_path=..., no_sync=True)` 调用，输出到独立目录，不进入 A 的生产 Top5 与预注册台账。
- 不重命名目录；不做投注建议；所有报告保留免责声明。

## 自愈上限

同一门禁连续 3 轮不通过先区分代码/环境；总轮次上限 6。

## G1–G5 达成（2026-11-13）

| Goal | 结论 | 证据 |
|---|---|---|
| G1 需求契约保真 | 达成 | `contract.md`；`tools/data_sync.py`、`tools/research_bridge.py`；18 项新增测试 |
| G2 权限与数据脚本 | 达成（ACL N/A） | `scripts/data_sync.py`；`evidence/phase0-data-sync-*.json` |
| G3 编译与验证 | 达成 | `evidence/phase5-qa-A-*.log`（353 passed；数据回灌后复跑 **359 passed**）；R0 日志 A/B/C |
| G4 工业质检 | 达成 | `release/review-card.md`（PASS，0 High/0 Medium） |
| G5 发布就绪 | 达成 | `release/handover.md`、`release/publish-copy.md` |
