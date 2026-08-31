# 🧬 K8-QUANT 系统目录架构与模块设计总纲 (System Architecture & Directory Guide)

> **版本**：v5.2 Standard Modular Architecture  
> **根目录**：`C:\D-pan\Dpanqianyi\Python-Project\data`  
> **设计理念**：前后端物理隔离、业务模块高内聚低耦合、全域路径智能中枢解析、老派操盘手大白话落地。

---

## 1. 总体目录全景图 (High-Level Directory Overview)

系统已完成全栈重构与清晰划分，根目录下主要分为三大核心战区：**前端大屏 (frontend)**、**后端计算大脑 (backend)**、**数据资产中心 (storage)**，外加测试、文档与一键启动入口。

```
C:\D-pan\Dpanqianyi\Python-Project\data\
│
├── 🎨 frontend/                       # 【前端体系】量化大屏界面与可视化组件
│   ├── static/                        # 静态 Web 资源 (Vue 3 + TailwindCSS + ECharts)
│   │   ├── index.html                 # 赛博暗黑量化决策大屏首页
│   │   ├── css/cyber_theme.css        # 6 大操盘视觉主题样式引擎 (深邃赛博/黑金尊享/极光星河/量子翡翠/深空暗夜/皓月雅白)
│   │   └── js/app.js                  # 侧边栏多级菜单树、动态 Tab 标签页、图表换肤与穿透分析
│   └── canvases/                      # TSX / React 动态看板组件库
│
├── 🧬 backend/                        # 【后端体系】十大功能模块与量化计算核心
│   ├── api/                           # 🌐 1. Web API 服务与数据接口 (FastAPI 异步微服务)
│   ├── core/                          # 🎯 2. 核心量化算法与评分引擎 (EF蹭热度/RW抓冷门/FO找周期/纯净池)
│   ├── data_acquisition/              # 🔄 3. 数据采集与资产同步 (官网抓取/热码生成/Excel总表同步)
│   ├── pipeline/                      # ⚡ 4. 自动化推演与调度流水线 (每日全流程研判报告生成)
│   ├── audit/                         # 📈 5. 复盘回测与风控审计 (Trinity三维审计/80码矩阵/KL散度变盘监控)
│   ├── learning/                      # 🧠 6. 自主学习与模拟操盘 (动态自学习/模拟实盘胜率跟踪)
│   ├── recognition/                   # 🛡️ 7. 环境态势识别 (大环境变盘/冷热周期识别)
│   ├── format/                        # 🎨 8. 表格格式化与样式渲染 (Excel增量底色与中奖边框着色)
│   ├── config/                        # ⚙️ 9. 配置中心与参数库 (YAML/JSON 权重配置与状态)
│   └── utils/                         # 🔧 10. 基础工具与路径中枢 (统一路径解析/文件并发锁/数据校验)
│
├── 💾 storage/                        # 【持久化数据与资产存储中心】
│   ├── raw/                           # 核心原始历史数据、点位文本、Excel总表、热码统计Excel
│   ├── reports/                       # 每日量化研判 Markdown 报告总库 (146+ 篇)
│   ├── reviews/                       # 历史每日复盘 JSON 库 (53+ 篇)
│   ├── cache/                         # 运行期模型缓存与 AI 操盘记忆
│   ├── chaos_tensors/                 # 混沌张量与高斯能量场阵列
│   ├── logs/                          # 系统运行时执行与调度日志
│   ├── backup/                        # 数据文件历史备份
│   ├── archive/                       # 历史归档与废弃代码
│   └── scratch/                       # 临时分析草稿与验证脚本
│
├── 🧪 tests/                          # 【测试套件】单元测试与系统集成验证 (100% 通过)
│   ├── test_directory_structure.py    # 目录架构与跨模块导入完整性测试
│   ├── test_web_api.py                # Web API 端点、数据契约与大屏服务测试
│   └── test_is_future_consistency.py  # 时序前向无未来函数严格审计
│
├── 📚 docs/                           # 【文档中心】需求说明书、算法推导与操盘规范
│   ├── ARCHITECTURE.md                # 架构设计与目录划分总纲
│   ├── web_system_prd.md              # Web 端大屏需求与交互设计
│   ├── ui_design_spec.md              # 视觉风格与主题规范
│   └── GEMINI.md                      # 操盘执行协议与项目指令
│
├── 🚀 run_server.py                   # 顶层一键启动 Web 操盘大屏 (自动唤起浏览器)
├── 🚀 start_web.bat / start_web.ps1   # Windows / PowerShell 一键快速启动脚本
└── ⚡ run_daily_quant_v4.ps1          # 每日全流程量化推演标准自动化脚本
```

---

## 2. 后端 10 大功能模块与业务菜单映射 (Backend Modules & Menus)

| 序号 | 后端模块目录 (`backend/`) | 对应 Web 菜单 / 业务职责 | 老派操盘手大白话解释 |
|:---|:---|:---|:---|
| **1** | `backend/api/` | 🌐 自动化调度中心 / Web 接口 | 把所有预测结果、走势图表打包成标准接口，喂给前端大屏展示。 |
| **2** | `backend/core/` | 🎯 核心操盘研判 / 算法模型实验室 | 系统的“主力大脑”。算高斯流能场（蹭热度）、遗漏回补（抓冷门）、傅里叶谐波（找周期）、纯净池（守号）、定金选2（找连体婴最佳搭档）。 |
| **3** | `backend/data_acquisition/` | 🔮 走势与数据态势 / 数据采集 | 天天去官方网站抓最新开奖、自动生成热码 Excel、把数据同步进总表。 |
| **4** | `backend/pipeline/` | ⚡ 自动化调度中心 / 流水线 | 每天晚上开奖后，一键串联抓数据、算算法、出研判 Markdown 报告的全流程流水线。 |
| **5** | `backend/audit/` | 📈 复盘与回测审计 | 胜率警告机制。检查三维权重（EF/RW/FO）有没有跑偏、算算以前推荐的号赚不赚钱、大环境有没有变盘（KL散度）。 |
| **6** | `backend/learning/` | 🧠 算法模型实验室 / 自主学习 | 让系统自己“吃一堑长一智”，根据昨天的开奖结果自动微调今天的模型打分权重。 |
| **7** | `backend/recognition/` | 🛡️ 走势与数据态势 / 环境识别 | 看看今天大盘是偏大号还是偏小号、是连号狂出还是冷号回补，提前识别盘面大势。 |
| **8** | `backend/format/` | 🎨 表格格式化与样式渲染 | 自动给 Excel 涂底色、画中奖红框，一目了然看趋势。 |
| **9** | `backend/config/` | ⚙️ 算法模型实验室 / 配置中心 | 集中存放模型的 YAML 和 JSON 配置文件，支持大屏实时动态调参。 |
| **10** | `backend/utils/` | 🔧 底层支撑工具箱 | 统一路径解析器（`paths.py`）、多进程防冲突排他锁、数据一致性自动修复。 |

---

## 3. 统一路径中枢 (`paths.py`) 工作机制

为了彻底消除路径硬编码，`backend/utils/paths.py` 充当全域路径中枢：
1. **自动上溯寻根**：无论脚本在根目录、`backend/core`、`backend/pipeline` 还是子模块中运行，自动寻找到 `data/` 根目录，防止 `__file__` 相对路径指向错乱。
2. **多层智能寻址 (`data_path`)**：
   - 优先查找 `data/` 根目录；
   - 自动匹配 `storage/raw/`、`storage/reports/`、`backend/config/`；
   - 新增文件写入时自动回落到标准路径，确保全系统 100% 兼容。

---

## 4. 常用操作命令指引 (Commands Guide)

- **一键启动 Web 量化决策大屏**：
  ```bash
  python run_server.py
  # 或双击 start_web.bat / 运行 start_web.ps1
  ```
- **每日全流程自动化推演 (抓取+计算+报告)**：
  ```powershell
  PowerShell -ExecutionPolicy Bypass -File run_daily_quant_v4.ps1
  ```
- **运行全量测试套件**：
  ```bash
  python -m pytest tests/
  ```
