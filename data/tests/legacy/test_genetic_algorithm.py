# -*- coding: utf-8 -*-
"""
快乐8 遗传算法号码预测系统自动化测试套件
========================================
测试范围：
1. 特征提取器输出维度与归一化校验
2. 遗传算法种群演化收敛性与精英保留校验
3. 尖刀金胆、黄金搭档选2、Top5、Top12 等决策格式与约束校验
4. 业务服务层缓存与 Walk-Forward 滚动回测有效性
5. FastAPI RESTful API 路由契约与响应验证
"""

import pytest
import numpy as np
from fastapi.testclient import TestClient

from backend.modules.legacy.genetic_algorithm.genetic_engine import GeneticAlgorithmEngine
from backend.modules.legacy.genetic_algorithm.service import GeneticServiceMixin
from backend.api.api_server import app


def test_genetic_engine_features():
    """测试特征提取输出形状与范围"""
    engine = GeneticAlgorithmEngine()
    feats = engine.extract_features_at_period(offset=0)
    assert feats.shape == (80, 8)
    assert np.all(feats >= 0.0)
    assert np.all(feats <= 1.0)


def test_genetic_engine_evolution_and_prediction():
    """测试遗传算法进化收敛与决策输出"""
    engine = GeneticAlgorithmEngine()
    evo_res = engine.run_evolution(pop_size=20, generations=10, eval_periods=10)
    assert evo_res["status"] == "success"
    assert len(evo_res["best_chromosome"]) == 8
    assert len(evo_res["convergence_curve"]) == 10

    # 检查单调性与收敛趋势
    fits = [c["best_fitness"] for c in evo_res["convergence_curve"]]
    assert fits[-1] >= fits[0]

    # 测试推演生成
    pred = engine.generate_prediction(best_chromosome=np.array(evo_res["best_chromosome"]))
    assert pred["status"] == "success"
    assert 1 <= pred["gold_core"] <= 80
    assert len(pred["gold_pair"]) == 2
    assert len(pred["top3_gold"]) == 3
    assert len(pred["top5_assault"]) == 3
    assert len(pred["top12_balanced"]) == 3
    assert pred["top5_assault"] == pred["top3_gold"]
    assert pred["top12_balanced"] == pred["top3_gold"]
    assert len(set(pred["top5_assault"])) == 3
    assert len(set(pred["top12_balanced"])) == 3
    assert "kill20_defense" not in pred
    assert len(pred["scores_80"]) == 80


def test_genetic_service_review():
    """测试业务服务层滚动样本外复盘"""
    class TestService(GeneticServiceMixin):
        def load_history(self, limit=None):
            engine = GeneticAlgorithmEngine()
            return engine.history[:limit] if limit else engine.history

    srv = TestService()
    rev = srv.get_genetic_review(n=10)
    assert rev["status"] == "success"
    assert "stats" in rev
    assert rev["stats"]["total_periods"] == 10
    assert len(rev["records"]) == 10


def test_genetic_api_routes():
    """测试 FastAPI 端点"""
    client = TestClient(app)
    # 建立测试会话登录
    login_res = client.post("/login", data={"passcode": "k8quant@2026"})
    assert login_res.status_code in [200, 302]
    
    # 1. Summary
    res_sum = client.get("/api/genetic/summary")
    assert res_sum.status_code == 200
    data_sum = res_sum.json()
    assert "gold_core" in data_sum
    assert "top5_assault" in data_sum
    assert "radar_features" in data_sum

    # 2. Review
    res_rev = client.get("/api/genetic/review?n=10")
    assert res_rev.status_code == 200
    data_rev = res_rev.json()
    assert data_rev["status"] == "success"

    # 3. Online run
    res_run = client.post("/api/genetic/run", json={"pop_size": 20, "generations": 10, "eval_periods": 10})
    assert res_run.status_code == 200
    data_run = res_run.json()
    assert "gold_core" in data_run
