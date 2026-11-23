# 优化模块使用说明

## 新增功能

### 1. B3 Right质量检查
- **模块**: `b3_right_quality_checker.py`
- **功能**: 自动评估B3 Right矩阵映射的数据质量
- **触发条件**: 质量评分<0.6时自动切换到置信度备选策略
- **质量评分维度**:
  - 数据完整性 (30%)
  - 历史命中率 (40%)
  - 数据多样性 (20%)
  - 时间点位匹配度 (10%)

### 2. K-means环境识别
- **模块**: `environment_recognition_enhancer.py`
- **功能**: 使用K-means聚类将环境分为5类
- **环境类别**:
  0. 热号爆发期 - 热号集中，趋势明显
  1. 冷号反弹期 - 冷号开始反弹
  2. 平衡震荡期 - 各区间分布均匀
  3. 趋势加速期 - 规律加速显现
  4. 混沌随机期 - 规律混乱

### 3. 环境-策略映射
每个环境类别对应不同的策略权重:
- 热号爆发期: MK:0.3, EF:0.4, RW:0.3
- 冷号反弹期: MK:0.2, EF:0.5, RW:0.3
- 平衡震荡期: MK:0.15, EF:0.42, RW:0.42
- 趋势加速期: MK:0.4, EF:0.3, RW:0.3
- 混沌随机期: MK:0.25, EF:0.25, RW:0.5

## 使用方法

### 运行增强版分析
```bash
python integrate_optimizations.py
```

### 单独测试模块
```bash
# 测试B3 Right质量检查
python -c "import b3_right_quality_checker as m; print('OK')"

# 测试环境识别
python -c "import environment_recognition_enhancer as m; print('OK')"
```

## 输出文件
- `daily_analysis_report_YYYYMMDD.md` - 每日分析报告（已增强）
- `system_optimization_log.json` - 优化日志记录

## 回测验证
建议定期（每周）运行回测验证优化效果:
```bash
python backtest_optimization.py
```
