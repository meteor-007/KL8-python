# 纯净池高置信定胆 — 方案1 数据驱动权重（L2 逻辑回归）

**日期：** 2026-07-15  
**状态：** 已批准（用户确认「同意」）  
**范围：** 优化评分算法本身；不做过滤提纯层；不上 GBM

## 1. 目标与成功标准

把人工阶跃打分改为可学习权重。Walk-Forward 近 60–80 期达标后再切主推：

| 指标 | 门槛 |
|------|------|
| 码级命中 Lift（相对 25%） | ≥ 1.35x，**或** 相对旧 `score≥3` Lift 提升 ≥ 0.10 |
| 平均每期出码 | 1.5–4（避免长期空仓） |
| 覆盖率 / 样本量 | cover_rate ≥ 0.20 且累计出手 ≥ 30 码 |
| 前视泄露 | 禁止（仅用开奖日以前历史） |

**WF 选参（2026-07-15 实测）：** delta=`0.04`, Lift=`1.21x`, 相对旧规则 ΔLift=`+0.10`, cover=`44.7%`, avg_size=`1.57` → `active=true`。  
推理：优先严格阈值；若当期无码则软回退 `P≥0.25` Top-K（标记 `lr_soft`）。

## 2. 特征（沿用现有）

| 特征 | 说明 |
|------|------|
| `omission` | 遗漏期数 |
| `log_omis` | `log1p(omission)` |
| `consecutive` | 池内连续出现 |
| `dual_source` | 数据2 去点位后是否同出（0/1） |
| `recent_hits` | 近 10 期命中次数 |
| `consec_ge2` | `consecutive >= 2`（0/1） |

样本：每期纯净池内每个号码 1 条；标签 = 当期是否开出。

## 3. 模型与选取规则

- **模型：** L2 逻辑回归（纯 numpy，无 sklearn 依赖）
- **输出：** 单码开出概率 \(P\)
- **高置信定胆：** 池内按 \(P\) 降序，取 \(P > 0.25 + \delta\) 的 Top-K  
  - 默认 K=3，\(\delta\) 由 WF 网格搜索（候选 0.00 / 0.02 / 0.05）
- **权重文件：** `cache/pure_pool_lr_weights.json`  
  （系数、截距、特征名、截点期号、WF 指标、`active` 开关）

## 4. Walk-Forward

- 训窗：50 期已开奖且有跟随/点位的期  
- 测：下 1 期；滚近最多 80 个测试折  
- 对比基线：同折旧规则 `score≥3`

## 5. 集成与改动文件

| 文件 | 变更 |
|------|------|
| `core/pure_pool_lr_trainer.py` | 新建：建样本、训练、WF、写权重 |
| `core/pure_pool_scorer.py` | LR 打分 + 报告影子/主推段 |
| `pipeline/full_report_engine.py` | 沿用 `run_pure_pool_analysis`；`pure_pool_top` 跟随 `active` |
| `cache/pure_pool_lr_weights.json` | 训练产物 |

默认 **影子模式**（`active=false`）：旧规则仍为主推；WF 达标后设 `active=true`。

## 6. 护栏

- L2 强度固定（`C` 等价惩罚）防过拟合  
- 最少有效训练行数门槛，不足则跳过激活  
- 每周或手动可重训：`python core/pure_pool_lr_trainer.py --train`

## 7. 非目标（本期不做）

- 过滤提纯组合（双源+遗漏再砍池）  
- GBM / 神经网络  
- 扩大新特征体系（方案2）
