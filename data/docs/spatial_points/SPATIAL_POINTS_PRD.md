# 🔮 空间重点点位分析 (Spatial Points Analysis) 子系统架构与落地白皮书

## 一、系统简介 (老派量化操盘手大白话)
本模块为快乐8全域 80 点位的空间热能与回补精排引擎。彻底废除不可解释的复杂黑盒堆叠，回归透明可审计的 4 维可解释特征加权与二级非线性回补精排机制：
1. **点位打分 (一级筛选)**：
   - 遗漏强度 (gap, 权重 35%)：憋了多久没开出来，衡量弹簧弹性与回补势头。
   - 冷热频次 (freq, 权重 20%)：近 20 期开出来的次数，衡量号码当前活跃度。
   - 邻区热度 (reg, 权重 25%)：看点位左右 ±1 三号区环绕热度，衡量局部区域空间能量场。
   - 邻居引力 (neb, 权重 20%)：看点位周围 ±2 邻域环绕热度，衡量邻居号码对该点位的引力拉动。
   - 点位得分映射：Sigmoid 映射至 0.50 ~ 0.65 标准区间；标准正态近似计算显著性 p 值 ($p < 0.05$ 判定显著)。
2. **号码精排 (二级提纯)**：
   - 在一级 Top 10 强势区域内，按遗漏深度做非线性增强，去重提纯：
     * 💎 核心五码 (Core 5)：最高优先级金胆梯队。
     * 🎯 精选十码 (Top 10)：主力进攻梯队。
     * 🌐 扩展十五 (Ext 15)：大盘防守梯队。
     * 🧭 8 分区覆盖均衡度监控 (01-10 至 71-80)。
3. **Walk-Forward 样本外复盘与置信评定**：
   - 严格无未来函数泄露（每期预测仅使用当期前数据）。
   - 统计 Top 10 均命中数 (基线 2.50 码 / 25%)、Core 5 均命中数 (基线 1.25 码 / 25%)、区域命中率 (基线 58.35%)。
   - 置信评级：🟢 高置信 (Level 1, $z \ge 1.64$)、🟡 中置信 (Level 2, $z \ge 0.84$)、🔴 无置信 (Level 3, 等权降级防守)。
4. **多维系统交叉风控**：
   - 🔴 杀号撞车预警：与 KillSeeker 杀号交叉核验，若重叠提示减仓防守。
   - 🟢 黄金共振共识：与 LSTM / Trinity 三维融合 / 顺口溜口诀交叉，若共振提示重点定胆。

---

## 二、代码拓扑与落盘结构

| 目录/文件 | 角色与功能说明 |
| :--- | :--- |
| `core/spatial_points/points_engine.py` | 80点位 4 维特征计算与 Sigmoid 得分映射 |
| `core/spatial_points/points_ranker.py` | 一级 Top 10 区域筛选与二级非线性精排 (Core5/Top10/Ext15/8区均衡) |
| `core/spatial_points/points_evaluator.py` | Walk-Forward 严格样本外切片滚动复盘与置信评定 |
| `core/spatial_points/points_cross_validator.py` | 跨系统交叉风控 (KillSeeker 撞车防守 + 多维黄金共振) |
| `run_points_daily.py` | 重点点位分析每日独立 CLI 运行入口 |
| `run_full_pipeline.py` (Section 3.7) | 接入主系统全量自动化每日推演流水线 |
| `backend/api/data_service.py` | 重点点位摘要、80 码矩阵、滚动复盘数据服务 |
| `backend/api/api_server.py` | 4 大 RESTful 接口：`/api/spatial-points/*` 与推演调度 |
| `frontend/static/index.html` & `app.js` | 3 大全新赛博朋克大屏视图 (决策驾驶舱/80码精排矩阵/滚动复盘审计) |
| `docs/spatial_points/` | 文档、历史演化日志与上下文记忆归档 |
| `outputs/spatial_points/` | 预测文本 (`重点点位预测.txt`) 与最新 JSON 产物 |
| `logs/spatial_points_logs.txt` | 逐期预测历史流水日志 |
