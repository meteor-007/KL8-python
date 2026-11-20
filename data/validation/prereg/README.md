# 预注册与前瞻锁定

对应复盘报告第 6 节。目的不是“提高命中率”，而是让结论**可被证伪**：
先写死假设、主端点、样本量与停止规则，再在新数据上做唯一一次正式分析。

## 文件

| 文件 | 作用 |
|---|---|
| `prereg/active.json` | 当前登记：假设、主端点、计划期数、冻结的代码/配置/数据前缀 |
| `data/state/prereg_ledger.jsonl` | 只追加的锁定记录：每期开奖前锁定的 Top5 与候选池 |
| `data/state/last_prediction_main.json` | 主系统当期预测快照（由 `main.py analyze` 写出） |
| `data/state/last_prediction_fusion.json` | 融合引擎当期预测快照（由引擎写出） |

## 命令

```bash
# 1. 建立登记（冻结当前代码/配置/数据前缀）
python scripts/prereg.py create \
    --id KL8-YYYY-MM-DD-001 \
    --model main \
    --periods 300 \
    --start 2026300 \
    --hypothesis "主系统 Top5 相对命中率高于 Hypergeom(80,20,5) 基线"

# 2. 每日运行会自动锁定（run_daily.py 检测到 active.json 后调用）
python scripts/run_daily.py --points "..."

# 也可手动锁定（必须在开奖前）
python scripts/prereg.py lock --model main --model fusion

# 3. 查看进度（不输出正式 p 值）
python scripts/prereg.py status

# 4. 达到计划期数后，做唯一一次正式分析
python scripts/prereg.py evaluate
# 未到期时只允许探索性分析（明确标注“非预注册”）
python scripts/prereg.py evaluate --exploratory

# 5. 手动作废
python scripts/prereg.py invalidate --reason "配置变更"
```

## 规则

1. **单主端点、单次最终分析**：`status` 只显示进度，不显示 p 值；避免每日窥视。
2. **冻结**：登记时保存代码哈希、配置哈希，以及截至最新开奖的数据前缀哈希。
   任一变化 → `lock` 拒绝并把登记标为 `invalidated`。
3. **禁止补锁**：目标期一旦进入开奖档案，`lock` 直接拒绝，防止事后挑选。
4. **只读评估**：`evaluate` 只读锁定记录与开奖档案，不重新选号、不改配置。
5. **两个基线**：主端点同时报告同池随机与全 80 随机；效应量、CI、p、T、MDE 一并给出。

## 当前登记

- 登记号：`KL8-2026-11-10-002`（`001` 因实施剩余整改已作废）
- 模型：主系统（13 模块 + H1–H7）
- 主端点：Top5 每期命中数相对 `Hypergeom(80,20,5)` 期望 1.25 的 lift
- 计划期数：300（起始 2026300）
- 分析：final_only（到期前不做正式检验）
- 计划 MDE：约 +10.8%（300 期，单侧 α=0.05，80% 功效）

> 本机制不构成投注建议。快乐8 每期开奖为独立随机事件。

## 配套：试验登记（研究自由度）

预注册只冻结“从现在开始”的实验；过去在同一份档案上试过的 11 个方法、7 维权重、
门控、护栏、阈值与十余项修复，属于已经花掉的研究自由度。它们记录在：

- `prereg/trials.jsonl`（只追加）
- `scripts/trials.py`（CLI）
- `prereg/TRIALS.md`（说明与当前汇总）

```bash
python scripts/trials.py summary        # Bonferroni α / 期望最大 z / 观测最好 z
python scripts/trials.py registration   # 对照预注册：登记前/后试验数
```

当前登记前 38 个试验，登记后 0 个；总体 E[max z]=2.142，观测最好 z=1.642，
与零分布最大 z 一致（噪声）。
