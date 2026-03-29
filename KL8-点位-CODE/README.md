# 数据分析系统（KL8-点位-CODE）

本项目是一个“前端可视化 + Python 数据链路”的数据分析系统，当前包含两条主线：

- 点位分析（系统核心分析）
- 专家关注号分析（按日期矩阵与命中复盘）

本 README 以“可执行优先”为目标，先给你能直接启动与定位问题的方法，再给技术结构与文档导航。

## 1. 快速启动

### 1.1 环境要求

- Python 3.11+
- Node.js 18+
- npm 可用
- Windows（当前启动脚本与端口处理已按 Windows 终端行为优化）

### 1.2 一键启动（推荐）

```powershell
python .\src\data\start_service.py
```

启动器会依次执行：

1. 数据更新（`data_fetcher_and_converter.py`）
2. 专家分析/汇总产出（`main_workflow.py` + 兼容导出）
3. 前端数据同步（`expert_dashboard.json`、`recommendation_history.csv` 等）
4. 启动 Vite 开发服务（固定端口 5173）

### 1.3 前端单独启动（仅调 UI）

```powershell
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

## 2. 系统定位与架构总览

### 2.1 前端层（React + Vite + TypeScript）

- 入口与路由骨架：`src/App.tsx`
- 点位决策简报页：`src/components/PointDecisionBriefScreen.tsx`
- 点位工作流视图模型：`src/data/pointAnalysisViewModel.ts`
- 点位简报模型：`src/data/pointDecisionBrief.ts`
- 专家看板页：`src/components/ExpertDashboardScreen.tsx`
- 数据加载：`src/data/dataLoader.ts`

### 2.2 分析引擎层

- 核心分析函数：`src/data/analysisEngine.ts`
- 覆盖统计、集群、热区、Markov、熵值、规则回测、综合判断等在此统一输出

### 2.3 Python 数据链路

- 启动编排：`src/data/start_service.py`
- 历史抓取与转换：`src/data/data_fetcher_and_converter.py`
- 专家 Excel 生成：`src/data-sum/main_workflow.py`、`src/data/generate_expert_excel.py`
- 专家 JSON 导出：`src/data/export_expert_dashboard.py`
- 历史开奖数据：`src/data/kl8_history_final.txt`

### 2.4 关键数据流向

1. 原始数据/历史开奖更新
2. 专家矩阵与汇总分析产出（Excel）
3. 导出前端可消费 JSON（`src/data/expert_dashboard.json`）
4. Web 读取 JSON 与历史数据渲染

## 3. 主要实现点（当前版本）

### 3.1 点位分析（“总览/证据/复盘”）

- 首屏决策简报：最终结论、Top5、宏观趋势、风险应对
- 证据层：Markov 交集、连号三元组、共现支撑、熵值校正
- 复盘层：规则回测（30/60/120）、覆盖轨迹、数据健康状态

### 3.2 专家关注号分析

- 按日期与矩阵块展示两套数据
- 历史命中复盘支持待开奖与缺失原因区分
- 专家看板 JSON 作为主数据源，CSV 仅兼容兜底

### 3.3 启动体验

- 固定端口 5173
- 启动前端口占用检查/处理
- 子进程输出清洗，中文终端可读性优先

## 4. 已知问题与后续路线

### 4.1 已知问题（需持续跟踪）

- 个别历史文件存在编码遗留，可能导致中文日志/文案出现乱码
- 历史开奖同步源的时效性需持续监控，防止复盘长期 `PENDING`

### 4.2 后续路线（建议优先级）

1. 数据健康卡前置（首屏）
2. 规则回测稳定性可视化增强
3. 点位与专家共识引擎进一步统一

## 5. 文档导航（本次落地）

- AI 改动日志（提交粒度）：[`docs/AI_CHANGELOG.md`](docs/AI_CHANGELOG.md)
- 项目记忆文档：[`docs/PROJECT_MEMORY.md`](docs/PROJECT_MEMORY.md)
- Skills 能力清单：[`docs/SKILLS_CATALOG.md`](docs/SKILLS_CATALOG.md)
- AITeam 协作手册：[`docs/AI_TEAM_PLAYBOOK.md`](docs/AI_TEAM_PLAYBOOK.md)

## 6. 文档联动规则（强制）

- README 是总入口，专项内容必须写入 `docs/` 下对应文档
- 任何代码改动合并前，必须同步：
  - `docs/AI_CHANGELOG.md`（新增提交记录）
  - `docs/PROJECT_MEMORY.md`（更新当前状态/下一步）

## 7. 变更记录自动化

### 7.1 安装 Git Hook（提交后自动追加 changelog 草稿）

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_git_hooks.ps1
```

安装后，每次 `git commit` 会自动执行：

```powershell
python scripts/update_ai_changelog.py --from-latest-commit
```

### 7.2 手动补写（支持补录/修正）

```powershell
python scripts/update_ai_changelog.py --title "你的改动标题" --background "需求背景" --files src/data/export_expert_dashboard.py src/data/start_service.py
```

### 7.3 失败回退方案

- 如果 hook 未生效，直接执行手动命令补写；
- 如果自动条目内容不完整，按 `docs/AI_CHANGELOG.md` 模板补全“核心实现点/验证结果/风险”。

## 8. 全局 Skills 路由状态

- 当前已开启“全局自动 Skills 严格路由”。
- 默认顺序：`kl8-analysis -> frontend-skill -> playwright`。
- 作用范围：全局会话（不仅限本项目）。
- 如需临时降级为关键词匹配模式，请在全局 `AGENTS.md` 中切换规则。
