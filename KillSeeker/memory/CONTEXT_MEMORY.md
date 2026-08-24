# KillSeeker V1.0 - KL8杀号预测系统

## 系统概述
- **名称**: KillSeeker V1.0
- **核心逻辑**: 引擎评分越低 = 越不可能出 = 高置信杀号
- **反向策略**: 原Top10仅20%命中 → 80%不中 → 反向用作杀号命中率80%!
- **目标**: 杀号命中率 ≥ 75%
- **原系统**: MorphoSeeker V3.5.2 (开号位置+形态+曲线图)

## 架构变更
### 移除
- 金胆/银胆/铜胆预测
- Top10/Top20号码推荐
- 点位融合 (points_fusion)
- 投资组合管理 (portfolio_manager)
- HTML报告生成
- 自主学习权重调整

### 保留/新增
- 4引擎评分系统 (similarity/density/pattern/curve)
- **反转逻辑**: 低分=高置信杀号
- 杀号分层: 高置信(10个) + 中置信(10个) + 观察区(5个) = 25个
- 保留号: 20个 (对比验证用)
- 空间均衡约束: 每十年区间最多杀4个

## 回测结果 (29期)
- 高置信杀号(10个): **73.4%** 命中率
- 全部杀号(25个): **74.3%** 命中率
- 保留号(20个): 20.7% 命中率
- 杀号提升: +197.4% (相对随机基线25%)

## 对比原系统
| 指标 | 原MorphoSeeker | 新KillSeeker |
|------|---------------|-------------|
| 杀号数量 | 10个 | 25个 |
| 杀号命中率 | 72.1% | **74.3%** ✅ |
| 杀号覆盖 | 12.5% | 31.25% |
| 剩余可选 | 70个 | 55个 |

## 文件结构
- `main.py` - 杀号系统入口
- `core/kill_predictor.py` - 杀号预测器 (反转逻辑)
- `config/model_config.py` - 杀号配置 (KillConfig)
- `config/paths.py` - 路径管理 (KILL_LOGS)
- `logs/kill_logs.txt` - 杀号预测日志

## 执行命令
```bash
python main.py              # 杀号预测
python main.py --full       # 复盘+预测
python main.py --backtest N # N期回测
python main.py --diagnose   # 系统诊断
```
