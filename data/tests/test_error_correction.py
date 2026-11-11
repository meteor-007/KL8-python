# -*- coding: utf-8 -*-
"""
残差改错预测模块自动化测试套件 (Test Error-Correction Module)
============================================================
覆盖核心算法引擎、服务层管道、Walk-Forward 对账与 FastAPI 路由端到端校验。
"""
import pytest
from fastapi.testclient import TestClient

from backend.api.api_server import app
from backend.utils.history_loader import load_history
from backend.modules.error_correction.residual_engine import (
    ResidualCorrectionEngine,
    TRAIN_WINDOW,
    FEATURE_NAMES,
)
from backend.modules.error_correction.service import (
    run_error_correction_pipeline,
    get_latest_error_correction_data,
    get_error_correction_review,
    get_output_paths,
)

client = TestClient(app)


@pytest.fixture(scope="module")
def history():
    """获取历史开奖数据样本"""
    return load_history(limit=TRAIN_WINDOW)


def test_residual_engine_prediction(history):
    """测试残差改错引擎的核心计算与契约完整性"""
    assert len(history) >= 25, "历史开奖数据量应大于25期"
    engine = ResidualCorrectionEngine(history_data=history)
    pred = engine.run_prediction()

    assert "error" not in pred, f"预测失败: {pred.get('error')}"
    assert pred["module_code"] == "error_correction"
    assert pred["prediction_mode"] == "residual_boosting_gbdt"

    # 1. 验证推荐选码契约（主口径：最优 3 码）
    top3 = pred["top3_gold"]
    top5 = pred["top5_gold"]

    assert len(top3) == 3, "Top3 长度应为 3"
    assert len(top5) == 3, "兼容字段 top5_gold 现为最优 3 码"
    assert len(set(top3)) == 3, "Top3 不应包含重复球号"
    assert top5 == top3
    assert "kill20_list" not in pred

    # 2. 验证球号取值范围 (1..80)
    for b in top3:
        assert 1 <= b <= 80, f"球号 {b} 超出 1-80 范围"

    # 3. 验证诊断信标结构
    assert "traps_avoided" in pred
    assert "rebounds_promoted" in pred
    assert isinstance(pred["traps_avoided"], list)
    assert isinstance(pred["rebounds_promoted"], list)

    # 4. 验证特征重要性
    imp = pred.get("feature_importance", {})
    assert len(imp) > 0, "特征重要性字典不应为空"
    for feat in imp.keys():
        assert feat in FEATURE_NAMES, f"特征名 {feat} 必须在白名单内"


def test_error_correction_service_pipeline():
    """测试残差改错服务层 pipeline 执行与文件持久化"""
    result = run_error_correction_pipeline(limit=80)
    assert result is not None
    assert result.get("top3_gold") is not None
    assert len(result["top3_gold"]) == 3
    assert len(result["top5_gold"]) == 3

    # 验证输出文件存在性
    paths = get_output_paths()
    import os
    for p in paths.values():
        assert os.path.exists(p), f"预期输出文件不存在: {p}"

    # 验证前端缓存快速读取
    latest = get_latest_error_correction_data()
    assert latest.get("module_code") == "error_correction"


def test_error_correction_rolling_review():
    """测试严格样本外 Walk-Forward 滚动实战对账"""
    review = get_error_correction_review(n=5, force_refresh=True)
    assert review.get("status") == "success"
    assert review.get("module_name") == "error_correction"
    assert len(review.get("records", [])) == 5

    stats = review.get("stats", {})
    assert "avg_top3_hit" in stats
    assert "top5_lift" not in stats
    assert "kill_evade_rate" not in stats
    assert stats["avg_top3_hit"] >= 0.0


def test_error_correction_api_routes():
    """测试残差改错模块的 FastAPI 接口响应"""
    # 1. 登录
    login_res = client.post("/login", data={"passcode": "k8quant@2026"})
    assert login_res.status_code in [200, 302]

    # 2. GET /api/error_correction/latest
    res_latest = client.get("/api/error_correction/latest")
    assert res_latest.status_code == 200
    body_latest = res_latest.json()
    assert body_latest.get("status") == "ok"
    assert "top3_gold" in body_latest.get("data", {}) or "top5_gold" in body_latest.get("data", {})

    # 3. GET /api/error_correction/review
    res_review = client.get("/api/error_correction/review?n=5")
    assert res_review.status_code == 200
    body_review = res_review.json()
    assert body_review.get("status") == "ok"
    assert "stats" in body_review.get("data", {})

    # 4. POST /api/pipeline/run-error-correction
    res_pipe = client.post("/api/pipeline/run-error-correction")
    assert res_pipe.status_code == 200
    body_pipe = res_pipe.json()
    assert body_pipe.get("status") == "QUEUED"
