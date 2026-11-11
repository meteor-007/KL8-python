# Cross-Module "Hit Leaderboard" Normalizer Spec (K8-Quant)

Each module review returns a per-period list. Map its row fields to the
canonical schema: period / predicted (main set) / actual / top1.

Legend: actual = the 20 drawn nums for the target period (80-code range).
pick-type = predicts nums to APPEAR; kill-type = predicts nums to EXCLUDE.

## Per-module entries

### trinity (主系统核心) — get_daily_reviews_ledger
- rows_key: `records` (one per period, from reviews/review_*.json)
- row_fields: {period: `period`, predicted: `top12` (top5/top20 also), actual: `actual_numbers`, top1: NONE}
- row_order: newest-first
- predicted_set_description: Top3=3（主口径最优3码；旧 top5/top12 字段同内容兼容）

- cheap_or_expensive: cheap (pure JSON reads)
- notes: review_*.json store HIT COUNTS (top5_hits/top12_hits/top20_hits), not the predicted number lists; get the lists via get_review_detail(period). This is the best per-period history source for the main system.

### lstm — get_lstm_review(n=15)
- rows_key: `rows` -> models/lstm/predictor.py:review_recent
- row_fields: {period: `target`, predicted: `top10`, actual: `actual`, top1: `gold`}
- row_order: oldest-first
- predicted_set_description: Top10 (10 nums) + 金胆 gold single
- cheap_or_expensive: cheap (reads outputs/predictions/prediction_*.txt; no retraining). Caveat: if prediction files missing, rows empty.
- notes: period key is `target`, not `period`.

### spatial_points — get_spatial_points_review(n=30)
- rows_key: `rows` -> core/spatial_points/points_evaluator.py:walk_forward_evaluate
- row_fields: {period: `period`, predicted: `ten`(10)/`core5`(5)/`ext15`(15), actual: `actual_nums`, top1: NONE}
- row_order: oldest-first
- predicted_set_description: ten=Top10 medium picks(10), core5=5 core, ext15=15
- cheap_or_expensive: cheap
- notes: actual_nums = draw sorted_nums. No dedicated top-1; derive core5[0]/order[0].

### follow — get_follow_review(n=30)
- rows_key: `rows` -> core/follow_analysis/follow_reviewer.py:walk_forward_evaluate
- row_fields: {period: `period`, predicted: `rep_picks`(5)/`inf_picks`(6)/`cf_picks`(8)/`inter_picks`, actual: NONE, top1: NONE}
- row_order: oldest-first
- predicted_set_description: rep=重复号Top5(5), inf=推断Top6(6), cf=条件跟随Top8(8), inter=共振交集(variable)
- cheap_or_expensive: cheap
- notes: ACTUAL nums NOT in row (only *_hit_nums). Join to history by period.

### suppression (未开点位反弹) — get_suppression_review(n=30)
- rows_key: `period_logs` -> core/point_suppression/suppression_evaluator.py
- row_fields: {period: `period`, predicted: `top1_num`(1)/`top3_nums`(3), actual: `actual_numbers`, top1: `top1_num`}
- row_order: oldest-first
- predicted_set_description: Top1 rebound candidate(1), Top3 candidates(3)
- cheap_or_expensive: cheap
- notes: pick-type (predicts numbers to reappear). rows_key is `period_logs`, not `rows`.

### kill (已退役 KillSeeker) — 不再提供 get_kill_review
- status: retired / removed
- notes: KillSeeker 模块树与 API 已拆除；勿再依赖 kill_seeker/logs。

### gemini (选2) — get_gemini_review(n=30)
- rows_key: `rows` -> gemini_pick2/engine.py:get_walk_forward_review
- row_fields: {period: `period`, predicted: `def5`(5)/`core4`(4)/`dans`(3), actual: `actual_numbers`, top1: `gold`}
- row_order: oldest-first
- predicted_set_description: def5=终极5码(5), core4=核心4码(4), dans=3胆(gold/silver/bronze)
- cheap_or_expensive: cheap (pure vector scoring; no LLM in review path)
- notes: gold/silver/bronze = dans[0..2]. actual_numbers sorted.

### gold_pick2 (定金选2) — get_gold_pick2_review(n=30)
- rows_key: `rows` -> core/gold_pick2/gold_pick2_reviewer.py:walk_forward_evaluate_pick2
- row_fields: {period: `period`, predicted: `top1_pair`(2), actual: `actual_nums`, top1: `top1_pair`}
- row_order: newest-first (list(reversed(rows)))
- predicted_set_description: 首推 pair(2)=top1_pair/top1_str; singles golden, hot
- cheap_or_expensive: cheap
- notes: .stats holds aggregate rates. warm pool computed but NOT stored as list (only warm_hits/warm_total).

### sixteen (16期中热) — get_sixteen_review(n=30)
- rows_key: `rows` -> backend/core/sixteen_period/sixteen_reviewer.py:run_walk_forward_review
- row_fields: {period: `period`, predicted: `top5`(5)/`top10`(10), actual: `actual_nums`, top1: `top1_str`}
- row_order: newest-first (list(reversed(rows)))
- predicted_set_description: 中热 medium_top5(5), medium_top10(10), gold/silver singles, top1 pair(2)
- cheap_or_expensive: cheap (cache/sixteen_period/latest_review.json used when n==30)
- notes: actual_nums = sorted_nums. med_pool list not stored; only med_pool_hits/med_pool_size.

### aggregation (数据汇总/终审) — get_aggregation_cockpit
- rows_key: NONE. No per-period row list.
- core/aggregation/consensus_engine.py run_aggregation/_run_walk_forward loops periods but only returns aggregate `walk_forward` = {stable_mean_hits, stable_lift, proxy_consensus_mean_hits, proxy_consensus_size, proxy_consensus_lift}.
- row_order: N/A
- cheap_or_expensive: cheap but WRITES output files; pulls subsystem picks.
- notes: Do NOT use for per-period rows; prefer get_daily_reviews_ledger (trinity) or the module reviews. get_aggregation_history_list/_detail return report TEXT.

## Recommended set for fair cross-module 命中率 (hits/len(set) per period)

| module | recommended set | size | top-1 |
|---|---|---|---|
| trinity | top12 | 12 | - |
| lstm | top10 | 10 | gold |
| spatial_points | ten | 10 | (core5[0]) |
| follow | rep_picks (repeat 金胆) | 5 | - |
| suppression | top1_num | 1 | top1_num |
| gemini | def5 | 5 | gold |
| gold_pick2 | top1_pair | 2 | top1_pair |
| sixteen | top3_gold | 3 | gold |
| kill | (retired) | - | - |

## Pick-type vs kill-type (compare differently)
- pick-type (hit = predicted num drawn): trinity, lstm, spatial_points, follow, suppression, gemini, gold_pick2, sixteen.
- kill/exclude-type: KillSeeker 已退役；datasource 等模块自有杀号池仍按各自口径。

## Field-mapping caveats
- follow & jingle rows lack full actual draw set -> join by period from load_history/load_draws_from_history.
- jingle (口诀): rows_key `pairs`; period = `target_issue`; predicted = `recommended` (variable set); actual absent (only hit_numbers); oldest-first.
- spatial_points/gold_pick2/sixteen actual = `actual_nums` (sorted_nums-based).
- lstm period key = `target`; jingle period key = `target_issue`; others = `period`.
- newest-first: trinity, gold_pick2, sixteen. oldest-first: lstm, spatial, follow, suppression, gemini, jingle.
