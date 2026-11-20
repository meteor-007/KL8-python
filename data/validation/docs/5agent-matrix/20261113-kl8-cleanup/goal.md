# Goal · KL8 三项目整合收尾清理（2026-11-13）

## 一句话需求

在不改动 A 冻结核心、不改变预注册模型的前提下，收尾三项目整合后的残留：C 文档路径与实际目录对齐、C 可复现性与测试入口、C 备份清理、A 任务板/输入目录清理评估、B 闲置会话收尾。

## R0 工程就绪体检（2026-11-13）

| 检查项 | A `点位+遗漏号分析` | C `微积分分区` |
|---|---|---|
| R1 构建 | `python main.py --help` exit 0 | `python main.py --help` exit 0 |
| R2 测试（策略 A） | `python -m pytest -q` → **359 passed** | `python -m pytest -q tests` → **40 passed**；根目录 `pytest` 仍收 `legacy_archive/tests`，37 errors |
| R3 环境 | 依赖已装；`daily_all.py` 可运行 | **无 requirements.txt**；本机 numpy 2.4.6 / torch 2.13.0+cpu / openpyxl 3.1.5 / pytest 9.1.1 |
| R4 门禁 | daily_all + git_sync；无 CI | 无 CI；无 pytest 配置 |
| R5 验收 | 测试 + `data_sync` + 预注册状态 | 根目录 pytest、依赖清单、路径一致性 |
| R6 链路 | 数据 → 引擎 → 融合 → 主系统 → 台账 | 研究引擎 → CLI/报告 |

**R0 结论**：
1. C 的 5 个未提交文件均为路径替换（`微积分分区` → `kl8-prediction-engine`），但目录未改名，属于**不一致**，需回退路径。
2. C 根目录 pytest 不可复现，需 `pytest.ini` 固定 `testpaths = tests`。
3. C 无依赖清单，需按本机已装版本补齐，不升级依赖。
4. B 本地副本已删除；两个闲置 Claude 会话仍以 B 为 cwd，需归档收尾。
5. A 的 `file/` 797M，当前 preflight 只选最近期图表；旧期压缩到 A 外 `backup/kl8_inputs/` 后删除，`file/` 保留 2026301–2026303、3 个母版和 294/295/298 的 7 个历史单测 fixture。fixture 工作副本可能被 WPS/Office 重存（OLE +1536 B），归档是原始字节权威副本，测试只要求可读/等价。

**测试策略**：策略 A（自动化测试）。**G2**：无 ACL/DDL，N/A。**自愈上限**：6 轮。

## G1–G5 验收

| Goal | 验收标准 | 证据 |
|---|---|---|
| G1 需求契约保真 | 清理项逐条落到文件/命令；不夹带模型变更 | `contract.md`、diff |
| G2 权限与数据脚本 | 无 ACL/DDL，N/A；数据清理先归档后删除 | `evidence/phase2-*` |
| G3 编译与验证 | A 359 passed；C 根目录 pytest 40 passed；`data_sync` exit 0 | `evidence/phase3-*` |
| G4 工业质检 | 独立审查 0 High / 0 Medium | `release/review-card.md` |
| G5 发布就绪 | 变更清单、验证命令、残留项 | `release/handover.md`、`publish-copy.md` |

## 约束

- 不改 A 冻结核心：`kl8/*.py`、`main.py`、`config.yaml`、融合模板、`run_daily.py`、`prereg.py`。
- 不把 C 的研究信号并入生产 Top5；不改变 `KL8-2026-11-11-001`。
- C 目录不重命名；文档路径回退到实际目录 `微积分分区`。
- A 的 `file/` 旧文件先压缩归档、再删除；保留最近三期与 3 个母版。
- B 的远端仓库保留；本次只归档闲置会话。