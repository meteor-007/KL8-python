# -*- coding: utf-8 -*-
import pytest
from fastapi.testclient import TestClient
from backend.api.api_server import app
from backend.utils.history_loader import load_history
from backend.modules.legacy.linear_algebra.linear_algebra_engine import LinearAlgebraEngine
from backend.modules.legacy.dtw_matching.dtw_engine import DTWEngine
from backend.modules.legacy.transformer_attention.transformer_engine import TransformerAttentionEngine
from backend.modules.legacy.matrix_profile.matrix_profile_engine import MatrixProfileEngine
from backend.modules.legacy.tda_engine.tda_engine import TDAEngine

client = TestClient(app)
history = load_history(limit=200)

def _assert_top3(pred):
    assert 'top3_gold' in pred
    assert len(pred['top3_gold']) == 3
    assert len(pred['top5_gold']) == 3
    assert pred['top5_gold'] == pred['top3_gold']

def test_linear_algebra_engine():
    engine = LinearAlgebraEngine(history_data=history)
    pred = engine.run_prediction()
    _assert_top3(pred)

def test_dtw_engine():
    engine = DTWEngine(history_data=history)
    pred = engine.run_prediction()
    _assert_top3(pred)

def test_transformer_engine():
    engine = TransformerAttentionEngine(history_data=history)
    pred = engine.run_prediction()
    _assert_top3(pred)

def test_matrix_profile_engine():
    engine = MatrixProfileEngine(history_data=history)
    pred = engine.run_prediction()
    _assert_top3(pred)

def test_tda_engine():
    engine = TDAEngine(history_data=history)
    pred = engine.run_prediction()
    _assert_top3(pred)

def test_api_endpoints():
    login_res = client.post('/login', data={'passcode': 'k8quant@2026'})
    assert login_res.status_code in [200, 302]

    # 这五个高维模型于 2026-10-22 全部退役：
    # 路由由 module_gate 判决拦截，统一返回 410 Gone（而不是 200）。
    retired = {
        '/api/quant/linear-algebra/latest': 'linear_algebra',
        '/api/quant/dtw/latest': 'dtw',
        '/api/quant/transformer/latest': 'transformer',
        '/api/quant/matrix-profile/latest': 'matrix_profile',
        '/api/quant/tda/latest': 'tda',
    }
    for ep, mid in retired.items():
        res = client.get(ep)
        assert res.status_code == 410, f"{ep} 应返回 410"
        body = res.json()
        assert body.get('status') == 'retired'
        assert body.get('module_id') == mid
