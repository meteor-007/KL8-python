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
- **核心逻辑优先级**：在评估预测结果时，应优先参考“首席战略官特供”中的 **Hidden Energy 5 (最终推荐 5 码)**。该模块表现最为稳定（长期平均命中 > 2 码）。
- **权重对冲机制**：若 Trinity 引擎 (Top 5/12) 连续 2 期命中低于平均值，应手动检查 `audit/v3_trinity_audit.py` 中的三维权重(EF/RW/FO)是否均衡。v4.0已移除MK/EO，仅保留EF/RW/FO三维融合，确保任一维度权重不超过0.50以防止过拟合。

### 4. 双层LSTM 深度学习子系统 (Deep Learning Time-Series Module)
- **模块定位**：`models/lstm/`（快捷入口：`core/lstm/` 与根目录 `run_lstm_daily.py`）。
- **算法核心**：双层 LSTM 时序神经网络，输入过去 30 期独热向量，多头输出 80 球概率 + 8 分区分布 + 10 尾数偏好。
- **调度方式**：
  - **流水线联动**：已整合进 `run_full_pipeline.py`（任务 3.5）和每日研报引擎 `auto_generate_daily_report.py`（4.5 段落）。
  - **独立运行**：在 `data` 目录下执行 `python run_lstm_daily.py [backfill_n]`。
- **输出资产**：
  - 预测文件：`outputs/predictions/prediction_YYYYNNN.txt`
  - 独立研报：`outputs/reports/lstm_analysis_report_YYYYNNN.md`
  - 模型权重：`cache/models/best_model.pt` 与 `outputs/models/best_model.pt`
