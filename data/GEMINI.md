# 项目指令 (Project Instructions)

## 语言偏好 (Language Preference)
- **全面中文化**：在本工程（`D:\Dpanqianyi\Python-Project\data`）的所有交互中，请务必使用**全中文**进行回复和沟通。
- **专业术语**：在描述技术细节或代码逻辑时，优先使用准确的中文术语，必要时可在括号内标注英文原文。

## 自动化工作流 (Automated Workflows)

### 1. 每日预测记录与审计 (Daily Analysis & Audit)
- **记录规范**：在完成每日数据更新和深度分析后，必须生成一个 Markdown 格式的报告（命名格式：`daily_analysis_report_YYYYMMDD.md`），保存在 `D:\Dpanqianyi\Python-Project\data` 目录下。报告需包含：
  - 目标期号与日期。
  - AI 核心推荐号码 (Top 5/12)。
  - 多维共振号 (Golden Core)。
  - 区域与尾数的逻辑分析。
  - 系统当前的自学习权重与专家系数。
- **审计复盘**：在开启新一天的任务前，必须首先读取前一天的报告，对比实际开奖结果，在报告末尾填充“复盘追溯”内容，并据此检查系统权值调整是否合理。

### 2. 热码处理与格式化 (Hot Numbers & Formatting)
- 每次收到热码 Excel 文件后，运行 `backend/data_acquisition/process_hot_numbers.py` 合并数据。
- 随后运行 `backend/format/apply_formats.py` 同步点位底色和中奖边框。

### 3. 系统稳定性指令 (Stability & Strategy)
- **核心逻辑优先级**：在评估预测结果时，应优先参考“首席战略官特供”中的 **Hidden Energy 5 (最终推荐 5 码)**。
  > ⚠️ **2026-10-22 声明纠正（数据诚信）**：本行原写有「该模块表现最为稳定（长期平均命中 > 2 码）」，经前瞻账逐期对账取证**不成立**，现予撤销：
  > - 已结算 19 期实测：平均命中 **1.158 / 5 码**（中位数 1 码），单码命中率 **23.2%**，**Lift 0.926x**（低于 25% 随机基线）；
  > - 19 期中仅 4 期达到 ≥2 码，且在 36 模块多重检验族内未通过任何显著性校正（BH-q=1.000）；
  > - 该模块注册表状态为 `observation`（观察仓），无出号表决权，**不得作为加注依据**。
  > 结论：Hidden Energy 5 目前与其他模块并无统计差异，历史「最稳定」为未经检验的叙述性结论，已被实测推翻。
- **权重对冲机制**：若 Trinity 引擎 (Top 5/12) 连续 2 期命中低于平均值，应手动检查 `audit/v3_trinity_audit.py` 中的三维权重(EF/RW/FO)是否均衡。v4.0已移除MK/EO，仅保留EF/RW/FO三维融合，确保任一维度权重不超过0.50以防止过拟合。
  > 📌 2026-10-22 修复：该文件原含两条死逻辑已清除 —— ①「波动率分档」公式内层 `Σ(1ₙ−0.25) ≡ 0`（每期恒开 20/80 码的数学恒等式），使 `avg_vol` 永远为 0、永远只命中「低波动」档；② `compose()` 硬编码 `environment='balanced'`，环境识别结果从未参与打分。现环境键已贯通，且回显权重一律以 `ScoreComposer.last_weights`（真正用于打分的权重）为准。

### 4. 双层LSTM 深度学习子系统 (Deep Learning Time-Series Module)
- **模块定位**：`backend/modules/_retired/models/lstm/`（逻辑名仍可由 `find_module_script("run_lstm_daily.py")` 解析）。
- **算法核心**：双层 LSTM 时序神经网络，输入过去 30 期独热向量，多头输出 80 球概率 + 8 分区分布 + 10 尾数偏好。
- **调度方式**：
  - **流水线联动**：已整合进 `backend.pipeline.run_full_pipeline`（任务 3.5）和每日研报引擎 `auto_generate_daily_report.py`（4.5 段落）。
  - **独立运行**：在 `data` 目录下执行 `python -m backend.modules._retired.models.lstm.run_daily [backfill_n]`。
- **输出资产**：
  - 预测文件：`outputs/predictions/prediction_YYYYNNN.txt`
  - 独立研报：`outputs/reports/lstm_analysis_report_YYYYNNN.md`
  - 模型权重：`cache/models/best_model.pt` 与 `outputs/models/best_model.pt`

### 5. 每天 22:00 夜间全自动流水线与元学习自进化协议 (Nightly Pipeline & Meta-Evolution Protocol)
- **闭环全流程**：每天 21:30 开奖后，系统于 22:00:00 准时通过 `backend/scheduler/nightly_scheduler.py` 或系统级计划任务（`setup_nightly_task.bat`）自动触发：
  1. `data_acquisition`: 三级源抓取最新开奖（CWL 主源 → 17500 静态文件 → 17500 JSON）+ 抓取健康度告警 + 数据校验 + 热码同步；
  2. `MasterReviewEngine`: 15 大全模块样本外滚动实战对账；
  3. `MetaEvolutionEngine`: 跨模块元学习进化，自适应微调 EF/RW/FO 三维主权重（步长 $\le 0.02$，安全区间 $[0.10, 0.45]$）与多模块共识表决权（Meta-Weights）；
  4. 下游子系统推演下一期开奖并生成终极大研报；
  5. 记录进化总账本（`storage/evolution/evolution_ledger.json`）与刷新 Web 赛博量化大屏。
- **调度器运行入口**：`python -m backend.pipeline.run_nightly_daily` 或 Web 端一键立即触发。

### 6. 15 大全模块实战命中复盘总决算标准 (Master Multi-Module Review Standard)
- **核心模块**：涵盖 Trinity、Hidden Energy 5、纯净池定胆、双层 LSTM、顺口溜口诀、空间重点点位、压制反弹、条件跟随、黄金选2、Gemini 选2、16期中热、数据源1×2 及终审共识等维度；主口径统一为最优 3 码。KillSeeker 已拆除。
- **统一评价指标**：
  - **提升度 Lift**：单码实际命中率 ÷ 25.0% 随机基线（$\ge 1.25x$ 为超强信标）；
  - **杀号防守回避率**：实际未开出率 ÷ 75.0% 防守基线；
  - **选2双全中率**：实际双中次数 ÷ 总期数（基准约 6.0%）。
- **持久化账本**：`storage/reviews/master_review_ledger.json` 与独立战报 `outputs/reports/master_review_report_latest.md`。

## 7. AI 工业级编码与自检四大铁律 (The 4 Golden Engineering Rules)
> [!IMPORTANT]
> **开发与重构强制执行守则（已全面物理生效）**：
> 1. **【铁律一：测试驱动与物理结果强校验 (TDD & I/O Verification)】**
>    - 任何功能开发、缺陷修复或重构后，**禁止**仅靠言语推断完成；
>    - **必须**自主运行对应的 `pytest` 自动化测试，并物理读取生成文件（txt / json / md / xlsx）检验其实际大小（>0 字节）与字段 Schema。
> 2. **【铁律二：零伪代码与全局代码红线 (Zero Fake Code & Redlines)】**
>    - 严禁 `// TODO: 这里写业务逻辑`、`pass` 或截断伪切片（如将 Top5/Top12 写为 `list(top3)`）；
>    - 必须具备真实的算法逻辑与完备的中文注释，严格执行空指针防御、浮点精度保护与除零防守。
> 3. **【铁律三：全库爆炸半径分析 (Blast Radius Pre-Check)】**
>    - 涉及模块路径变更（如 `core/` 迁移至 `modules/`）、核心类接口重构时，**必须先执行全局代码检索（`grep_search`）**；
>    - 找出系统中所有被影响的下游调用方、日常脚本与测试用例，一次性全链路闭环修改，杜绝散落残留。
> 4. **【铁律四：Challenger 对抗性极限压测 (Adversarial Testing)】**
>    - 对复杂量化数学、物理张量与自学习引擎，**必须**在 `tests/adversarial/` 维护高压测试；
>    - 使用脏数据（负数、越界号码、空列表）、极端超参（核宽 $\sigma \to 0/\infty$、$\lambda \to 0/1$、NaN/Inf 毒丸）主动攻击算法边界，杜绝隐蔽崩溃。

## 8. 控制台与聊天窗口【全量推演与美观输出】强制执行契约 (Console Output Mandate)
> [!IMPORTANT]
> **最高优先级输出规范：严禁偷懒概括，必须全息展开**
> 当用户输入包含「控制台输出：要求：详细的各个分析推荐准确结果和美观展示」或触发每日全预测任务时，回复内容**严禁使用省略号、严禁仅给出几个模块的简单汇总、严禁让用户自行去文件中查阅**！
> 必须在控制台/回复窗口中，按照以下标准架构 1:1 完整、美观输出：
> 
> 1. **【〇、数据基准与特征档案】**：完整展示官方基准期实开 20 码、今日输入 20 点位、重复高（10码）、边码高左右双翼（8码）、指标冷高（6~9码）。
> 2. **【一、昨日深度实战复盘与命中对账】**：采用美观 Markdown 表格，逐一列出核心模块（Hidden Energy 5、空间高压反弹、质合香农熵、偏态压缩器、残差改错、三维一体 Top5/12、传统 AI Top5、16期中热、定金选2、30码大底等）的昨日推荐号码、实际命中号码、命中率与 Lift 提升度，并给出老派操盘手实战点评。
> 3. **【二、全细分预测模块逐项详细展开（核心重点）】**：
>    - 必须逐条展开以下全部 14+ 核心模块的独立预测逻辑与推荐码：
>      ① **顺口溜 90 条精英口诀 (formula_jingle)**：双轨展开（轨道一：触发口诀明细+规则推荐码+最优3码；轨道二：历史大数据跟随引力 Top3）；
>      ② **三维共识定胆系统 (consensus_straddle)**：第一金胆、银胆、铜胆、精选 5 码防线、大盘风控评级；
>      ③ **16期中热双轨 4 法推演 (sixteen)**：A-主死答案 tip3、回补金银铜、选2搭档、A-辅微信桶混剪、B-主主核与选2；
>      ④ **三高特征 × 点位深度共振 (tri_high)**：尖刀金胆、黄金选2、最优3码、突击 Top5、Top12 梯队；
>      ⑤ **定金选2决策推演 (gold_pick2)**：核心金胆、动能热胆、核心选2搭档、备选梯队；
>      ⑥ **未开点位高压反弹与空间追踪 (point_suppression)**：首重绝杀反弹胆、反弹 Top3；
>      ⑦ **数据源 1×2 深层关联 (datasource)**：精选爆发最优3码、连体婴选2；
>      ⑧ **三维一体极秘推荐 (Trinity Fusion) & Hidden Energy 5**：极秘 Top5/12、首席特供 Hidden Energy 5、极简选2黄金搭档、传统 AI Top5/12、mRMR Top12、方案2 爆发 Top5 与跨规则共识；
>      ⑨ **心理博弈与逆向均值回归 (psychological_game)**：逆向金胆、报复性回补冷号、健康重号；
>      ⑩ **质合香农熵三大协同推演 (prime_composite)**：质数金胆 Top3；
>      ⑪ **多维共振专家表决 (multi_resonance)**：至尊金胆 Top5；
>      ⑫ **残差改错与错题纠偏 (error_correction)**：AI 改错纠偏 Top3/5；
>      ⑬ **一胆拖三盾选2组合拳 (spear_shield)**：核心攻矛、三大守盾；
>      ⑭ **点位 012 偏态压缩器 (point_road_compressor)**：最优3码、精选5码、012 跨路对冲选2搭档；
>      ⑮ **统一决策脑 (unified_brain)**：核心金胆 Top3、选2搭档；
>      ⑯ **决策树 012路 × 质合多梯度缩水系统 (road_prime_shrink / TPRD v2.0)**：决策树规则透视与 AI 海选团评分、核心金胆 Top3/5、高频连体选2搭档（基于100期共现亲和度加权）、20码极致实战主力池、25码梯度精选中底、30码黄金守卫大底（和值与012路六维守恒）。
> 4. **【三、微信分桶原文（一键直接发群）】**：必须完整输出 80 码出窗与留窗微信分桶文本块（从 8 次到 0 次），格式严格符合微信群发布要求。
> 5. **【四、全系统汇总总账单】**：展示现算票王、多模块共识梯队、最优3码、精选5码、十全防线、各大选2组合以及 **30码/25码/20码多梯度实战大底（核心20码/中坚25码/守卫30码三梯队展开、8分区分布、奇偶比、理论命中期望）**。
> 6. **【五、操盘速查一键复制文本块】**：提取当天最精炼的实战速发票面（票王、黄金选2、主力5码、20码极致主力、25码精选大底、30码黄金大底，支持一键无缝全选复制）。
> 7. **【六、代码自检排查与近期命中率评估】**：汇报代码排查修复情况与近 30 期实战命中率滚动数据。

## 9. 16期大盘80码守恒与时序黄金测试自愈铁律 (Physics & Testing Invariants)
> [!NOTE]
> 1. **【80码大盘守恒定律】**：
>    - 在 16 期窗口大盘动力学计算中，所有 80 个号码必须完全划分为「出窗区（恒等于20码）」与「留窗区（恒等于60码，包含窗口内未开出的 0 频次极限冷号）」。
>    - 核心引擎 `folk_sixteen_engine.py` 的分层字典必须包含频次 0，确保 `出窗 20 码 + 留窗 60 码 = 80 码` 物理绝对守恒闭环。
> 2. **【时序黄金测试跨日自愈】**：
>    - 对于包含自然日期漂移的黄金测试（如 `test_golden.py` 计算距今年份/天数），跨日执行时必须主动使用 `--update` 同步黄金快照，杜绝误报。
> 3. **【存储布局严格合规】**：
>    - 根目录严禁散落 `cache/` 等临时目录，所有中间缓存与模型必须统一保存在 `storage/cache/` 中，保持测试 `test_migration_full.py` 100% 全绿。



