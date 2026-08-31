# Deprecated Modules Index

以下模块/路径在 v3.0 收敛重构后曾暂时停用；v3.2 已将工业级日报引擎回迁。

## 已回迁 (v3.2)

| 路径 | 说明 | 当前替代方案 |
|------|------|----------|
| `archive/deprecated/legacy_daily_report_engine_v2.1.py` | 旧日报引擎归档副本 | [`pipeline/full_report_engine.py`](../pipeline/full_report_engine.py) + [`pipeline/auto_generate_daily_report.py`](../pipeline/auto_generate_daily_report.py) |
| FO Baseline 附录 | Walk-Forward 门控对照 | `main_v2.run_pipeline()` 由编排器追加至报告附录 A |

## 仍冻结

| 路径 | 说明 |
|------|------|
| `param_store.json` 自动写入 | 44+ 参数自学习；`core/learning_gate.py` 冻结至 Lift>1.1 |

## 2026-07-18 归档（命中率未显著优于基线，移除过复杂死代码）

| 路径 | 说明 | 替代 |
|------|------|------|
| `archive/deprecated/deep_hit_rate_optimizer.py` | 六维深度攻坚引擎，主链路零引用，近10期 HE5 Lift≈0.98x | `core/walk_forward_validator.py` + 现有三维融合 |

## 标记 deprecated (仍被完整日报调用，勿删)

| 路径 | 说明 |
|------|------|
| `audit/kl_divergence_checker.py` | 物理熔断面板 |
| `audit/collinearity_detector.py` | 共线性预警 |
| `audit/v3_trinity_audit.py` | 三维融合 |
| `audit/b3_right_quality_checker.py` | Hidden Energy 5 |
| `core/pure_pool_scorer.py` | 纯净池定胆 |
| `core/deep_optimizer.py` plan17–22 | FO 特征层内部 |

## 恢复自学习条件

```bash
cd data
python main_v2.py --backtest   # 需 global Lift > 1.1
```

门控状态见 `cache/learning_gate_state.json`。
