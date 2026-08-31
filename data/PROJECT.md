# Project: K8-Quant Prediction Subsystems Refactoring & E2E Delivery

## Architecture
快乐8智能量化操盘系统 (K8-Quant) 全系统预测号码模块精细化重构体系包含：
1. **数据与算法层 (Backend Engines)**: 空间点位、高压反弹、定金选2、Gemini选2、顺口溜、跟班跟随、双层LSTM、16期中热、KillSeeker杀号、三维主系统、终审共识等 10 大子系统。
2. **服务聚合与 API 层 (Backend Data Service & API Server)**: `backend/api/data_service.py` 与 `backend/api/api_server.py`，对外提供 40+ 个 RESTful API 接口，并输出 `/api/quant/modules-overview` 大盘聚合快照。
3. **交互与展现层 (Frontend Vue & Cyber Themes)**: `frontend/static/index.html`, `frontend/static/js/app.js`, `frontend/static/css/cyber_theme.css`，支持 10 大子系统预测大盘卡片、15 个专属驾驶舱、6 大赛博主题热切换与 ECharts 图表换肤。
4. **验证与测试层 (4-Tier E2E Testing Pyramid)**: 覆盖 Tier 1 (功能契约)、Tier 2 (边界容错与自愈)、Tier 3 (跨系统协同)、Tier 4 (真实生产负载与全量入口脚本) 及 40/40 RESTful API 100% PASS 自动化验收套件。

---

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | 空间重点点位分析三联结构与4维特征 | 输出前5核心点位，含【左邻+核心+右邻】三联邻域联动结构与4维量化特征(gap, freq, reg_heat, neb_heat, score)，精选10码大名单与Top3聚集带 | M1 | R1 Requirement |
| 2 | 未开点位高压反弹三连伴生与压制系数 | 输出Top3弹簧回补码，含【前一位+反弹码+后一位】三连伴生区间、压制系数k、反弹评分与S/A/B置信评定 | M1 | R1 Requirement |
| 3 | 定金选2双重金胆与Top3黄金搭档卡 | 输出双重金胆(首席+活跃)及Top3黄金连体搭档卡(同出次数、协同得分、图卷积权重与特征标签) | M1 | R1 Requirement |
| 4 | 顺口溜口诀触发文本与命中统计 | 展示触发的具体口诀文本(如“见28带09，隔期寻36”)、带出推荐码及FDR/OOF命中统计 | M1 | R1 Requirement |
| 5 | 跟班跟随三路推演与交集共振 | 同时输出重复号Top5、推演跟随Top6、多窗条件跟随Top8及多路交集共振码 | M1 | R1 Requirement |
| 6 | 深度模型与全子系统特征数据补齐 | 双层LSTM、16期中热、KillSeeker杀号、三维主系统、终审共识补齐金银铜胆、防线码、排雷阵地、安全保留码、动态出入窗、多路投票热榜及样本外实战提升度(Lift) | M1 | R1 Requirement |
| 7 | Web 前端 10 大子系统大盘卡片重构 | 在 `index.html` 与 `app.js` 中重构 10 大子系统预测大盘为高信息密度交互大盘，包含核心号码、算法特征面板、提升度指标、研判结论及驾驶舱入口 | M2 | R2 Requirement |
| 8 | 6 大赛博主题适配与抗畸变 | 适配深邃赛博、黑金尊享、极光星河、量子翡翠、深空暗夜、皓月雅白 6 大主题，确保无文字折行、无布局变形、高对比度与 ECharts 联动换肤 | M2 | R2 Requirement |
| 9 | 40+ RESTful API 自动化测试 100% PASS | 全系统 40+ 个核心 RESTful API 接口自动化测试，数据字段 100% 真实推演填充，0 异常，通过率 100.0% | M3 | R3 Requirement |
| 10 | 15 大 Web 驾驶舱 Tab 页面穿透与健康度 100% | 15 个 Tab 页面与 32 个细分视图切换顺畅，数据无空白，0 控制台报错，全系统健康度评分达到 100.0% | M3 | R3 Requirement |

---

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | 后端 10 大子模块算法与数据服务重构 (R1) | `backend/api/data_service.py`, `backend/core/`, `models/lstm/`, `kill_seeker/` 等数据契约与算法特征全量对齐 | none | PLANNED |
| M2 | Web 前端大盘与 6 大赛博主题精细化重构 (R2) | `frontend/static/index.html`, `frontend/static/js/app.js`, `frontend/static/css/cyber_theme.css` 卡片重构与抗折行优化 | M1 | PLANNED |
| M3 | 全系统 E2E 自动化穿透测试与 100% 验收 (R3) | 4-Tier E2E 测试套件、40/40 API 100% PASS 测试、15 Tab 健康度全量回归 | M1, M2 | PLANNED |

---

## Interface Contracts
### 1. `/api/quant/modules-overview` 数据大盘契约
返回 10 大子模块快照字典：
- `lstm`: `{ name, gold_dan, silver_dan, bronze_dan, top10, top20, lift, win_rate, consistency, status, ... }`
- `spatial_points`: `{ name, core5: [{point, left, right, gap, freq, reg_heat, neb_heat, score}], ten: [], top_regions: [], lift, hit_rate, ... }`
- `gold_pick2`: `{ name, chief_gold, active_gold, top_pairs: [{num1, num2, co_occurrence, synergy_score, gcn_weight, tag}], lift, ... }`
- `gemini`: `{ name, gold_dan, silver_dan, bronze_dan, defense_line: [], operators: {}, lift, ... }`
- `jingle`: `{ name, triggered_rules: [{formula_text, trigger, predict, hit_count, oof_win_rate}], recommended_numbers: [], lift, ... }`
- `follow`: `{ name, repeat_top5: [], inference_top6: [], conditional_top8: [], resonance_dan: [], lift, ... }`
- `suppression`: `{ name, top3_rebound: [{number, triplet: [left, core, right], k_factor, rebound_score, confidence_grade}], lift, ... }`
- `sixteen`: `{ name, gold_dan, silver_dan, bronze_dan, defense5: [], top10: [], dynamic_windows: {}, lift, ... }`
- `killseeker`: `{ name, high_kill10: [], mid_kill10: [], low_kill5: [], safe_retention8: [], kill_rate, ... }`
- `aggregation`: `{ name, vote_leaders: [], consensus_dan_pool: [], stable_top10: [], resonance_dan: [], lift, ... }`

### 2. 前端 15 大驾驶舱 Tab 路由契约
- `openTab(tabId, title)` 导航至对应专属驾驶舱 (`points_cockpit`, `suppression_cockpit`, `gold_pick2_cockpit`, `jingle_cockpit`, `follow_cockpit`, `lstm_cockpit`, `sixteen_cockpit`, `kill_cockpit`, `gemini_cockpit`, `agg_cockpit`, etc.)。

---

## Code Layout
- `backend/api/api_server.py`: FastAPI 路由注册与 HTTP 响应处理
- `backend/api/data_service.py`: 统一数据层聚合与 10 大子模块预测大盘组装
- `backend/core/spatial_points/`: 空间点位三联结构、4维特征与区域热点计算
- `backend/core/point_suppression/`: 高压弹簧反弹、三连伴生区间与 $K$ 系数评估
- `backend/core/gold_pick2/`: 双重金胆、图卷积搭档卡与协同打分
- `backend/core/formula_jingle/`: 顺口溜口诀触发、口诀文本生成与命中统计
- `backend/core/follow_analysis/`: 三路跟随推演与多路交集共振计算
- `backend/core/sixteen_period/`: 16期中热光谱、出入窗与金银铜防线
- `backend/core/aggregation/`: 7路多维共振、多路投票热榜与终审共识
- `models/lstm/`: 双层 LSTM 深度时序神经网络多头概率预测
- `kill_seeker/`: 25 码分层杀号与 8 码安全保留区计算
- `frontend/static/index.html`: Web 页面结构与 10 大卡片 DOM
- `frontend/static/js/app.js`: Vue 3 状态管理、主题控制与 API 调用
- `frontend/static/css/cyber_theme.css`: 6 大赛博主题与视觉样式
- `tests/`: 自动化测试用例集 (含 `tests/e2e/` 4-Tier 测试金字塔与 API 测试)
