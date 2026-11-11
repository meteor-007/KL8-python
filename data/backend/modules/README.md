# backend/modules — 预测模块包

包名保持**扁平英文**（便于 `import` / `python -m` / `find_module_script`）。  
**不要**再物理拆成 `daily/`、`research/` 子目录；分组只看本说明与 [`docs/MODULE_INDEX.md`](../../docs/MODULE_INDEX.md)。

舱位定义对齐 `backend/core/module_gate.py` 的 `lane` 字段。

## daily（日常舱）

日常流水线 / 大屏默认会跑或陈列：

| 目录 | 中文 |
|------|------|
| `sixteen` | 16期中热 |
| `aggregation` | 终审汇总陈列 |
| `gold_pick2` | 定胆选2 |
| `formula_jingle` | 顺口溜口诀 |
| `point_suppression` | 未开点位高压反弹 |
| `datasource` | 数据源 1×2 |
| `point_omission` | 点位+遗漏 |
| `tri_high` | 三高×点位 |
| `prime_composite` | 质合尾数 |
| `psychological_game` | 心理博弈 |
| `multi_resonance` | 多维共振 |
| `trinity` | Trinity 三维融合 |
| `unified_audit` | 统一对账 |
| `kl8_lab` | 点位遗漏实验室 |
| `master_review` | 主复盘引擎入口 |

## research（研究舱）

默认折叠；夜间 / 重跑需 `--with-research`：

| 目录 | 中文 |
|------|------|
| `genetic_algorithm` | 遗传算法 |
| `dtw_matching` | DTW |
| `transformer_attention` | Transformer |
| `matrix_profile` | Matrix Profile |
| `tda_engine` | TDA |
| `linear_algebra` | 线性代数 |
| `random_forest` | 随机森林 |
| `error_correction` | 残差改错 |
| `unified_brain` | 统一决策脑 |

## `_retired/`（已退役代码）

物理在 `_retired/`，一般不再参与主推：

- `models/lstm` — 双层 LSTM  
- `follow` — 条件跟随  
- `gemini_pick2` — Gemini 选2  
- `spatial_points` — 空间重点点位  

逻辑名仍可由 `find_module_script("run_lstm_daily.py")` 等解析到此处。

## 常用命令

```bash
python -m backend.modules.sixteen.run_daily
python -m backend.modules.error_correction.run_daily
python -m backend.pipeline.run_full_pipeline
```

完整对照表见 [`docs/MODULE_INDEX.md`](../../docs/MODULE_INDEX.md)。
