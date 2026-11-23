# 快乐8 点位+遗漏号分析系统

把《思路.txt》里的「深度分析四重奏 + 十大高价值方案 + 综合研判任务清单」落地为一套
**独立自研**的命令行 + Markdown 报告系统。全部模块自研，除 `numpy/scipy/requests/PyYAML`
外无外部算法依赖。

> **定位（重要）**：本系统是**统计观察工具**，不是预测器。快乐8 每期开奖近似独立同分布，
> 任何「规律」都可能是随机噪声。系统会通过真实档案滚动外样本回测与随机基线对照，
> 明确标出哪些信号经不起检验；**最可能诚实的结论是「没有可检测的规律」**。
> 报告不构成任何投注建议，也不做金额/期数规划。

---

## 1. 安装

```bash
python -m pip install -r requirements.txt        # 运行依赖
python -m pip install -r requirements-dev.txt    # 测试依赖（可选）
```

要求 **Python 3.11+**（实测 3.11.6）。

## 2. 数据来源

系统按「四级兜底」取数（详见方案 §8.1）：

1. **共享目录**（默认 `../Python-Project/data`）：`daily_points.txt`（点位档案）、
   `kl8_history_final.txt`（开奖历史）；
2. **联网增量抓取**（双源，超时 10 s，失败降级）；
3. **`data/uploads/` 与 `data/seed/` 上传/种子兜底**；
4. **点位手动录入**（唯一人工环节）。

共享目录写入默认为 `read_only`，不会改动源文件；需要写回时在 `config.yaml` 中把
`data.python_project.mode` 改为 `read_write`。

## 3. 快速开始

```bash
python main.py doctor                            # 数据体检（§2.6）
python main.py input-points                      # 交互录入今日点位
python main.py daily                             # 抓取 → 分析 → 报告（一条命令）
```

报告输出到 `output/<date>/daily_report.md`，终端同时打印一句话摘要与推荐清单。

## 4. 命令行

| 命令 | 说明 |
|---|---|
| `run` / `daily` | fetch → 校验 → 分析 → 报告（一条命令） |
| `analyze` / `report` | 只做分析并出报告 |
| `input-points` | 录入今日点位：`--points "04 10 12 …"`、`--yes` 非交互 |
| `points add -i` / `points add -r "…"` / `points list` | 点位档案的录入与查看 |
| `fetch [--dry-run] [--seed]` | 增量抓取开奖；`--seed` 另存最近 500 期本地种子 |
| `backfill --from P --to Q` / `catchup` | 逐期补录遗漏期点位（禁止自动生成） |
| `backtest [--n 60 \| --all] [--no-report]` | 滚动外样本回测 |
| `doctor` | 数据体检 |

通用参数（`run/daily/analyze/report`）：

```
--points  <file>    覆盖点位文件路径
--history <file>    覆盖开奖文件路径
--methods a,b,c     只跑部分方法（调试用，不写在线学习状态）
--period  <期号>    指定分析某历史期号（默认自动推断下一期）
--no-fetch          跳过抓取
--no-backtest       跳过回测
--n <期数>          回测窗口期数
--out <目录>        报告输出根目录（默认 output/）
```

**退出码**：`0` = 成功且回测存在统计显著信号；`2` = 成功但走退化分支
（无统计显著信号，**这是正常结果**）；`1` = 运行错误。

## 5. 分析方法

十大类需求落地为 13 个模块，统一接口契约（`scores` 覆盖 1–80 号、`narrative` 结构化分章节）：

| 模块 | 方法 | 模块 | 方法 |
|---|---|---|---|
| `cluster.py` | ① 连号集群行为 | `linalg_svd.py` | ⑦ 共现/协方差/SVD/条件概率 |
| `cyclic.py` | ② 周期性共振与波段节奏 | `complex_fft.py` | ⑧ 复变/Hilbert/FFT |
| `heatmap.py` | ③ 数字场域能量分布图 | `graph_net.py` | ⑨ 图网络关系挖掘 |
| `contrarian.py` | ④ 反向心理博弈模型 | `volatility.py` | ⑩ 波动率聚类（二项过度离散） |
| `markov.py` | ⑤ 马尔可夫转移 + HMM | `remainder.py` | ⑪ 余数空间映射 + 周期共振 |
| `fibonacci.py` | ⑥ 斐波那契/黄金分割 | `entropy.py` | ⑫ 熵值评估 + 均衡监控 |
| `adversarial.py` | ⑬ 对抗生成思维（逐号反证门控） | | |

融合链路唯一：**方法分 → H1–H7 七维分 → 综合分**（`ensemble.py` → `scoring.py`）。
Exp3 在线权重按「已开出期」滚动更新，回测与外样本评估严格无前视。

## 6. 目录结构

```
├── main.py                 # CLI 入口
├── config.yaml             # 路径/权重/阈值/抓取源
├── kl8/                    # 全部模块（见 §5 与方案 §3.1）
├── data/
│   ├── seed/ uploads/      # 兜底数据
│   ├── cache/backup/       # 抓取缓存与写回前备份
│   ├── logs/               # 运行日志（保留 90 天）
│   └── state/              # 在线权重、运行心跳
├── output/<date>/daily_report.md
└── tests/                  # pytest 测试套件
```

## 7. 配置

见 `config.yaml`。要点：

- **路径解析顺序**：显式配置 > 环境变量 `KL8_DATA_DIR` > 默认相对路径；
- **集中式阈值**：归一化方法、信号强度、显著性水平、FDR 方法、数据新鲜度阈值；
- **H1–H7 权重**：热度 / 遗漏反弹 / 集群 / 周期波动 / 共现图 / 马尔可夫 / 熵均衡；
- **可复现**：`reproducibility.seed` 固定全部随机过程。

## 8. 测试

```bash
python -m pytest tests/ -q
```

分层：单元（解析/扩展/归一化/统计量）、契约（`ModuleResult` 接口语义）、
集成（真实档案端到端）、无前视（`test_no_leak.py`）。
**不做真实网络测试**（易 flaky），抓取路径用本地 mock。

## 9. 合规

报告渲染后强制全文扫描违禁表述（投注组合、资金管理、必胜承诺等），命中即拒绝落盘；
仅放行「不构成投注建议」这类否定式免责表述。免责声明无条件输出。
数据抓取只取公开开奖信息，遵守目标站点 robots 与访问频率；分析结果全部本机生成，不上传第三方。

## 10. 文档

完整设计规格见 `可行性落地方案.md`（v2.0），需求原始描述见 `思路.txt`。

## 11. 版本同步

每日一条命令（流程 + 台账自动提交推送）：

```bash
python scripts/daily_all.py --points "01 02 ..."
```

它依次执行 `run_daily.py`（前置检查 → 引擎 → 融合研报 → 主系统 → 模块明细 →
预注册锁定），成功后用 `git_sync.py` 只提交预注册台账（锁定记录、登记、试验登记）
并推送。默认拒绝代码/配置变更，提交前扫描疑似密钥。

```bash
python scripts/daily_all.py --dry-run     # 只做前置检查
python scripts/daily_all.py --no-git      # 只跑流程
python scripts/git_sync.py --status       # 只看会提交什么
python scripts/git_sync.py --all --message "docs: ..."   # 显式提交其它文件
```

它不在预注册冻结哈希内，因此日常同步不会让登记失效。

## 12. 多项目整合（2026-11-13）

三个 KL8 项目按“单一生产/审计线 + 可选研究引擎”整合：

| 项目 | 角色 | 说明 |
|---|---|---|
| `kl8-point-analysis`（本项目） | **生产/审计** | 13 模块 + H1–H7 + 300 期预注册 + 每日自动化 |
| `yuce-kaiyuan` | 历史参考 | 前身 10 模块；本地副本已于 2026-11-13 删除，代码在 GitHub；5 行前瞻记录、meta 与协议归档到 `docs/archive/yuce-kaiyuan/` |
| `kl8-prediction-engine` | 研究引擎 | Transformer + 贝叶斯图谱 + Borda 双融合 + 30 码缩水；已 vendored 到本项目 `research/`，不再依赖外部 C 目录 |

**统一数据**：历史与点位以本项目的共享档案为准；只读校验：

```bash
python scripts/data_sync.py --json
```

退出码：`0`=一致，`2`=发现差异（正常诊断结果），`1`=执行错误。2026-11-13 已把 A 的
2123 期历史回灌到 B/C 并修正三期单号差异；B 本地已删除，C 的研究引擎已 vendored 到
`research/`。历史回灌命令与 `--order` 说明见
`docs/5agent-matrix/20261113-kl8-cleanup/`，日常不再需要执行。

B 的 5 行前瞻记录（2026300–2026302）、meta、预注册协议已归档到
`docs/archive/yuce-kaiyuan/`，含 SHA-256、来源说明和本地文件清单；B 本地副本已于
2026-11-13 删除，`data_sync` 会自动跳过不存在的目标。

**研究引擎对比**（独立输出，不进入生产 Top5 / 预注册台账）：

```bash
python scripts/research_compare.py --period 2026302 --epochs 10
```

前置条件：目标期点位已在档案中（先执行每日第 1 步）；研究路径使用本地
`research/kl8_engine/`，依赖 `torch` / `openpyxl`（`pip install -r research/requirements.txt`），
生产路径不需要。研究测试单独运行：

```bash
python -m pytest -q research/tests
```

产物：`output/research/<期号>/research_compare.md` 与 `.json`。

研究引擎的迁移说明、来源 commit、依赖与测试命令见 `research/VENDORED.md`；
完整三项目契约见 `docs/5agent-matrix/20261113-kl8-integration/`，本次迁移的
R0/契约/任务板/证据见 `docs/5agent-matrix/20261113-kl8-research-migration/`。

## 13. 目录维护

- `legacy/scripts/`：历史一次性引擎/生成/补丁脚本，不参与生产与测试；当前日报使用
  `scripts/make_fusion_daily.py` + 冻结的 `scripts/fusion_engine_template.py`。
- `docs/archive/source/`：原始 `思路.txt` 与可行性方案。
- `file/`：当期/最近期图表输入；`output/`：运行产物；`scratch/` 已归档到
  `C:\D-pan\Dpanqianyi\backup\`。
- 测试依赖保留：`scripts/fusion_engine_293.py`、`294.py`、`295.py`、`2026298.py`。
- 数据完整性与条件功效报告：`python scripts/integrity_power_report.py`，输出
  `docs/reports/integrity_power_<日期>.md` 与 `.json`（只读诊断，不改预注册）。
