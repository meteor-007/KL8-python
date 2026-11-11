# 模块中英文索引（MODULE_INDEX）

> 包目录保持英文扁平；本表解决「中文功能名 ↔ 路径 ↔ 怎么跑」。  
> 舱位对齐 `backend/core/module_gate.py` 的 `lane`。  
> 逻辑名供 `find_module_script("…")` / Web 任务调度使用。

## 流水线（非单模块）

| 中文 | 路径 | 运行命令 | 逻辑名 |
|------|------|----------|--------|
| 每日全流程 | `backend/pipeline/run_full_pipeline.py` | `python -m backend.pipeline.run_full_pipeline` | `run_full_pipeline.py` |
| 夜间闭环 | `backend/pipeline/run_nightly_daily.py` | `python -m backend.pipeline.run_nightly_daily` | `run_nightly_daily.py` |

## daily（日常舱）

| 中文 | 英文目录 | 运行命令 | 逻辑名 |
|------|----------|----------|--------|
| 16期中热 | `sixteen` | `python -m backend.modules.sixteen.run_daily` | `run_sixteen_daily.py` |
| 终审汇总陈列 | `aggregation` | `python -m backend.modules.aggregation.run_daily` | `run_aggregation_daily.py` |
| 定胆选2 | `gold_pick2` | `python -m backend.modules.gold_pick2.run_daily` | `run_pick2_daily.py` |
| 顺口溜口诀 | `formula_jingle` | `python -m backend.modules.formula_jingle.run_daily` | `run_jingle_daily.py` |
| 未开点位高压反弹 | `point_suppression` | `python -m backend.modules.point_suppression.run_daily` | `run_suppression_daily.py` |
| 数据源 1×2 | `datasource` | `python -m backend.modules.datasource.run_daily` | `run_datasource_daily.py` |
| 点位+遗漏 | `point_omission` | `python -m backend.modules.point_omission.run_daily` | `run_omission_daily.py` / `run_point_omission_daily.py` |
| 三高×点位 | `tri_high` | `python -m backend.modules.tri_high.tri_high_engine` | `run_tri_high_daily.py` |
| 质合尾数 | `prime_composite` | `python -m backend.modules.prime_composite.run_daily` | `run_prime_composite_daily.py` |
| 心理博弈 | `psychological_game` | `python -m backend.modules.psychological_game.run_daily` | `run_psychological_game_daily.py` |
| 多维共振 | `multi_resonance` | `python -m backend.modules.multi_resonance.run_daily` | `run_multi_resonance_daily.py` |
| Trinity | `trinity` | （多由汇总/大屏消费） | — |
| 统一对账 | `unified_audit` | `python -m backend.modules.unified_audit.run_daily` | `run_unified_audit_daily.py` |
| 点位遗漏实验室 | `kl8_lab` | `python -m backend.modules.kl8_lab.run_daily` | `run_kl8_lab_daily.py` |
| 主复盘 | `master_review` | `python -m backend.modules.master_review.run_daily` | `run_master_review_daily.py` |
| 逐模块逐期复盘 | `daily_review` | `python -m backend.modules.daily_review.run_daily harvest\|review\|settle [期号]` | `run_daily.py` |
| 跟随统计推演 | `calc_follow_stats.py` | `python backend/modules/calc_follow_stats.py [--window 70] [--pair 2 10 --pair-window 500]` | — |

## research（研究舱）

日常默认不跑；`run_nightly` / `_rerun_predict_modules_today.py` 需 `--with-research`。

| 中文 | 英文目录 | 运行命令 | 逻辑名 |
|------|----------|----------|--------|
| 遗传算法 | `genetic_algorithm` | `python -m backend.modules.genetic_algorithm.run_daily` | `run_genetic_daily.py` |
| DTW | `dtw_matching` | `python -m backend.modules.dtw_matching.run_daily` | `run_dtw_daily.py` |
| Transformer | `transformer_attention` | `python -m backend.modules.transformer_attention.run_daily` | `run_transformer_daily.py` |
| Matrix Profile | `matrix_profile` | `python -m backend.modules.matrix_profile.run_daily` | `run_matrix_profile_daily.py` |
| TDA | `tda_engine` | `python -m backend.modules.tda_engine.run_daily` | `run_tda_daily.py` |
| 线性代数 | `linear_algebra` | `python -m backend.modules.linear_algebra.run_daily` | `run_linear_algebra_daily.py` |
| 随机森林 | `random_forest` | `python -m backend.modules.random_forest.run_daily` | `run_random_forest_daily.py` |
| 残差改错 | `error_correction` | `python -m backend.modules.error_correction.run_daily` | `run_error_correction_daily.py` |
| 统一决策脑 | `unified_brain` | `python -m backend.modules.unified_brain.run_daily` | `run_unified_brain_daily.py` |
| 决策脑自进化 | `unified_brain` | `python -m backend.modules.unified_brain.run_evolution_daily` | `run_evolution_daily.py` |

## retired（已退役，代码在 `_retired/`）

| 中文 | 英文路径 | 运行命令 | 逻辑名 |
|------|----------|----------|--------|
| 双层 LSTM | `_retired/models/lstm` | `python -m backend.modules._retired.models.lstm.run_daily` | `run_lstm_daily.py` |
| 条件跟随 | `_retired/follow` | （一般不跑） | `run_follow_daily.py` |
| Gemini 选2 | `_retired/gemini_pick2` | （一般不跑） | `run_geminixuan2_daily.py` |
| 空间重点点位 | `_retired/spatial_points` | （一般不跑） | `run_points_daily.py` |

## 运维入口（根目录 / scripts）

| 用途 | 路径 |
|------|------|
| Web 服务 | `python run_server.py` 或 `start_web.bat` |
| Windows 服务壳 | `windows_service.py` → `scripts/ops/` |
| 日更防重 | `daily_run_guard.py` → `scripts/daily_run_guard.py` |
| 录入点位 | `input_daily_points.py` → `scripts/input_daily_points.py` |
| 组装前端 | `python scripts/build_web.py` |
| 重跑当期模块 | `python scripts/_rerun_predict_modules_today.py` |
| 一次性迁移脚本 | `archive/scratch/migration_scripts/`（勿当日常入口） |

## 活数据

一律使用项目根 **`storage/`**（`raw` / `cache` / `outputs` / `reports` / `reviews` / …）。  
不要写 `backend/storage` 或 `backend/outputs`（旧残留已迁 `archive/scratch/legacy_backend_data/`）。

## 逐模块逐期复盘 (daily_review) 口径说明

大白话：各模块每天各写各的产物、格式各异，过去只能逐个翻文件看"这期中了几码"。

- **harvest（开奖前）**：按声明式清单从各模块**真实产物**抽取当期推荐号码，写入追加式前瞻账
  `storage/cache/paper_trading_modules.jsonl`（走 `core.module_gate.record_module_picks`，幂等）。
  因果要点：该账是 append-only，**覆盖式落盘**（如各研究舱 `*_latest.json`）的模块由此获得按期历史，
  不必改造各模块自身的落盘逻辑。
- **review / settle（开奖后）**：补 `actual/hits` 后输出 `storage/reports/复盘明细_<期号>.md`
  与 `storage/reviews/period_review/review_<期号>.json`，包含逐模块命中明细、滚动口径对照
  （同 `module_ledger_report`：lift/CI/p/BH-FDR）、以及**无法复盘模块的如实清单**。
- **期号语义**：`period` = **被预测期**（不是号码来源期）。
- **口径对齐**：已由汇总引擎记账的模块（点位反弹=首重 1 码、顺口溜=推荐 7 码、定金选2=Top5 配对全号…）
  收割时使用**同一口径**，避免同一模块两套口径导致 Lift 漂移。
- **防污染**：覆盖式产物必须自证目标期一致才收（不符则记为"未刷新"跳过）；已对账（已开奖）的账禁止重写，
  口径修正需显式点名 `--refresh <模块id>`。
- **驱动位置**：`run_full_pipeline` 任务 3.952（收割）与 3.956（复盘）。
- **已纳入账本的模块数**：34 个（含 `follow_rank` 跟随统计推演 —— 该模块 1码版过去用 Σw 当试验数会制造假显著，
  已于 2026-09-24 改为精确加权伯努利检验 + BH-FDR，产物落 `storage/outputs/follow_rank/follow_rank_<期号>.json`，
  由 `run_full_pipeline` 任务 3.951 生成）。
  **窗口口径**：1码 `--window` 默认 **70 期**；2码 `--pair-window` 默认 **500 期**
  （双号同出是低频事件，70 期窗口样本常只有个位数——示例 `12-74` 70期仅 8 次、500期 38 次、全量 137 次，
  70 期下 2码基本没有统计功效，故单独放宽）。两者填 `0` 均为全量历史。
  注意 1码与 2码窗口不同是**有意为之**，跨模式比较时先确认窗口。
