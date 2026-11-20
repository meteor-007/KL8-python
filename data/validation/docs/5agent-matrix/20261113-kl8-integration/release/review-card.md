# 独立质检体检卡 · KL8 三项目整合（2026-11-13 · 复审 rev3）

审查角色：审大关（review-audit，只读）
审查范围：`tools/data_sync.py`、`scripts/data_sync.py`、`tools/research_bridge.py`、`scripts/research_compare.py`、`tests/test_data_sync.py`、`tests/test_research_bridge.py`、`docs/5agent-matrix/20261113-kl8-integration/contract.md`、`README.md` §12、`每日指令.txt` 第 8 步、`output/research/2026301/`。
说明：本卡基于修复后的当前文件重新复核，不沿用 rev1/rev2 结论；复审过程未重跑 C 引擎。

## 结论

**PASS**（0 High / 0 Medium / 0 Low）

rev2 遗留的 7 个 Low 已全部修复并有代码/测试/探针证据；上轮 3 个 Medium 保持 fixed。冻结核心未改、预注册 `KL8-2026-11-11-001` 冻结校验通过、研究结果仍不进入生产 Top5/台账。可进入发布收尾。

## 上轮 3 个 Medium（回归复核）

| 上轮问题 | 结果 | 证据（文件:行） |
|---|---|---|
| Medium#1 跨年期号：禁止 latest+1；C 返回期号不一致须中止 | **fixed（保持）** | `tools/research_bridge.py:26` `next_period_after`；`:89-96` 默认目标期；`:150-155` `_assert_period`；`:366` 运行后断言；`tests/test_research_bridge.py:90-94,107-110`（2026351→2027001、2027001 vs 2026352 中止） |
| Medium#2 A Top5：snapshot → 台账 → 日报，写入 JSON | **fixed（保持）** | `tools/research_bridge.py:194-216`（台账）、`:218-238`（日报）、`:241-263`（`_a_top5` 顺序）；`:369-371` 写 `a_top5`/`a_top5_source`；`output/research/2026301/research_compare.md` 显示 `03 44 11 16 56`，JSON `a_top5_source="ledger"`；探针 2026302 走 snapshot |
| Medium#3 契约一致性 | **fixed（保持）** | `contract.md:51-62` data_sync schema/退出码；`:65-82` 研究行为与 `engine_output_dir` 语义；`:85-100` 报告字段与实际 JSON 一致（含 `disclaimer` 仅 Markdown 页脚说明） |

## 本轮 7 个 Low 逐项复核

| # | 上轮 Low | 结果 | 证据（文件:行） |
|---|---|---|---|
| L1 | contract §3.3 步骤 2 的 output_dir/历史源与实现矛盾 | **fixed** | `contract.md:74` 补 `--points` 严格解析；`:78` 步骤 2 改为 `history_path=<canonical 或裁剪档案>`、`output_dir=<engine_output_dir>`；`:82` 明确引擎目录/报告目录分工 |
| L2 | `ResearchConfig` 默认值字面量、`_top_scores` 的 10 未常量 | **fixed** | `tools/research_bridge.py:38` `DEFAULT_TOP_K`；`:49-52` dataclass 默认值引用 `DEFAULT_*`；`:131,146` `_top_scores` 使用 `DEFAULT_TOP_K` |
| L3 | `--points` 非法 token 被静默丢弃 | **fixed** | `scripts/research_compare.py:27-37` `_strict_points`（非数字 token/数量≠20/越界/重复均报错），`:80-84` 返回 exit 1；探针：20 合法+`99`→“21 个号码”，20 合法+`abc`→“包含非法 token”，均 exit 1 |
| L4 | 中止路径、`_a_top5` 回退、`--apply` 无 target 无单测 | **fixed** | `tests/test_research_bridge.py:107-110`（中止）、`:113-133`（ledger/日报回退）；`tests/test_data_sync.py:116-119`（`--apply` 无 target exit 1）；定向 14 passed |
| L5 | Markdown“数据源”在历史期显示 canonical 而非裁剪档案 | **fixed** | `tools/research_bridge.py:283` 改为 `summary.get('history_used', cfg.history_path)` |
| L6 | REQUIRED/date 校验未使用，非法行未进入比较结论 | **fixed** | `tools/data_sync.py:35-57` `_parse_line`（REQUIRED + `DATE_RE` + 号码校验）；`:106-141` `CompareResult.source_invalid/target_invalid` 且 `ok` 纳入；`:144-164` compare 统计；`:181-190` render 输出非法行列；`contract.md:58-60` 同步 |
| L7 | `--apply` 成功提示固定“已备份”、失败不清理 `.tmp` | **fixed** | `tools/data_sync.py:193-211` `apply_copy` 返回是否备份、异常时 `tmp.unlink`；`scripts/data_sync.py:57-63` 按目标存在与否显示“已备份/新建”；探针：新目标 `backed_up=False`、已有目标生成 `.bak`、无 `.tmp` 残留，CLI 提示“目标为新建” |

## 新发现

本轮未发现新的 High / Medium / Low 问题。修复未改变生产路径，未引入新依赖。

## 验证命令与结果

| 命令（cwd=仓库根） | exit | 结果摘要 |
|---|---|---|
| `python -m pytest -q tests/test_data_sync.py tests/test_research_bridge.py` | 0 | `14 passed in 1.60s`（新增中止、`_a_top5` 回退、`--apply` 无 target 用例） |
| `python -m pytest -q`（全量 A） | 0 | `355 passed in 51.97s` |
| `python scripts/data_sync.py --json` | **2** | A 历史 2123 期/最新 2026302；B、C 各 2122 期/最新 2026301；两条 history 比较均 missing `[2026302]`、extra `[]`、mismatched `[2023179, 2024295, 2025037]`、`source_invalid/target_invalid=0/0`；points 337/337、`ok=true`。差异退出码 2 为契约设计行为 |
| `python scripts/prereg.py status` | 0 | active；已锁定/已开奖/剩余 2/2/298；**冻结校验：通过** |
| `python scripts/research_compare.py --points "<19 点>" / "20 合法点+99" / "20 合法点+abc"` | 1 / 1 / 1 | 分别提示“必须恰好 20 个”“解析出 21 个号码”“包含非法 token” |
| `python scripts/research_compare.py --help` | 0 | 参数完整，含 `--engine-output-dir` |
| 只读取数探针（不跑 C） | 0 | 2026301 → `([3,44,11,16,56], "ledger")`；2026302 → `([57,11,16,56,73], "snapshot")`；`_assert_period(2027001, 2026352)` 正确抛错 |
| `apply_copy`/CLI 探针（临时目录） | 0 | 新目标 `backed_up=False` 且提示“目标为新建”；已有目标生成 `.bak`、内容替换成功；无 `.tmp` 残留 |
| `output/research/2026301/` 只读检查 | — | 报告/JSON 为修复后产物（未在本轮重跑 C）：`period=requested_period=2026301`、`a_top5_source=ledger`、Markdown 顶部数据源取 `history_used` |
| `git status --short` + `git diff --stat <冻结清单>` | 0 | 基线提交 `28528db`；本轮改动仅 contract.md、tools/scripts/tests 6 个文件（+新增 evidence）；冻结核心 `kl8/*.py`、`main.py`、`config.yaml`、`scripts/run_daily.py`、`scripts/prereg.py`、`scripts/fusion_engine_template.py` 及 `data/state/`、`prereg/` 均无改动 |

## 红线检查

| 项 | 结论 |
|---|---|
| 零 High/Medium/Low | 通过（0/0/0） |
| 冻结核心 | 通过：无 diff；`prereg.py status` 冻结校验通过 |
| 预注册台账 | 通过：`data/state/prereg_ledger.jsonl`、`prereg/` 无改动；研究桥接只读台账 |
| 生产隔离 | 通过：研究结果仅写 `output/research/`，不进入生产 Top5/台账 |
| 空安全/资源/密钥/路径 | 通过：缺失文件/快照均有兜底；`.tmp` 异常清理；无未关闭句柄；未见 PII/密钥；`--apply` 默认拒绝 canonical 冻结数据，`--force` 为显式逃生口 |

## 未覆盖 / 待人工确认

1. 本次复审未重跑 C 引擎（避免再次写入 `output/`）；`output/research/2026301` 采用既有修复后产物核对。生产解释器需已安装 C 的 `torch/openpyxl`。
2. 跨年边界：C 内部 `target_period = latest+1`（`kl8_engine/data.py:87-89`），年末默认目标期 2027001 会触发桥接中止（exit 1）。这是 Medium#1 要求的保护行为；若需跨年出研究报告，需 C 侧修复期号推断。
3. B/C 历史落后 1 期、3 期号码差异属数据漂移，业务侧确认是否回灌；不影响研究桥接（读取 A canonical）。
4. 当前修复为工作区未提交改动（基线 `28528db`），发布时按 release-ops 流程提交。