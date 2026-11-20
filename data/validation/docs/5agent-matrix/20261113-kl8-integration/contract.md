# Contract · KL8 三项目整合

## 1. 架构

```
                ┌──────────────────────────────────────────┐
                │ A: kl8-point-analysis（唯一生产/审计线）  │
                │  kl8/ 13 模块 + H1–H7 + 预注册 + 试验登记 │
                │  main.py / scripts/daily_all.py           │
                └───────────────┬──────────────────────────┘
                                │ 只读统一数据
        ┌───────────────────────┼───────────────────────────┐
        ▼                       ▼                           ▼
┌───────────────┐      ┌──────────────────┐      ┌────────────────────┐
│ Canonical Data│      │ B: yuce-kaiyuan  │      │ C: kl8-prediction- │
│ history/points│      │ 历史参考，不合并 │      │ engine（研究引擎） │
└───────────────┘      └──────────────────┘      └────────────────────┘
                                │                           │
                                └──── research_compare ─────┘
                                     独立对比报告（不进入生产 Top5）
```

**原则**：A 的生产路径与预注册不变；C 只作为可选研究引擎；B 不再运行每日流水线。

## 2. 数据契约

| 项 | 规范 |
|---|---|
| 历史文件 | `date:YYYY-MM-DD,period:NNNNNNN,numbers:NN-NN-...`；每期 20 个 1–80 不重复号 |
| 点位文件 | `date:YYYY-MM-DD,period:NNNNNNN,points:NN NN ...`；每期 20 个 1–80 不重复号 |
| 排序 | 契约不依赖文件顺序；读取方必须按期号排序（C 已内部排序；A 使用降序档案） |
| 期号 | 7 位 `YYYY` + 年内序号；禁止 `period+1` 跨年推断 |
| 权威源 | 历史：A 的 `../Python-Project/data/storage/raw/kl8_history_final.txt`；点位：A 的 `data/cache/points_archive.txt` |
| 只读 | 校验脚本默认只读；`--apply` 才写目标，写前备份 |
| 漂移 | 以“期号集合 + 最新期 + 每期号码集合”比较，不比较行顺序/换行 |

**已知状态（2026-11-13）**：A/C 历史均为 2123 期（最新 2026302，无非法行）；C 保持正序。B 历史在删除本地副本前已回灌并推送（2123 期/2026302），本地副本已删除，代码与历史保留在 GitHub；前瞻记录、meta、协议归档在 A 的 `docs/archive/yuce-kaiyuan/`。A 缓存点位与 B 删除前的点位 sha256 相同（337 期，最新 2026302）。

## 3. CLI 契约

### 3.1 生产线（不变）

```bash
python scripts/daily_all.py --points "01 02 ... 80"
```

行为：`run_daily` → 预注册锁定 → `git_sync` 台账提交/推送。任何新增能力不得改变生产 Top5 或预注册台账。

### 3.2 数据校验

```bash
python scripts/data_sync.py --json
python scripts/data_sync.py --apply --target <path>
python scripts/data_sync.py --apply --kind history --target <path> --order descending|ascending
```

输出 JSON：
- `summaries`：`A_history` / `A_points` / `B_history` / `B_points` / `C_history`，各含 `path`、`count`、`latest`、`oldest`、`invalid_count`、`invalid_samples`；
- `skipped`：目标文件不存在的比较项（如 B 本地已删除），不计入差异；
- `comparisons[]`：`kind`、`source`、`target`、`source_count`、`target_count`、`source_latest`、`target_latest`、`missing`、`extra`、`mismatched`、`source_invalid`、`target_invalid`、`ok`。

非法行（字段缺失/日期格式/号码数量/范围/重复）不参与比较，但会计入 `invalid_count` / `source_invalid` / `target_invalid`，并可能表现为 `missing`——报告需同时看这三个计数。

退出码：`0`=全部一致；`2`=有差异（正常诊断结果）；`1`=执行错误。
`--apply` 需要 `--target`，写前备份并原子替换；默认**拒绝**覆盖 A 的 canonical 冻结数据（会使预注册失效），确需加 `--force`。
`--order`：`preserve`（默认，按源文件字节顺序复制）、`descending`（A/B 倒序）、`ascending`（C 正序）。按序写出时逐行校验、号码升序归一化（保留目标项目原有行格式），遇到非法行立即中止且不改目标文件。

### 3.3 研究对比

```bash
python scripts/research_compare.py --period 2026302 \
    --engine-root "C:/D-pan/Dpanqianyi/微积分分区" \
    --epochs 10 --fusion borda \
    --engine-output-dir output/research/engine_state
```

`--points` 采用严格解析：任何非数字 token、数量不为 20、越界或重复都会报错，不会被静默丢弃。

行为：
1. 读取 A 的 canonical 历史与点位（只读）。
2. 调研究引擎的 `run_pipeline(history_path=<canonical 或裁剪到 < period 的档案>, no_sync=True, points=<20>, output_dir=<engine_output_dir>`)；`engine_output_dir` 默认 `output/research/engine_state`，对比报告写 `output/research/<period>/`。
3. 生成 `research_compare.md` + `research_compare.json`，包含 A Top5、C Borda/weighted 主选、30 码大底、缩水指标、复盘/AUC、警告。
4. **不写入** A 的预注册台账、不改变 A 的生产推荐。
5. 期号：默认用 `next_period_after(最新期, 最新开奖日+1)`（禁止 latest+1）；C 返回的 `target_period` 与请求期不一致时**中止**，避免跨年错标。
6. `engine_output_dir` 默认 `output/research/engine_state`，保存研究引擎的跨期推荐日志以支持复盘；对比报告写 `output/research/<period>/`。

## 4. 研究对比报告字段（G1）

| 字段 | 说明 |
|---|---|
| `period` / `requested_period` | 目标期（二者应一致） |
| `a_top5` / `a_top5_source` | A 主系统五码核心；来源 `snapshot` / `ledger` / `daily_report` / `none` |
| `borda.main_pool` | C Borda 融合主选（12 码） |
| `borda.gold_pool` | C 金胆池 |
| `borda.shrinkage_pool_30` | C 30 码大底 |
| `borda.full_order_top10` / `scores_top10` | C 全序前 10 / 分数前 10 |
| `weighted.main_pool` | C 加权融合主选（若 `comparison=True`） |
| `shrinkage` | 注数、成本、保 5/保 4/保 3 概率、ROI（C 自带口径，仅展示） |
| `review` | 上一期金胆/主选/Top20/30 码命中、AUC |
| `warnings` | C 的告警 |
| `history_used` / `points` | 实际使用的历史文件与点位（历史期是裁剪后的档案） |
| `elapsed_seconds` / `progress` | 耗时与 C 的进度摘要 |
| `disclaimer` | 不构成投注建议（仅 Markdown 页脚；JSON 不含此字段） |

## 5. 预注册策略

- 新增 `tools/`、`scripts/`、`tests/`、`docs/` 不影响 A 的冻结哈希（`kl8/*.py`、`main.py`、`config.yaml`、融合模板、`run_daily.py`、`prereg.py`）。
- 若必须修改上述冻结文件：先 `python scripts/prereg.py invalidate --reason ...`，改完后重建登记，起始期为下一未开奖期。
- 本次整合默认**不改冻结核心**，保留 `KL8-2026-11-11-001` 有效。

## 6. 非目标

- 不把 B 的 10 模块重复代码合并进 A。
- 不把 C 的 Transformer/Bayes 结果直接写入 A 的生产 Top5。
- 不引入未评估的新依赖；C 的 torch 依赖只在研究引擎路径使用。
- 不做投注建议、不承诺收益。

## 7. 验收

- T1：`pytest tests/test_data_sync.py` 通过；`data_sync --json` 输出 A/B/C 差异。
- T2：`pytest tests/test_research_bridge.py` 通过；`research_compare --help` 正常；真实调用（可选）生成报告。
- T3：README/每日指令包含新入口。
- T4：A 341+、B 27、C 40 全绿。
- T5：review-card 零 High/Medium。
- T6：handover/publish 齐备。