# -*- coding: utf-8 -*-
"""
tests/test_all_rectifications_verified.py
=========================================
【K8-QUANT 2026-09-10 终审问题整改全量物理核验测试套件】

测试范围:
  1. test_b6_kill_modules_observation_demotion:
     验证 B6 杀号门禁降级已落地，datasource_1x2_kill 处于 observation，权重 0.0。
  2. test_c8_fo_walk_forward_channel_present:
     验证 C8 终审共识 walk-forward 显著性审计池扩展至 5 个通道，已接入无前瞻 FO 特征遗漏通道。
  3. test_d1_d2_loss_ledger_real_loss_present:
     验证 D1/D2 自学习 Loss 计算非空，损失历史中存在真实 Cross-Entropy 数值且无全空伪记录。
  4. test_d5_pending_predictions_deduplicated:
     验证 D5 pending_predictions 无重复期号，长度受限且不会随重复执行无界累积。
  5. test_e5_evolution_ledgers_deduplicated:
     验证 E5 evolution_ledger (generation 唯一) 与 unified_evolution_ledger (target_period 唯一)，无重复刷量。
  6. test_g4_report_caliber_metadata_present:
     验证 G4 研报总库新旧口径标定正常，包含 is_honest_caliber 与 caliber_version 字段。
  7. test_g5_static_snapshots_sync:
     验证 G5 夜间高可用静态快照全量刷新机制执行正常，6 份静态快照均成功同步。
"""
from backend.utils.paths import get_cache_dir
import os
import json
import pytest

_PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_b6_kill_modules_observation_demotion():
    """核验 B6: 杀号模块已拆除（KillSeeker + datasource_1x2_kill）"""
    from backend.core.module_gate import ModuleGate

    gate = ModuleGate(_PROJ_DIR)
    mods = gate.registry().get("modules", {})
    assert "datasource_1x2_kill" not in mods, "datasource_1x2_kill 应已从门控移除"
    assert "killseeker" not in mods, "KillSeeker 模块应已完全移除"


def test_c8_fo_walk_forward_channel_present():
    """核验 C8: walk_forward 显著性审计池扩展至 5 个通道，已接入无前瞻 FO 通道"""
    from backend.core.aggregation.consensus_engine import ConsensusEngine
    engine = ConsensusEngine(_PROJ_DIR)
    draws = engine.load_draws()
    assert len(draws) >= 80, "测试所需历史开奖样本不足"
    wf_res = engine._run_walk_forward(draws=draws[-100:], k=20)
    
    assert "fo_eval" in wf_res, "walk-forward 缺少 fo_eval 输出"
    assert "fdr_summary" in wf_res, "walk-forward 缺少 fdr_summary 输出"
    fdr_summary = wf_res["fdr_summary"]
    channels = fdr_summary.get("channels", [])
    assert "feature_omission" in channels, "fdr_summary 未包含 feature_omission (FO) 通道"
    assert len(channels) == 5, f"通道总数应为 5, 实际: {len(channels)}"
    
    fo_info = wf_res["fo_eval"]
    assert "lift" in fo_info, "FO 通道缺少 lift 结果"
    assert "p_value" in fo_info, "FO 通道缺少 p_value 结果"


def test_d1_d2_loss_ledger_real_loss_present():
    """核验 D1 和 D2: loss_history 存在非空真实的 Cross-Entropy Loss 记录"""
    loss_path = os.path.join(get_cache_dir(), "loss_history.json")
    assert os.path.exists(loss_path), "缺少 loss_history.json"
    with open(loss_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data.get("records", []) if isinstance(data, dict) else data
    assert len(records) > 0, "loss_history records 不能为空"
    
    valid_records = [
        r for r in records
        if r.get("losses") and any(v is not None and v > 0 for v in r["losses"].values())
    ]
    assert len(valid_records) > 0, "loss_history 没有任何非空有效损失计算记录"
    
    periods = [str(r.get("period")) for r in records]
    assert len(periods) == len(set(periods)), f"loss_history 期号存在重复: {periods}"


def test_d5_pending_predictions_deduplicated():
    """核验 D5: learner_state 中的 pending_predictions 去重且长度受限"""
    state_path = os.path.join(get_cache_dir(), "learner_state.json")
    assert os.path.exists(state_path), "缺少 learner_state.json"
    with open(state_path, "r", encoding="utf-8") as f:
        state = json.load(f)

    pending = state.get("pending_predictions", [])
    periods = [str(p.get("period")) for p in pending]
    assert len(periods) == len(set(periods)), f"pending_predictions 存在重复期号: {periods}"
    assert len(pending) <= 10, f"pending_predictions 超过最大保留上限 10 条: {len(pending)}"


def test_e5_evolution_ledgers_deduplicated():
    """核验 E5: 进化总账本 generation 唯一，主脑总账本 target_period 严格去重"""
    evo_path = os.path.join(_PROJ_DIR, "storage", "evolution", "evolution_ledger.json")
    assert os.path.exists(evo_path), "缺少 evolution_ledger.json"
    with open(evo_path, "r", encoding="utf-8") as f:
        evo_rows = json.load(f)

    generations = [r.get("generation") for r in evo_rows]
    assert len(generations) == len(set(generations)), f"evolution_ledger 存在重复代数 generation"

    ub_path = os.path.join(_PROJ_DIR, "storage", "evolution", "unified_evolution_ledger.json")
    if os.path.exists(ub_path):
        with open(ub_path, "r", encoding="utf-8") as f:
            ub_rows = json.load(f)
        ub_periods = [str(r.get("target_period")) for r in ub_rows]
        assert len(ub_periods) == len(set(ub_periods)), f"unified_evolution_ledger 存在重复 target_period"


def test_g4_report_caliber_metadata_present():
    """核验 G4: 研报列表包含诚实口径版本元数据"""
    from backend.api.data_service import QuantDataService
    ds = QuantDataService(_PROJ_DIR)
    reports = ds.get_report_list()
    assert len(reports) > 0, "研报列表不能为空"

    for r in reports:
        assert "is_honest_caliber" in r, f"研报缺少 is_honest_caliber: {r.get('filename')}"
        assert "caliber_version" in r, f"研报缺少 caliber_version: {r.get('filename')}"
        assert "caliber_desc" in r, f"研报缺少 caliber_desc: {r.get('filename')}"

    latest_rep = reports[0]
    if int(latest_rep.get("raw_date", "0")) >= 20260910:
        assert latest_rep["is_honest_caliber"] is True, "最新研报应标记为 is_honest_caliber=True"
        assert "v3.0" in latest_rep["caliber_version"], f"最新研报口径版本应含 v3.0, 实际: {latest_rep['caliber_version']}"


def test_g5_static_snapshots_sync():
    """核验 G5: 夜间流水线末尾高可用静态快照强同步功能"""
    from backend.pipeline.run_nightly_pipeline import sync_nightly_static_snapshots
    res = sync_nightly_static_snapshots(_PROJ_DIR)
    
    assert "evolution_history.json" in res, "缺少 evolution_history.json 同步记录"
    assert "prime_tail_analysis.json" in res, "缺少 prime_tail_analysis.json 同步记录"
    assert "psychological_game_analysis.json" in res, "缺少 psychological_game_analysis.json 同步记录"
    assert "psychological_game_backtest_ledger.json" in res, "缺少 psychological_game_backtest_ledger.json 同步记录"
    assert "multi_resonance_consensus.json" in res, "缺少 multi_resonance_consensus.json 同步记录"
    assert "unified_decision_latest.json" in res, "缺少 unified_decision_latest.json 同步记录"

    for fname, info in res.items():
        assert info.get("status") == "ok", f"静态快照 {fname} 同步失败: {info}"
