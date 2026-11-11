# Project: 快乐8 全栈统一决策主脑与真自进化重构工程 (PROJECT.md)

## Architecture (大白话系统架构)

本项目彻底推翻旧有“多模块各自猜号后加权/数人头（大白话：各个子模块各自报名单，最后数票数或死板加权）”的反模式，重构为高内聚、低耦合、数学严密且纯物理态的全局决策中枢：

```
[历史开奖数据 / 内存流]
        │
        ▼
【阶段 1：五大物理特征提取器 (Feature Engineering Layer)】
 ├── 1. 时序惯性张量 (TimeInertiaExtractor): 双层LSTM 80球连续转移概率 (大白话：看冷热势头)
 ├── 2. 空间能量密度势能 (SpatialEnergyExtractor): 高斯核聚类势能 V_i (大白话：蹭热度，看哪片区域扎堆)
 ├── 3. 离散形态规则向量 (DiscreteRuleExtractor): 90条口诀激活态向量 (大白话：经典老经验与形态出击)
 ├── 4. 拓扑共现与跟随粘性 (TopologicalCooccurrenceExtractor): Markov与双元共现 80x80 矩阵 (大白话：找跟班与连体搭档)
 └── 5. 绝对防守禁区掩码 (DefenseMaskExtractor): KillSeeker 0/1 硬雷区掩码 (大白话：绝对不能碰的危险红线)
        │
        ▼
【阶段 2：统一物理概率解算主脑 (Unified Master Decision Brain)】
 ├── 彻底废除线性加权 (w1*mod1 + w2*mod2) 与正则解析文本
 ├── 杀号硬掩码物理归零 (-10^9 势垒，概率绝对为 0，大白话：一票否决踩刹车)
 ├── 80 维连续状态空间联合解算能量场与玻尔兹曼概率 P(N_1, ..., N_80)
 └── 一脉相承四级层级化决策：
      ├── ① 尖刀金胆 (1 码 / 极高确定性先锋)
      ├── ② 黄金连体伴随 (定金选2 / 以金胆为锚点顺藤摸瓜找最佳搭档)
      ├── ③ 突击主力 (Top 5 / 核心进攻火力)
      └── ④ 8区覆盖底仓 (Top 12 / 八大区间均衡防守大本营)
        │
        ▼
【阶段 3：真实残差反向传播自进化内核 (True Parameter Self-Evolution Engine)】
 ├── 每日 22:00 同步真实开奖后，计算预测概率与真实标签的 Focal Loss (焦点残差损失)
 ├── 空间高斯核宽 sigma 梯度自适应微调 (大白话：自动调节热度扩散范围)
 ├── 时序动量衰减率 lambda 自适应微调 (大白话：自动平衡长周期与短周期惯性)
 └── 90 条口诀规则库动态赛马机制 (大白话：能打胜仗的晋升权重，屡战屡败的降级淘汰)
 └── 记录总账本：storage/evolution/unified_evolution_ledger.json
        │
        ▼
【阶段 4：22:00 夜间全自动流水线闭环与 Web 驾驶舱端到端联调】
 ├── backend/pipeline/run_nightly_pipeline.py 5 阶段自动闭环
 ├── FastAPI 后端 API: /api/quant/unified-brain & /api/evolution/status
 └── 前端 Web 驾驶舱: 五维特征态势雷达图、80码状态空间概率热力图、四级层级化卡片、自进化代数日志
```

---

## Feature Inventory (全量功能特性清单)

| # | Feature (功能特性) | Description (大白话描述) | Milestone | Source |
|---|--------------------|--------------------------|-----------|--------|
| F1 | TimeInertiaExtractor | 双层LSTM 80球连续转移概率张量输出，内存级流转，杜绝文本正则截断 | M1 | R1 / Survey |
| F2 | SpatialEnergyExtractor | 高斯核局部聚类势能 $V_i = \sum \exp(-\text{dist}^2 / 2\sigma^2)$，暴露 $\sigma$ 供进化微调 | M1 | R1 / Survey |
| F3 | DiscreteRuleExtractor | 90条口诀规则激活态向量，与形态反弹特征融合，支持动态规则权重 | M1 | R1 / Survey |
| F4 | TopologicalCooccurrenceExtractor | 马尔可夫转移与 $80\times 80$ 双元共现矩阵，输出节点势能与粘性拓扑 | M1 | R1 / Survey |
| F5 | DefenseMaskExtractor | KillSeeker 防守硬掩码，输出 80 维 0/1 布尔向量，作为绝对物理势垒 | M1 | R1 / Survey |
| F6 | UnifiedMasterDecisionBrain | 80维状态空间物理能量解算，彻底废除线性加权，杀号物理归零势垒 | M2 | R2 / Survey |
| F7 | Hierarchical Decision Strategy | 四级层级化决策：尖刀金胆 ➔ 黄金选2 ➔ 突击Top5 ➔ 8区底仓Top12 | M2 | R2 / Survey |
| F8 | Unified Brain CLI Runner | `run_unified_brain_daily.py` 独立解算脚本，落盘 JSON/Markdown 资产 | M2 | R2, R5 / Survey |
| F9 | True Self-Evolution Engine | 基于 Focal Loss 焦点残差的真自进化内核，量化上一期预测误差 | M3 | R3 / Survey |
| F10| Adaptive Hyperparameter Tuning | 自适应微调高斯 $\sigma$、时序 $\lambda$ 与 90条口诀优胜劣汰赛马 | M3 | R3 / Survey |
| F11| Evolution CLI Runner & Ledger | `run_evolution_daily.py` 进化脚本与 `unified_evolution_ledger.json` 账本 | M3 | R3, R5 / Survey |
| F12| 22:00 Nightly Pipeline | 夜间流水线 5 阶段全自动闭环（数据同步➔参数进化➔特征提取➔主脑解算➔复盘刷新） | M4 | R4, R5 / Survey |
| F13| Web Backend API Integration | FastAPI 端点 `/api/quant/unified-brain` 与 `/api/evolution/status` 契约强化 | M4 | R4 / Survey |
| F14| Web Cockpit Visualization | 前端五维特征雷达、80码概率热力图、层级决策卡片与自进化代数日志 | M4 | R4 / Survey |
| F15| E2E Verification & Hardening | 全栈端到端自动化测试套件 (Tiers 1-4) + Tier 5 对抗性覆盖加固 | M5 | R5 / Dual-Track |

---

## Milestones (里程碑分解与依赖)

| # | Name (里程碑名称) | Scope (任务范围) | Dependencies | Status |
|---|-------------------|------------------|--------------|--------|
| M1 | 5大物理特征提供器重构 | 重构 `TimeInertiaExtractor`, `SpatialEnergyExtractor`, `DiscreteRuleExtractor`, `TopologicalCooccurrenceExtractor`, `DefenseMaskExtractor`，实现纯内存特征流 | none | DONE |
| M2 | 统一决策主脑与层级策略 | 实现 `UnifiedDecisionBrain` 状态空间概率解算，物理杀号硬阻断，四级层级化决策生成，完成 `run_unified_brain_daily.py` | M1 | DONE |
| M3 | 真实残差反向自进化内核 | 实现 `UnifiedBrainEvolutionEngine`，计算 Focal Loss，反向自适应微调 $\sigma, \lambda$ 与口诀赛马，完成 `run_evolution_daily.py` 与账本记录 | M2 | IN_PROGRESS |
| M4 | 22:00夜间流水线与Web驾驶舱 | 联调 `run_nightly_pipeline.py`，加固 Web 后端 API，重构前端雷达图、热力图、层级卡片与进化日志 | M2, M3 | PLANNED |
| M5 | 全栈E2E验收与对抗加固 | 运行完整 E2E 自动化测试套件（Tiers 1-4），完成 Tier 5 白盒对抗性覆盖加固与全系统验收 | M1, M2, M3, M4 | PLANNED |

---

## Interface Contracts (接口契约与数据流定义)

### 1. 特征提取层 ↔ 统一主脑
```python
class UnifiedFeatureBundle:
    time_inertia: np.ndarray        # shape: (80,), float64, in [0.0, 1.0]
    spatial_energy: np.ndarray      # shape: (80,), float64, in [0.0, 1.0]
    rule_activation: np.ndarray     # shape: (80,), float64, in [0.0, 1.0]
    topological_energy: np.ndarray  # shape: (80,), float64, in [0.0, 1.0]
    cooccurrence_matrix: np.ndarray # shape: (80, 80), float64, symmetric
    defense_mask: np.ndarray        # shape: (80,), bool, True=Safe, False=Hard Kill
    meta_info: dict                 # target_period, draw_date, params
```

### 2. 统一主脑 ↔ 下游层级决策与资产输出
```python
class UnifiedDecisionResult:
    target_period: int
    probabilities: np.ndarray       # shape: (80,), float64, sum(p) == 1.0 (Safe numbers only)
    killed_numbers: List[int]       # length: 15-25
    gold_core: int                  # 尖刀金胆 (1码)
    gold_pair: List[int]            # 黄金连体伴随 (2码, [gold_core, companion])
    top5_assault: List[int]         # 突击主力 (5码)
    top12_balanced: List[int]       # 8区覆盖底仓 (12码, 保证8大分区至少全覆盖)
    radar_features: dict            # 五大维度 0-100 标准化得分，供 Web 雷达图使用
```

### 3. 真实开奖残差 ↔ 自进化内核
```python
class EvolutionStepResult:
    target_period: int
    focal_loss: float
    actual_draw: List[int]          # 20 个开奖号码
    old_params: dict                # {"sigma": float, "lambda_decay": float, ...}
    new_params: dict                # {"sigma": float, "lambda_decay": float, ...}
    rule_stats: dict                # 90 条口诀在当期的命中率、晋升/降级/淘汰状态
    generation: int
```

---

## Code Layout (代码物理布局与文件边界)

```
backend/
├── core/
│   └── unified_brain/
│       ├── __init__.py
│       ├── feature_extractors.py       # [M1 Owned] 五大物理特征提取器核心实现
│       ├── unified_brain.py            # [M2 Owned] 统一概率解算主脑与四级层级策略
│       ├── loss_and_backprop.py        # [M3 Owned] Focal Loss 残差与超参数自适应微调
│       └── evolution_engine.py         # [M3 Owned] 规则赛马与进化总账本
├── pipeline/
│   └── run_nightly_pipeline.py         # [M4 Owned] 22:00 夜间全自动 5 阶段闭环
├── scheduler/
│   └── nightly_scheduler.py            # [M4 Owned] 守护进程定时触发调度器
├── api/
│   ├── api_server.py                   # [M4 Owned] FastAPI 路由端点加固
│   └── data_service.py                 # [M4 Owned] 数据服务层适配
frontend/
└── static/
    ├── index.html                      # [M4 Owned] 前端 Web 驾驶舱页面结构
    └── js/app.js                       # [M4 Owned] 前端图表渲染与轮询刷新逻辑
root/
├── run_unified_brain_daily.py          # [M2 Owned] 每日主脑解算主入口
├── run_evolution_daily.py              # [M3 Owned] 每日自进化主入口
└── run_nightly_daily.py                # [M4 Owned] 22:00 夜间全量调度入口
tests/
├── e2e/                                # [M5 / E2E Track Owned] 端到端自动化测试集
│   ├── test_e2e_features.py            # Tier 1
│   ├── test_e2e_boundary.py            # Tier 2
│   ├── test_e2e_combinations.py        # Tier 3
│   └── test_e2e_workloads.py           # Tier 4
└── adversarial/
    └── test_adversarial_coverage.py    # Tier 5 对抗性加固
```
