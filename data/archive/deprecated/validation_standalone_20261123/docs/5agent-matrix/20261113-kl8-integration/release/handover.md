# Handover · KL8 三项目整合（2026-11-13）

## 1. 本次交付

以 `kl8-point-analysis`（A）为唯一生产/审计线，新增两个**不触碰冻结核心**的能力：

| 能力 | 文件 | 作用 |
|---|---|---|
| 统一数据校验 | `tools/data_sync.py`、`scripts/data_sync.py` | A/B/C 历史与点位只读比对；差异清单；可选 `--apply`（默认拒绝覆盖 A canonical） |
| C 研究引擎桥接 | `tools/research_bridge.py`、`scripts/research_compare.py` | 调 C 的 Transformer + 贝叶斯 + Borda + 30 码缩水，输出独立对比报告 |
| 文档 | `README.md` §12、`每日指令.txt` 第 8 步 | 入口、依赖、边界说明 |
| 测试 | `tests/test_data_sync.py`、`tests/test_research_bridge.py` | 18 项新增测试 |
| 过程产物 | `docs/5agent-matrix/20261113-kl8-integration/` | goal / contract / taskboard / evidence / release |

## 2. 生产命令（不变）

```bash
python scripts/daily_all.py --points "01 02 ... 80"
```

流程：前置检查 → 引擎 → 融合研报 → 主系统 → 模块明细 → 预注册锁定 → 台账 git 提交/推送。

## 3. 新增命令

```bash
# 数据一致性（退出码 0=一致 / 2=有差异 / 1=错误）
python scripts/data_sync.py --json

# C 研究引擎对比（独立输出，不进入生产 Top5 / 预注册）
python scripts/research_compare.py --period 2026302 --epochs 10
```

前置条件：
- 目标期点位已在档案中（先执行每日第 1 步）。
- 研究路径依赖 C 目录的 `torch` / `openpyxl`；生产路径不需要。

## 4. 数据状态（2026-11-13）

| 文件 | 期数 | 最新 | 说明 |
|---|---|---|---|
| A history | 2123 | 2026302 | 权威源 |
| A points | 337 | 2026302 | 与 B 点位 sha256 相同 |
| B history | 2123 | 2026302 | 已回灌并推送；本地副本 2026-11-13 删除，归档在 A |
| C history | 2123 | 2026302 | 已回灌（正序），写前备份 |

**2026-11-13 回灌**：B/C 原先各落后 1 期，且 2023179 / 2024295 / 2025037 与 A 各差一个号
（A 分别为 26 / 4 / 36，B/C 为 24 / 44 / 34），已按 A 权威源改正。写出时按期号重排并把号码
升序归一化，保持 B/C 原有格式；B 只新增 2 行（2026301 在 B 工作区未提交、2026302 为新期），
C 只新增 1 行，其余为 3 行号码修正。备份：
`yuce-kaiyuan/kl8_history_final.txt.<时间戳>.bak`、`微积分分区/kl8_history.txt.<时间戳>.bak`。
回灌后 `data_sync.py --json` 退出码 0，三组比较（B 历史 / C 历史 / B 点位）全部 `ok=true`。

B 的 5 行前瞻记录（2026300–2026302，含 2 行未提交内容）、meta 和预注册协议已归档到
`docs/archive/yuce-kaiyuan/`，附来源、SHA-256 和行级清单；归档副本与源文件字节一致。
B 本地副本已于 2026-11-13 完全删除（内容与空目录均已移除）；删除前已结束占用该目录的闲置 Claude 会话进程，会话记录仍可恢复。

## 5. 预注册

- 登记：`KL8-2026-11-11-001`（main / top5_lift / 300 期 / 起始 2026301）
- 状态：active；冻结校验通过
- 本次新增文件均不在冻结哈希范围（`kl8/*.py`、`main.py`、`config.yaml`、融合模板、`run_daily.py`、`prereg.py` 均未改）

## 6. 验证

- A 全量：**359 passed**
- 新增定向：**18 passed**（`tests/test_data_sync.py` 11 + `tests/test_research_bridge.py` 7）
- `data_sync.py --json`：exit 0（A/B/C 历史与点位全部一致）
- B 回归：**27 passed**；C 回归：**40 passed**（根目录 `pytest`，已由 `pytest.ini` 固定）
- 独立质检：**PASS**（0 High / 0 Medium；7 Low 非阻塞）
- 研究对比实跑：2026301/2026302 均生成报告；2026301 的 A Top5 从台账取到 `03 44 11 16 56`

## 7. 已知限制

1. C 的 `target_period` 内部使用 `latest+1`；桥接默认用 A 的跨年规则并在不一致时中止。跨年首期研究对比需先修 C 的期号推断。
2. B/C 历史已于 2026-11-13 回灌到 A canonical（2123 期）；回灌前备份保留在各自目录，确认无误后可人工清理。回灌只改数据，不改 B/C 代码；B/C 的历史文件已提交并推送（B `a4cb2de` / C `7b29e4b`），B 的其余工作区改动未提交。B 的前瞻记录、meta、协议已归档到 `docs/archive/yuce-kaiyuan/`；B 本地副本已完全删除。
3. `data_sync --apply` 默认拒绝覆盖 A canonical；确需覆盖需 `--force`，但会使预注册失效。
4. 研究结果不进入生产 Top5 / 台账；不要用研究引擎输出替代预注册推荐。

## 8. 回滚

本次为**纯新增**（tools/scripts/tests/docs + README/每日指令文字）；删除新增文件即可回滚，生产路径与预注册不受影响。