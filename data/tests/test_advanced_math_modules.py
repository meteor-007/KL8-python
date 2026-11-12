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
    
    endpoints = [
        '/api/quant/linear-algebra/latest',
        '/api/quant/dtw/latest',
        '/api/quant/transformer/latest',
        '/api/quant/matrix-profile/latest',
        '/api/quant/tda/latest',
    ]
    for ep in endpoints:
        res = client.get(ep)
        assert res.status_code == 200
        data = res.json()
        assert data.get('code') == 200 or 'top5_gold' in data or 'top3_gold' in data
